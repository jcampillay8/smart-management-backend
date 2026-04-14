# alembic/env.py
import asyncio
from logging.config import fileConfig
import os
import logging
import sys
from re import match
from sqlalchemy import pool, text
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config, AsyncEngine
from sqlalchemy.exc import SQLAlchemyError

from alembic import context
from alembic.script import ScriptDirectory
from alembic.runtime.environment import EnvironmentContext

# 1. Configuración de rutas e imports de la app
from src.config import get_settings
from src.database import BaseModel

# --- IMPORTACIÓN DE TODOS LOS MODELOS ---
# Es CRUCIAL importar todos para que Alembic detecte los cambios
from src.models import User, Chat, Message
from src.authentication.models import (
    UserSessionHistory, 
    PasswordResetToken, 
    RefreshToken, 
    EmailConfirmationToken
)

# --- CONFIGURACIÓN DE LOGGING Y ENGINE ---
current_settings = get_settings()
fileConfig(context.config.config_file_name)
logger = logging.getLogger("alembic.env")

# Determinar URL de la base de datos
db_url = str(current_settings.DATABASE_URL) if current_settings.DATABASE_URL else (
    f"postgresql+asyncpg://{current_settings.DB_USER}:{current_settings.DB_PASSWORD}@"
    f"{current_settings.DB_HOST}:{current_settings.DB_PORT}/{current_settings.DB_NAME}"
)

config = context.config
config.set_main_option("sqlalchemy.url", db_url)
target_metadata = BaseModel.metadata

def process_revision_directives(context: EnvironmentContext, revision, directives):
    """Genera IDs secuenciales (0001, 0002...) en lugar de hashes aleatorios."""
    # Revisamos si autogenerate está presente en el contexto
    if context.config.cmd_opts and getattr(context.config.cmd_opts, "autogenerate", False):
        migration_script = directives[0]
        script_directory = ScriptDirectory.from_config(context.config)
        head_revision = script_directory.get_current_head()

        if head_revision is None:
            new_rev_id = 1
        else:
            matched = match(r"^0*(\d+)$", head_revision)
            if matched:
                new_rev_id = int(matched.group(1)) + 1
            else:
                return 

        migration_script.rev_id = f"{new_rev_id:04}"

def run_migrations_offline() -> None:
    """Modo offline."""
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        process_revision_directives=process_revision_directives,
        version_table_schema="chat",
        include_schemas=True,
    )

    with context.begin_transaction():
        context.execute(text("CREATE SCHEMA IF NOT EXISTS chat"))
        context.run_migrations()

def do_run_migrations(connection: Connection) -> None:
    """Función sincrónica ejecutada dentro del motor asíncrono."""
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        process_revision_directives=process_revision_directives,
        version_table_schema="chat",
        include_schemas=True,
    )

    with context.begin_transaction():
        # Aseguramos que el esquema exista antes de intentar crear tablas
        connection.execute(text("CREATE SCHEMA IF NOT EXISTS chat"))
        context.run_migrations()

async def run_async_migrations() -> None:
    """Configuración del motor asíncrono y ejecución."""
    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    try:
        async with connectable.connect() as connection:
            await connection.run_sync(do_run_migrations)
        await connectable.dispose()
    except Exception:
        logger.error("🔥 Error durante la ejecución de migraciones asíncronas")
        import traceback; traceback.print_exc()
        sys.exit(1)

def run_migrations_online() -> None:
    """Modo online."""
    asyncio.run(run_async_migrations())

if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()