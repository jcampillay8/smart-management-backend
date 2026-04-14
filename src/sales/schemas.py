# src/sales/schemas.py
from pydantic import BaseModel, ConfigDict, Field
from uuid import UUID
from datetime import datetime
from typing import List, Optional

# --- Ingredientes de la Receta ---
class RecetaIngredienteBase(BaseModel):
    producto_id: UUID
    bodega_id: UUID  # De dónde se descuenta por defecto
    cantidad: float = Field(..., ge=0, description="Cantidad del insumo necesaria")

class RecetaIngredienteCreate(RecetaIngredienteBase):
    pass

class RecetaIngredienteOut(RecetaIngredienteBase):
    id: UUID
    model_config = ConfigDict(from_attributes=True)

# --- Recetas (El Producto Final) ---
class RecetaBase(BaseModel):
    nombre: str = Field(..., min_length=1, max_length=200)
    precio: float = Field(..., ge=0)

class RecetaCreate(RecetaBase):
    # Permite enviar la lista de ingredientes al crear la receta
    ingredientes: List[RecetaIngredienteCreate]

class RecetaOut(RecetaBase):
    id: UUID
    created_at: datetime
    ingredientes: List[RecetaIngredienteOut]
    model_config = ConfigDict(from_attributes=True)

# --- Ventas ---
class VentaRecetaBase(BaseModel):
    receta_id: UUID
    cantidad: int = Field(default=1, ge=1)
    precio_unitario: float = Field(..., ge=0)

class VentaRecetaCreate(VentaRecetaBase):
    """El usuario_id se inyectará desde el token en el router/service"""
    pass

class VentaRecetaOut(VentaRecetaBase):
    id: UUID
    usuario_id: int
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)