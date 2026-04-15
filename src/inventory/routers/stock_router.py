# src/inventory/routers/stock_router.py
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from uuid import UUID
from datetime import date
from typing import List

from src.database import get_async_session
from src.dependencies import get_current_user
from src.models import User, RegistroStock
from src.inventory.services.stock_service import StockService
from src.inventory.services.history_service import HistoryService
from src.inventory.schemas import RegistroStockCreate, RegistroStockOut
from src.authentication.dependencies import get_valid_record_for_modification

router = APIRouter()

@router.post("/consume", response_model=RegistroStockOut)
async def create_manual_consumption(
    data: RegistroStockCreate,
    db: AsyncSession = Depends(get_async_session),
    user: User = Depends(get_current_user)
):
    service = StockService(db)
    return await service.register_consumption(data, user.id)

@router.get("/log", response_model=List[RegistroStockOut])
async def get_inventory_log(
    log_date: date = Query(default_factory=date.today),
    bodega_id: str = Query(default="all"),
    db: AsyncSession = Depends(get_async_session)
):
    service = HistoryService(db)
    return await service.get_consumption_log(log_date, bodega_id)

@router.delete("/consume/{record_id}")
async def remove_consumption(
    # La dependencia asíncrona que creamos valida permisos y existencia
    record: RegistroStock = Depends(get_valid_record_for_modification),
    db: AsyncSession = Depends(get_async_session)
):
    # Lógica de restauración de stock antes de borrar
    service = StockService(db)
    # Podrías mover esta lógica al service, pero aquí la simplificamos:
    # ... (lógica de revertir stock) ...
    await db.delete(record)
    await db.commit()
    return {"detail": "Registro eliminado exitosamente"}