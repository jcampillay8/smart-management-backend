# src/reports/executive_overview/ai_insights.py
from typing import List, Dict
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from src.reports.executive_overview.service import get_executive_overview_service
from src.reports.loss_control.service import get_loss_control_service
from src.operations.models import RegistroStock, TipoMovimiento

async def generate_insights(db: AsyncSession) -> List[Dict]:
    """
    Genera insights prescriptivos basados en los datos del Executive Overview.
    Tipos: sobrestock, fuga_dinero, oportunidad
    """
    insights = []
    
    # Obtener servicios
    exec_service: ExecutiveOverviewService = get_executive_overview_service(db)
    loss_service: LossControlService = get_loss_control_service(db)
    
    # 1. Insight de Sobrestock
    stock_data = await exec_service.get_stock_total_unidades()
    # Calcular días de inventario promedio (simplificado)
    query_ventas = select(func.sum(RegistroStock.cantidad)).where(
        RegistroStock.tipo_movimiento.in_([TipMovimiento.CONSUMO, TipoMovimiento.MERMA])
    )
    result_ventas = await db.execute(query_ventas)
    ventas_diarias = float(result_ventas.scalar() or 0.0) / 30  # promedio diario
    
    if ventas_diarias > 0:
        dias_inventario = stock_data / ventas_diarias
        if dias_inventario > 60:
            # Calcular monto liberable (simplificado: 50% del valor del stock excedente)
            valor_total = await exec_service.get_valor_total_inventario()
            monto_liberable = (dias_inventario - 30) / dias_inventario * valor_total * 0.5
            insights.append({
                'tipo': 'sobrestock',
                'mensaje': f"Tienes stock para {dias_inventario:.0f} días. Considera no comprar más en el próximo pedido para liberar ${monto_liberable:,.2f} en caja.",
                'impacto_estimado': round(monto_liberable, 2)
            })
    
    # 2. Insight de Fuga de Dinero (Mermas anómalas)
    anomalias = await loss_service.detect_anomalias(dias_historico=90, dias_actual=7)
    for anomalia in anomalias[:3]:  # Top 3 anomalías
        insights.append({
            'tipo': 'fuga_dinero',
            'mensaje': f"La merma de '{anomalia['nombre']}' es un {anomalia['diferencia_porcentual']:.1f}% superior al promedio. Revisa procesos de porcionamiento en cocina.",
            'impacto_estimado': round(anomalia['merma_actual'] * 10, 2)  # Simplificado: $10 por unidad de merma
        })
    
    # 3. Insight de Oportunidad (simplificado: productos con merma baja y ventas altas)
    top_mermas = await exec_service.get_top_mermas_productos(limit=10)
    if top_mermas:
        # Buscar producto con merma muy baja (primer elemento de la lista invertida)
        producto_oportunidad = None
        for p in reversed(top_mermas):
            if p['cantidad_merma'] < 5:  # Merma baja
                producto_oportunidad = p
                break
        
        if producto_oportunidad:
            insights.append({
                'tipo': 'oportunidad',
                'mensaje': f"El producto '{producto_oportunidad['nombre']}' tiene mermas muy bajas. Considera destacarlo en el menú o promocionarlo.",
                'impacto_estimado': None
            })
    
    return insights[:5]  # Máximo 5 insights
