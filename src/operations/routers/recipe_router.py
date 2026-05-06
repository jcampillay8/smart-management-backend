# src/operations/routers/recipe_router.py
from fastapi import APIRouter, Depends, Query, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from uuid import UUID
from typing import List

from src.database import get_async_session
from src.dependencies import get_current_user
from src.models import User # Ajusta según tu ruta de User
from src.operations.services.recipe_service import RecipeService
from src.operations.schemas import RecetaCreate, RecetaOut, CategoriaRecetaCreate, CategoriaRecetaOut # Asegúrate de tener estos schemas

router = APIRouter()

# =========================================================================
# ENDPOINTS ADMINISTRATIVOS (Para Gestion.tsx)
# =========================================================================

@router.get("", response_model=List[RecetaOut])
async def list_recipes(
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user)
):
    """Obtiene la lista de todas las recetas para la tabla de Gestión."""
    service = RecipeService(db)
    return await service.get_all_recipes()

@router.post("", response_model=RecetaOut, status_code=status.HTTP_201_CREATED)
async def create_new_recipe(
    data: RecetaCreate,
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user)
):
    """Crea una nueva receta con sus ingredientes."""
    service = RecipeService(db)
    return await service.create_recipe(data)

# =========================================================================
# ENDPOINTS DE CATEGORÍAS DE RECETAS
# =========================================================================

@router.get("/categories", response_model=List[CategoriaRecetaOut])
async def list_recipe_categories(
    db: AsyncSession = Depends(get_async_session),
    _ = Depends(get_current_user)
):
    return await RecipeService(db).get_recipe_categories()

@router.post("/categories", response_model=CategoriaRecetaOut)
async def create_recipe_category(
    data: CategoriaRecetaCreate,
    db: AsyncSession = Depends(get_async_session),
    _ = Depends(get_current_user)
):
    return await RecipeService(db).create_recipe_category(data)

@router.put("/categories/{id}", response_model=CategoriaRecetaOut)
async def update_recipe_category(
    id: UUID,
    data: CategoriaRecetaCreate,
    db: AsyncSession = Depends(get_async_session),
    _ = Depends(get_current_user)
):
    return await RecipeService(db).update_recipe_category(id, data)

@router.delete("/categories/{id}")
async def delete_recipe_category(
    id: UUID,
    db: AsyncSession = Depends(get_async_session),
    _ = Depends(get_current_user)
):
    return await RecipeService(db).delete_recipe_category(id)


@router.get("/ingredients")
async def list_all_recipe_ingredients(
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user)
):
    """Obtiene todos los ingredientes de todas las recetas."""
    service = RecipeService(db)
    return await service.get_all_ingredients()

# =========================================================================
# ENDPOINTS OPERATIVOS Y CRUD (Consumo y Disponibilidad)
# =========================================================================

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

@router.post("/{receta_id}/consume")
async def register_recipe_usage(
    receta_id: UUID,
    area_id: UUID,
    cantidad: int = Query(ge=1),
    db: AsyncSession = Depends(get_async_session),
    user: User = Depends(get_current_user)
):
    """Ejecuta el descuento de stock por el uso de una receta en un área específica."""
    service = RecipeService(db)
    return await service.execute_recipe_consumption(receta_id, cantidad, user.id, area_id)

@router.get("/{receta_id}/availability")
async def check_recipe_stock(
    receta_id: UUID,
    area_id: UUID,
    cantidad: int = Query(default=1),
    db: AsyncSession = Depends(get_async_session)
):
    """Consulta si hay ingredientes suficientes en la bodega de consumo del área."""
    service = RecipeService(db)
    return await service.check_recipe_availability(receta_id, cantidad, area_id)