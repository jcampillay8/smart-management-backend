# src/purchases/schemas.py
import uuid
from datetime import datetime, date
from typing import List, Optional
from pydantic import BaseModel, ConfigDict

class CompraItemBase(BaseModel):
    producto_id: uuid.UUID
    bodega_id: Optional[uuid.UUID] = None
    cantidad: float
    precio_unitario: float

class CompraItemCreate(CompraItemBase):
    pass

class CompraItem(CompraItemBase):
    id: uuid.UUID
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)

class CompraBase(BaseModel):
    estado: str = "pendiente"
    pedido_realizado: bool = False
    fecha: date
    total: float
    factura_url: Optional[str] = None
    proveedor: Optional[str] = None
    notas: Optional[str] = None

class CompraCreate(CompraBase):
    items: List[CompraItemCreate]

class CompraUpdate(BaseModel):
    estado: Optional[str] = None
    pedido_realizado: Optional[bool] = None
    fecha: Optional[date] = None
    total: Optional[float] = None
    factura_url: Optional[str] = None
    proveedor: Optional[str] = None
    notas: Optional[str] = None

class Compra(CompraBase):
    id: uuid.UUID
    usuario_id: int
    created_at: datetime
    updated_at: datetime
    items: List[CompraItem]
    model_config = ConfigDict(from_attributes=True)

class ScanInvoiceRequest(BaseModel):
    imageBase64: str
    mimeType: Optional[str] = "image/jpeg"

class ScanRecipeRequest(BaseModel):
    imageBase64: str
    mimeType: Optional[str] = "image/jpeg"


# ======================
# PROVEEDORES
# ======================
class ProveedorBase(BaseModel):
    nombre_empresa: str
    rut: Optional[str] = None
    nombre_contacto: Optional[str] = None
    telefono: Optional[str] = None
    direccion: Optional[str] = None
    email: Optional[str] = None


class ProveedorCreate(ProveedorBase):
    pass


class ProveedorUpdate(BaseModel):
    nombre_empresa: Optional[str] = None
    rut: Optional[str] = None
    nombre_contacto: Optional[str] = None
    telefono: Optional[str] = None
    direccion: Optional[str] = None
    email: Optional[str] = None


class ProveedorOut(ProveedorBase):
    id: uuid.UUID
    created_at: datetime
    updated_at: datetime
    model_config = ConfigDict(from_attributes=True)
