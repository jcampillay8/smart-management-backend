import asyncio
from sqlalchemy import text
from src.database import engine

async def run():
    async with engine.connect() as conn:
        await conn.execute(text("COMMIT"))
        try:
            await conn.execute(text("ALTER TYPE operations.approle ADD VALUE 'PROPIETARIO' AFTER 'SUPERVISOR'"))
            print("Enum value 'PROPIETARIO' added successfully")
        except Exception as e:
            print(f"Error adding enum value: {e}")

if __name__ == "__main__":
    asyncio.run(run())
