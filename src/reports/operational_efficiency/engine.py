# src/reports/operational_efficiency/engine.py
from datetime import date, timedelta
from typing import List, Dict

def calcular_rotacion_inventario(
    costo_ventas: float,
    inventario_inicio: float,
    inventario_fin: float
) -> float:
    """
    Fórmula: Rotación = Costo_Ventas / Promedio_Inventario
    Promedio_Inventario = (Inventario_Inicio + Inventario_Fin) / 2
    """
    promedio_inventario = (inventario_inicio + inventario_fin) / 2
    if promedio_inventario == 0:
        return 0.0
    return costo_ventas / promedio_inventario

def calcular_punto_pedido(
    demanda_diaria: float,
    tiempo_entrega_dias: int,
    stock_seguridad: float = 0.0
) -> float:
    """
    Fórmula: Punto_Pedido = (Demanda_Diaria * Tiempo_Entrega) + Stock_Seguridad
    Corregido para manejar tipos Decimal de la base de datos.
    """
    # Forzamos la conversión a float para evitar el TypeError con Decimal
    dd = float(demanda_diaria)
    te = float(tiempo_entrega_dias)
    ss = float(stock_seguridad) if stock_seguridad is not None else 0.0
    
    return (dd * te) + ss

def calcular_demanda_diaria(
    ventas_periodo: float,
    dias_periodo: int = 30
) -> float:
    """Calcula demanda promedio diaria"""
    if dias_periodo == 0:
        return 0.0
    return ventas_periodo / dias_periodo

def calcular_dias_inventario(
    stock_actual: float,
    demanda_diaria: float
) -> float:
    """Calcula cuántos días de inventario quedan"""
    if demanda_diaria == 0:
        return float('inf')
    return stock_actual / demanda_diaria

def identificar_productos_sobrestock(
    productos_rotacion: List[Dict],
    umbral_rotacion_baja: float = 0.5,
    umbral_dias_inventario: float = 60
) -> List[Dict]:
    """Identifica productos con sobrestock basado en rotación baja y días de inventario altos"""
    sobrestock = []
    for p in productos_rotacion:
        if p['rotacion'] < umbral_rotacion_baja and p['dias_inventario'] > umbral_dias_inventario:
            sobrestock.append(p)
    return sobrestock
