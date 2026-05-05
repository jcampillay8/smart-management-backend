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
    exec_service = get_executive_overview_service(db)
    loss_service = get_loss_control_service(db)
    
    # 1. Insight de Sobrestock
    stock_data = await exec_service.get_stock_total_unidades()
    query_ventas = (
        select(func.sum(RegistroStock.cantidad))
        .where(
            RegistroStock.tipo_movimiento.in_([
                TipoMovimiento.CONSUMO, 
                TipoMovimiento.MERMA
            ])
        )
    )
    result_ventas = await db.execute(query_ventas)
    ventas_diarias = float(result_ventas.scalar() or 0.0) / 30
    
    if ventas_diarias > 0:
        dias_inventario = stock_data / ventas_diarias
        if dias_inventario > 60:
            valor_total = await exec_service.get_valor_total_inventario()
            monto_liberable = (dias_inventario - 30) / dias_inventario * valor_total * 0.5
            insights.append({
                'tipo': 'sobrestock',
                'mensaje': f"Tienes stock para {dias_inventario:.0f} días. Considera no comprar más en el próximo pedido para liberar ${monto_liberable:,.2f} en caja.",
                'impacto_estimado': round(monto_liberable, 2)
            })
    
    # 2. Insight de Fuga de Dinero
    anomalias = await loss_service.detect_anomalias(dias_historico=90, dias_actual=7)
    for anomalia in anomalias[:3]:
        insights.append({
            'tipo': 'fuga_dinero',
            'mensaje': f"La merma de '{anomalia['nombre']}' es un {anomalia['diferencia_porcentual']:.1f}% superior al promedio. Revisa procesos de porcionamiento en cocina.",
            'impacto_estimado': round(anomalia['merma_actual'] * 10, 2)
        })
    
    # 3. Insight de Oportunidad
    top_mermas = await exec_service.get_top_mermas_productos(limit=10)
    if top_mermas:
        producto_oportunidad = None
        for p in reversed(top_mermas):
            if p['cantidad_merma'] < 5:
                producto_oportunidad = p
                break
        
        if producto_oportunidad:
            insights.append({
                'tipo': 'oportunidad',
                'mensaje': f"El producto '{producto_oportunidad['nombre']}' tiene mermas muy bajas. Considera destacarlo en el menú o promocionarlo.",
                'impacto_estimado': None
            })
    
    # 4. Conectar con módulo de IA para generar lenguaje natural
    insights = await enhance_with_ai(db, insights)
    
    return insights[:5]


async def enhance_with_ai(db: AsyncSession, insights: List[Dict]) -> List[Dict]:
    """
    Usa el módulo de IA existente para mejorar la redacción de los insights.
    """
    if not insights:
        return insights
    
    prompt = "Mejora la redacción de estos insights empresariales para que suenen más profesionales y accionables:\n"
    for i, insight in enumerate(insights, 1):
        prompt += f"{i}. {insight['mensaje']}\n"
    
    try:
        from src.ai_management.services import ask_oppy_ai
        ai_response = await ask_oppy_ai(
            db=db,
            messages=[{"role": "user", "content": prompt}],
            user_id=1,  # TODO: Obtener user_id real
            caller="ai_insights"
        )
        
        # Si la IA responde, actualizar mensajes
        if ai_response and isinstance(ai_response, str):
            # Por ahora mantenemos los mensajes originales
            # En el futuro se puede parsear la respuesta de la IA
            pass
    except Exception as e:
        print(f"Error al conectar con IA: {e}")
    
    return insights
