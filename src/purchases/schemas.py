# src/purchases/schemas.py
import uuid
from datetime import datetime, date
from typing import List, Optional
from pydantic import BaseModel, ConfigDict, field_validator

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

class IncidenciaCreate(BaseModel):
    tipo: str
    titulo: str
    detalle: Optional[dict] = None

class ReceptionItem(BaseModel):
    producto_id: uuid.UUID
    cantidad_recibida: float
    costo_neto: float
    fecha_vencimiento: Optional[date] = None

class ReceptionCreate(BaseModel):
    items: List[ReceptionItem]
    action: Optional[str] = None # 'modify_order' | 'reject_order'

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

    @field_validator('rut', mode='before')
    @classmethod
    def validate_rut(cls, v):
        if v is not None and v != '':
            import re
            # 1. Eliminar puntos si vinieran por error
            cleaned = str(v).replace('.', '')
            # Permitir que los datos antiguos pasen o intentar arreglarlos
            if not re.match(r'^\d{7,8}-[0-9Kk]$', cleaned):
                # Limpieza agresiva de legacy data para el response y el input
                just_alphanum = re.sub(r'[^0-9kK]', '', cleaned)
                if len(just_alphanum) > 1:
                    body = just_alphanum[:-1]
                    dv = just_alphanum[-1].upper()
                    if len(body) >= 7 and len(body) <= 8:
                        return f"{body}-{dv}"
                return v # Si es muy inválido, dejarlo pasar para no crashear (Pydantic no fallará si no lanzamos ValueError aquí, el campo es str)
            return cleaned.upper()
        return v


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

# ======================
# PLANTILLAS EMAIL
# ======================
class PlantillaEmailBase(BaseModel):
    nombre: str
    asunto: str
    cuerpo: str

class PlantillaEmailCreate(PlantillaEmailBase):
    pass

class PlantillaEmailUpdate(BaseModel):
    nombre: Optional[str] = None
    asunto: Optional[str] = None
    cuerpo: Optional[str] = None

class PlantillaEmailOut(PlantillaEmailBase):
    id: uuid.UUID
    created_by: Optional[int] = None
    model_config = ConfigDict(from_attributes=True)
