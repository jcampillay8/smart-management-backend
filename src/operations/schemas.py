# src/operations/schemas.py
from pydantic import BaseModel, ConfigDict, Field
from uuid import UUID
from datetime import datetime, date
from typing import Optional, List
from .models import TipoMovimiento

# --- Sub-esquemas para Eventos ---
class EventoProductoSchema(BaseModel):
    producto_id: UUID
    bodega_id: UUID
    cantidad: float

class EventoRecetaSchema(BaseModel):
    receta_id: UUID
    cantidad: int

# --- Eventos ---
class EventoBase(BaseModel):
    nombre: str = Field(..., min_length=3, max_length=200)
    fecha: date
    valor_publico: Optional[float] = Field(None, ge=0)

class EventoCreate(EventoBase):
    # Aquí es donde el front envía los datos brutos
    items: List[EventoProductoSchema] = []
    recetas: List[EventoRecetaSchema] = []

class EventoOut(EventoBase):
    id: UUID
    ejecutado: bool
    cancelado: bool
    usuario_id: int
    created_at: datetime
    # Relación cargada de productos
    productos: List[EventoProductoSchema] = []
    
    model_config = ConfigDict(from_attributes=True)

# --- Registros de Stock (Movimientos) ---
class RegistroStockBase(BaseModel):
    producto_id: UUID
    bodega_id: UUID
    cantidad: float = Field(..., description="Cantidad del movimiento")
    tipo_movimiento: TipoMovimiento
    
    fecha_recuento: date = Field(default_factory=date.today)
    fecha_vencimiento: Optional[date] = None
    
    motivo_merma: Optional[str] = None
    descripcion_merma: Optional[str] = None
    evento_id: Optional[UUID] = None

class RegistroStockCreate(RegistroStockBase):
    """Esquema para crear un movimiento. 
    El usuario_id se obtendrá del token en el service/router."""
    pass

class RegistroStockOut(RegistroStockBase):
    id: UUID
    usuario_id: int
    created_at: datetime
    
    # Opcional: Podrías incluir info básica del producto para el historial
    # producto_nombre: str (Se puede manejar con un alias o en el service)
    
    model_config = ConfigDict(from_attributes=True)

# --- Esquema para el Cálculo de Stock Actual ---
class StockActualOut(BaseModel):
    producto_id: UUID
    bodega_id: UUID
    cantidad_disponible: float
    unidad: str
    fecha_ultimo_recuento: date