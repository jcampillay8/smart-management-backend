# src/config.py
import logging
import os
from random import randint
from pathlib import Path

import boto3
from typing import List, Dict, Any, Optional, Literal
from pydantic import HttpUrl, Field, EmailStr, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict
import pytz


class GlobalSettings(BaseSettings):
    # ⚠️ Amplía model_config
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",   # <--- clave: ignora variables no mapeadas
    )

    ENVIRONMENT: str 

    ALLOWED_ORIGINS: str
    def get_allowed_origins(self) -> List[str]:
        return [origin.strip() for origin in self.ALLOWED_ORIGINS.split(",")]

    LOG_LEVEL: int = logging.DEBUG
    SENTRY_DSN: Optional[str] = None

    # --- DB ---
    DB_USER: Optional[str] = None
    DB_PASSWORD: Optional[str] = None
    DB_HOST: Optional[str] = None
    DB_PORT: Optional[int] = None
    DB_NAME: Optional[str] = None
    DB_SCHEMA: Optional[str] = None
    DATABASE_URL: Optional[str] = None

    # --- JWT/Seguridad ---
    JWT_ACCESS_SECRET_KEY: str
    JWT_REFRESH_SECRET_KEY: str
    ENCRYPTION_ALGORITHM: str
    ACCESS_TOKEN_EXPIRE_MINUTES: int
    NEW_ACCESS_TOKEN_EXPIRE_MINUTES: int
    REFRESH_TOKEN_EXPIRE_MINUTES: int
    PASSWORD_RESET_TOKEN_EXPIRE_MINUTES: int = 60

    # --- App / Front ---
    WEBSITE_URL: HttpUrl
    API_URL: HttpUrl

    # --- SMTP heredado (sigue por compatibilidad) ---
    MAIL_USERNAME: str
    MAIL_PASSWORD: str
    MAIL_FROM: str
    MAIL_PORT: int
    MAIL_SERVER: str
    MAIL_FROM_NAME: str = "Tu Aplicación"
    MAIL_STARTTLS: bool = True
    MAIL_SSL_TLS: bool = False
    USE_CREDENTIALS: bool = True
    VALIDATE_CERTS: bool = True

    # --- NUEVO: Email por API (Resend) ---
    EMAIL_PROVIDER: Literal["smtp", "resend"] = "smtp"
    RESEND_API_KEY: Optional[SecretStr] = None
    EMAIL_FROM: Optional[str] = None                  # e.g. "OppyChat Support <oppychat@gmail.com>"
    SUPPORT_EMAIL: EmailStr = "support@oppychat.com"  # default

    @property
    def email_from_resolved(self) -> str:
        """
        Si EMAIL_FROM no está definido en .env, construye uno
        a partir de MAIL_FROM_NAME y MAIL_FROM (útil para SMTP).
        """
        return self.EMAIL_FROM or f"{self.MAIL_FROM_NAME} <{self.MAIL_FROM}>"

    BASE_DIR: Path = Path(__file__).parent.parent 
    TEMPLATES_DIR: Path = Path(os.path.join(BASE_DIR, "templates"))

    TZ: str = "America/Santiago"

    # --- OAuth ---
    GOOGLE_CLIENT_ID: Optional[str] = None
    GOOGLE_CLIENT_SECRET: Optional[str] = None

    ADMIN_SECRET_KEY: str
    SECRET_KEY: str

    # --- IA ---
    GEMINI_API_KEY: str

    # --- Redis, status, static, AWS (igual que tenías) ---
    REDIS_CACHE_ENABLED: bool = True
    REDIS_HOST: str
    REDIS_PORT: int
    REDIS_PASSWORD: Optional[str] = None
    REDIS_CACHE_EXPIRATION_SECONDS: int = 60 * 30
    REDIS_DB: int = 0

    SECONDS_TO_SEND_USER_STATUS: int = 3600
    SECONDS_FOR_USER_STATUS_EXPIRATION: int = 60 

    STATIC_HOST: HttpUrl

    AWS_ACCESS_KEY_ID: Optional[str] = None
    AWS_SECRET_ACCESS_KEY: Optional[str] = None
    AWS_REGION: Optional[str] = None
    AWS_IMAGES_BUCKET: Optional[str] = None
    
class TestSettings(GlobalSettings):
    DB_SCHEMA: str = Field(f"test_{randint(1, 100)}", alias="DB_SCHEMA")


class DevelopmentSettings(GlobalSettings):
    pass


class ProductionSettings(GlobalSettings):
    AWS_ACCESS_KEY_ID: Optional[str] = None
    AWS_SECRET_ACCESS_KEY: Optional[str] = None
    AWS_REGION: Optional[str] = None
    AWS_IMAGES_BUCKET: Optional[str] = None
    
    LOG_LEVEL: int = logging.INFO
    
    @staticmethod
    def get_aws_client_for_image_upload():
        if all(
            (
                aws_access_key_id := os.environ.get("AWS_ACCESS_KEY_ID"),
                aws_secret_access_key := os.environ.get("AWS_SECRET_ACCESS_KEY"),
                region_name := os.environ.get("AWS_REGION"),
            )
        ):
            aws_session = boto3.Session(
                aws_access_key_id=aws_access_key_id,
                aws_secret_access_key=aws_secret_access_key,
                region_name=region_name,
            )
            s3_resource = aws_session.resource("s3")
            
            return s3_resource.meta.client
        else:
            return None
        

def get_settings():
    env =os.environ.get("ENVIRONMENT", "development")
    if env == "test":
        return TestSettings()
    elif env == "development":
        return DevelopmentSettings()
    elif env == "production":
        return ProductionSettings()
    
    return GlobalSettings()


settings = get_settings()
settings.TZ = pytz.timezone(settings.TZ)

LOGGING_CONFIG: dict = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "standard": {"format": "%(asctime)s [%(levelname)s] %(name)s: %(message)s"},
    },
    "handlers": {
        "default": {
            "level": settings.LOG_LEVEL,
            "formatter": "standard",
            "class": "logging.StreamHandler",
            "stream": "ext://sys.stdout",
        },
    },
    "loggers": {
        "": {"handlers": ["default"], "level": settings.LOG_LEVEL, "propagate": False},
        "uvicorn": {
            "handlers": ["default"],
            "level": logging.DEBUG,
            "propagate": False,
        }
    }
}
