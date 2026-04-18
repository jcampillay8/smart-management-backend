# src/sales/router.py
from fastapi import APIRouter
from src.sales.routers.sales_router import router as sales_main_router

sales_router = APIRouter(prefix="/sales", tags=["Sales & Recipes"])

# Rutas principales de recetas y ventas (viven en /sales/...)
sales_router.include_router(sales_main_router)