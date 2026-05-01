# src/reports/operational_efficiency/service.py
from datetime import date, timedelta
from typing import List, Dict, Optional
from sqlalchemy import select, func, and_, or_
from sqlalchemy.ext.asyncio import AsyncSession

from src.database import async_session_maker
from src.config import settings
from src.inventory.models import Producto, ProductoBodega, Bodega
from src.operations.models import RegistroStock, TipoMovimiento, Transferencia
from src.purchases.models import Compra, Proveedor
from .engine import (
    calcular_rotacion_inventario,
    calcular_punto_pedido,
    calcular_demanda_diaria,
    calcular_dias_inventario,
    identificar_productos_sobrestock
)

class OperationalEfficiencyService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.schema = settings.DB_SCHEMA

    async def get_rotacion_inventario(
        self, 
        fecha_inicio: Optional[date] = None, 
        fecha_fin: Optional[date] = None,
        bodega_id: Optional[str] = None
    ) -> List[Dict]:
        """
        1. Cálculo detallado de rotación de inventario por producto
        """
        if not fecha_inicio:
            fecha_inicio = date.today() - timedelta(days=30)
        if not fecha_fin:
            fecha_fin = date.today()
        dias_periodo = (fecha_fin - fecha_inicio).days or 1
        
        # Obtener ventas/salidas del período (usamos registros_stock tipo CONSUMO y MERMA)
        query_ventas = (
            select(
                RegistroStock.producto_id,
                Producto.nombre,
                func.sum(RegistroStock.cantidad).label('total_salidas')
            )
            .join(Producto, Producto.id == RegistroStock.producto_id)
            .where(
                and_(
                    RegistroStock.fecha_recuento.between(fecha_inicio, fecha_fin),
                    RegistroStock.tipo_movimiento.in_([TipMovimiento.CONSUMO, TipoMovimiento.MERMA])
                )
            )
            .group_by(RegistroStock.producto_id, Producto.nombre)
        )
        
        if bodega_id:
            query_ventas = query_ventas.where(RegistroStock.bodega_id == bodega_id)
            
        result_ventas = await self.session.execute(query_ventas)
        ventas_dict = {str(row.producto_id): row for row in result_ventas.all()}
        
        # Obtener datos de inventario (inicio y fin)
        # Simplificado: usamos stock_actual como aproximación
        query_stock = (
            select(
                ProductoBodega.producto_id,
                func.avg(ProductoBodega.stock_actual).label('promedio_stock'),
                func.avg(Producto.costo_unitario).label('costo_promedio')
            )
            .join(Producto, Producto.id == ProductoBodega.producto_id)
            .group_by(ProductoBodega.producto_id)
        )
        
        if bodega_id:
            query_stock = query_stock.where(ProductoBodega.bodega_id == bodega_id)
            
        result_stock = await self.session.execute(query_stock)
        
        rotacion_list = []
        for row in result_stock.all():
            p_id = str(row.producto_id)
            if p_id in ventas_dict:
                venta_row = ventas_dict[p_id]
                costo_ventas = float(venta_row.total_salidas) * float(row.costo_promedio or 0)
                demanda_diaria = calcular_demanda_diaria(costo_ventas, dias_periodo)
                
                rotacion = calcular_rotacion_inventario(
                    costo_ventas,
                    float(row.promedio_stock or 0),
                    float(row.promedio_stock or 0)
                )
                
                rotacion_list.append({
                    'producto_id': p_id,
                    'nombre': venta_row.nombre,
                    'rotacion': round(rotacion, 2),
                    'stock_promedio': float(row.promedio_stock or 0),
                    'costo_ventas': costo_ventas,
                    'demanda_diaria': demanda_diaria,
                    'dias_inventario': calcular_dias_inventario(
                        float(row.promedio_stock or 0), demanda_diaria
                    )
                })
        
        return sorted(rotacion_list, key=lambda x: x['rotacion'], reverse=True)

    async def get_transferencias_reporte(
        self, 
        fecha_inicio: Optional[date] = None,
        fecha_fin: Optional[date] = None,
        bodega_id: Optional[str] = None
    ) -> List[Dict]:
        """
        2. Reporte de transferencias inter-bodegas
        """
        query = (
            select(
                Transferencia.id,
                Producto.nombre.label('producto_nombre'),
                BodegaOrigen.nombre.label('bodega_origen'),
                BodegaDestino.nombre.label('bodega_destino'),
                Transferencia.cantidad,
                Transferencia.fecha,
                Transferencia.motivo
            )
            .join(Producto, Producto.id == Transferencia.producto_id)
            .join(Bodega, Bodega.id == Transferencia.bodega_origen_id, aliased=True)
            .join(Bodega, Bodega.id == Transferencia.bodega_destino_id, aliased=True)
            .where(Transferencia.fecha.between(fecha_inicio or date.today() - timedelta(days=30), 
                                       fecha_fin or date.today()))
        )
        
        if bodega_id:
            query = query.where(
                or_(Transferencia.bodega_origen_id == bodega_id, 
                     Transferencia.bodega_destino_id == bodega_id)
            )
            
        result = await self.session.execute(query)
        return [
            {
                'id': str(row.id),
                'producto_nombre': row.producto_nombre,
                'bodega_origen': row.bodega_origen,
                'bodega_destino': row.bodega_destino,
                'cantidad': float(row.cantidad),
                'fecha': row.fecha.isoformat() if row.fecha else '',
                'motivo': row.motivo
            }
            for row in result.all()
        ]

    async def get_alertas_punto_pedido(self, margen_cercania: float = 0.2) -> List[Dict]:
        """
        3. Productos cerca del punto de pedido (por debajo o dentro del margen de cercanía)
        """
        # Obtener productos con proveedor y tiempo de entrega
        query = (
            select(
                Producto.id,
                Producto.nombre,
                ProductoBodega.stock_actual,
                ProductoBodega.stock_minimo,
                Proveedor.tiempo_entrega_promedio_dias.label('tiempo_entrega')
            )
            .join(ProductoBodega, ProductoBodega.producto_id == Producto.id)
            .outerjoin(Proveedor, Proveedor.id == Producto.proveedor_id)
        )
        
        result = await self.session.execute(query)
        alertas = []
        
        for row in result.all():
            # Calcular demanda diaria basada en consumo histórico (últimos 30 días)
            query_consumo = (
                select(func.sum(RegistroStock.cantidad))
                .where(
                    and_(
                        RegistroStock.producto_id == row.id,
                        RegistroStock.fecha_recuento >= date.today() - timedelta(days=30),
                        RegistroStock.tipo_movimiento.in_([TipMovimiento.CONSUMO, TipoMovimiento.MERMA])
                    )
                )
            )
            result_consumo = await self.session.execute(query_consumo)
            consumo_total = float(result_consumo.scalar() or 0)
            demanda_diaria = consumo_total / 30  # promedio diario
            
            tiempo_entrega = row.tiempo_entrega or 7  # default 7 días
            stock_seguridad = row.stock_minimo or 0
            
            punto_pedido = calcular_punto_pedido(demanda_diaria, tiempo_entrega, stock_seguridad)
            diferencia = float(row.stock_actual or 0) - punto_pedido
            
            # Alerta si está por debajo O dentro del margen de cercanía (por defecto 20% arriba)
            if diferencia < (punto_pedido * margen_cercania):
                alertas.append({
                    'producto_id': str(row.id),
                    'nombre': row.nombre,
                    'stock_actual': float(row.stock_actual or 0),
                    'punto_pedido': round(punto_pedido, 2),
                    'diferencia': round(diferencia, 2)
                })
        
        return alertas

    async def get_rotacion_promedio_general(self) -> float:
        """Calcula rotación promedio general del inventario"""
        query = (
            select(func.sum(RegistroStock.cantidad * Producto.costo_unitario))
            .join(Producto, Producto.id == RegistroStock.producto_id)
            .where(
                RegistroStock.tipo_movimiento.in_([TipMovimiento.CONSUMO, TipoMovimiento.MERMA])
            )
        )
        result_ventas = await self.session.execute(query)
        costo_ventas = float(result_ventas.scalar() or 0)
        
        query_stock = select(func.avg(ProductoBodega.stock_actual * Producto.costo_unitario))
        result_stock = await self.session.execute(query_stock)
        promedio_stock = float(result_stock.scalar() or 0)
        
        return calcular_rotacion_inventario(costo_ventas, promedio_stock, promedio_stock)

# Función factory
async def get_operational_efficiency_service(session: AsyncSession) -> OperationalEfficiencyService:
    return OperationalEfficiencyService(session)
