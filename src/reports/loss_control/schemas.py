# src/reports/loss_control/schemas.py
from typing import List, Optional
from pydantic import BaseModel

class MermaByMotivo(BaseModel):
    motivo: str
    cantidad_total: float
    porcentaje: float

class MermaByProducto(BaseModel):
    producto_id: str
    nombre: str
    cantidad_total: float
    bodega_nombre: Optional[str] = None

class ProductoAnomalia(BaseModel):
    producto_id: str
    nombre: str
    merma_actual: float
    promedio_historico: float
    desviacion: float
    diferencia_porcentual: float

class LossControlResponse(BaseModel):
    mermas_por_motivo: List[MermaByMotivo]
    top_productos_merma: List[MermaByProducto]
    anomalias: List[ProductoAnomalia]
