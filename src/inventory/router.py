# src/inventory/router.py
from fastapi import APIRouter
from src.inventory.routers.stock_router import router as stock_router
from src.inventory.routers.catalog_router import router as catalog_router
from src.inventory.routers.merma_router import router as merma_router 
from src.inventory.routers.history_router import router as history_router

inventory_router = APIRouter(prefix="/inventory", tags=["Inventory"])

# Rutas de Catálogo (Directas en /inventory/...)
inventory_router.include_router(catalog_router)

# Rutas de Stock (Bajo /inventory/stock/...)
inventory_router.include_router(stock_router, prefix="/stock")

# Rutas de Mermas (Bajo /inventory/mermas/...)
inventory_router.include_router(merma_router, prefix="/mermas")

inventory_router.include_router(history_router, prefix="/history")