# src/registration/router.py
import logging
from fastapi import APIRouter, Depends, Form, File, UploadFile, HTTPException, status
from fastapi.responses import RedirectResponse, HTMLResponse
from sqlalchemy.ext.asyncio import AsyncSession

from src.config import settings
from src.database import get_async_session
from src.registration import services as reg_services  # módulo
from src.registration.schemas import UserRegisterSchema  # schema

logger = logging.getLogger(__name__)
account_router = APIRouter(tags=["Account Management"])

@account_router.post(
    "/register",
    status_code=status.HTTP_202_ACCEPTED,
    summary="Register a new user and send a confirmation email",
    response_description="A confirmation email has been sent to the user's email address.",
)
async def register_user(
    db_session: AsyncSession = Depends(get_async_session),
    first_name: str = Form(..., max_length=50),
    last_name: str = Form(..., max_length=50),
    username: str = Form(..., min_length=3, max_length=50),
    email: str = Form(..., max_length=100),
    password: str = Form(..., min_length=8),
    terms_accepted: bool = Form(...),
    user_image: UploadFile | None = File(None, description="Profile image of the user"),
):
    user_data = UserRegisterSchema(
        first_name=first_name,
        last_name=last_name,
        username=username,
        email=email,
        password=password,
        terms_accepted=terms_accepted,
    )

    # Validación contraseña
    reg_services.validate_password_complexity(user_data.password)

    # Duplicados
    existing_user = await reg_services.get_user_by_email_or_username(
        db_session,
        email=user_data.email.lower(),
        username=user_data.username.lower(),
    )
    if existing_user:
        if existing_user.email == user_data.email.lower():
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Ya existe un usuario con este correo electrónico.")
        if existing_user.username == user_data.username.lower():
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Ya existe un usuario con este nombre de usuario.")

    if not user_data.terms_accepted:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Debes aceptar los Términos y Condiciones para registrarte.")

    # Enviar email de confirmación (incluye lógica de bypass para emails de prueba de MP)
    return await reg_services.register_user_and_send_confirmation( # 👈 LÍNEA CORREGIDA
        db_session=db_session,
        user_schema=user_data,
        uploaded_image=user_image,
    )

from fastapi.responses import RedirectResponse

@account_router.get("/confirm-email/{token}")
async def confirm_email(
    token: str,
    db_session: AsyncSession = Depends(get_async_session),
):
    # 1. Activamos al usuario en la DB (Esto ya funciona en Neon)
    await reg_services.confirm_user_email(db_session=db_session, token=token)
    
    # 2. Redirección directa al esquema de la app. 
    # Si el AndroidManifest tiene BROWSABLE, esto despertará a la App.
    app_url = f"oppychat://confirm-success?token={token}"
    
    return RedirectResponse(url=app_url)
