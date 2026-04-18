# src/dependencies.py
from typing import Annotated, AsyncGenerator

from jose import jwt, JWTError # <--- JWTError ya está importado
from fastapi.security import OAuth2PasswordBearer
import redis.asyncio as aioredis
from fastapi import Cookie, Depends, HTTPException, status, Request
from sqlalchemy.ext.asyncio import AsyncSession

from src.authentication.services import get_user_by_login_identifier
from src.config import settings
from src.database import get_async_session, redis_pool, async_session_maker
from src.models import User, AppRole, PermisoMerma
from pydantic import ValidationError
from sqlalchemy.future import select as sa_select

# Esto permite que Swagger (docs) y Flutter envíen el token en el Header
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/login/", auto_error=False) 

async def get_current_user(
    request: Request,
    token: Annotated[str | None, Depends(oauth2_scheme)] = None,
    db_session: AsyncSession = Depends(get_async_session),
) -> User:
    # 1. Intentar obtener el token del Header (vía oauth2_scheme) o de la Cookie
    if not token:
        token = request.cookies.get("access_token")
    
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )

    try:
        payload = jwt.decode(token, settings.JWT_ACCESS_SECRET_KEY, algorithms=[settings.ENCRYPTION_ALGORITHM])
        login_identifier: str = payload.get("sub")
        if not login_identifier:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Could not validate credentials",
                headers={"WWW-Authenticate": "Bearer"},
            )
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token expired")
    except JWTError: 
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid Access Token")

    user: User | None = await get_user_by_login_identifier(db_session, login_identifier=login_identifier)

    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if user.is_deleted:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User is not active",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return user

async def get_current_active_user(
    current_user: Annotated[User, Depends(get_current_user)]
) -> User:
    # get_current_user ya maneja si el usuario está "eliminado" (inactivo en este contexto)
    return current_user

async def get_current_admin_user(
    current_user: Annotated[User, Depends(get_current_active_user)]
) -> User:
    if current_user.role != AppRole.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Not an admin user"
        )
    return current_user

def require_role(allowed_roles: list[AppRole]):
    async def role_checker(current_user: Annotated[User, Depends(get_current_active_user)]):
        if current_user.role not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN, detail="No tienes permisos para realizar esta acción"
            )
        return current_user
    return role_checker

async def verify_merma_permission(
    current_user: Annotated[User, Depends(get_current_active_user)],
    db_session: AsyncSession = Depends(get_async_session)
) -> User:
    if current_user.role in [AppRole.ADMIN, AppRole.SUPERVISOR]:
        return current_user
    
    query = sa_select(PermisoMerma).where(PermisoMerma.user_id == current_user.id)
    result = await db_session.execute(query)
    permiso = result.scalar_one_or_none()
    
    if not permiso:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="No tienes permisos para registrar mermas"
        )
    return current_user

async def get_cache_setting():
    return settings.REDIS_CACHE_ENABLED


async def get_cache() -> aioredis.Redis:
    return aioredis.Redis(connection_pool=redis_pool)
