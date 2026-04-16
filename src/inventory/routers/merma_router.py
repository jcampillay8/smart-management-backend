# src/inventory/routers/merma_router.py
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List
from uuid import UUID

from src.database import get_async_session
from src.dependencies import get_current_user  # Ajusta según tu ruta de auth
from src.models import User
from src.operations.schemas import (
    RegistroStockCreate, 
    RegistroStockOut, 
    MermaStatsOut # El que definimos para los gráficos
)
from src.inventory.services.merma_service import MermaService

router = APIRouter()

@router.post("/", response_model=RegistroStockOut, status_code=201)
async def registrar_nueva_merma(
    payload: RegistroStockCreate,
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user)
):
    """
    Registra una pérdida de stock (merma) especificando el motivo y la descripción.
    """
    service = MermaService(db)
    return await service.registrar_merma(payload, current_user.id)

@router.get("/historial", response_model=List[RegistroStockOut])
async def obtener_historial_mermas(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user)
):
    """
    Obtiene el listado de movimientos de tipo MERMA para la tabla del frontend.
    """
    service = MermaService(db)
    return await service.obtener_historial_mermas(skip=skip, limit=limit)

@router.get("/stats", response_model=List[dict])
async def obtener_estadisticas_mermas(
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user)
):
    """
    Retorna datos agregados para los gráficos de Recharts (ej. merma por día).
    """
    service = MermaService(db)
    return await service.obtener_stats_mermas()