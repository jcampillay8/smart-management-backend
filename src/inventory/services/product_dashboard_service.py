# src/inventory/services/product_dashboard_service.py
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_, cast, Date as SQLDate
from sqlalchemy.orm import selectinload
from datetime import date, timedelta
from uuid import UUID
from typing import List, Dict, Any

from src.models import RegistroStock
from src.inventory.models import Producto, Categoria, ProductoBodega


RANGE_DAYS = {
    "1D": 1,
    "3D": 3,
    "7D": 7,
    "30D": 30,
    "365D": 365,
}

# Tipos que cuentan como "compra" formal (registrados al recibir un pedido)
COMPRA_TIPOS = ["compra"]
# Tipos que cuentan como "consumo"
CONSUMO_TIPOS = ["consumo"]
# Tipos que cuentan como "merma"
MERMA_TIPOS = ["merma", "ajuste_negativo"]


class ProductDashboardService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_dashboard(self, producto_id: UUID, range_key: str = "30D", desde: str = None, hasta: str = None) -> Dict[str, Any]:
        if range_key == "custom" and desde and hasta:
            from datetime import datetime
            fecha_desde = datetime.strptime(desde, "%Y-%m-%d").date()
            fecha_hasta = datetime.strptime(hasta, "%Y-%m-%d").date()
            days = (fecha_hasta - fecha_desde).days
        else:
            days = RANGE_DAYS.get(range_key, 30)
            fecha_hasta = date.today()
            fecha_desde = fecha_hasta - timedelta(days=days)

        # 1. Obtener datos base del producto
        producto_stmt = (
            select(Producto, Categoria.nombre.label("categoria_nombre"))
            .join(Categoria, Categoria.id == Producto.categoria_id)
            .where(Producto.id == producto_id)
            .options(selectinload(Producto.proveedor_principal))
        )
        prod_res = await self.db.execute(producto_stmt)
        row = prod_res.first()
        if not row:
            return None
        prod, cat_nombre = row

        # 2. Stock actual (suma de todos los ProductoBodega)
        stock_stmt = select(func.sum(ProductoBodega.stock_actual)).where(
            ProductoBodega.producto_id == producto_id
        )
        stock_res = await self.db.execute(stock_stmt)
        stock_actual = float(stock_res.scalar() or 0)

        # 3. Movimientos en el período
        mov_stmt = (
            select(
                cast(RegistroStock.created_at, SQLDate).label("fecha"),
                RegistroStock.tipo_movimiento,
                func.sum(func.abs(RegistroStock.cantidad)).label("cantidad"),
            )
            .where(
                and_(
                    RegistroStock.producto_id == producto_id,
                    cast(RegistroStock.created_at, SQLDate) >= fecha_desde,
                    cast(RegistroStock.created_at, SQLDate) <= fecha_hasta,
                )
            )
            .group_by(
                cast(RegistroStock.created_at, SQLDate),
                RegistroStock.tipo_movimiento,
            )
            .order_by(cast(RegistroStock.created_at, SQLDate))
        )
        mov_res = await self.db.execute(mov_stmt)
        movimientos = mov_res.all()

        # 4. Agregar por tipo
        compras_serie: Dict[str, float] = {}
        consumos_serie: Dict[str, float] = {}
        mermas_serie: Dict[str, float] = {}

        for mov in movimientos:
            fecha_str = str(mov.fecha)
            qty = float(mov.cantidad or 0)
            if mov.tipo_movimiento in COMPRA_TIPOS:
                compras_serie[fecha_str] = compras_serie.get(fecha_str, 0) + qty
            elif mov.tipo_movimiento in CONSUMO_TIPOS:
                consumos_serie[fecha_str] = consumos_serie.get(fecha_str, 0) + qty
            elif mov.tipo_movimiento in MERMA_TIPOS:
                mermas_serie[fecha_str] = mermas_serie.get(fecha_str, 0) + qty

        costo = float(prod.costo_unitario or 0)

        def build_serie(serie_dict: Dict[str, float]) -> List[Dict]:
            return [
                {"fecha": f, "cantidad": round(q, 3), "valor": round(q * costo, 0)}
                for f, q in sorted(serie_dict.items())
            ]

        compras_qty = sum(compras_serie.values())
        consumos_qty = sum(consumos_serie.values())
        mermas_qty = sum(mermas_serie.values())

        # 5. Rotación estimada: días para agotar el stock al ritmo de consumo actual
        consumo_diario = consumos_qty / days if days > 0 and consumos_qty > 0 else None
        rotacion_dias = round(stock_actual / consumo_diario, 1) if consumo_diario and consumo_diario > 0 else None

        # 6. Stock promedio simple: promedio entre el stock al inicio y al final del período
        # Aproximación: stock_actual + consumos - compras (antes del período)
        stock_inicio_aprox = stock_actual + consumos_qty - compras_qty
        stock_promedio = round((max(stock_inicio_aprox, 0) + stock_actual) / 2, 2)

        return {
            "producto": {
                "id": str(prod.id),
                "nombre": prod.nombre,
                "unidad": prod.unidad,
                "costo_unitario": costo,
                "precio_venta": float(prod.precio_venta or 0),
                "categoria_nombre": cat_nombre,
                "imagen_url": prod.imagen_url,
                "marca": prod.marca,
                "proveedor": prod.proveedor_principal.nombre_empresa if prod.proveedor_principal else None,
            },
            "stock_actual": stock_actual,
            "stock_promedio": stock_promedio,
            "rotacion_dias": rotacion_dias,
            "compras": {
                "cantidad": round(compras_qty, 3),
                "valor": round(compras_qty * costo, 0),
                "serie": build_serie(compras_serie),
            },
            "consumos": {
                "cantidad": round(consumos_qty, 3),
                "valor": round(consumos_qty * costo, 0),
                "serie": build_serie(consumos_serie),
            },
            "mermas": {
                "cantidad": round(mermas_qty, 3),
                "valor": round(mermas_qty * costo, 0),
                "serie": build_serie(mermas_serie),
            },
            "periodo": {
                "desde": str(fecha_desde),
                "hasta": str(fecha_hasta),
                "dias": days,
            },
        }
