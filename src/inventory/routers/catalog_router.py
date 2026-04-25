# src/inventory/routers/catalog_router.py
from fastapi import APIRouter, Depends, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Optional
from uuid import UUID

from src.database import get_async_session
from src.dependencies import get_current_user
from src.inventory.services.catalog_service import CatalogService
from src.inventory.schemas import (
    CategoriaOut, CategoriaCreate, 
    BodegaOut, BodegaCreate, 
    ProductoOut, ProductoCreate,
    ProductoBodegaOut, ProductoBodegaCreate
)

router = APIRouter()

# ==========================================
# CATEGORÍAS
# ==========================================

@router.get("/categories", response_model=List[CategoriaOut], summary="List Categories")
async def list_categories(db: AsyncSession = Depends(get_async_session)):
    """Retorna todas las categorías para poblar selectores y filtros."""
    return await CatalogService(db).get_categories()

@router.post("/categories", response_model=CategoriaOut, status_code=status.HTTP_201_CREATED)
async def create_category(
    data: CategoriaCreate, 
    db: AsyncSession = Depends(get_async_session),
    _ = Depends(get_current_user)
):
    return await CatalogService(db).create_category(data)

@router.put("/categories/{categoria_id}", response_model=CategoriaOut)
async def update_category(
    categoria_id: UUID,
    data: CategoriaCreate,
    db: AsyncSession = Depends(get_async_session),
    _ = Depends(get_current_user)
):
    return await CatalogService(db).update_category(categoria_id, data)

@router.delete("/categories/{categoria_id}")
async def delete_category(
    categoria_id: UUID,
    db: AsyncSession = Depends(get_async_session),
    _ = Depends(get_current_user)
):
    await CatalogService(db).delete_category(categoria_id)
    return {"status": "success", "message": "Categoría eliminada"}

# ==========================================
# BODEGAS
# ==========================================

@router.get("/bodegas", response_model=List[BodegaOut], summary="List Bodegas")
async def list_bodegas(db: AsyncSession = Depends(get_async_session)):
    """Retorna la lista de bodegas."""
    return await CatalogService(db).get_bodegas()

@router.post("/bodegas", response_model=BodegaOut, status_code=status.HTTP_201_CREATED)
async def create_bodega(
    data: BodegaCreate, 
    db: AsyncSession = Depends(get_async_session),
    _ = Depends(get_current_user)
):
    return await CatalogService(db).create_bodega(data)

# ==========================================
# PRODUCTOS
# ==========================================

@router.get("/products", response_model=List[ProductoOut], summary="List Products with Filters")
async def list_products(
    categoria_id: Optional[UUID] = Query(None, description="Filtrar por ID de categoría"),
    bodega_id: Optional[UUID] = Query(None, description="Filtrar por ID de bodega"),
    search: Optional[str] = Query(None, description="Buscar por nombre de producto"),
    db: AsyncSession = Depends(get_async_session)
):
    """Retorna el catálogo filtrado."""
    return await CatalogService(db).get_products(
        categoria_id=categoria_id,
        bodega_id=bodega_id,
        search=search
    )

@router.post("/products", response_model=ProductoOut, status_code=status.HTTP_201_CREATED)
async def create_product(
    data: ProductoCreate, 
    db: AsyncSession = Depends(get_async_session),
    _ = Depends(get_current_user)
):
    """Crea producto y sus configuraciones de bodega en una sola transacción."""
    return await CatalogService(db).create_product(data)

@router.put("/products/{producto_id}", response_model=ProductoOut)
async def update_product(
    producto_id: UUID,
    data: ProductoCreate,
    db: AsyncSession = Depends(get_async_session),
    _ = Depends(get_current_user)
):
    """Actualiza producto y sobrescribe configuraciones de bodega."""
    return await CatalogService(db).update_product(producto_id, data)

@router.delete("/products/{producto_id}")
async def delete_product(
    producto_id: UUID,
    db: AsyncSession = Depends(get_async_session),
    _ = Depends(get_current_user)
):
    await CatalogService(db).delete_product(producto_id)
    return {"status": "success", "message": "Producto eliminado"}

# ==========================================
# CONFIGURACIÓN ESPECÍFICA (Vincular Producto a Bodega)
# ==========================================

@router.post("/product-setup", response_model=ProductoBodegaOut, status_code=status.HTTP_201_CREATED)
async def setup_product_in_bodega(
    data: ProductoBodegaCreate, 
    db: AsyncSession = Depends(get_async_session),
    _ = Depends(get_current_user)
):
    """Asigna o actualiza stock mínimo por bodega."""
    return await CatalogService(db).link_product_to_bodega(data)

@router.get("/product-setup", response_model=List[ProductoBodegaOut])
async def get_product_setup(
    bodega_id: Optional[UUID] = Query(None, description="Filtrar por bodega"),
    db: AsyncSession = Depends(get_async_session)
):
    """Obtiene la configuración de productos en bodega(s)."""
    return await CatalogService(db).get_product_setup(bodega_id)