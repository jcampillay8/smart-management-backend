# src/sales/routers/sales_router.py
from fastapi import APIRouter, Depends, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from uuid import UUID
from typing import List

from src.database import get_async_session
from src.sales.schemas import (
    RecetaCreate, RecetaOut, 
    VentaRecetaCreate, VentaRecetaOut
)
from src.sales.services.sales_service import SalesService
from src.dependencies import get_current_user
from src.models import User

router = APIRouter()

# --- GESTIÓN DE RECETAS ---

@router.get("/recipes", response_model=List[RecetaOut])
async def list_recipes(db: AsyncSession = Depends(get_async_session)):
    """Lista el catálogo de recetas con sus ingredientes."""
    return await SalesService(db).get_all_recipes()

@router.post("/recipes", response_model=RecetaOut, status_code=status.HTTP_201_CREATED)
async def create_recipe(
    data: RecetaCreate,
    db: AsyncSession = Depends(get_async_session),
    _ = Depends(get_current_user)
):
    return await SalesService(db).create_recipe(data)

@router.put("/recipes/{receta_id}", response_model=RecetaOut)
async def update_recipe(
    receta_id: UUID,
    data: RecetaCreate,
    db: AsyncSession = Depends(get_async_session),
    _ = Depends(get_current_user)
):
    return await SalesService(db).update_recipe(receta_id, data)

@router.delete("/recipes/{receta_id}")
async def delete_recipe(
    receta_id: UUID,
    db: AsyncSession = Depends(get_async_session),
    _ = Depends(get_current_user)
):
    return await SalesService(db).delete_recipe(receta_id)

# --- OPERACIONES DE VENTA ---

@router.post("/sell", response_model=VentaRecetaOut, status_code=status.HTTP_201_CREATED)
async def register_sale(
    data: VentaRecetaCreate,
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user)
):
    """
    Registra una venta y descuenta stock automáticamente.
    Atómico: Si no hay stock suficiente, la venta no se registra.
    """
    return await SalesService(db).register_sale(data, current_user.id)

@router.get("/availability/{receta_id}")
async def check_availability(
    receta_id: UUID,
    cantidad: int = Query(default=1, ge=1),
    db: AsyncSession = Depends(get_async_session)
):
    """Consulta si es posible realizar una venta antes de procesarla."""
    return await SalesService(db).check_availability(receta_id, cantidad)