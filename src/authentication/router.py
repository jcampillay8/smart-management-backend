import logging
from datetime import datetime, timedelta, timezone
from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, Cookie, Depends, HTTPException, Response, status, Request
from fastapi.security import OAuth2PasswordRequestForm
from fastapi_limiter.depends import RateLimiter
from sqlalchemy.ext.asyncio import AsyncSession
from jose import jwt, JWTError

from src.authentication.schemas import (
    UserPublicSchema, ForgotPasswordSchema, ResetPasswordSchema, LoginResponseSchema
)
from src.authentication.services import (
    authenticate_user,
    get_user_by_login_identifier,
    process_forgot_password,
    verify_password_reset_token,
    reset_user_password,
    create_refresh_token_db_entry,
    revoke_refresh_token,
    update_user_session_logout_time
)
from src.authentication.utils import create_access_token, create_refresh_token
from src.config import settings
from src.database import get_async_session
from src.models import User

logger = logging.getLogger(__name__)
auth_router = APIRouter(tags=["Authentication"])

def get_cookie_settings(request: Request):
    """Detecta entorno para ajustar políticas de seguridad de cookies."""
    origin = request.headers.get("origin")
    if origin == "http://localhost:5173" or settings.ENVIRONMENT == "development":
        return {"samesite": "lax", "secure": False}
    return {
        "samesite": "none" if settings.ENVIRONMENT == "production" else "lax", 
        "secure": settings.ENVIRONMENT == "production"
    }

@auth_router.post("/login/", response_model=LoginResponseSchema)
async def login(
    response: Response,
    request: Request,
    db_session: AsyncSession = Depends(get_async_session),
    form_data: OAuth2PasswordRequestForm = Depends(),
) -> LoginResponseSchema:
    # 1. Autenticación (El servicio ya hace el flush/commit necesario)
    user = await authenticate_user(
        db_session=db_session, 
        login_identifier=form_data.username.lower(), 
        password=form_data.password, 
        request=request
    )

    if not user:
        raise HTTPException(status_code=401, detail="Credenciales incorrectas")
        
    # 2. Generación de Tokens
    access_token = create_access_token(user.email)
    refresh_token = create_refresh_token(user.email)
    
    # 3. Registro en DB (Fundamental para la seguridad)
    refresh_expires = datetime.now(timezone.utc) + timedelta(minutes=settings.REFRESH_TOKEN_EXPIRE_MINUTES)
    await create_refresh_token_db_entry(
        db_session=db_session,
        user_id=user.id,
        token=refresh_token,
        expires_at=refresh_expires,
        request=request
    )
    
    # 4. Configuración de Cookies
    cookie_conf = get_cookie_settings(request)
    response.set_cookie(key="access_token", value=access_token, httponly=True, **cookie_conf)
    response.set_cookie(key="refresh_token", value=refresh_token, httponly=True, **cookie_conf)

    # 5. Respuesta limpia usando Pydantic
    # Agregamos manualmente los campos que no están en el modelo User de la DB
    user.token_expires_at = int((datetime.now(timezone.utc) + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)).timestamp())
    user.access_token = access_token

    return user # Pydantic se encarga del resto

@auth_router.post("/refresh/")
async def refresh_token(
    request: Request,
    response: Response,
    refresh_token: Annotated[str | None, Cookie()] = None,
    db_session: AsyncSession = Depends(get_async_session),
):
    if not refresh_token:
        raise HTTPException(status_code=401, detail="No refresh token provided")

    try:
        # 1. Validar firma y extraer email
        payload = jwt.decode(refresh_token, settings.JWT_REFRESH_SECRET_KEY, algorithms=[settings.ENCRYPTION_ALGORITHM])
        email = payload.get("sub")
        
        # 2. 🚀 VALIDACIÓN CRÍTICA: ¿Existe y está activo en la DB?
        user = await get_user_by_refresh_token(db_session, refresh_token)
        if not user:
            raise HTTPException(status_code=401, detail="Session expired or revoked")
        
        # 3. Generar nuevo access token
        new_access_token = create_access_token(user.email)
        cookie_conf = get_cookie_settings(request)
        response.set_cookie(key="access_token", value=new_access_token, httponly=True, **cookie_conf)

        return {
            "token_expires_at": int((datetime.now(timezone.utc) + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)).timestamp()),
            "accessToken": new_access_token 
        }
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid token signature")
    except Exception as e:
        logger.error(f"Error en refresh token: {e}")
        raise HTTPException(status_code=401, detail="Could not refresh session")

@auth_router.post("/logout/")
async def logout(
    response: Response,
    request: Request,
    refresh_token: Annotated[str | None, Cookie()] = None,
    db_session: AsyncSession = Depends(get_async_session),
):
    # 🚀 Evitamos BackgroundTasks aquí para asegurar que la DB cierre la sesión correctamente
    if refresh_token:
        await revoke_refresh_token(db_session, refresh_token)

    cookie_conf = get_cookie_settings(request)
    response.delete_cookie(key="access_token", **cookie_conf)
    response.delete_cookie(key="refresh_token", **cookie_conf)
    
    return {"message": "Logged out successfully"}

@auth_router.post("/forgot-password/")
async def forgot_password(
    schema: ForgotPasswordSchema,
    background_tasks: BackgroundTasks,
    db_session: AsyncSession = Depends(get_async_session),
):
    # Usamos el nuevo servicio atómico que coordina todo
    background_tasks.add_task(process_forgot_password, db_session, schema.email)
    return {"message": "Si el email existe, recibirás instrucciones pronto."}

@auth_router.post("/reset-password/")
async def reset_password(
    schema: ResetPasswordSchema,
    db_session: AsyncSession = Depends(get_async_session),
):
    try:
        user = await verify_password_reset_token(db_session, schema.token)
        await reset_user_password(db_session, user.id, schema.token, schema.new_password)
        return {"message": "Contraseña restablecida con éxito."}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))