# src/reports/operational_efficiency/router.py
from typing import List, Optional
from datetime import date
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from src.database import get_async_session
from src.dependencies import get_current_user
from src.models import User
from src.reports.operational_efficiency.service import get_operational_efficiency_service
from src.reports.operational_efficiency.schemas import (
    RotacionProducto,
    TransferenciaReporte,
    PuntoPedidoAlerta,
    OperationalEfficiencyResponse
)

router = APIRouter(tags=["Operational Efficiency"])

@router.get("/rotation", response_model=List[RotacionProducto])
async def get_rotation(
    fecha_inicio: Optional[date] = None,
    fecha_fin: Optional[date] = None,
    bodega_id: Optional[str] = None,
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user)
):
    """Rotación de inventario por producto/bodega"""
    service = get_operational_efficiency_service(db)
    return await service.get_rotacion_inventario(fecha_inicio, fecha_fin, bodega_id)

@router.get("/transfers", response_model=List[TransferenciaReporte])
async def get_transfers(
    fecha_inicio: Optional[date] = None,
    fecha_fin: Optional[date] = None,
    bodega_id: Optional[str] = None,
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user)
):
    """Reporte de transferencias inter-bodegas"""
    service = get_operational_efficiency_service(db)
    return await service.get_transferencias_reporte(fecha_inicio, fecha_fin, bodega_id)

@router.get("/reorder-points", response_model=List[PuntoPedidoAlerta])
async def get_reorder_points(
    margen_cercania: float = 0.2,
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user)
):
    """Productos cerca del punto de pedido (dentro del margen de cercanía)"""
    service = get_operational_efficiency_service(db)
    return await service.get_alertas_punto_pedido(margen_cercania)

@router.get("/summary", response_model=OperationalEfficiencyResponse)
async def get_operational_summary(
    fecha_inicio: Optional[date] = None,
    fecha_fin: Optional[date] = None,
    bodega_id: Optional[str] = None,
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user)
):
    """Resumen completo de eficiencia operacional"""
    service = get_operational_efficiency_service(db)
    
    rotacion = await service.get_rotacion_inventario(fecha_inicio, fecha_fin, bodega_id)
    transferencias = await service.get_transferencias_reporte(fecha_inicio, fecha_fin, bodega_id)
    alertas = await service.get_alertas_punto_pedido()
    rotacion_promedio = await service.get_rotacion_promedio_general()
    
    return OperationalEfficiencyResponse(
        rotacion_productos=rotacion,
        transferencias_recientes=transferencias,
        alertas_punto_pedido=alertas,
        rotacion_promedio_general=round(rotacion_promedio, 2)
    )
