# src/inventory/router.py
from fastapi import APIRouter
from src.inventory.routers.stock_router import router as stock_router

inventory_router = APIRouter(prefix="/inventory", tags=["Inventory"])

inventory_router.include_router(stock_router)