# src/inventory/routers/stock_router.py
from fastapi import APIRouter, Depends, Query, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from uuid import UUID
from datetime import date
from typing import List

# Importaciones ajustadas a tu estructura
from src.database import get_async_session  # Asegúrate de que este sea el nombre correcto
from src.dependencies import get_current_user
from src.models import User, RegistroStock
from src.inventory.services.stock_service import StockService
from src.inventory.services.history_service import HistoryService
# Importamos el nuevo Schema Bulk
from src.inventory.schemas import RegistroStockCreate, RegistroStockOut, StockBulkCreate
from src.authentication.dependencies import get_valid_record_for_modification

router = APIRouter()

@router.post("/bulk-movements", status_code=status.HTTP_201_CREATED)
async def create_bulk_movements(
    data: StockBulkCreate, 
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user)
):
    """
    Endpoint principal para StockRegistro.tsx. 
    Recibe la lista de movimientos (conteo, transferencia, entrada, etc.)
    """
    service = StockService(db)
    # Procesamos la lista de movimientos de forma atómica
    await service.create_movements(data.movements, user_id=current_user.id)
    return {"message": "Movimientos registrados exitosamente"}

@router.post("/consume", response_model=RegistroStockOut)
async def create_manual_consumption(
    data: RegistroStockCreate,
    db: AsyncSession = Depends(get_async_session),
    user: User = Depends(get_current_user)
):
    """Usado para consumos rápidos o mermas individuales."""
    service = StockService(db)
    return await service.register_consumption(data, user.id)

@router.get("/log", response_model=List[RegistroStockOut])
async def get_inventory_log(
    log_date: date = Query(default_factory=date.today),
    bodega_id: str = Query(default="all"),
    db: AsyncSession = Depends(get_async_session)
):
    """Consulta el historial de movimientos de un día."""
    service = HistoryService(db)
    # Convertimos 'all' a None para el servicio
    b_id = None if bodega_id == "all" else UUID(bodega_id)
    return await service.get_consumption_log(log_date, b_id)

@router.delete("/consume/{record_id}")
async def remove_consumption(
    record: RegistroStock = Depends(get_valid_record_for_modification),
    db: AsyncSession = Depends(get_async_session)
):
    """
    Elimina un registro y REVIERTE el stock en la bodega.
    """
    service = StockService(db)
    
    # 1. Revertimos el stock antes de borrar el registro
    # (Si era un consumo de 10, sumamos 10 a la bodega)
    try:
        await service.revert_stock_movement(record)
        
        # 2. Borramos el registro del historial
        await db.delete(record)
        await db.commit()
        return {"detail": "Registro eliminado y stock restaurado"}
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=500, detail=f"No se pudo revertir el stock: {str(e)}")