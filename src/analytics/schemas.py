# src/analytics/schemas.py
from pydantic import BaseModel, ConfigDict, Field
from typing import List, Optional
from uuid import UUID
from datetime import date

class StockAlert(BaseModel):
    producto_id: UUID
    nombre: str
    bodega_id: UUID
    bodega_nombre: str
    cantidad_actual: float
    stock_minimo: float
    unidad: str
    tipo_alerta: str  # "critical" (sin stock), "warning" (bajo mínimo)

class ExpiryAlert(BaseModel):
    producto_id: UUID
    nombre: str
    bodega_id: UUID
    bodega_nombre: str
    cantidad: float
    fecha_vencimiento: date
    dias_para_vencer: int
    tipo_alerta: str  # "critical" (vencido), "warning" (próximo)

# --- NUEVO: Alertas de Proyección para Eventos ---
class EventProjectionAlert(BaseModel):
    evento_id: UUID
    evento_nombre: str
    fecha_evento: date
    producto_nombre: str
    bodega_nombre: str
    stock_proyectado: float  # Lo que quedará después del evento
    cantidad_necesaria: float # Lo que pide el evento
    insuficiente: bool
    sugerencia_alternativa: Optional[str] = None

class DashboardSummaryOut(BaseModel):
    alertas_stock: List[StockAlert] = []
    alertas_vencimiento: List[ExpiryAlert] = []
    alertas_eventos: List[EventProjectionAlert] = [] # Agregado para Proyeccion.tsx
    
    model_config = ConfigDict(from_attributes=True)