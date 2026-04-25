# src/inventory/routers/stock_router.py
from fastapi import APIRouter, Depends, Query, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from uuid import UUID
from datetime import date
from typing import List

from src.database import get_async_session
from src.dependencies import get_current_user
from src.models import User, RegistroStock
from src.inventory.services.stock_service import StockService
from src.inventory.services.history_service import HistoryService
from src.inventory.services.inventory_engine_service import InventoryEngineService
from src.inventory.schemas import RegistroStockCreate, RegistroStockOut, StockBulkCreate, TransferenciaStockCreate
from src.authentication.dependencies import get_valid_record_for_modification

router = APIRouter()

@router.get("/status")
async def get_inventory_status(
    bodega_id: str = Query(default="all"),
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user)
):
    """
    Retorna el estado actual del inventario (Snapshot).
    Calculado en tiempo real con Polars. Sustituye la lógica pesada del frontend.
    """
    engine = InventoryEngineService(db)
    return await engine.get_stock_snapshot(bodega_id)

@router.post("/bulk-movements", status_code=status.HTTP_201_CREATED)
async def create_bulk_movements(
    data: StockBulkCreate, 
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user)
):
    """Registra múltiples movimientos de forma atómica."""
    service = StockService(db)
    await service.create_movements(data.movements, user_id=current_user.id)
    return {"message": "Movimientos registrados exitosamente"}

@router.post("/consume", response_model=RegistroStockOut)
async def create_manual_consumption(
    data: RegistroStockCreate,
    db: AsyncSession = Depends(get_async_session),
    user: User = Depends(get_current_user)
):
    """Consumos rápidos o mermas individuales."""
    service = StockService(db)
    return await service.register_consumption(data, user.id)

@router.get("/log", response_model=List[RegistroStockOut])
async def get_inventory_log(
    log_date: date = Query(default_factory=date.today),
    bodega_id: str = Query(default="all"),
    db: AsyncSession = Depends(get_async_session)
):
    """Historial de movimientos de un día específico."""
    service = HistoryService(db)
    b_id = None if bodega_id == "all" else UUID(bodega_id)
    return await service.get_consumption_log(log_date, b_id)

@router.delete("/consume/{record_id}")
async def remove_consumption(
    record: RegistroStock = Depends(get_valid_record_for_modification),
    db: AsyncSession = Depends(get_async_session)
):
    """Elimina un registro y revierte el stock físicamente."""
    service = StockService(db)
    try:
        await service.revert_stock_movement(record)
        await db.delete(record)
        await db.commit()
        return {"detail": "Registro eliminado y stock restaurado"}
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=500, detail=f"Error al revertir stock: {str(e)}")

@router.post("/transfer", status_code=status.HTTP_201_CREATED)
async def transfer_stock(
    data: TransferenciaStockCreate,
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user)
):
    """Transfiere stock de una bodega a otra."""
    service = StockService(db)
    return await service.transfer_stock(
        producto_id=data.producto_id,
        bodega_origen_id=data.bodega_origen_id,
        bodega_destino_id=data.bodega_destino_id,
        cantidad=data.cantidad,
        user_id=current_user.id,
        fecha_recuento=data.fecha_recuento
    )