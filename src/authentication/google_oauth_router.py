# src/authentication/google_oauth_router.py
from pydantic import BaseModel
import logging
from datetime import datetime, timedelta, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession
from authlib.integrations.starlette_client import OAuth, OAuthError
from google.oauth2 import id_token
from google.auth.transport import requests

from src.config import settings
from src.database import get_async_session
from src.authentication.services import (
    get_user_by_email,
    create_user_from_google_credentials,
    create_user_session_history,
    create_refresh_token_db_entry
)
from src.authentication.utils import create_access_token, create_refresh_token

logger = logging.getLogger(__name__)

# --- Configuración del cliente OAuth ---
oauth = OAuth()
oauth.register(
    name='google',
    client_id=settings.GOOGLE_CLIENT_ID,
    client_secret=settings.GOOGLE_CLIENT_SECRET,
    server_metadata_url='https://accounts.google.com/.well-known/openid-configuration',
    client_kwargs={'scope': 'openid email profile'},
)

google_router = APIRouter(prefix="/auth/google", tags=["Auth Google"])

# 1. Definimos qué esperamos recibir desde Flutter
class GoogleMobileAuthRequest(BaseModel):
    id_token: str

# 2. Creamos el endpoint POST que Flutter está buscando
@google_router.post("/mobile-signin", summary="Verify Google Token from Mobile App")
async def google_mobile_signin(
    data: GoogleMobileAuthRequest,
    db_session: Annotated[AsyncSession, Depends(get_async_session)],
    request: Request
):
    try:
        # Validar el token con Google usando tu CLIENT_ID de WEB
        # Nota: Google recomienda usar el Web Client ID para validación en backend
        id_info = id_token.verify_oauth2_token(
            data.id_token, 
            requests.Request(), 
            settings.GOOGLE_CLIENT_ID 
        )

        email = id_info.get("email").lower()
        
        # 3. Reutilizamos tu lógica de base de datos que ya tienes en el callback
        user = await get_user_by_email(db_session, email=email)
        
        if not user:
            # Crear usuario si no existe
            user = await create_user_from_google_credentials(
                db_session,
                email=email,
                given_name=id_info.get("given_name", ""),
                family_name=id_info.get("family_name", ""),
                picture=id_info.get("picture", None),
                request=request
            )
        
        # 4. Generar los tokens de OppyChat (JWT)
        access_token = create_access_token(subject=user.email)
        refresh_token = create_refresh_token(subject=user.email)

        await db_session.commit()

        return {
            "access_token": access_token,
            "refresh_token": refresh_token,
            "token_type": "bearer"
        }

    except ValueError as e:
        logger.error(f"Token de Google inválido: {e}")
        raise HTTPException(status_code=401, detail="Token de Google inválido")

@google_router.get("/login", summary="Initiate Google OAuth login flow")
async def google_login(request: Request):
    """Redirige al usuario a la página de inicio de sesión de Google."""
    redirect_uri = request.url_for('google_auth_callback')
    return await oauth.google.authorize_redirect(request, redirect_uri)

@google_router.get("/callback", name="google_auth_callback", summary="Handle Google OAuth callback")
async def google_auth_callback(
    request: Request,
    db_session: Annotated[AsyncSession, Depends(get_async_session)]
):
    try:
        token = await oauth.google.authorize_access_token(request)
    except OAuthError as error:
        logger.error(f"Error de OAuth: {error.error}")
        raise HTTPException(status_code=400, detail="Error en la autenticación con Google.")

    user_info = token.get('userinfo')
    if not user_info or not user_info.get("email"):
        raise HTTPException(status_code=400, detail="Información de usuario incompleta.")

    normalized_email = user_info.get("email").lower()
    user = await get_user_by_email(db_session, email=normalized_email)

    if not user:
        # 1. Crear usuario (Asegúrate que este servicio use .flush() y no .commit())
        user = await create_user_from_google_credentials(
            db_session,
            email=normalized_email,
            given_name=user_info.get("given_name", ""),
            family_name=user_info.get("family_name", ""),
            picture=user_info.get("picture", None),
            request=request
        )
        # 🚀 Eliminamos la llamada a assign_default_bots... (YAGNI)
    else:
        user.last_login = datetime.now(timezone.utc)
        await create_user_session_history(db_session, user.id, request)

    # --- Gestión de Tokens ---
    access_token = create_access_token(subject=user.email)
    refresh_token = create_refresh_token(subject=user.email)

    refresh_expires = datetime.now(timezone.utc) + timedelta(minutes=settings.REFRESH_TOKEN_EXPIRE_MINUTES)
    await create_refresh_token_db_entry(
        db_session=db_session,
        user_id=user.id,
        token=refresh_token,
        expires_at=refresh_expires,
        request=request
    )
    
    # Único commit para toda la operación
    await db_session.commit()

    # --- Respuesta y Cookies ---
    from src.authentication.auth_router import get_cookie_settings # Import local para evitar circular
    
    base_url = str(settings.WEBSITE_URL).rstrip('/')
    response = RedirectResponse(url=f"{base_url}/callback", status_code=status.HTTP_302_FOUND)

    cookie_conf = get_cookie_settings(request)
    # Combinamos con max_age
    cookie_params = {**cookie_conf, "httponly": True, "max_age": settings.REFRESH_TOKEN_EXPIRE_MINUTES * 60}

    response.set_cookie(key="access_token", value=access_token, **cookie_params)
    response.set_cookie(key="refresh_token", value=refresh_token, **cookie_params)

    return response