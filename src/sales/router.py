# src/sales/router.py
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List

from src.database import get_db
from src.sales.schemas import RecetaOut, RecetaCreate
from src.sales.services.recipe_service import RecipeService
from src.sales.routers.event_router import router as event_router

# Router principal del módulo Sales
sales_router = APIRouter(prefix="/sales")

# 1. Incluimos el router especializado en Eventos
sales_router.include_router(event_router)

# 2. Endpoints de Recetas (directos aquí o en otro sub-router)
@sales_router.post("/recipes", response_model=RecetaOut, tags=["Sales - Recipes"])
async def create_recipe(data: RecetaCreate, db: AsyncSession = Depends(get_db)):
    service = RecipeService(db)
    return await service.create_recipe(data)

@sales_router.get("/recipes", response_model=List[RecetaOut], tags=["Sales - Recipes"])
async def list_recipes(db: AsyncSession = Depends(get_db)):
    service = RecipeService(db)
    return await service.get_all_recipes()