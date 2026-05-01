# src/reports/executive_overview/schemas.py
from typing import List, Optional
from datetime import date
from pydantic import BaseModel

class ExecutiveOverviewResponse(BaseModel):
    # Bloque 1: Resumen General
    valor_total_inventario: float
    porcentaje_merma: float
    stock_total_unidades: float
    
    # Bloque 2: Visión Financiera (simplificado)
    total_compras_periodo: float
    total_ventas_periodo: float
    
    # Bloque 3: Control de Pérdidas (Top 5)
    top_mermas_productos: List["ProductMerma"]
    
    # Bloque 4: Operación y Eficiencia
    rotacion_promedio: float
    productos_bajo_stock: List["ProductoStock"]

class ProductMerma(BaseModel):
    producto_id: str
    nombre: str
    cantidad_merma: float
    motivo_principal: str

class ProductoStock(BaseModel):
    producto_id: str
    nombre: str
    stock_actual: float
    stock_minimo: float
    bodega_nombre: str

class InsightResponse(BaseModel):
    tipo: str  # "sobrestock", "fuga_dinero", "oportunidad"
    mensaje: str
    impacto_estimado: Optional[float] = None
