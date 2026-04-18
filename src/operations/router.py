# src/operations/router.py
from fastapi import APIRouter
from src.operations.routers.event_router import router as event_router
from src.operations.routers.recipe_router import router as recipe_router

operations_router = APIRouter(prefix="/operations", tags=["Operations"])

# Rutas de Eventos (viven en /operations/events/...)
operations_router.include_router(event_router, prefix="/events")

# Rutas de Recetas (viven en /operations/recipes/...)
operations_router.include_router(recipe_router, prefix="/recipes")