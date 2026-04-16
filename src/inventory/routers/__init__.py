# src/inventory/routers/__init__.py
from .stock_router import router as stock_router
from .catalog_router import router as catalog_router # Si no estaba, agrégalo
from .merma_router import router as merma_router    # <--- Agregar esta línea
from .history_router import router as history_router