import asyncio
from sqlalchemy import text
from src.database import engine

async def run():
    async with engine.connect() as conn:
        # PostgreSQL's ALTER TYPE ... ADD VALUE cannot be executed in a transaction block
        # so we need to set isolation level to AUTOCOMMIT if needed, 
        # or just hope the connection is not in a transaction.
        # However, SQLAlchemy's engine.connect() usually starts a transaction.
        
        await conn.execute(text("COMMIT")) # Ensure we are out of any implicit transaction
        try:
            await conn.execute(text("ALTER TYPE operations.approle ADD VALUE 'propietario' AFTER 'supervisor'"))
            print("Enum value 'propietario' added successfully")
        except Exception as e:
            if "already exists" in str(e):
                print("Enum value 'propietario' already exists")
            else:
                print(f"Error adding enum value: {e}")

if __name__ == "__main__":
    asyncio.run(run())
