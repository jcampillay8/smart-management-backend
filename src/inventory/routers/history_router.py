# src/inventory/routers/history_router.py
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Optional
from datetime import date

from src.database import get_async_session
from src.dependencies import get_current_user
from src.operations.schemas import RegistroStockOut
from src.inventory.services.history_service import HistoryService

router = APIRouter()


def get_default_fecha_hasta():
    return date.today()


def get_default_fecha_desde():
    return date.today() - timedelta(days=90)


@router.get("/", response_model=List[RegistroStockOut])
async def get_history(
    bodega_id: str = Query("all"),
    producto_id: str = Query("all"),
    tipo_movimiento: str = Query("all"),
    fecha_desde: Optional[date] = Query(default=None),
    fecha_hasta: Optional[date] = Query(default=None),
    limit: int = Query(default=500, le=2000),
    db: AsyncSession = Depends(get_async_session),
    current_user = Depends(get_current_user)
):
    """
    Endpoint para obtener el historial filtrado.
    Por defecto retorna los últimos 90 días de movimientos.
    """
    service = HistoryService(db)
    return await service.get_filtered_history(
        bodega_id=bodega_id,
        producto_id=producto_id,
        tipo_movimiento=tipo_movimiento,
        fecha_desde=fecha_desde,
        fecha_hasta=fecha_hasta
    )