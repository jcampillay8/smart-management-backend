# src/reports/operational_efficiency/service.py
from datetime import date, timedelta
from typing import List, Dict, Optional as Opt
from sqlalchemy import select, func, and_, orm
from sqlalchemy.ext.asyncio import AsyncSession

from src.config import settings
from src.inventory.models import Producto, ProductoBodega, Bodega
from src.operations.models import Transferencia, RegistroStock, TipoMovimiento
from src.reports.operational_efficiency.engine import (
    calcular_rotacion_inventario,
    calcular_punto_pedido,
    calcular_demanda_diaria,
    calcular_dias_inventario,
)


class OperationalEfficiencyService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.schema = settings.DB_SCHEMA

    async def get_rotacion_inventario(
        self,
        fecha_inicio: date = None,
        fecha_fin: date = None,
        bodega_id: Opt[str] = None,
    ) -> List[Dict]:
        if not fecha_inicio:
            fecha_inicio = date.today() - timedelta(days=30)
        if not fecha_fin:
            fecha_fin = date.today()

        query = (
            select(
                Producto.id,
                Producto.nombre,
                ProductoBodega.stock_actual,
                ProductoBodega.bodega_id,
            )
            .join(ProductoBodega, ProductoBodega.producto_id == Producto.id)
        )
        if bodega_id:
            query = query.where(ProductoBodega.bodega_id == bodega_id)

        result = await self.session.execute(query)
        rows = result.all()

        # Calcular costo de ventas por producto desde registros_stock
        ventas_query = (
            select(
                RegistroStock.producto_id,
                func.sum(RegistroStock.cantidad).label("total_vendido"),
            )
            .where(
                and_(
                    RegistroStock.tipo_movimiento == TipoMovimiento.VENTA,
                    RegistroStock.fecha_recuento.between(fecha_inicio, fecha_fin),
                )
            )
            .group_by(RegistroStock.producto_id)
        )
        ventas_result = await self.session.execute(ventas_query)
        ventas_dict = {str(r.producto_id): float(r.total_vendido or 0) for r in ventas_result.all()}

        productos = []
        for row in rows:
            costo_ventas = ventas_dict.get(str(row.id), 0)
            stock_promedio = float(row.stock_actual or 0)
            rotacion = calcular_rotacion_inventario(costo_ventas, stock_promedio, stock_promedio)

            productos.append({
                "producto_id": str(row.id),
                "nombre": row.nombre,
                "rotacion": round(rotacion, 2),
                "stock_promedio": stock_promedio,
                "costo_ventas": round(costo_ventas, 2),
            })

        return sorted(productos, key=lambda x: x["rotacion"])

    async def get_transferencias_reporte(
        self,
        fecha_inicio: date = None,
        fecha_fin: date = None,
        bodega_id: Opt[str] = None,
    ) -> List[Dict]:
        if not fecha_inicio:
            fecha_inicio = date.today() - timedelta(days=30)
        if not fecha_fin:
            fecha_fin = date.today()

        BodegaOrigen = orm.aliased(Bodega)
        BodegaDestino = orm.aliased(Bodega)

        query = (
            select(
                Transferencia.id,
                Producto.nombre.label("producto_nombre"),
                BodegaOrigen.nombre.label("bodega_origen"),
                BodegaDestino.nombre.label("bodega_destino"),
                Transferencia.cantidad,
                Transferencia.fecha,
                Transferencia.motivo,
            )
            .join(Producto, Producto.id == Transferencia.producto_id)
            .join(BodegaOrigen, BodegaOrigen.id == Transferencia.bodega_origen_id)
            .join(BodegaDestino, BodegaDestino.id == Transferencia.bodega_destino_id)
            .where(Transferencia.fecha.between(fecha_inicio, fecha_fin))
            .order_by(Transferencia.fecha.desc())
        )

        result = await self.session.execute(query)
        rows = result.all()

        return [
            {
                "id": str(r.id),
                "producto_nombre": r.producto_nombre,
                "bodega_origen": r.bodega_origen,
                "bodega_destino": r.bodega_destino,
                "cantidad": float(r.cantidad),
                "fecha": r.fecha.isoformat() if r.fecha else "",
                "motivo": r.motivo,
            }
            for r in rows
        ]

    async def get_alertas_punto_pedido(
        self, margen_cercania: float = 0.2
    ) -> List[Dict]:
        query = (
            select(
                Producto.id,
                Producto.nombre,
                ProductoBodega.stock_actual,
                ProductoBodega.stock_minimo,
            )
            .join(ProductoBodega, ProductoBodega.producto_id == Producto.id)
            .where(ProductoBodega.stock_minimo > 0)
        )
        result = await self.session.execute(query)
        rows = result.all()

        alertas = []
        for row in rows:
            stock_actual = float(row.stock_actual or 0)
            stock_minimo = float(row.stock_minimo or 0)
            punto_pedido = calcular_punto_pedido(0, 0, stock_minimo)
            diferencia = stock_actual - punto_pedido

            if abs(diferencia) <= punto_pedido * margen_cercania or diferencia < 0:
                alertas.append({
                    "producto_id": str(row.id),
                    "nombre": row.nombre,
                    "stock_actual": stock_actual,
                    "punto_pedido": round(punto_pedido, 2),
                    "diferencia": round(diferencia, 2),
                })

        return sorted(alertas, key=lambda x: x["diferencia"])

    async def get_rotacion_promedio_general(self) -> float:
        productos = await self.get_rotacion_inventario()
        if not productos:
            return 0.0
        return sum(p["rotacion"] for p in productos) / len(productos)


def get_operational_efficiency_service(session: AsyncSession) -> OperationalEfficiencyService:
    return OperationalEfficiencyService(session)
