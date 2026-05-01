# src/reports/router.py
from fastapi import APIRouter
from src.reports.executive_overview.router import router as executive_router
from src.reports.loss_control.router import router as loss_router
from src.reports.operational_efficiency.router import router as efficiency_router
from src.reports.financial_vision.router import router as financial_router

router = APIRouter(prefix="/reports", tags=["Reports"])

router.include_router(executive_router, prefix="/executive-overview")
router.include_router(loss_router, prefix="/loss-control")
router.include_router(efficiency_router, prefix="/operational-efficiency")
router.include_router(financial_router, prefix="/financial-vision")
