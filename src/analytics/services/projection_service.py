# src/analytics/services/projection_service.py
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_, or_
from datetime import date, timedelta # <--- IMPORTANTE: añadir timedelta
from uuid import UUID
from typing import List, Dict, Optional

from src.inventory.models import Producto, ProductoBodega, Bodega
from src.operations.models import Evento, RegistroStock
from src.sales.models import Receta, RecetaIngrediente
from ..schemas import (
    EventProjectionAlert, 
    ProductoProyeccionDetalleOut, 
    ProjectionPoint
)

class ProjectionService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_event_projections(self) -> List[EventProjectionAlert]:
        """Analiza eventos futuros y proyecta si el stock es suficiente."""
        stmt_eventos = select(Evento).where(
            and_(Evento.ejecutado == False, Evento.cancelado == False)
        ).order_by(Evento.fecha.asc())
        
        result_eventos = await self.db.execute(stmt_eventos)
        eventos = result_eventos.scalars().all()
        
        alertas = []
        for evento in eventos:
            necesidades = await self._get_event_requirements(evento.id)
            for req in necesidades:
                p_id = req["producto_id"]
                b_id = req["bodega_id"]
                cantidad_necesaria = req["total_necesario"]

                stock_valido = await self._get_valid_stock_for_date(p_id, b_id, evento.fecha)
                stock_proyectado = stock_valido - cantidad_necesaria
                
                if stock_proyectado < 0 or stock_proyectado < req["stock_minimo"]:
                    sugerencia = await self._find_alternative_stock(p_id, b_id, evento.fecha)
                    
                    alertas.append(EventProjectionAlert(
                        evento_id=evento.id,
                        evento_nombre=evento.nombre,
                        fecha_evento=evento.fecha,
                        producto_nombre=req["producto_nombre"],
                        bodega_nombre=req["bodega_nombre"],
                        stock_proyectado=round(stock_proyectado, 2),
                        cantidad_necesaria=round(cantidad_necesaria, 2),
                        insuficiente=(stock_proyectado < 0),
                        sugerencia_alternativa=sugerencia
                    ))
        return alertas

    async def get_product_projection_curve(
        self, producto_id: UUID, bodega_id: UUID, dias: int = 30
    ) -> ProductoProyeccionDetalleOut:
        """Genera la serie temporal de stock para el gráfico de Recharts."""
        hoy = date.today()
        limite = hoy + timedelta(days=dias)

        res_p = await self.db.execute(select(Producto).where(Producto.id == producto_id))
        producto = res_p.scalar_one()

        cantidad_actual = await self._get_valid_stock_for_date(producto_id, bodega_id, hoy)
        
        # Obtenemos consumos específicos para este producto
        consumos = await self._get_upcoming_consumptions(producto_id, bodega_id, hoy, limite)

        puntos = []
        saldo = cantidad_actual
        for i in range(dias + 1):
            fecha_f = hoy + timedelta(days=i)
            eventos_hoy = [c for c in consumos if c["fecha"] == fecha_f]
            total_consumo_hoy = sum(e["cantidad"] for e in eventos_hoy)
            
            saldo -= total_consumo_hoy
            puntos.append(ProjectionPoint(
                fecha=fecha_f,
                cantidad=round(saldo, 2),
                evento_nombre=eventos_hoy[0]["nombre"] if eventos_hoy else None
            ))

        return ProductoProyeccionDetalleOut(
            producto_id=producto.id,
            nombre=producto.nombre,
            unidad=producto.unidad,
            stock_actual=cantidad_actual,
            stock_minimo=producto.stock_minimo,
            puntos=puntos
        )

    async def _get_upcoming_consumptions(self, p_id: UUID, b_id: UUID, inicio: date, fin: date) -> List[Dict]:
        """Auxiliar para el gráfico: busca consumos de un producto entre dos fechas."""
        stmt = (
            select(Evento.fecha, Evento.nombre, RecetaIngrediente.cantidad)
            .join(Receta, Receta.evento_id == Evento.id)
            .join(RecetaIngrediente, RecetaIngrediente.receta_id == Receta.id)
            .where(
                and_(
                    RecetaIngrediente.producto_id == p_id,
                    RecetaIngrediente.bodega_id == b_id,
                    Evento.fecha >= inicio,
                    Evento.fecha <= fin,
                    Evento.ejecutado == False,
                    Evento.cancelado == False
                )
            )
        )
        res = await self.db.execute(stmt)
        return [{"fecha": r.fecha, "nombre": r.nombre, "cantidad": r.cantidad} for r in res.all()]

    async def _get_event_requirements(self, evento_id: UUID) -> List[Dict]:
        """Explota materiales de un evento."""
        stmt = (
            select(
                RecetaIngrediente.producto_id,
                Producto.nombre.label("producto_nombre"),
                ProductoBodega.stock_minimo,
                RecetaIngrediente.bodega_id,
                Bodega.nombre.label("bodega_nombre"),
                func.sum(RecetaIngrediente.cantidad).label("total_necesario")
            )
            .join(Producto, RecetaIngrediente.producto_id == Producto.id)
            .join(Bodega, RecetaIngrediente.bodega_id == Bodega.id)
            .join(Receta, RecetaIngrediente.receta_id == Receta.id)
            .join(ProductoBodega, and_(
                ProductoBodega.producto_id == Producto.id,
                ProductoBodega.bodega_id == Bodega.id
            ))
            .where(Receta.evento_id == evento_id)
            .group_by(RecetaIngrediente.producto_id, Producto.nombre, ProductoBodega.stock_minimo, RecetaIngrediente.bodega_id, Bodega.nombre)
        )
        res = await self.db.execute(stmt)
        return [dict(r._mapping) for r in res.all()]

    async def _get_valid_stock_for_date(self, p_id: UUID, b_id: UUID, fecha_limite: date) -> float:
        """Calcula stock no vencido para una fecha específica."""
        stmt = select(func.sum(RegistroStock.cantidad)).where(
            and_(
                RegistroStock.producto_id == p_id,
                RegistroStock.bodega_id == b_id,
                or_(
                    RegistroStock.fecha_vencimiento >= fecha_limite,
                    RegistroStock.fecha_vencimiento == None
                )
            )
        )
        res = await self.db.execute(stmt)
        return float(res.scalar() or 0.0)

    async def _find_alternative_stock(self, p_id: UUID, b_original_id: UUID, fecha: date) -> Optional[str]:
        """Sugerencia de stock en otras bodegas."""
        stmt = (
            select(Bodega.nombre, func.sum(RegistroStock.cantidad).label("total"))
            .join(RegistroStock, RegistroStock.bodega_id == Bodega.id)
            .where(
                and_(
                    RegistroStock.producto_id == p_id,
                    Bodega.id != b_original_id,
                    or_( RegistroStock.fecha_vencimiento >= fecha, RegistroStock.fecha_vencimiento == None )
                )
            )
            .group_by(Bodega.nombre)
            .having(func.sum(RegistroStock.cantidad) > 0)
        )
        res = await self.db.execute(stmt)
        alts = res.all()
        if not alts: return None
        sugs = [f"{round(r.total, 2)} en {r.nombre}" for r in alts]
        return f"Sugerencia: Trasladar desde ({', '.join(sugs)})"