# src/reports/financial_vision/router.py
from typing import List, Optional
from datetime import date
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from src.database import get_async_session
from src.dependencies import get_current_user
from src.models import User
from src.reports.financial_vision.service import get_financial_vision_service
from src.reports.financial_vision.schemas import (
    PlatoMenu,
    BreakEvenResult,
    PrimeCostResult,
    VariacionPrecio,
    FinancialVisionResponse
)

router = APIRouter(tags=["Financial Vision"])

@router.get("/menu-engineering", response_model=List[PlatoMenu])
async def get_menu_engineering(
    fecha_inicio: Optional[date] = None,
    fecha_fin: Optional[date] = None,
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user)
):
    """Matriz de platos (Estrellas, Perros, etc.)"""
    service = get_financial_vision_service(db)
    return await service.get_matriz_menu(fecha_inicio, fecha_fin)

@router.get("/breakeven", response_model=BreakEvenResult)
async def get_breakeven(
    fecha_inicio: Optional[date] = None,
    fecha_fin: Optional[date] = None,
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user)
):
    """Punto de equilibrio actual y proyectado"""
    service = get_financial_vision_service(db)
    return await service.get_break_even(fecha_inicio, fecha_fin)

@router.get("/prime-cost", response_model=PrimeCostResult)
async def get_prime_cost(
    fecha_inicio: Optional[date] = None,
    fecha_fin: Optional[date] = None,
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user)
):
    """Prime cost del período"""
    service = get_financial_vision_service(db)
    return await service.get_prime_cost(fecha_inicio, fecha_fin)

@router.get("/price-variation", response_model=List[VariacionPrecio])
async def get_price_variation(
    dias_atras: int = 90,
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user)
):
    """Inflación interna de insumos"""
    service = get_financial_vision_service(db)
    return await service.get_variacion_precios(dias_atras)

@router.get("/summary", response_model=FinancialVisionResponse)
async def get_financial_summary(
    fecha_inicio: Optional[date] = None,
    fecha_fin: Optional[date] = None,
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user)
):
    """Resumen completo de visión financiera"""
    service = get_financial_vision_service(db)
    
    matriz = await service.get_matriz_menu(fecha_inicio, fecha_fin)
    break_even = await service.get_break_even(fecha_inicio, fecha_fin)
    prime_cost = await service.get_prime_cost(fecha_inicio, fecha_fin)
    variacion = await service.get_variacion_precios()
    
    return FinancialVisionResponse(
        matriz_menu=matriz,
        break_even=break_even,
        prime_cost=prime_cost,
        variacion_precios=variacion
    )
