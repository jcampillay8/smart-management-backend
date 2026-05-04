import asyncio
from src.database import async_session_maker
from src.models import User, AppRole
from sqlalchemy import select

async def run():
    async with async_session_maker() as db:
        result = await db.execute(select(User).where(User.username == 'xslyrk'))
        user = result.scalar_one_or_none()
        if user:
            print(f"User found: {user.username}, Current Role: {user.role}")
        else:
            print("User xslyrk not found")

if __name__ == "__main__":
    asyncio.run(run())
