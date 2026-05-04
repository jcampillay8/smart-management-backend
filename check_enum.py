import asyncio
from sqlalchemy import text
from src.database import engine

async def run():
    async with engine.connect() as conn:
        result = await conn.execute(text("SELECT enumlabel FROM pg_enum JOIN pg_type ON pg_enum.enumtypid = pg_type.oid WHERE typname = 'approle'"))
        labels = [row[0] for row in result.fetchall()]
        print(f"Current labels: {labels}")

if __name__ == "__main__":
    asyncio.run(run())
