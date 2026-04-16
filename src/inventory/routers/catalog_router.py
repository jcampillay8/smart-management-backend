# src/inventory/routers/catalog_router.py
from fastapi import APIRouter, Depends, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Optional
from uuid import UUID
from src.database import get_async_session
from src.inventory.services.catalog_service import CatalogService
from src.inventory.schemas import (
    CategoriaOut, CategoriaCreate, 
    BodegaOut, BodegaCreate, 
    ProductoOut, ProductoCreate,
    ProductoBodegaOut, ProductoBodegaCreate
)

router = APIRouter()

@router.get("/categories", response_model=List[CategoriaOut], summary="List Categories")
async def list_categories(db: AsyncSession = Depends(get_async_session)):
    """Retorna todas las categorías para poblar selectores y filtros."""
    service = CatalogService(db)
    return await service.get_categories()

@router.get("/bodegas", response_model=List[BodegaOut], summary="List Bodegas")
async def list_bodegas(db: AsyncSession = Depends(get_async_session)):
    """Retorna la lista de bodegas (ej: Central, Barra, Cocina)."""
    service = CatalogService(db)
    return await service.get_bodegas()

@router.get("/products", response_model=List[ProductoOut], summary="List Products with Filters")
async def list_products(
    categoria_id: Optional[UUID] = Query(None, description="Filtrar por ID de categoría"),
    bodega_id: Optional[UUID] = Query(None, description="Filtrar por ID de bodega"),
    search: Optional[str] = Query(None, description="Buscar por nombre de producto"),
    db: AsyncSession = Depends(get_async_session)
):
    """
    Retorna el catálogo de productos permitiendo filtrar por:
    - **Categoría**: Solo productos de una familia específica.
    - **Bodega**: Solo productos que tengan configuración en esa bodega.
    - **Búsqueda**: Coincidencia parcial en el nombre.
    """
    service = CatalogService(db)
    return await service.get_products(
        categoria_id=categoria_id,
        bodega_id=bodega_id,
        search=search
    )

@router.post("/categories", response_model=CategoriaOut, status_code=status.HTTP_201_CREATED)
async def create_category(data: CategoriaCreate, db: AsyncSession = Depends(get_async_session)):
    return await CatalogService(db).create_category(data)

# --- Bodegas ---
@router.post("/bodegas", response_model=BodegaOut, status_code=status.HTTP_201_CREATED)
async def create_bodega(data: BodegaCreate, db: AsyncSession = Depends(get_async_session)):
    return await CatalogService(db).create_bodega(data)

# --- Productos ---
@router.post("/products", response_model=ProductoOut, status_code=status.HTTP_201_CREATED)
async def create_product(data: ProductoCreate, db: AsyncSession = Depends(get_async_session)):
    return await CatalogService(db).create_product(data)

# --- Configuración (Vincular Producto a Bodega) ---
@router.post("/product-setup", response_model=ProductoBodegaOut, status_code=status.HTTP_201_CREATED)
async def setup_product_in_bodega(data: ProductoBodegaCreate, db: AsyncSession = Depends(get_async_session)):
    """Este endpoint es vital para asignar stock mínimo por bodega."""
    return await CatalogService(db).link_product_to_bodega(data)