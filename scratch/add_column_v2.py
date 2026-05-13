import asyncio
from sqlalchemy import text
from src.database import engine
from src.config import settings

async def add_tipo_negocio_column():
    async with engine.begin() as conn:
        print(f"Adding column to {settings.DB_SCHEMA}.configuracion_restaurante...")
        try:
            # PostgreSQL syntax for adding column if not exists
            await conn.execute(text(f"ALTER TABLE {settings.DB_SCHEMA}.configuracion_restaurante ADD COLUMN IF NOT EXISTS tipo_negocio VARCHAR(100)"))
            print("Column added successfully or already exists.")
        except Exception as e:
            print(f"Error: {e}")

if __name__ == "__main__":
    asyncio.run(add_tipo_negocio_column())
