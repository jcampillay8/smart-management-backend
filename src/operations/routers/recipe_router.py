# src/operations/routers/recipe_router.py
from fastapi import APIRouter, Depends, Query, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from uuid import UUID
from typing import List

from src.database import get_async_session
from src.dependencies import get_current_user
from src.authentication.models import User # Ajusta según tu ruta de User
from src.operations.services.recipe_service import RecipeService
from src.operations.schemas import RecetaCreate, RecetaOut # Asegúrate de tener estos schemas

router = APIRouter()

# =========================================================================
# ENDPOINTS ADMINISTRATIVOS (Para Gestion.tsx)
# =========================================================================

@router.get("/", response_model=List[RecetaOut])
async def list_recipes(
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user)
):
    """Obtiene la lista de todas las recetas para la tabla de Gestión."""
    service = RecipeService(db)
    return await service.get_all_recipes()

@router.post("/", response_model=RecetaOut, status_code=status.HTTP_201_CREATED)
async def create_new_recipe(
    data: RecetaCreate,
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user)
):
    """Crea una nueva receta con sus ingredientes."""
    service = RecipeService(db)
    return await service.create_recipe(data)

@router.put("/{receta_id}", response_model=RecetaOut)
async def update_recipe(
    receta_id: UUID,
    data: RecetaCreate,
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user)
):
    """Actualiza la definición de una receta existente."""
    service = RecipeService(db)
    return await service.update_recipe(receta_id, data)

@router.delete("/{receta_id}")
async def delete_recipe(
    receta_id: UUID,
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user)
):
    """Elimina una receta del catálogo."""
    service = RecipeService(db)
    return await service.delete_recipe(receta_id)

# =========================================================================
# ENDPOINTS OPERATIVOS (Consumo y Disponibilidad)
# =========================================================================

@router.post("/{receta_id}/consume")
async def register_recipe_usage(
    receta_id: UUID,
    cantidad: int = Query(ge=1),
    db: AsyncSession = Depends(get_async_session),
    user: User = Depends(get_current_user)
):
    """Ejecuta el descuento de stock por el uso de una receta."""
    service = RecipeService(db)
    return await service.execute_recipe_consumption(receta_id, cantidad, user.id)

@router.get("/{receta_id}/availability")
async def check_recipe_stock(
    receta_id: UUID,
    cantidad: int = Query(default=1),
    db: AsyncSession = Depends(get_async_session)
):
    """Consulta si hay ingredientes suficientes para producir una cantidad."""
    service = RecipeService(db)
    return await service.check_recipe_availability(receta_id, cantidad)