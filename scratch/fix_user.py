import asyncio
import os
import sys

# Add src to path
sys.path.append(os.path.join(os.getcwd(), "src"))

from src.database import async_session_maker
from src.models import User
from src.utils import get_hashed_password
from sqlalchemy import select

async def fix_user():
    async with async_session_maker() as session:
        username = "xslyrk"
        password = "_Q1o0w2i9e3u8"
        
        query = select(User).where(User.username == username)
        result = await session.execute(query)
        user = result.scalar_one_or_none()
        
        if user:
            print(f"User found: {user.username}. Updating password and status.")
            user.password = get_hashed_password(password)
            user.has_accepted_terms = True
            user.is_superuser = True
            user.is_deleted = False
            await session.commit()
            print("User updated successfully.")
        else:
            print(f"User {username} not found. Creating...")
            new_user = User(
                username=username,
                email="jose@example.com",
                password=get_hashed_password(password),
                first_name="Jose",
                last_name="G",
                has_accepted_terms=True,
                is_superuser=True
            )
            session.add(new_user)
            await session.commit()
            print("User created successfully.")

if __name__ == "__main__":
    asyncio.run(fix_user())
