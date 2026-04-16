# src/inventory/routers/history_router.py
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Optional
from datetime import date

from src.database import get_async_session
from src.authentication.dependencies import get_current_user
from src.operations.schemas import RegistroStockOut
from src.inventory.services.history_service import HistoryService

router = APIRouter()

@router.get("/", response_model=List[RegistroStockOut])
async def get_history(
    bodega_id: str = Query("all"),
    producto_id: str = Query("all"),
    tipo_movimiento: str = Query("all"),
    fecha_desde: Optional[date] = None,
    fecha_hasta: Optional[date] = None,
    db: AsyncSession = Depends(get_async_session),
    current_user = Depends(get_current_user)
):
    """
    Endpoint para obtener el historial filtrado.
    Sustituye la consulta directa a Supabase en Historial.tsx.
    """
    service = HistoryService(db)
    return await service.get_filtered_history(
        bodega_id=bodega_id,
        producto_id=producto_id,
        tipo_movimiento=tipo_movimiento,
        fecha_desde=fecha_desde,
        fecha_hasta=fecha_hasta
    )