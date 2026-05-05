# src/reports/loss_control/router.py
from typing import List, Optional
from datetime import date
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from src.database import get_async_session
from src.dependencies import get_current_user
from src.models import User
from src.reports.loss_control.service import get_loss_control_service
from src.reports.loss_control.schemas import (
    MermaByMotivo, 
    MermaByProducto, 
    ProductoAnomalia,
    LossControlResponse
)

router = APIRouter(tags=["Loss Control"])

@router.get("/by-reason", response_model=List[MermaByMotivo])
async def get_mermas_by_reason(
    fecha_inicio: Optional[date] = None,
    fecha_fin: Optional[date] = None,
    bodega_id: Optional[str] = None,
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user)
):
    """Mermas agrupadas por motivo para gráfico de torta"""
    service = get_loss_control_service(db)
    return await service.get_mermas_by_motivo(fecha_inicio, fecha_fin, bodega_id)

@router.get("/by-product", response_model=List[MermaByProducto])
async def get_mermas_by_product(
    limit: int = 10,
    fecha_inicio: Optional[date] = None,
    fecha_fin: Optional[date] = None,
    bodega_id: Optional[str] = None,
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user)
):
    """Top N productos con más merma"""
    service = get_loss_control_service(db)
    return await service.get_top_mermas_by_producto(limit, fecha_inicio, fecha_fin, bodega_id)

@router.get("/anomalies", response_model=List[ProductoAnomalia])
async def detect_anomalies(
    dias_historico: int = 90,
    dias_actual: int = 7,
    threshold_desviacion: float = 2.0,
    bodega_id: Optional[str] = None,
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user)
):
    """Productos con merma anómala basado en desviación estándar"""
    service = get_loss_control_service(db)
    return await service.detect_anomalias(dias_historico, dias_actual, threshold_desviacion, bodega_id)

@router.get("/summary", response_model=LossControlResponse)
async def get_loss_control_summary(
    fecha_inicio: Optional[date] = None,
    fecha_fin: Optional[date] = None,
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user)
):
    """Resumen completo de pérdidas y control de mermas"""
    service = get_loss_control_service(db)
    
    mermas_por_motivo = await service.get_mermas_by_motivo(fecha_inicio, fecha_fin)
    top_productos = await service.get_top_mermas_by_producto(10, fecha_inicio, fecha_fin)
    anomalias = await service.detect_anomalias()
    
    return LossControlResponse(
        mermas_por_motivo=mermas_por_motivo,
        top_productos_merma=top_productos,
        anomalias=anomalias
    )
