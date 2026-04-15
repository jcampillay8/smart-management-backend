# src/sales/routers/sales_router.py
from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession
from uuid import UUID
from typing import List

from src.database import get_db
from src.sales.schemas import RecetaCreate, RecetaOut, VentaRecetaCreate, VentaRecetaOut
from src.sales.services.sales_service import SalesService # Asumiendo que crearás este service
from src.authentication.dependencies import get_current_user
from src.models import User

router = APIRouter(prefix="/sales", tags=["Sales & Recipes"])

@router.post("/recipes", response_model=RecetaOut, status_code=status.HTTP_201_CREATED)
async def create_recipe(
    recipe_data: RecetaCreate,
    db: AsyncSession = Depends(get_db)
):
    """Crea una nueva receta con sus ingredientes."""
    service = SalesService(db)
    return await service.create_recipe(recipe_data)

@router.get("/recipes", response_model=List[RecetaOut])
async def list_recipes(db: AsyncSession = Depends(get_db)):
    """Lista todas las recetas disponibles."""
    service = SalesService(db)
    return await service.get_all_recipes()

@router.post("/sell", response_model=VentaRecetaOut)
async def register_sale(
    sale_data: VentaRecetaCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Registra una venta directa de una receta y descuenta stock inmediatamente."""
    service = SalesService(db)
    return await service.register_sale(sale_data, current_user.id)