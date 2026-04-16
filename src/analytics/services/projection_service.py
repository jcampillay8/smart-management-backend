# src/analytics/services/projection_service.py
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_
from datetime import date
from uuid import UUID
from typing import List, Dict

from src.inventory.models import Producto, RegistroStock, ProductoBodega, Bodega
from src.operations.models import Evento, Receta, RecetaIngrediente
from ..schemas import EventProjectionAlert

class ProjectionService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_event_projections(self) -> List[EventProjectionAlert]:
        """
        Analiza eventos futuros y proyecta si el stock actual en la bodega 
        específica es suficiente, considerando recetas e ingredientes.
        """
        # 1. Obtener eventos no ejecutados ni cancelados
        stmt_eventos = select(Evento).where(
            and_(Evento.ejecutado == False, Evento.cancelado == False)
        ).order_by(Evento.fecha.asc())
        
        result_eventos = await self.db.execute(stmt_eventos)
        eventos = result_eventos.scalars().all()
        
        alertas = []

        for evento in eventos:
            # 2. Obtener los productos necesarios para este evento (vía recetas)
            # Nota: Esto asume una relación o tabla asociativa evento_recetas
            # Simulamos el cálculo de explosión de materiales (MRP)
            necesidades = await self._get_event_requirements(evento.id)
            
            for req in necesidades:
                # 3. Calcular stock actual disponible en la bodega específica
                stock_actual = await self._get_current_stock(req["producto_id"], req["bodega_id"])
                
                # 4. Verificar disponibilidad por fecha de vencimiento (Lógica de Analiticas.tsx)
                # Solo contamos stock que venza DESPUÉS de la fecha del evento
                stock_valido = await self._get_valid_stock_for_date(
                    req["producto_id"], 
                    req["bodega_id"], 
                    evento.fecha
                )
                
                stock_proyectado = stock_valido - req["cantidad_necesaria"]
                
                if stock_proyectado < 0:
                    # Buscar si hay stock en otras bodegas para sugerir (alt_suggestion)
                    sugerencia = await self._find_alternative_stock(
                        req["producto_id"], 
                        req["bodega_id"], 
                        abs(stock_proyectado)
                    )
                    
                    alertas.append(EventProjectionAlert(
                        evento_id=evento.id,
                        evento_nombre=evento.nombre,
                        fecha_evento=evento.fecha,
                        producto_nombre=req["producto_nombre"],
                        bodega_nombre=req["bodega_nombre"],
                        stock_proyectado=stock_proyectado,
                        cantidad_necesaria=req["cantidad_necesaria"],
                        insuficiente=True,
                        sugerencia_alternativa=sugerencia
                    ))
                
        return alertas

    async def _get_event_requirements(self, evento_id: UUID) -> List[Dict]:
        """
        Explota las recetas del evento para obtener la lista total de 
        ingredientes, cantidades y sus bodegas de origen.
        """
        # Esta es una simplificación de la lógica de 'evento_productos' y 'recetas'
        # que manejas en el frontend.
        # [Implementar lógica de JOIN entre Evento -> Receta -> Ingrediente]
        return [] # Retornaría lista de {producto_id, bodega_id, cantidad_necesaria, ...}

    async def _get_current_stock(self, producto_id: UUID, bodega_id: UUID) -> float:
        stmt = select(func.sum(RegistroStock.cantidad)).where(
            and_(
                RegistroStock.producto_id == producto_id,
                RegistroStock.bodega_id == bodega_id
            )
        )
        res = await self.db.execute(stmt)
        return res.scalar() or 0.0

    async def _get_valid_stock_for_date(self, p_id: UUID, b_id: UUID, fecha_limite: date) -> float:
        """
        Calcula stock que no esté vencido para la fecha del evento.
        Filtra registros donde fecha_vencimiento sea >= fecha_evento o NULL.
        """
        stmt = select(func.sum(RegistroStock.cantidad)).where(
            and_(
                RegistroStock.producto_id == p_id,
                RegistroStock.bodega_id == b_id,
                (RegistroStock.fecha_vencimiento >= fecha_limite) | (RegistroStock.fecha_vencimiento == None)
            )
        )
        res = await self.db.execute(stmt)
        return res.scalar() or 0.0

    async def _find_alternative_stock(self, p_id: UUID, b_original_id: UUID, deficit: float) -> str:
        """
        Busca si otras bodegas tienen el producto para sugerir un traslado.
        """
        stmt = select(Bodega.nombre, func.sum(RegistroStock.cantidad)).join(
            RegistroStock, RegistroStock.bodega_id == Bodega.id
        ).where(
            and_(
                RegistroStock.producto_id == p_id,
                Bodega.id != b_original_id
            )
        ).group_by(Bodega.nombre).having(func.sum(RegistroStock.cantidad) > 0)
        
        res = await self.db.execute(stmt)
        alts = res.all()
        
        if not alts:
            return "No hay stock disponible en otras bodegas."
        
        sug = ". ".join([f"Hay {cant} en {nom}" for nom, cant in alts])
        return f"Sugerencia: {sug}"