# src/inventory/routers/history_router.py
from fastapi import APIRouter, Depends, Query, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import delete
from typing import List, Optional
from datetime import date, timedelta

from src.database import get_async_session
from src.dependencies import get_current_user
from src.operations.schemas import RegistroStockOut
from src.inventory.services.history_service import HistoryService
from src.models import AppRole, User, RegistroStock

router = APIRouter()


def get_default_fecha_hasta():
    return date.today()


def get_default_fecha_desde():
    return date.today() - timedelta(days=90)


@router.get("", response_model=List[RegistroStockOut])
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


@router.delete("", status_code=status.HTTP_204_NO_CONTENT)
async def clear_history(
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user)
):
    """
    Elimina TODO el historial de movimientos. Solo permitido para el Propietario.
    """
    if current_user.role != AppRole.PROPIETARIO:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Solo el Propietario puede eliminar el historial"
        )
    
    await db.execute(delete(RegistroStock))
    await db.commit()
    return None