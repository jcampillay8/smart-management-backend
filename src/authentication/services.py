# src/authentication/services.py
import asyncio
import secrets
import string
import logging
from datetime import datetime, timedelta, timezone

from fastapi import Request, BackgroundTasks
from sqlalchemy import and_, or_, select, update, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.models import User
from src.authentication.models import UserSessionHistory, PasswordResetToken, RefreshToken
from src.config import settings
from src.utils import get_hashed_password, verify_password
from src.email.email_service import email_service

logger = logging.getLogger(__name__)

# --- BÚSQUEDA DE USUARIOS ---

async def get_user_by_login_identifier(db_session: AsyncSession, *, login_identifier: str) -> User | None:
    """Busca un usuario por email o username de forma eficiente."""
    query = (
        select(User)
        .where(
            and_(
                or_(User.email == login_identifier, User.username == login_identifier),
                User.is_deleted.is_(False)
            )
        )
        # 🚀 Quitamos el selectinload innecesario para el login
    )
    result = await db_session.execute(query)
    return result.scalar_one_or_none()

async def get_user_by_email(db_session: AsyncSession, *, email: str) -> User | None:
    """Busca específicamente por email."""
    query = select(User).where(and_(User.email == email, User.is_deleted.is_(False)))
    result = await db_session.execute(query)
    return result.scalar_one_or_none()

# --- AUTENTICACIÓN Y SESIONES ---
async def authenticate_user(db_session: AsyncSession, login_identifier: str, password: str, request: Request | None = None) -> User | None:
    """Valida credenciales y prepara la sesión (sin commit final)."""
    await asyncio.sleep(0.1) 
    
    user = await get_user_by_login_identifier(db_session, login_identifier=login_identifier)

    if not user or not verify_password(password, user.password):
        return None

    user.last_login = datetime.now(timezone.utc)
    
    if request:
        # No hacemos commit aquí, dejamos que el router decida
        await create_user_session_history(db_session, user.id, request)

    await db_session.flush() # 🚀 Asegura cambios en la sesión sin finalizar la transacción
    return user

async def create_user_session_history(db_session: AsyncSession, user_id: int, request: Request) -> None:
    """Registra los metadatos de la sesión actual."""
    session_entry = UserSessionHistory(
        user_id=user_id,
        login_time=datetime.now(timezone.utc),
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent")
    )
    db_session.add(session_entry)

async def update_user_session_logout_time(db_session: AsyncSession, user_id: int, request: Request) -> None:
    """Marca el fin de la sesión para una IP específica."""
    ip_address = request.client.host if request.client else None
    stmt = (
        update(UserSessionHistory)
        .where(
            and_(
                UserSessionHistory.user_id == user_id,
                UserSessionHistory.logout_time.is_(None),
                UserSessionHistory.ip_address == ip_address
            )
        )
        .values(logout_time=datetime.now(timezone.utc))
    )
    await db_session.execute(stmt)
    await db_session.commit()

# --- GOOGLE OAUTH ---

async def create_user_from_google_credentials(
    db_session: AsyncSession,
    email: str,
    given_name: str = "",
    family_name: str = "",
    picture: str | None = None,
    request: Request | None = None
) -> User:
    """Crea un usuario desde Google con contraseña aleatoria segura."""
    alphabet = string.ascii_letters + string.digits + string.punctuation
    random_pass = "".join(secrets.choice(alphabet) for _ in range(24))
    
    user = User(
        username=email,
        email=email,
        first_name=given_name,
        last_name=family_name,
        user_image=picture,
        password=get_hashed_password(random_pass),
        last_login=datetime.now(timezone.utc)
    )
    db_session.add(user)
    await db_session.flush() # Para obtener el ID antes del commit final

    if request:
        await create_user_session_history(db_session, user.id, request)
    
    await db_session.flush()
    await db_session.refresh(user)
    return user

# --- PASSWORD RESET ---

async def generate_password_reset_token(db_session: AsyncSession, user: User) -> str:
    """Genera token y revoca los anteriores no usados."""
    await db_session.execute(
        update(PasswordResetToken)
        .where(and_(PasswordResetToken.user_id == user.id, PasswordResetToken.is_used.is_(False)))
        .values(is_used=True)
    )
    
    token = secrets.token_urlsafe(32)
    expires_at = datetime.now(timezone.utc) + timedelta(minutes=settings.PASSWORD_RESET_TOKEN_EXPIRE_MINUTES)

    reset_entry = PasswordResetToken(
        user_id=user.id,
        token=token,
        expires_at=expires_at,
        is_used=False
    )
    db_session.add(reset_entry)
    await db_session.commit()
    return token

async def verify_password_reset_token(db_session: AsyncSession, token: str) -> User:
    """Valida el token de forma robusta."""
    query = select(PasswordResetToken).where(PasswordResetToken.token == token)
    result = await db_session.execute(query)
    token_entry = result.scalar_one_or_none()

    if not token_entry:
        raise ValueError("Token inválido.")
    if token_entry.is_used:
        raise ValueError("Token ya utilizado.")
    
    # 🚀 Comparación directa de fechas con zona horaria
    if token_entry.expires_at < datetime.now(timezone.utc):
        raise ValueError("Token expirado.")

    user = await db_session.get(User, token_entry.user_id)
    if not user or user.is_deleted:
        raise ValueError("Usuario no disponible.")
        
    return user

async def reset_user_password(db_session: AsyncSession, user_id: int, token: str, new_password: str) -> None:
    """Actualiza la contraseña y quema el token."""
    user = await db_session.get(User, user_id)
    if not user:
        raise ValueError("Usuario no encontrado.")

    user.password = get_hashed_password(new_password)
    
    await db_session.execute(
        update(PasswordResetToken)
        .where(PasswordResetToken.token == token)
        .values(is_used=True)
    )
    await db_session.commit()

# --- REFRESH TOKENS ---

async def create_refresh_token_db_entry(
    db_session: AsyncSession,
    user_id: int,
    token: str,
    expires_at: datetime,
    request: Request
) -> None:
    """Registra el refresh token con info del dispositivo."""
    entry = RefreshToken(
        user_id=user_id,
        token=token,
        expires_at=expires_at,
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent")
    )
    db_session.add(entry)
    await db_session.commit()

async def revoke_refresh_token(db_session: AsyncSession, token: str) -> bool:
    """Revoca un token específico."""
    stmt = (
        update(RefreshToken)
        .where(and_(RefreshToken.token == token, RefreshToken.is_revoked.is_(False)))
        .values(is_revoked=True)
    )
    result = await db_session.execute(stmt)
    await db_session.commit()
    return result.rowcount > 0

async def revoke_all_user_sessions(db_session: AsyncSession, user_id: int) -> int:
    """Revoca todos los tokens activos (Cierre de sesión global)."""
    stmt = (
        update(RefreshToken)
        .where(and_(RefreshToken.user_id == user_id, RefreshToken.is_revoked.is_(False)))
        .values(is_revoked=True)
    )
    result = await db_session.execute(stmt)
    await db_session.commit()
    return result.rowcount

async def get_user_by_refresh_token(db_session: AsyncSession, token: str) -> User | None:
    """
    Verifica si un refresh token existe, no está revocado y no ha expirado.
    Retorna al usuario asociado.
    """
    query = (
        select(RefreshToken)
        .where(
            and_(
                RefreshToken.token == token,
                RefreshToken.is_revoked.is_(False),
                RefreshToken.expires_at > datetime.now(timezone.utc)
            )
        )
    )
    result = await db_session.execute(query)
    token_entry = result.scalar_one_or_none()

    if not token_entry:
        return None

    return await db_session.get(User, token_entry.user_id)

# --- ORQUESTADOR DE CONTRASEÑA OLVIDADA ---

async def process_forgot_password(
    db_session: AsyncSession, 
    email: str, 
    background_tasks: BackgroundTasks
) -> bool:
    """
    Orquesta el flujo de 'olvidé mi contraseña':
    1. Busca al usuario.
    2. Genera el token.
    3. Envía el email en segundo plano.
    """
    user = await get_user_by_email(db_session, email=email)
    
    # Por seguridad, si el usuario no existe, devolvemos True 
    # para no dar pistas de qué emails están registrados.
    if not user:
        logger.warning(f"Intento de recuperación de contraseña para email no registrado: {email}")
        return True

    try:
        # 1. Generar el token (esto ya hace commit según tu función)
        token = await generate_password_reset_token(db_session, user)
        
        # 2. Enviar el email usando BackgroundTasks para no bloquear la respuesta
        # Asegúrate de que email_service.send_password_reset_email exista
        background_tasks.add_task(
            email_service.send_password_reset_email,
            email_to=user.email,
            token=token,
            username=user.username or user.first_name
        )
        
        return True
    except Exception as e:
        logger.error(f"Error procesando recuperación de contraseña para {email}: {e}")
        return False