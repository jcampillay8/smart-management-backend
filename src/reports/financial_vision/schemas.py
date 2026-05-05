# src/reports/financial_vision/schemas.py
from typing import List, Optional
from pydantic import BaseModel

class PlatoMenu(BaseModel):
    receta_id: str
    nombre: str
    precio_venta: float
    costo_receta: float
    margen: float
    margen_porcentaje: float
    cantidad_vendida: int
    categoria: str  # Estrellas, Caballos de batalla, Puzzles, Perros

class BreakEvenResult(BaseModel):
    gastos_fijos: float
    margen_promedio: float
    punto_equilibrio: float
    ventas_actuales: float
    porcentaje_cubierto: float

class PrimeCostResult(BaseModel):
    costo_alimentos: float
    costo_labor: float  # Por ahora 0, requiere módulo de RRHH
    total_prime_cost: float
    ventas_totales: float
    prime_cost_porcentaje: float

class VariacionPrecio(BaseModel):
    producto_id: str
    nombre: str
    proveedor_nombre: Optional[str] = None
    precio_anterior: float
    precio_actual: float
    porcentaje_cambio: float

class FinancialVisionResponse(BaseModel):
    matriz_menu: List[PlatoMenu]
    break_even: BreakEvenResult
    prime_cost: PrimeCostResult
    variacion_precios: List[VariacionPrecio]
