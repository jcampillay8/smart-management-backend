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
# CONFIGURACIÓN PRODUCTO-BODEGA
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
# PRODUCTOS (Ajustado para Gestion.tsx)
# ==========================================
class ProductoBase(BaseModel):
    nombre: str = Field(..., min_length=1, max_length=200)
    unidad: str = Field(default="unidad", description="Ej: Kg, Litro, Unidad")
    costo_unitario: float = Field(default=0.0, ge=0)
    categoria_id: UUID
    # --- AJUSTE IVA ---
    iva_incluido: bool = Field(default=True)
    iva_porcentaje: float = Field(default=19.0, ge=0)

class ProductoCreate(ProductoBase):
    # Gestion.tsx envía esto cuando guardas un producto nuevo o editado
    bodegas_config: Optional[List[ProductoBodegaBase]] = []

class ProductoOut(ProductoBase):
    id: UUID
    bodegas_config: List[ProductoBodegaOut] = []
    categoria: Optional[CategoriaOut] = None
    
    model_config = ConfigDict(from_attributes=True)

# ==========================================
# REGISTRO DE STOCK (Sin cambios)
# ==========================================
class RegistroStockCreate(BaseModel):
    producto_id: UUID
    bodega_id: UUID
    cantidad: float  
    tipo_movimiento: str = Field(..., pattern="^(entrada|salida|merma|conteo|transferencia|ajuste_positivo|ajuste_negativo|consumo)$")
    fecha_recuento: date = Field(default_factory=date.today)
    fecha_vencimiento: Optional[date] = None
    motivo_merma: Optional[str] = None
    descripcion_merma: Optional[str] = None
    transfer_id: Optional[UUID] = None
    evento_id: Optional[UUID] = None 

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
    descripcion_merma: Optional[str] = None 
    nombre_producto: Optional[str] = None
    nombre_bodega: Optional[str] = None
    user_display_name: Optional[str] = None 
    
    model_config = ConfigDict(from_attributes=True)

class StockBulkCreate(BaseModel):
    movements: List[RegistroStockCreate]