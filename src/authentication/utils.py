# src/authentication/utils.py

from datetime import datetime, timedelta, timezone
from typing import Any
from jose import jwt
from src.config import settings


def create_access_token(subject: str | Any, expires_delta: timedelta = None) -> str:
    # Usar datetime aware (con zona horaria)
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)

    to_encode = {"exp": expire, "sub": str(subject)}
    return jwt.encode(to_encode, settings.JWT_ACCESS_SECRET_KEY, settings.ENCRYPTION_ALGORITHM)


def create_refresh_token(subject: str | Any, expires_delta: timedelta = None) -> str:
    # Cambiar int por timedelta en el type hint y usar timezone.utc
    expire = datetime.now(timezone.utc) + (expires_delta or timedelta(minutes=settings.REFRESH_TOKEN_EXPIRE_MINUTES))
    
    to_encode = {"exp": expire, "sub": str(subject)}
    return jwt.encode(to_encode, settings.JWT_REFRESH_SECRET_KEY, settings.ENCRYPTION_ALGORITHM)

def create_admin_access_token(subject: str | Any, expires_delta: timedelta = None) -> str:
    # Consistencia total con timezone.utc
    expire = datetime.now(timezone.utc) + (expires_delta or timedelta(hours=24))
    
    to_encode = {"exp": expire, "sub": str(subject)}
    return jwt.encode(to_encode, settings.ADMIN_SECRET_KEY, settings.ENCRYPTION_ALGORITHM)