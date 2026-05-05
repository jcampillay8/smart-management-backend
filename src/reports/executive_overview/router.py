# src/reports/executive_overview/router.py
from typing import List, Optional, Dict
from datetime import date
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from src.database import get_async_session
from src.dependencies import get_current_user
from src.models import User
from src.reports.executive_overview.service import get_executive_overview_service
from src.reports.executive_overview.schemas import ExecutiveOverviewResponse, InsightResponse, ProductMerma, ProductoStock

router = APIRouter(tags=["Executive Overview"])

@router.get("", response_model=ExecutiveOverviewResponse)
async def get_executive_overview(
    bodega_id: Optional[str] = None,
    fecha_inicio: Optional[date] = None,
    fecha_fin: Optional[date] = None,
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user)
):
    """Endpoint principal: Resumen General (4 bloques)"""
    service = get_executive_overview_service(db)
    return await service.get_resumen_general(bodega_id, fecha_inicio, fecha_fin)

@router.get("/insights", response_model=List[InsightResponse])
async def get_insights(
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user)
):
    """Genera insights prescriptivos (Sobrestock, Fuga, Oportunidad)"""
    from src.reports.executive_overview.ai_insights import generate_insights
    return await generate_insights(db)

@router.get("/merma/by-product", response_model=List[ProductMerma])
async def get_merma_by_product(
    limit: int = 5,
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user)
):
    """Top N productos con merma"""
    service = get_executive_overview_service(db)
    return await service.get_top_mermas_productos(limit)

@router.get("/merma/by-motivo", response_model=List[Dict])
async def get_merma_by_motivo(
    fecha_inicio: Optional[date] = None,
    fecha_fin: Optional[date] = None,
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user)
):
    """Agregación de mermas por motivo para gráfico de torta"""
    service = get_executive_overview_service(db)
    return await service.get_mermas_by_motivo(fecha_inicio, fecha_fin)

@router.get("/stock/low", response_model=List[ProductoStock])
async def get_low_stock(
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user)
):
    """Productos por debajo de stock mínimo"""
    service = get_executive_overview_service(db)
    return await service.get_productos_bajo_stock()
