# src/analytics/services/report_service.py
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_, extract
from datetime import date, timedelta
from uuid import UUID
from typing import List, Dict

from src.inventory.models import Producto, RegistroStock, Bodega
from src.operations.models import Receta

class ReportService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_inventory_valuation(self) -> Dict:
        """
        Calcula el valor total del inventario actual (Stock * Costo Unitario).
        Útil para el balance financiero en Informes.tsx.
        """
        # Obtenemos todos los productos con su costo y stock actual consolidado
        stmt = select(
            Producto.id,
            Producto.nombre,
            Producto.costo_unitario,
            func.sum(RegistroStock.cantidad).label("stock_total")
        ).join(RegistroStock, Producto.id == RegistroStock.producto_id)\
         .group_by(Producto.id, Producto.nombre, Producto.costo_unitario)

        result = await self.db.execute(stmt)
        items = result.all()

        valor_total = sum((item.stock_total * item.costo_unitario) for item in items if item.stock_total > 0)
        
        return {
            "valor_total_neto": valor_total,
            "moneda": "CLP",
            "detalle_por_producto": [
                {
                    "nombre": item.nombre,
                    "stock": item.stock_total,
                    "valorizado": item.stock_total * item.costo_unitario
                } for item in items if item.stock_total > 0
            ]
        }

    async def get_merma_stats(self, days: int = 30) -> Dict:
        """
        Calcula el impacto económico de las mermas en los últimos X días.
        Filtra por tipos de movimiento: 'merma', 'ajuste_negativo'.
        """
        desde_fecha = date.today() - timedelta(days=days)
        
        stmt = select(
            Producto.nombre,
            func.sum(func.abs(RegistroStock.cantidad)).label("cantidad_perdida"),
            func.sum(func.abs(RegistroStock.cantidad) * Producto.costo_unitario).label("costo_perdida"),
            RegistroStock.motivo_merma
        ).join(Producto, Producto.id == RegistroStock.producto_id)\
         .where(
             and_(
                 RegistroStock.tipo_movimiento.in_(["merma", "ajuste_negativo"]),
                 RegistroStock.fecha_recuento >= desde_fecha
             )
         ).group_by(Producto.nombre, RegistroStock.motivo_merma)

        result = await self.db.execute(stmt)
        mermas = result.all()

        total_dinero_perdido = sum(m.costo_perdida for m in mermas)

        return {
            "periodo_dias": days,
            "total_perdida_economica": total_dinero_perdido,
            "desglose": [
                {
                    "producto": m.nombre,
                    "cantidad": m.cantidad_perdida,
                    "motivo": m.motivo_merma,
                    "perdida_valorizada": m.costo_perdida
                } for m in mermas
            ]
        }

    async def get_monthly_movement_summary(self, year: int, month: int):
        """
        Genera un resumen de entradas y salidas para un mes específico.
        Ideal para gráficos de barras comparativos.
        """
        stmt = select(
            RegistroStock.tipo_movimiento,
            func.sum(func.abs(RegistroStock.cantidad)).label("total_qty")
        ).where(
            and_(
                extract('year', RegistroStock.fecha_recuento) == year,
                extract('month', RegistroStock.fecha_recuento) == month
            )
        ).group_by(RegistroStock.tipo_movimiento)

        result = await self.db.execute(stmt)
        resumen = result.all()

        return {
            "mes": month,
            "anio": year,
            "movimientos": {r.tipo_movimiento: r.total_qty for r in resumen}
        }