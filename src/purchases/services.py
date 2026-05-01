# src/purchases/services.py
from datetime import date, timedelta
from typing import List, Dict
from sqlalchemy import select, func, and_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from src.database import async_session_maker
from src.config import settings
from src.purchases.models import Compra, CompraItem, Proveedor
from src.inventory.models import Producto

class PurchaseService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.schema = settings.DB_SCHEMA

    async def get_fill_rate_by_proveedor(
        self, 
        fecha_inicio: date = None,
        fecha_fin: date = None
    ) -> List[Dict]:
        """
        1. Fill Rate: (cantidad_recibida / cantidad_pedida) * 100 por proveedor
        Nota: cantidad_recibida es el campo 'cantidad' en CompraItem
        """
        if not fecha_inicio:
            fecha_inicio = date.today() - timedelta(days=30)
        if not fecha_fin:
            fecha_fin = date.today()

        # Obtener datos agrupados por proveedor
        query = (
            select(
                Proveedor.id,
                Proveedor.nombre_empresa,
                func.sum(CompraItem.cantidad_pedida).label('total_pedido'),
                func.sum(CompraItem.cantidad).label('total_recibido')
            )
            .join(Compra, Compra.id == CompraItem.compra_id)
            .join(Proveedor, Proveedor.id == Compra.proveedor_id)
            .where(Compra.fecha.between(fecha_inicio, fecha_fin))
            .group_by(Proveedor.id, Proveedor.nombre_empresa)
        )
        
        result = await self.session.execute(query)
        rows = result.all()
        
        fill_rates = []
        for row in rows:
            total_pedido = float(row.total_pedido or 0)
            total_recibido = float(row.total_recibido or 0)
            
            if total_pedido > 0:
                fill_rate = (total_recibido / total_pedido) * 100
            else:
                fill_rate = 0.0
                
            fill_rates.append({
                'proveedor_id': str(row.id),
                'nombre_empresa': row.nombre_empresa,
                'total_pedido': total_pedido,
                'total_recibido': total_recibido,
                'fill_rate': round(fill_rate, 2)
            })
        
        return sorted(fill_rates, key=lambda x: x['fill_rate'])

    async def get_variacion_precios_by_proveedor(
        self, 
        dias_atras: int = 90
    ) -> List[Dict]:
        """
        2. Variación de precios por proveedor
        Compara precios más recientes vs históricos agrupados por proveedor
        """
        fecha_corte = date.today() - timedelta(days=dias_atras)
        
        # Obtener historial de precios con proveedor
        query = (
            select(
                Proveedor.id,
                Proveedor.nombre_empresa,
                Producto.nombre.label('producto_nombre'),
                CompraItem.precio_unitario,
                Compra.fecha
            )
            .join(Compra, Compra.id == CompraItem.compra_id)
            .join(Proveedor, Proveedor.id == Compra.proveedor_id)
            .join(Producto, Producto.id == CompraItem.producto_id)
            .where(Compra.fecha >= fecha_corte)
            .order_by(Proveedor.id, CompraItem.producto_id, Compra.fecha.desc())
        )
        
        result = await self.session.execute(query)
        rows = result.all()
        
        # Procesar para obtener variación por proveedor
        proveedor_data = {}
        for row in rows:
            p_id = str(row.id)
            if p_id not in proveedor_data:
                proveedor_data[p_id] = {
                    'nombre_empresa': row.nombre_empresa,
                    'productos': {}
                }
            
            prod_id = str(row.producto_id) if hasattr(row, 'producto_id') else str(row.id)  # Ajuste
            if prod_id not in proveedor_data[p_id]['productos']:
                proveedor_data[p_id]['productos'][prod_id] = {
                    'nombre': row.producto_nombre,
                    'precios': []
                }
            proveedor_data[p_id]['productos'][prod_id]['precios'].append(float(row.precio_unitario))
        
        variaciones = []
        for p_id, data in proveedor_data.items():
            total_variacion = 0
            count_productos = 0
            
            for prod_id, prod_data in data['productos'].items():
                precios = prod_data['precios']
                if len(precios) >= 2:
                    precio_anterior = precios[-1]
                    precio_actual = precios[0]
                    if precio_anterior > 0:
                        variacion = ((precio_actual - precio_anterior) / precio_anterior) * 100
                        total_variacion += variacion
                        count_productos += 1
            
            promedio_variacion = total_variacion / count_productos if count_productos > 0 else 0
            
            variaciones.append({
                'proveedor_id': p_id,
                'nombre_empresa': data['nombre_empresa'],
                'promedio_variacion_porcentual': round(promedio_variacion, 2),
                'productos_analizados': count_productos
            })
        
        return sorted(variaciones, key=lambda x: abs(x['promedio_variacion_porcentual']), reverse=True)

    async def get_calendario_pagos(
        self, 
        dias_adelante: int = 7
    ) -> List[Dict]:
        """
        3. Calendario de pagos
        Facturas próximas a vencer basadas en Compra.fecha + Proveedor.dias_plazo_pago
        """
        hoy = date.today()
        fecha_limite = hoy + timedelta(days=dias_adelante)
        
        query = (
            select(
                Compra.id,
                Compra.fecha,
                Compra.total,
                Proveedor.nombre_empresa,
                Proveedor.dias_plazo_pago,
                Proveedor.tiempo_entrega_promedio_dias
            )
            .join(Proveedor, Proveedor.id == Compra.proveedor_id)
            .where(
                and_(
                    Compra.proveedor_id.isnot(None),  # Simplificado
                    Compra.estado != 'pagado'  # Asumiendo que hay un campo estado
                )
            )
        )
        
        result = await self.session.execute(query)
        rows = result.all()
        
        pagos = []
        for row in rows:
            # Calcular fecha vencimiento
            dias_plazo = row.dias_plazo_pago or 0
            fecha_vencimiento = row.fecha + timedelta(days=dias_plazo)
            
            # Solo incluir si vence en el rango
            if hoy <= fecha_vencimiento <= fecha_limite:
                dias_restantes = (fecha_vencimiento - hoy).days
                
                pagos.append({
                    'compra_id': str(row.id),
                    'proveedor_nombre': row.nombre_empresa,
                    'fecha_compra': row.fecha.isoformat(),
                    'fecha_vencimiento': fecha_vencimiento.isoformat(),
                    'monto': float(row.total),
                    'dias_restantes': dias_restantes,
                    'estado': 'proximo' if dias_restantes <= 3 else 'programado'
                })
        
        return sorted(pagos, key=lambda x: x['dias_restantes'])

    async def create_purchase(self, purchase_data: dict, items: list, user_id: int):
        """Create a new purchase with items"""
        from src.inventory.models import ProductoBodega
        from sqlalchemy.orm import selectinload
        
        db_purchase = Compra(
            **{k: v for k, v in purchase_data.items() if k != 'items'},
            usuario_id=user_id
        )
        self.session.add(db_purchase)
        await self.session.flush()
        
        for item in items:
            db_item = CompraItem(
                **item,
                compra_id=db_purchase.id
            )
            self.session.add(db_item)
            
            # Update stock if purchase is completed
            if purchase_data.get('estado') == "realizada" and item.get('bodega_id'):
                stmt = select(ProductoBodega).where(
                    ProductoBodega.producto_id == item['producto_id'],
                    ProductoBodega.bodega_id == item['bodega_id']
                )
                result = await self.session.execute(stmt)
                pb = result.scalar_one_or_none()
                if pb:
                    pb.stock_actual += item['cantidad']
                else:
                    new_pb = ProductoBodega(
                        producto_id=item['producto_id'],
                        bodega_id=item['bodega_id'],
                        stock_actual=item['cantidad']
                    )
                    self.session.add(new_pb)
        
        await self.session.commit()
        stmt = select(Compra).options(selectinload(Compra.items)).where(Compra.id == db_purchase.id)
        result = await self.session.execute(stmt)
        return result.scalar_one()

    async def get_purchase(self, purchase_id: str):
        """Get a purchase by ID"""
        from sqlalchemy.orm import selectinload
        stmt = select(Compra).options(selectinload(Compra.items)).where(Compra.id == purchase_id)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def update_purchase(self, purchase_id: str, update_data: dict):
        """Update a purchase"""
        from sqlalchemy.orm import selectinload
        stmt = select(Compra).options(selectinload(Compra.items)).where(Compra.id == purchase_id)
        result = await self.session.execute(stmt)
        db_purchase = result.scalar_one_or_none()
        
        if not db_purchase:
            return None
            
        for key, value in update_data.items():
            setattr(db_purchase, key, value)
        
        await self.session.commit()
        await self.session.refresh(db_purchase)
        return db_purchase

    async def mark_pedido(self, purchase_id: str):
        """Mark purchase as ordered"""
        return await self.update_purchase(purchase_id, {'pedido_realizado': True})

    async def mark_received(self, purchase_id: str):
        """Mark purchase as received and update stock"""
        from src.inventory.models import ProductoBodega
        
        stmt = select(Compra).options(selectinload(Compra.items)).where(Compra.id == purchase_id)
        result = await self.session.execute(stmt)
        db_purchase = result.scalar_one_or_none()
        
        if not db_purchase:
            return None
            
        db_purchase.estado = "realizada"
        
        for item in db_purchase.items:
            if item.bodega_id:
                stock_stmt = select(ProductoBodega).where(
                    ProductoBodega.producto_id == item.producto_id,
                    ProductoBodega.bodega_id == item.bodega_id
                )
                stock_result = await self.session.execute(stock_stmt)
                pb = stock_result.scalar_one_or_none()
                if pb:
                    pb.stock_actual += item.cantidad
                else:
                    new_pb = ProductoBodega(
                        producto_id=item.producto_id,
                        bodega_id=item.bodega_id,
                        stock_actual=item.cantidad
                    )
                    self.session.add(new_pb)
        
        await self.session.commit()
        await self.session.refresh(db_purchase)
        return db_purchase

    async def cancel_purchase(self, purchase_id: str):
        """Cancel a purchase"""
        return await self.update_purchase(purchase_id, {'estado': "cancelada"})

    async def restore_purchase(self, purchase_id: str):
        """Restore a cancelled purchase"""
        return await self.update_purchase(purchase_id, {'estado': "pendiente", 'pedido_realizado': False})

    async def list_purchases(self) -> List[Dict]:
        """Lista todas las compras con sus items (para el endpoint GET /purchases/)"""
        query = (
            select(Compra)
            .options(selectinload(Compra.items))
            .order_by(Compra.fecha.desc())
        )
        result = await self.session.execute(query)
        compras = result.scalars().all()
        
        # Convertir a diccionarios para el response
        return [
            {
                'id': str(c.id),
                'usuario_id': c.usuario_id,
                'estado': c.estado,
                'pedido_realizado': c.pedido_realizado,
                'fecha': c.fecha.isoformat() if c.fecha else '',
                'total': float(c.total),
                'factura_url': c.factura_url,
                'proveedor_id': str(c.proveedor_id) if c.proveedor_id else None,
                'notas': c.notas,
                'items': [
                    {
                        'id': str(i.id),
                        'producto_id': str(i.producto_id),
                        'bodega_id': str(i.bodega_id) if i.bodega_id else None,
                        'cantidad': float(i.cantidad),
                        'cantidad_pedida': float(i.cantidad_pedida),
                        'precio_unitario': float(i.precio_unitario)
                    } for i in c.items
                ]
            } for c in compras
        ]

# Factory function
async def get_purchase_service(session: AsyncSession) -> PurchaseService:
    return PurchaseService(session)
