# src/database.py
# Manejo de fechas y tipos para sesiones asíncronas
import logging 
from datetime import datetime
from typing import AsyncGenerator

# Cliente Redis asincrónico
import redis.asyncio as aioredis

# Componentes principales de SQLAlchemy (asincrónico y ORM)
from sqlalchemy import Boolean, DateTime, MetaData, func
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker

# Importamos la configuración central desde src/config.py
from src.config import settings

logger = logging.getLogger(__name__)

# ---------------------------------------------
# 🔗 Construcción de la URL de conexión a PostgreSQL

DATABASE_URL = settings.DATABASE_URL or (
    f"postgresql+asyncpg://"
    f"{settings.DB_USER}:{settings.DB_PASSWORD}@{settings.DB_HOST}:{settings.DB_PORT}/{settings.DB_NAME}"
)

# ---------------------------------------------
# 🏷️ Metadata con esquema personalizado

# Define el schema a usar por defecto en todas las tablas
metadata = MetaData(schema=settings.DB_SCHEMA)

# ---------------------------------------------
# 🧩 Mixin para quitar campos comunes en casos específicos (como respuestas simplificadas)

class RemoveBaseFieldMixin:
    created_at = None
    updated_at = None
    is_deleted = None

# ---------------------------------------------
# 🧬 Clase base que usarán todos los modelos del proyecto

class BaseModel(DeclarativeBase):
    __abstract__ = True
    metadata = metadata

    # Campos comunes en todos los modelos (auditoría y borrado lógico)
    # NOTA: DateTime(timezone=True) es correcto y fundamental.
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
    is_deleted: Mapped[bool] = mapped_column(Boolean, default=False)

    def to_dict(self):
        return {field.name: getattr(self, field.name) for field in self.__table__.c}


# 🚀 Creación del engine asincrónico de SQLAlchemy optimizado
engine = create_async_engine(
    DATABASE_URL, 
    pool_size=40,          # Capacidad base del pool
    max_overflow=20,       # Conexiones extra en picos de tráfico
    pool_recycle=3600,     # Recicla conexiones cada 1 hora para evitar "stale connections"
    # Eliminamos AUTOCOMMIT para garantizar la integridad de los datos (ACID)
    echo=False             # Cámbialo a True solo para debugging de SQL en consola
)

# 🧵 Creador de sesiones asincrónicas
async_session_maker = sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False, # Importante para acceder a atributos tras el commit
    autocommit=False,       # Refuerza que no se haga commit automático
    autoflush=False         # Evita enviar SQL innecesario antes de tiempo
)

# ---------------------------------------------
# 📦 Función que será usada como dependencia en FastAPI

async def get_async_session() -> AsyncGenerator[AsyncSession, None]:
    async with async_session_maker() as session:
        yield session

            
# ---------------------------------------------
# 🧠 Función para crear un pool de conexiones a Redis

def create_redis_pool():
    return aioredis.ConnectionPool(
        host=settings.REDIS_HOST,
        port=settings.REDIS_PORT,
        password=settings.REDIS_PASSWORD,
        db=settings.REDIS_DB,
    )

# Instancia global del pool de Redis para ser reutilizado en toda la app
redis_pool = create_redis_pool()