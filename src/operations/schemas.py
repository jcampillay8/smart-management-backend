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
    
    # Asegúrate de que estos coincidan con lo que envía el .tsx
    # El front envía: "vencimiento", "daño", "error", "otro"
    motivo_merma: Optional[str] = Field(None, pattern="^(vencimiento|daño|error|otro)$")
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
    
    # AGREGADO: Útil para que el historial en el front 
    # no muestre solo UUIDs crudos
    nombre_producto: Optional[str] = None 
    nombre_bodega: Optional[str] = None
    
    model_config = ConfigDict(from_attributes=True)

# --- Esquema para el Cálculo de Stock Actual ---
class StockActualOut(BaseModel):
    producto_id: UUID
    bodega_id: UUID
    cantidad_disponible: float
    unidad: str
    fecha_ultimo_recuento: date

class MermaStatsOut(BaseModel):
    total_perdida_7d: float
    total_perdida_30d: float
    porcentaje_salud: float # (Stock real vs Mermas)
    datos_grafico: List[dict] # Para Recharts