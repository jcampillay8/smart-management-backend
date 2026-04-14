# src/registration/services.py
import logging
import os
import secrets
from io import BytesIO
from datetime import datetime, timezone, timedelta
import uuid
import re # Importar para validación de regex de contraseña

import aiofiles
from fastapi import UploadFile, HTTPException, status # Importar HTTPException y status
from PIL import Image
from sqlalchemy import or_, update
from sqlalchemy.future import select as sa_select # Renombrado para evitar conflicto con la función de Python `select`
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import joinedload

from src.config import settings
from src.models import User, Chat, Message, MessageRole
from src.registration.schemas import UserRegisterSchema
from src.authentication.models import EmailConfirmationToken
from src.email.email_service import email_service
from src.utils import get_hashed_password

logger = logging.getLogger(__name__)

DEFAULT_CHUNK_SIZE = 1024 * 1024 * 1  # 1 megabyte

TEST_EMAILS_BYPASS = {
    "test_user_1784867943983167886@testuser.com",
    "test_user01@gmail.com",
    "test_user02@gmail.com",
    "Benjamin@oppychat.com"
    # Agrega otros correos de prueba de MP si es necesario para otros países:
    # "test_user_OTRO_PAIS@testuser.com",
}

TEST_EMAIL_REDIRECT = None

# --- Función para validar la complejidad de la contraseña (se mantiene sin cambios) ---
def validate_password_complexity(password: str):
    """
    Valida la complejidad de la contraseña.
    Requiere:
    - Mínimo 8 caracteres
    - Al menos una letra mayúscula
    - Al menos una letra minúscula
    - Al menos un número
    - Al menos un carácter especial (ej. !@#$%^&*)
    """
    if len(password) < 8:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="La contraseña debe tener al menos 8 caracteres."
        )
    if not re.search(r"[A-Z]", password):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="La contraseña debe contener al menos una letra mayúscula."
        )
    if not re.search(r"[a-z]", password):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="La contraseña debe contener al menos una letra minúscula."
        )
    if not re.search(r"\d", password):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="La contraseña debe contener al menos un número."
        )
    if not re.search(r"[!@#$%^&*(),.?\":{}|<>]", password):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="La contraseña debe contener al menos un carácter especial."
        )
    if ' ' in password:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="La contraseña no puede contener espacios."
        )

# --- Se corrige la función 'select' de sqlalchemy para evitar conflicto con 'select' de Python ---
async def get_user_by_email_or_username(db_session: AsyncSession, *, email: str, username: str) -> User | None:
    """
    Obtiene un usuario por su email o nombre de usuario.
    """
    query = sa_select(User).where(or_(User.email == email, User.username == username))
    result = await db_session.execute(query)
    user: User | None = result.scalar_one_or_none()
    return user

async def create_user_from_confirmation(
    db_session: AsyncSession,
    *,
    user_data: dict,
) -> User:
    """
    Crea un nuevo usuario en la base de datos a partir de los datos de un token
    de confirmación. Asume que la validación de email/username ya se hizo.
    """
    try:
        new_user = User(
            username=user_data["username"].lower(),
            email=user_data["email"].lower(),
            first_name=user_data["first_name"],
            last_name=user_data["last_name"],
            password=user_data["password_hash"],
            has_accepted_terms=user_data["terms_accepted"],
            user_image=user_data["image_url"], # Usa la URL de la imagen del token
            is_deleted=False,
        )

        db_session.add(new_user)
        await db_session.commit()
        await db_session.refresh(new_user)
        
    except IntegrityError as e:
        await db_session.rollback()
        if "users_email_key" in str(e) or "email" in str(e).lower():
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Ya existe un usuario con este correo electrónico."
            )
        else:
            logger.error(f"Error de integridad al crear usuario: {e}", exc_info=True)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Ocurrió un error inesperado."
            )
    except Exception as e:
        await db_session.rollback()
        logger.error(f"Error inesperado y no manejado al crear usuario {user_data.get('username')}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Ocurrió un error inesperado al registrar el usuario."
        )

    return new_user

# --- FUNCIONES PARA EL FLUJO DE CONFIRMACIÓN DE EMAIL ---

async def register_user_and_send_confirmation(
    db_session: AsyncSession,
    user_schema: UserRegisterSchema,
    uploaded_image: UploadFile | None = None
):
    """
    Gestiona el flujo de registro. Si el email es un email de prueba conocido,
    se salta la confirmación y crea el usuario inmediatamente.
    """
    
    # 1. Validar si el email de prueba requiere bypass
    user_email_lower = user_schema.email.lower()
    
    hashed_password = get_hashed_password(user_schema.password)
    
    image_url = None
    if uploaded_image:
        # Asumo que ImageSaver es una clase existente en tu codebase
        image_saver = ImageSaver(db_session=db_session)
        image_url = await image_saver.save_user_image(uploaded_image, user_schema.username)

    # 2. Invalida tokens previos no usados para este email (importante antes de cualquier acción)
    await db_session.execute(
        update(EmailConfirmationToken)
        .where(
            EmailConfirmationToken.user_email == user_email_lower,
            EmailConfirmationToken.is_used == False,
        )
        .values(is_used=True)
    )
    await db_session.commit()

    # 3. Guardar los datos del usuario en la tabla de tokens (necesario incluso para el bypass)
    confirmation_token_entry = EmailConfirmationToken(
        user_email=user_email_lower,
        token=secrets.token_urlsafe(32), # Genera un token dummy o real, según el caso
        username=user_schema.username.lower(),
        password_hash=hashed_password,
        first_name=user_schema.first_name,
        last_name=user_schema.last_name,
        terms_accepted=user_schema.terms_accepted,
        image_url=image_url,
        expires_at=datetime.now(timezone.utc) + timedelta(minutes=60),
        is_used=True if user_email_lower in TEST_EMAILS_BYPASS else False # Marcar como usado si es bypass
    )
    db_session.add(confirmation_token_entry)
    await db_session.commit()
    await db_session.refresh(confirmation_token_entry)

    # ⭐️ LÓGICA DE BYPASS ⭐️
    if user_email_lower in TEST_EMAILS_BYPASS:
        logger.info(f"Bypassing email confirmation for test user: {user_email_lower}")
        
        # 4. Crear el usuario inmediatamente
        user_data = {
            "username": confirmation_token_entry.username,
            "email": confirmation_token_entry.user_email,
            "first_name": confirmation_token_entry.first_name,
            "last_name": confirmation_token_entry.last_name,
            "password_hash": confirmation_token_entry.password_hash,
            "terms_accepted": confirmation_token_entry.terms_accepted,
            "image_url": confirmation_token_entry.image_url,
        }
        await create_user_from_confirmation(db_session, user_data=user_data)

        # 5. Retornar mensaje de éxito de creación
        return {"message": "Usuario de prueba creado exitosamente (Confirmación de email omitida).", "user_created": True}
    
    # ⭐️ FLUJO NORMAL (Enviar Email) ⭐️
    
    base = str(settings.API_URL).rstrip('/') # Asegúrate de tener API_URL en tu config/env

    # La URL ahora debe ser la ruta exacta que definiste en el router del backend
    confirmation_url = f"{base}/confirm-email/{confirmation_token_entry.token}"

    context = {
        "user_name": user_schema.first_name or user_schema.username or user_schema.email,
        "confirmation_url": confirmation_url, # Ahora apunta al puerto 8000
        "app_name": settings.MAIL_FROM_NAME,
        "expiration_minutes": 60,
    }
    
    # -------------------------------------------------------------------------
    # 🎯 Lógica de Redirección y Definición de Destinatarios (Corregida) 🎯
    # -------------------------------------------------------------------------
    
    # Definir el sujeto y el destinatario por defecto (el real)
    subject = "Confirma tu correo electrónico"
    
    # El destinatario será el de redirección si está activo, de lo contrario, el real del usuario.
    # El requerimiento dice: si NO está en TEST_EMAILS_BYPASS, debe ser enviado al correo que se ingresa.
    # Esto implica que si el flujo es normal, se debe usar el email del usuario,
    # A MENOS que se quiera forzar la redirección (ej. en desarrollo).

    # El siguiente bloque implementa:
    # 1. Destino = TEST_EMAIL_REDIRECT si está definido (modo debug/redirección activa).
    # 2. Destino = user_schema.email si NO está definido.
    
    # La variable TEST_EMAIL_REDIRECT ya está definida como "jgcampill@gmail.com"
    # Este bloque cumple con la lógica de redirección de debug.

    if TEST_EMAIL_REDIRECT:
        recipients_list = [TEST_EMAIL_REDIRECT] # Redirigir la lista
        logger.warning(f"DEBUG: Email de confirmación para '{user_schema.email}' redirigido a: {TEST_EMAIL_REDIRECT}")
        # Modificar el asunto para facilitar la identificación
        subject = f"[REDIRECTED - ORIGINAL: {user_schema.email}] {subject}"
    else:
        recipients_list = [user_schema.email] # Usar el correo real del usuario
        
    # Asumo que tu email_service.send_email ya maneja tareas en segundo plano
    await email_service.send_email(
        subject=subject,                       # ✅ USAR LA VARIABLE CALCULADA
        recipients=recipients_list,            # ✅ USAR LA VARIABLE CALCULADA
        template_name="email_confirmation.html",
        template_vars=context,
    )

    return {"message": "Email de confirmación enviado exitosamente.", "user_created": False}


async def confirm_user_email(db_session: AsyncSession, token: str) -> dict:
    result = await db_session.execute(
        sa_select(EmailConfirmationToken).where(EmailConfirmationToken.token == token)
    )
    token_entry = result.scalar_one_or_none()

    if (
        not token_entry
        or token_entry.is_used
        or (
            token_entry.expires_at and
            (
                (token_entry.expires_at.tzinfo is None and token_entry.expires_at.replace(tzinfo=timezone.utc) < datetime.now(timezone.utc))
                or (token_entry.expires_at.tzinfo is not None and token_entry.expires_at < datetime.now(timezone.utc))
            )
        )
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="El enlace de confirmación es inválido o ha expirado."
        )

    token_entry.is_used = True
    await db_session.commit()

    user_data = {
        "username": token_entry.username,
        "email": token_entry.user_email,
        "first_name": token_entry.first_name,
        "last_name": token_entry.last_name,
        "password_hash": token_entry.password_hash,
        "terms_accepted": token_entry.terms_accepted,
        "image_url": token_entry.image_url,
    }

    await create_user_from_confirmation(db_session, user_data=user_data)

    await db_session.delete(token_entry)
    await db_session.commit()

    return {"message": "Correo electrónico confirmado. Usuario creado exitosamente."}

# --- CLASE ImageSaver UNIFICADA Y CORREGIDA ---
class ImageSaver:
    def __init__(self, db_session: AsyncSession):
        self.db_session: AsyncSession = db_session

    async def save_user_image(self, uploaded_image: UploadFile, username: str) -> str | None:
        """
        Guarda la imagen de perfil de forma independiente, sin un objeto User.
        """
        try:
            file_extension: str = uploaded_image.filename.split(".")[-1].lower()
            filename: str = f"{username}.{file_extension}"

            match settings.ENVIRONMENT:
                case "development":
                    return await self._save_image_to_static(uploaded_image, filename)
                case "production":
                    return await self._save_image_to_aws_bucket(uploaded_image, filename)
                case _:
                    logger.error(f"Unsupported environment: {settings.ENVIRONMENT}")
                    return None
        except Exception as e:
            logger.error(f"Error al guardar la imagen para el usuario {username}: {e}", exc_info=True)
            return None

    async def _save_image_to_static(self, uploaded_image: UploadFile, filename: str) -> str:
        """
        Guarda la imagen en el sistema de archivos local y devuelve la URL.
        """
        folder_path = "src/static/images/profile"
        os.makedirs(folder_path, exist_ok=True)
        file_path = f"{folder_path}/{filename}"

        # Reemplazar la imagen si ya existe
        if os.path.exists(file_path):
            os.remove(file_path)

        async with aiofiles.open(file_path, "wb") as f:
            while chunk := await uploaded_image.read(DEFAULT_CHUNK_SIZE):
                await f.write(chunk)
        
        # Redimensionar la imagen después de guardarla en el disco
        resized_image = self._resize_image(file_path)
        resized_image.save(file_path, resized_image.format)

        image_url = f"/static/images/profile/{filename}"
        return image_url

    async def _save_image_to_aws_bucket(self, uploaded_image: UploadFile, filename: str) -> str | None:
        """
        Guarda la imagen en un bucket de S3 y devuelve la URL.
        """
        if (
            (aws_client := settings.get_aws_client_for_image_upload(), aws_bucket := settings.AWS_IMAGES_BUCKET)
            and aws_client
            and aws_bucket
        ):
            image_file: bytes = await uploaded_image.read()
            with BytesIO() as in_memory_image_file:
                resized_image = self._resize_image(BytesIO(image_file))
                resized_image.save(in_memory_image_file, format='PNG')
                in_memory_image_file.seek(0)
                
                aws_client.upload_fileobj(
                    in_memory_image_file, aws_bucket, filename, ExtraArgs={"ContentType": "image/png"}
                )
            
            image_url: str = f"https://{aws_bucket}.s3.amazonaws.com/{filename}"
            return image_url
        else:
            logger.error("AWS client or bucket information is missing.")
            return None

    def _resize_image(self, file_path_or_bytes: str | BytesIO) -> Image:
        """
        Redimensiona una imagen a 600x600 píxeles.
        """
        image = Image.open(file_path_or_bytes)
        resized_image = image.resize((600, 600), Image.LANCZOS)
        return resized_image
