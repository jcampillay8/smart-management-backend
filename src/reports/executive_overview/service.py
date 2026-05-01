# src/reports/executive_overview/service.py
from datetime import date, timedelta
from typing import List, Optional, Dict
from sqlalchemy import select, func, and_
from sqlalchemy.ext.asyncio import AsyncSession

from src.database import async_session_maker
from src.config import settings
from src.inventory.models import Producto, ProductoBodega, Bodega
from src.operations.models import RegistroStock, TipoMovimiento, MotivoMerma 
from src.purchases.models import Compra, Proveedor
from src.sales.models import VentaReceta, Receta

class ExecutiveOverviewService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.schema = settings.DB_SCHEMA

    async def get_valor_total_inventario(self, bodega_id: Optional[str] = None) -> float:
        """Cálculo de valor total del inventario: sum(stock_actual * costo_unitario)"""
        query = select(
            func.sum(ProductoBodega.stock_actual * Producto.costo_unitario)
        ).join(Producto, Producto.id == ProductoBodega.producto_id)
        
        if bodega_id:
            query = query.where(ProductoBodega.bodega_id == bodega_id)
            
        result = await self.session.execute(query)
        return float(result.scalar() or 0.0)

    async def get_porcentaje_merma(
        self, 
        fecha_inicio: Optional[date] = None, 
        fecha_fin: Optional[date] = None
    ) -> float:
        """Cálculo de % de merma: (merma_total / (merma_total + stock_actual)) * 100"""
        # Obtener merma total (salidas con motivo_merma)
        query_merma = select(func.sum(RegistroStock.cantidad)).where(
            and_(
                RegistroStock.tipo_movimiento == TipoMovimiento.MERMA,
                RegistroStock.motivo_merma.isnot(None)
            )
        )
        
        if fecha_inicio:
            query_merma = query_merma.where(RegistroStock.fecha_recuento >= fecha_inicio)
        if fecha_fin:
            query_merma = query_merma.where(RegistroStock.fecha_recuento <= fecha_fin)
            
        result_merma = await self.session.execute(query_merma)
        merma_total = float(result_merma.scalar() or 0.0)
        
        if merma_total == 0:
            return 0.0
            
        # Obtener stock actual total
        query_stock = select(func.sum(ProductoBodega.stock_actual))
        result_stock = await self.session.execute(query_stock)
        stock_actual = float(result_stock.scalar() or 0.0)
        
        # Calcular porcentaje
        if (merma_total + stock_actual) == 0:
            return 0.0
        return (merma_total / (merma_total + stock_actual)) * 100

    async def get_top_mermas_productos(self, limit: int = 5) -> List[Dict]:
        """Top N productos con más merma"""
        query = (
            select(
                RegistroStock.producto_id,
                Producto.nombre,
                func.sum(RegistroStock.cantidad).label('total_merma'),
                RegistroStock.motivo_merma
            )
            .join(Producto, Producto.id == RegistroStock.producto_id)
            .where(
                and_(
                    RegistroStock.tipo_movimiento == TipoMovimiento.MERMA,
                    RegistroStock.motivo_merma.isnot(None)
                )
            )
            .group_by(RegistroStock.producto_id, Producto.nombre, RegistroStock.motivo_merma)
            .order_by(func.sum(RegistroStock.cantidad).desc())
            .limit(limit)
        )
        
        result = await self.session.execute(query)
        rows = result.all()
        
        # Agrupar por producto para obtener motivo principal
        productos_dict = {}
        for row in rows:
            p_id = str(row.producto_id)
            if p_id not in productos_dict:
                productos_dict[p_id] = {
                    'producto_id': p_id,
                    'nombre': row.nombre,
                    'cantidad_merma': 0.0,
                    'motivo_principal': str(row.motivo_merma) if row.motivo_merma else 'sin_motivo'
                }
            productos_dict[p_id]['cantidad_merma'] += float(row.total_merma)
        
        return list(productos_dict.values())[:limit]

    async def get_rotacion_inventario(
        self, 
        fecha_inicio: Optional[date] = None, 
        fecha_fin: Optional[date] = None
    ) -> float:
        """Velocidad de rotación: Costo_Ventas / Promedio_Inventario"""
        if not fecha_inicio:
            fecha_inicio = date.today() - timedelta(days=30)
        if not fecha_fin:
            fecha_fin = date.today()
            
        # Costo de ventas (asumiendo que es la suma de recetas vendidas * costo de receta)
        # Por ahora usamos registros de salida/consumo como aproximación
        query_ventas = (
            select(func.sum(RegistroStock.cantidad * Producto.costo_unitario))
            .join(Producto, Producto.id == RegistroStock.producto_id)
            .where(
                and_(
                    RegistroStock.fecha_recuento.between(fecha_inicio, fecha_fin),
                    or_(
                        RegistroStock.tipo_movimiento == TipoMovimiento.CONSUMO,
                        RegistroStock.tipo_movimiento == TipoMovimiento.MERMA
                    )
                )
            )
        )
        
        result_ventas = await self.session.execute(query_ventas)
        costo_ventas = float(result_ventas.scalar() or 0.0)
        
        # Inventario promedio (simplificado: promedio entre inicio y fin)
        query_stock_inicio = select(func.sum(ProductoBodega.stock_actual * Producto.costo_unitario))
        query_stock_fin = select(func.sum(ProductoBodega.stock_actual * Producto.costo_unitario))
        
        result_inicio = await self.session.execute(query_stock_inicio)
        result_fin = await self.session.execute(query_stock_fin)
        
        stock_inicio = float(result_inicio.scalar() or 0.0)
        stock_fin = float(result_fin.scalar() or 0.0)
        promedio_inventario = (stock_inicio + stock_fin) / 2
        
        if promedio_inventario == 0:
            return 0.0
            
        return costo_ventas / promedio_inventario

    async def get_resumen_general(
        self, 
        bodega_id: Optional[str] = None,
        fecha_inicio: Optional[date] = None,
        fecha_fin: Optional[date] = None
    ) -> Dict:
        """Endpoint principal: Combina todos los bloques del resumen ejecutivo"""
        if not fecha_inicio:
            fecha_inicio = date.today() - timedelta(days=30)
        if not fecha_fin:
            fecha_fin = date.today()
        
        # Bloque 1: Resumen General
        valor_total = await self.get_valor_total_inventario(bodega_id)
        porcentaje_merma = await self.get_porcentaje_merma(fecha_inicio, fecha_fin)
        stock_unidades = await self.get_stock_total_unidades()
        
        # Bloque 2: Visión Financiera
        total_compras = await self.get_compras_periodo(fecha_inicio, fecha_fin)
        total_ventas = await self.get_ventas_periodo(fecha_inicio, fecha_fin)
        
        # Bloque 3: Control de Pérdidas (Top 5)
        top_mermas = await self.get_top_mermas_productos(limit=5)
        
        # Bloque 4: Operación y Eficiencia
        rotacion_promedio = await self.get_rotacion_promedio_general()
        productos_bajo_stock = await self.get_productos_bajo_stock()
        
        return {
            'valor_total_inventario': round(valor_total, 2),
            'porcentaje_merma': round(porcentaje_merma, 2),
            'stock_total_unidades': round(stock_unidades, 2),
            'total_compras_periodo': round(total_compras, 2),
            'total_ventas_periodo': round(total_ventas, 2),
            'top_mermas_productos': top_mermas,
            'rotacion_promedio_general': round(rotacion_promedio, 2),
            'productos_bajo_stock': productos_bajo_stock
        }

    async def get_stock_total_unidades(self) -> float:
        """Total de unidades en inventario"""
        query = select(func.sum(ProductoBodega.stock_actual))
        result = await self.session.execute(query)
        return float(result.scalar() or 0.0)

    async def get_compras_periodo(
        self, 
        fecha_inicio: Optional[date] = None, 
        fecha_fin: Optional[date] = None
    ) -> float:
        """Total de compras en el período"""
        query = select(func.sum(Compra.total))
        
        if fecha_inicio:
            query = query.where(Compra.fecha >= fecha_inicio)
        if fecha_fin:
            query = query.where(Compra.fecha <= fecha_fin)
            
        result = await self.session.execute(query)
        return float(result.scalar() or 0.0)

    async def get_ventas_periodo(
        self, 
        fecha_inicio: Optional[date] = None, 
        fecha_fin: Optional[date] = None
    ) -> float:
        """Total de ventas en el período (simplificado: suma de ventas de recetas)"""
        # Necesitamos join con Receta para obtener precio
        query = (
            select(func.sum(VentaReceta.cantidad * VentaReceta.precio_unitario))
        )
        
        if fecha_inicio or fecha_fin:
            # Aquí asumimos que hay un campo fecha en VentaReceta, sino usaríamos otro enfoque
            pass  # Por ahora retornamos 0, hay que ajustar según modelo real
            
        result = await self.session.execute(query)
        return float(result.scalar() or 0.0)

    async def get_productos_bajo_stock(self) -> List[Dict]:
        """Productos por debajo de stock mínimo"""
        query = (
            select(
                Producto.id,
                Producto.nombre,
                ProductoBodega.stock_actual,
                ProductoBodega.stock_minimo,
                Bodega.nombre.label('bodega_nombre')
            )
            .join(ProductoBodega, ProductoBodega.producto_id == Producto.id)
            .join(Bodega, Bodega.id == ProductoBodega.bodega_id)
            .where(ProductoBodega.stock_actual <= ProductoBodega.stock_minimo)
        )
        
        result = await self.session.execute(query)
        rows = result.all()
        
        return [
            {
                'producto_id': str(row.id),
                'nombre': row.nombre,
                'stock_actual': float(row.stock_actual),
                'stock_minimo': float(row.stock_minimo),
                'bodega_nombre': row.bodega_nombre
            }
            for row in rows
        ]

# Función factory para obtener el servicio
async def get_executive_overview_service(session: AsyncSession) -> ExecutiveOverviewService:
    return ExecutiveOverviewService(session)
