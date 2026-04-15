# src/operations/routers/recipe_router.py
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from uuid import UUID

from src.database import get_async_session
from src.dependencies import get_current_user
from src.models import User
from src.operations.services.recipe_service import RecipeService

router = APIRouter()

@router.post("/{receta_id}/consume")
async def register_recipe_usage(
    receta_id: UUID,
    cantidad: int = Query(ge=1),
    db: AsyncSession = Depends(get_async_session),
    user: User = Depends(get_current_user)
):
    service = RecipeService(db)
    return await service.execute_recipe_consumption(receta_id, cantidad, user.id)

@router.get("/{receta_id}/availability")
async def check_recipe_stock(
    receta_id: UUID,
    cantidad: int = Query(default=1),
    db: AsyncSession = Depends(get_async_session)
):
    service = RecipeService(db)
    return await service.check_recipe_availability(receta_id, cantidad)