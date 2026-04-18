# src/analytics/services/stats_service.py
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_
from datetime import date, timedelta
from uuid import UUID
from typing import List

# Importamos modelos de los otros módulos
from src.inventory.models import Producto, Bodega, ProductoBodega
from src.sales.models import Receta, RecetaIngrediente
from src.operations.models import Evento, RegistroStock
from ..schemas import StockAlert, ExpiryAlert, DashboardSummaryOut, EventProjectionAlert

class StatsService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_dashboard_summary(self) -> DashboardSummaryOut:
        """
        Calcula todas las alertas para la pantalla de Novedades.
        """
        alertas_stock = await self._get_stock_alerts()
        alertas_vencimiento = await self._get_expiry_alerts()
        # alertas_eventos se implementará cuando conectemos Proyecciones
        
        return DashboardSummaryOut(
            alertas_stock=alertas_stock,
            alertas_vencimiento=alertas_vencimiento,
            alertas_eventos=[]
        )

    async def _get_stock_alerts(self) -> List[StockAlert]:
        """
        Compara Stock Actual vs Stock Mínimo por cada producto y bodega.
        """
        # 1. Obtenemos la configuración de mínimos
        stmt = select(
            Producto.id.label("producto_id"),
            Producto.nombre,
            Producto.unidad,
            Bodega.id.label("bodega_id"),
            Bodega.nombre.label("bodega_nombre"),
            ProductoBodega.stock_minimo
        ).join(ProductoBodega, Producto.id == ProductoBodega.producto_id)\
         .join(Bodega, Bodega.id == ProductoBodega.bodega_id)

        result = await self.db.execute(stmt)
        configuraciones = result.all()
        
        alertas = []

        for conf in configuraciones:
            # 2. Calculamos stock actual para esta combinación producto-bodega
            # Nota: Esto es una suma de movimientos. En el futuro, 
            # usar la Vista SQL simplificaría este paso.
            stock_stmt = select(func.sum(RegistroStock.cantidad)).where(
                and_(
                    RegistroStock.producto_id == conf.producto_id,
                    RegistroStock.bodega_id == conf.bodega_id
                )
            )
            stock_res = await self.db.execute(stock_stmt)
            cantidad_actual = stock_res.scalar() or 0.0

            # 3. Determinamos si hay alerta
            if cantidad_actual <= 0:
                alertas.append(StockAlert(
                    producto_id=conf.producto_id,
                    nombre=conf.nombre,
                    bodega_id=conf.bodega_id,
                    bodega_nombre=conf.bodega_nombre,
                    cantidad_actual=cantidad_actual,
                    stock_minimo=conf.stock_minimo,
                    unidad=conf.unidad,
                    tipo_alerta="critical" # Sin stock
                ))
            elif cantidad_actual < conf.stock_minimo:
                alertas.append(StockAlert(
                    producto_id=conf.producto_id,
                    nombre=conf.nombre,
                    bodega_id=conf.bodega_id,
                    bodega_nombre=conf.bodega_nombre,
                    cantidad_actual=cantidad_actual,
                    stock_minimo=conf.stock_minimo,
                    unidad=conf.unidad,
                    tipo_alerta="warning" # Bajo el mínimo
                ))
        
        return alertas

    async def _get_expiry_alerts(self) -> List[ExpiryAlert]:
        """
        Busca productos próximos a vencer (ventana de 7 días) o ya vencidos.
        """
        hoy = date.today()
        proxima_semana = hoy + timedelta(days=7)

        # Buscamos registros de stock positivos con fecha de vencimiento
        # Agrupamos por producto/bodega/fecha para consolidar lotes
        stmt = select(
            RegistroStock.producto_id,
            Producto.nombre,
            RegistroStock.bodega_id,
            Bodega.nombre.label("bodega_nombre"),
            RegistroStock.fecha_vencimiento,
            func.sum(RegistroStock.cantidad).label("cantidad_lote")
        ).join(Producto, Producto.id == RegistroStock.producto_id)\
         .join(Bodega, Bodega.id == RegistroStock.bodega_id)\
         .where(RegistroStock.fecha_vencimiento != None)\
         .group_by(
             RegistroStock.producto_id, 
             Producto.nombre, 
             RegistroStock.bodega_id, 
             Bodega.nombre, 
             RegistroStock.fecha_vencimiento
         ).having(func.sum(RegistroStock.cantidad) > 0)

        result = await self.db.execute(stmt)
        lotes = result.all()

        alertas = []
        for lote in lotes:
            dias_restantes = (lote.fecha_vencimiento - hoy).days
            
            if lote.fecha_vencimiento <= hoy:
                tipo = "critical" # Ya venció
            elif lote.fecha_vencimiento <= proxima_semana:
                tipo = "warning" # Por vencer
            else:
                continue

            alertas.append(ExpiryAlert(
                producto_id=lote.producto_id,
                nombre=lote.nombre,
                bodega_id=lote.bodega_id,
                bodega_nombre=lote.bodega_nombre,
                cantidad=lote.cantidad_lote,
                fecha_vencimiento=lote.fecha_vencimiento,
                dias_para_vencer=dias_restantes,
                tipo_alerta=tipo
            ))

        return alertas