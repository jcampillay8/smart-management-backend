# src/analytics/router.py
from .routers.analytics_router import router as analytics_router

# Re-exportamos para facilitar el acceso
__all__ = ["analytics_router"]