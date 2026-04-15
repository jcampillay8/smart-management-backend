# src/inventory/schemas.py
from datetime import date, datetime
from pydantic import BaseModel, ConfigDict, Field
from uuid import UUID
from typing import Optional, List

# ==========================================
# CATEGORÍAS
# ==========================================
class CategoriaBase(BaseModel):
    nombre: str = Field(..., min_length=1, max_length=100)

class CategoriaCreate(CategoriaBase):
    pass

class CategoriaOut(CategoriaBase):
    id: UUID
    # created_at: datetime # Opcional según si tu BaseModel lo incluye
    model_config = ConfigDict(from_attributes=True)

# ==========================================
# BODEGAS
# ==========================================
class BodegaBase(BaseModel):
    nombre: str = Field(..., min_length=1, max_length=100)

class BodegaCreate(BodegaBase):
    pass

class BodegaOut(BodegaBase):
    id: UUID
    model_config = ConfigDict(from_attributes=True)

# ==========================================
# CONFIGURACIÓN PRODUCTO-BODEGA (Mínimos y Actual)
# ==========================================
class ProductoBodegaBase(BaseModel):
    bodega_id: UUID
    stock_minimo: float = Field(default=0.0, ge=0)

class ProductoBodegaCreate(ProductoBodegaBase):
    producto_id: UUID

class ProductoBodegaOut(ProductoBodegaBase):
    id: UUID
    stock_actual: float = 0.0
    model_config = ConfigDict(from_attributes=True)

# ==========================================
# PRODUCTOS
# ==========================================
class ProductoBase(BaseModel):
    nombre: str = Field(..., min_length=1, max_length=200)
    unidad: str = Field(default="unidad", description="Ej: Kg, Litro, Unidad")
    costo_unitario: float = Field(default=0.0, ge=0)
    categoria_id: UUID

class ProductoCreate(ProductoBase):
    # Permite opcionalmente configurar el stock en bodegas al crear el producto
    bodegas_config: Optional[List[ProductoBodegaBase]] = []

class ProductoOut(ProductoBase):
    id: UUID
    # Relaciones que el frontend necesita para alertas y filtros
    bodegas_config: List[ProductoBodegaOut] = []
    categoria: Optional[CategoriaOut] = None
    
    model_config = ConfigDict(from_attributes=True)

# ==========================================
# REGISTRO DE STOCK (MOVIMIENTOS)
# ==========================================
class RegistroStockCreate(BaseModel):
    producto_id: UUID
    bodega_id: UUID
    cantidad: float  
    # Regex para validar los tipos de movimiento permitidos
    tipo_movimiento: str = Field(..., pattern="^(entrada|salida|merma|conteo|transferencia|ajuste_positivo|ajuste_negativo|consumo)$")
    fecha_recuento: date = Field(default_factory=date.today)
    fecha_vencimiento: Optional[date] = None
    motivo_merma: Optional[str] = None
    descripcion_merma: Optional[str] = None
    transfer_id: Optional[UUID] = None
    evento_id: Optional[UUID] = None # Para trazabilidad con operaciones

class RegistroStockOut(BaseModel):
    id: UUID
    producto_id: UUID
    bodega_id: UUID
    cantidad: float
    tipo_movimiento: str
    fecha_recuento: date
    fecha_vencimiento: Optional[date]
    created_at: datetime
    usuario_id: int
    motivo_merma: Optional[str] = None
    
    model_config = ConfigDict(from_attributes=True)

# ==========================================
# CARGA MASIVA (Para StockRegistro.tsx)
# ==========================================
class StockBulkCreate(BaseModel):
    """Esquema para recibir la lista de cambios desde el frontend."""
    movements: List[RegistroStockCreate]