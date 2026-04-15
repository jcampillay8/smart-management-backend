# src/inventory/schemas.py
from datetime import date, datetime
from pydantic import BaseModel, ConfigDict, Field
from uuid import UUID
from datetime import datetime
from typing import Optional, List

# --- Categorías ---
class CategoriaBase(BaseModel):
    nombre: str = Field(..., min_length=1, max_length=100)

class CategoriaCreate(CategoriaBase):
    pass

class CategoriaOut(CategoriaBase):
    id: UUID
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)

# --- Bodegas ---
class BodegaBase(BaseModel):
    nombre: str = Field(..., min_length=1, max_length=100)

class BodegaCreate(BodegaBase):
    pass

class BodegaOut(BodegaBase):
    id: UUID
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)

# --- Relación Producto-Bodega (Configuración de Stock Mínimo) ---
class ProductoBodegaBase(BaseModel):
    bodega_id: UUID
    stock_minimo: float = Field(default=0.0, ge=0)

class ProductoBodegaOut(ProductoBodegaBase):
    id: UUID
    stock_actual: float = 0.0
    model_config = ConfigDict(from_attributes=True)

# --- Productos ---
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
    created_at: datetime
    # Incluimos la configuración de bodegas para que el front sepa los stocks mínimos
    bodegas_config: List[ProductoBodegaOut] = []
    
    model_config = ConfigDict(from_attributes=True)

class RegistroStockCreate(BaseModel):
    producto_id: UUID
    bodega_id: UUID
    cantidad: float = Field(..., gt=0)
    fecha_recuento: Optional[date] = None
    fecha_vencimiento: Optional[date] = None
    descripcion_merma: Optional[str] = None

class RegistroStockOut(BaseModel):
    id: UUID
    producto_id: UUID
    cantidad: float
    tipo_movimiento: str
    fecha_recuento: date
    fecha_vencimiento: Optional[date]
    created_at: datetime
    # Podrías añadir campos extra mediante joins en el router (nombre_producto, etc.)
    model_config = ConfigDict(from_attributes=True)