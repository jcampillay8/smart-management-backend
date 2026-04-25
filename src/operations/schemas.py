# src/operations/schemas.py
from pydantic import BaseModel, ConfigDict, Field
from uuid import UUID
from datetime import datetime, date
from typing import Optional, List

# --- RECETAS (Ajuste principal para Gestion.tsx) ---

class IngredienteRecetaBase(BaseModel):
    producto_id: UUID
    bodega_id: UUID
    cantidad: float = Field(..., ge=0.001)

class IngredienteRecetaOut(IngredienteRecetaBase):
    # Esto permite que el front muestre el nombre del ingrediente en la lista
    nombre_producto: Optional[str] = None 
    unidad: Optional[str] = None
    model_config = ConfigDict(from_attributes=True)

class RecetaBase(BaseModel):
    nombre: str = Field(..., min_length=1, max_length=200)
    precio: float = Field(..., ge=0)
    iva_incluido: bool = Field(default=True)
    iva_porcentaje: float = Field(default=19.0, ge=0)

class RecetaCreate(RecetaBase):
    # Lista de ingredientes que se envía desde el Dialog de Recetas
    ingredientes: List[IngredienteRecetaBase]

class RecetaOut(RecetaBase):
    id: UUID
    ingredientes: List[IngredienteRecetaOut] = []
    created_at: Optional[datetime] = None
    model_config = ConfigDict(from_attributes=True)

# --- EVENTOS ---

class EventoProductoSchema(BaseModel):
    producto_id: UUID
    bodega_id: UUID
    cantidad: float

class EventoRecetaSchema(BaseModel):
    receta_id: UUID
    cantidad: int

class EventoBase(BaseModel):
    nombre: str = Field(..., min_length=3, max_length=200)
    fecha: date
    valor_publico: Optional[float] = Field(None, ge=0)

class EventoCreate(EventoBase):
    items: List[EventoProductoSchema] = []
    recetas: List[EventoRecetaSchema] = []

class EventoOut(EventoBase):
    id: UUID
    ejecutado: bool
    cancelado: bool
    usuario_id: int
    created_at: datetime
    productos: List[EventoProductoSchema] = []
    model_config = ConfigDict(from_attributes=True)

# --- REGISTROS DE STOCK (Movimientos) ---

class RegistroStockBase(BaseModel):
    producto_id: UUID
    bodega_id: UUID
    cantidad: float = Field(..., description="Cantidad del movimiento")
    # Cambiado a str si prefieres validación simple o mantén TipoMovimiento si es Enum
    tipo_movimiento: str 
    fecha_recuento: date = Field(default_factory=date.today)
    fecha_vencimiento: Optional[date] = None
    motivo_merma: Optional[str] = Field(None, pattern="^(vencimiento|daño|error|otro)$")
    descripcion_merma: Optional[str] = None
    evento_id: Optional[UUID] = None

class RegistroStockCreate(RegistroStockBase):
    pass

class RegistroStockOut(RegistroStockBase):
    id: UUID
    usuario_id: int
    created_at: datetime
    nombre_producto: Optional[str] = None 
    nombre_bodega: Optional[str] = None
    model_config = ConfigDict(from_attributes=True)

# --- ESTADÍSTICAS Y OTROS ---

class StockActualOut(BaseModel):
    producto_id: UUID
    bodega_id: UUID
    cantidad_disponible: float
    unidad: str
    fecha_ultimo_recuento: date

class MermaStatsOut(BaseModel):
    total_perdida_7d: float
    total_perdida_30d: float
    porcentaje_salud: float 
    datos_grafico: List[dict]
# --- CONTEOS DE INVENTARIO ---

class ConteoItemBase(BaseModel):
    producto_id: UUID
    cantidad_contada: float
    fecha_vencimiento: Optional[date] = None

class ConteoItemCreate(ConteoItemBase):
    pass

class ConteoItem(ConteoItemBase):
    id: UUID
    conteo_id: UUID
    model_config = ConfigDict(from_attributes=True)

class ConteoInventarioBase(BaseModel):
    bodega_id: UUID
    nombre: Optional[str] = Field(default=None, max_length=200)
    estado: str = "en_progreso"

class ConteoInventarioCreate(ConteoInventarioBase):
    pass

class ConteoInventarioUpdate(BaseModel):
    nombre: Optional[str] = None
    estado: Optional[str] = None
    completed_at: Optional[datetime] = None

class ConteoInventario(ConteoInventarioBase):
    id: UUID
    usuario_id: int
    created_at: datetime
    completed_at: Optional[datetime] = None
    items: List[ConteoItem] = []
    model_config = ConfigDict(from_attributes=True)
