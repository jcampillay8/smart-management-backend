# src/reports/loss_control/service.py
from datetime import date, timedelta
from typing import List, Dict
from sqlalchemy import select, func, and_
# from sqlalchemy.orm import joinedload  # Pendiente si se necesita carga eager
from sqlalchemy.ext.asyncio import AsyncSession

from src.database import async_session_maker
from src.config import settings
from src.operations.models import RegistroStock, TipoMovimiento, MotivoMerma
from src.inventory.models import Producto, Bodega

class LossControlService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.schema = settings.DB_SCHEMA

    async def get_mermas_by_motivo(
        self, 
        fecha_inicio: date = None, 
        fecha_fin: date = None,
        bodega_id: str = None
    ) -> List[Dict]:
        """1. Agregación de mermas por motivo para gráfico de torta"""
        query = (
            select(
                RegistroStock.motivo_merma,
                func.sum(RegistroStock.cantidad).label('total')
            )
            .where(
                and_(
                    RegistroStock.tipo_movimiento == TipoMovimiento.MERMA,
                    RegistroStock.motivo_merma.isnot(None)
                )
            )
            .group_by(RegistroStock.motivo_merma)
        )
        
        if fecha_inicio:
            query = query.where(RegistroStock.fecha_recuento >= fecha_inicio)
        if fecha_fin:
            query = query.where(RegistroStock.fecha_recuento <= fecha_fin)
        if bodega_id:
            query = query.where(RegistroStock.bodega_id == bodega_id)
            
        result = await self.session.execute(query)
        rows = result.all()
        
        # 1. Calcular total general usando valor absoluto para porcentajes correctos
        total_general = sum(abs(float(row.total)) for row in rows)
        
        mermas = []
        for row in rows:
            # 2. Aplicar abs() para eliminar signos negativos técnicos
            cantidad = abs(float(row.total))
            
            # 3. Calcular porcentaje sobre la base absoluta
            porcentaje = (cantidad / total_general * 100) if total_general > 0 else 0
            
            mermas.append({
                # 4. Limpiar el nombre del motivo (ej: "CADUCIDAD" en lugar de "MotivoMerma.CADUCIDAD")
                'motivo': str(row.motivo_merma).split('.')[-1] if row.motivo_merma else 'sin_motivo',
                'cantidad_total': cantidad,
                'porcentaje': round(porcentaje, 2)
            })
        
        # 5. Ordenar por cantidad de mayor a menor para que el gráfico sea más legible
        return sorted(mermas, key=lambda x: x['cantidad_total'], reverse=True)

    async def get_top_mermas_by_producto(
        self, 
        limit: int = 10,
        fecha_inicio: date = None,
        fecha_fin: date = None,
        bodega_id: str = None
    ) -> List[Dict]:
        """2. Agregación de mermas por producto (Top N)"""
        query = (
            select(
                RegistroStock.producto_id,
                Producto.nombre,
                func.sum(RegistroStock.cantidad).label('total_merma'),
                Bodega.nombre.label('bodega_nombre')
            )
            .join(Producto, Producto.id == RegistroStock.producto_id)
            .outerjoin(Bodega, Bodega.id == RegistroStock.bodega_id)
            .where(
                and_(
                    RegistroStock.tipo_movimiento == TipoMovimiento.MERMA,
                    RegistroStock.motivo_merma.isnot(None)
                )
            )
            .group_by(RegistroStock.producto_id, Producto.nombre, Bodega.nombre)
            .order_by(func.sum(RegistroStock.cantidad).desc())
            .limit(limit)
        )
        
        if fecha_inicio:
            query = query.where(RegistroStock.fecha_recuento >= fecha_inicio)
        if fecha_fin:
            query = query.where(RegistroStock.fecha_recuento <= fecha_fin)
        if bodega_id:
            query = query.where(RegistroStock.bodega_id == bodega_id)
            
        result = await self.session.execute(query)
        rows = result.all()
        
        return [
            {
                'producto_id': str(row.producto_id),
                'nombre': row.nombre,
                'cantidad_total': float(row.total_merma),
                'bodega_nombre': row.bodega_nombre
            }
            for row in rows
        ]

    async def detect_anomalias(
        self, 
        dias_historico: int = 90,
        dias_actual: int = 7,
        threshold_desviacion: float = 2.0,
        bodega_id: str = None
    ) -> List[Dict]:
        """
        3. Detección de anomalías: 
        Compara merma reciente vs histórica usando desviación estándar
        """
        hoy = date.today()
        fecha_inicio_hist = hoy - timedelta(days=dias_historico)
        fecha_inicio_actual = hoy - timedelta(days=dias_actual)
        
        # Obtener promedio y desviación histórica por producto
        query_hist = (
            select(
                RegistroStock.producto_id,
                Producto.nombre,
                func.avg(RegistroStock.cantidad).label('promedio'),
                func.stddev(RegistroStock.cantidad).label('desviacion')
            )
            .join(Producto, Producto.id == RegistroStock.producto_id)
            .where(
                and_(
                    RegistroStock.tipo_movimiento == TipoMovimiento.MERMA,
                    RegistroStock.fecha_recuento >= fecha_inicio_hist,
                    RegistroStock.fecha_recuento < fecha_inicio_actual,
                    RegistroStock.motivo_merma.isnot(None)
                )
            )
            .group_by(RegistroStock.producto_id, Producto.nombre)
        )
        
        if bodega_id:
            query_hist = query_hist.where(RegistroStock.bodega_id == bodega_id)
            
        result_hist = await self.session.execute(query_hist)
        hist_data = {str(row.producto_id): row for row in result_hist.all()}
        
        # Obtener merma actual por producto
        query_actual = (
            select(
                RegistroStock.producto_id,
                Producto.nombre,
                func.sum(RegistroStock.cantidad).label('merma_actual')
            )
            .join(Producto, Producto.id == RegistroStock.producto_id)
            .where(
                and_(
                    RegistroStock.tipo_movimiento == TipoMovimiento.MERMA,
                    RegistroStock.fecha_recuento >= fecha_inicio_actual,
                    RegistroStock.motivo_merma.isnot(None)
                )
            )
            .group_by(RegistroStock.producto_id, Producto.nombre)
        )
        
        if bodega_id:
            query_actual = query_actual.where(RegistroStock.bodega_id == bodega_id)
        
        result_actual = await self.session.execute(query_actual)
        anomalias = []
        
        for row in result_actual.all():
            p_id = str(row.producto_id)
            if p_id in hist_data:
                hist_row = hist_data[p_id]
                promedio = abs(float(hist_row.promedio or 0))
                # Capturamos la desviación asegurando que no sea None
                desviacion = abs(float(hist_row.desviacion or 0))
                merma_actual = abs(float(row.merma_actual))
                
                # 1. Mejora: Diferencia porcentual con protección contra división por cero
                if promedio > 0:
                    diferencia_porcentual = ((merma_actual - promedio) / promedio) * 100
                else:
                    diferencia_porcentual = 100.0 if merma_actual > 0 else 0.0
                
                # 2. Mejora: Lógica de Umbral Inteligente
                # Si la desviación es 0 (pocos datos), usamos un umbral basado en el promedio 
                # para que el sistema no sea "ciego" ante saltos masivos.
                if desviacion == 0:
                    # Si no hay desviación, alertar si la merma actual supera, por ejemplo, 
                    # 1.5 veces el promedio histórico (ajustable).
                    umbral = promedio * 1.5 
                else:
                    umbral = promedio + (threshold_desviacion * desviacion)
                
                # 3. Detectar anomalía
                if merma_actual > umbral:
                    anomalias.append({
                        'producto_id': p_id,
                        'nombre': row.nombre,
                        'merma_actual': round(merma_actual, 2),
                        'promedio_historico': round(promedio, 2),
                        'desviacion': round(desviacion, 2),
                        'diferencia_porcentual': round(diferencia_porcentual, 2),
                        'mensaje': "Salto brusco sin historial de variabilidad" if desviacion == 0 else "Desviación estadística crítica"
                    })
        
        return sorted(anomalias, key=lambda x: x['diferencia_porcentual'], reverse=True)

# Función factory
def get_loss_control_service(session: AsyncSession) -> LossControlService:
    return LossControlService(session)
