# src/analytics/routers/analytics_router.py
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Dict

from src.database import get_async_session
from ..schemas import DashboardSummaryOut, EventProjectionAlert
from ..services.stats_service import StatsService
from ..services.report_service import ReportService
from ..services.projection_service import ProjectionService

router = APIRouter(prefix="/analytics", tags=["Analytics"])

@router.get("/dashboard-summary", response_model=DashboardSummaryOut)
async def get_dashboard_summary(db: AsyncSession = Depends(get_async_session)):
    """
    Endpoint principal para Analiticas.tsx (Novedades).
    Consolida alertas de stock, vencimientos y proyecciones de eventos.
    """
    stats_service = StatsService(db)
    projection_service = ProjectionService(db)
    
    # Obtenemos las alertas base (stock y vencimiento)
    summary = await stats_service.get_dashboard_summary()
    
    # Enriquecemos con las proyecciones de eventos futuros
    summary.alertas_eventos = await projection_service.get_event_projections()
    
    return summary

@router.get("/inventory-valuation")
async def get_inventory_valuation(db: AsyncSession = Depends(get_async_session)):
    """
    Obtiene el valor total del inventario actual para Informes.tsx.
    """
    report_service = ReportService(db)
    return await report_service.get_inventory_valuation()

@router.get("/merma-stats")
async def get_merma_stats(
    days: int = Query(30, ge=1, le=365), 
    db: AsyncSession = Depends(get_async_session)
):
    """
    Estadísticas de pérdida por merma o ajustes negativos.
    """
    report_service = ReportService(db)
    return await report_service.get_merma_stats(days=days)

@router.get("/projections", response_model=List[EventProjectionAlert])
async def get_detailed_projections(db: AsyncSession = Depends(get_async_session)):
    """
    Endpoint específico para Proyeccion.tsx.
    """
    projection_service = ProjectionService(db)
    return await projection_service.get_event_projections()