# src/inventory/router.py
from fastapi import APIRouter
from src.inventory.routers.stock_router import router as stock_router
from src.inventory.routers.catalog_router import router as catalog_router

inventory_router = APIRouter(prefix="/inventory", tags=["Inventory"])

# Rutas de Catálogo (Directas en /inventory/...)
inventory_router.include_router(catalog_router)

# Rutas de Stock (Bajo /inventory/stock/...)
inventory_router.include_router(stock_router, prefix="/stock")