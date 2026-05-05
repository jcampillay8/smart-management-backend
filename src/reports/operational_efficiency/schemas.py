# src/reports/operational_efficiency/schemas.py
from typing import List, Optional
from pydantic import BaseModel

class RotacionProducto(BaseModel):
    producto_id: str
    nombre: str
    rotacion: float
    stock_promedio: float
    costo_ventas: float

class TransferenciaReporte(BaseModel):
    id: str
    producto_nombre: str
    bodega_origen: str
    bodega_destino: str
    cantidad: float
    fecha: str
    motivo: Optional[str] = None

class PuntoPedidoAlerta(BaseModel):
    producto_id: str
    nombre: str
    stock_actual: float
    punto_pedido: float
    diferencia: float  # Negativo indica que está por debajo del punto de pedido

class OperationalEfficiencyResponse(BaseModel):
    rotacion_productos: List[RotacionProducto]
    transferencias_recientes: List[TransferenciaReporte]
    alertas_punto_pedido: List[PuntoPedidoAlerta]
    rotacion_promedio_general: float
