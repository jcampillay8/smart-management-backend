# src/operations/router.py
from fastapi import APIRouter
from src.operations.routers.recipe_router import router as recipe_router

operations_router = APIRouter(prefix="/operations", tags=["Operations"])

operations_router.include_router(recipe_router, prefix="/recipes")