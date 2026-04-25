# src/operations/services/event_service.py
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from fastapi import HTTPException
from uuid import UUID
import logging

from src.operations.models import Evento, EventoProducto
from src.operations.schemas import EventoCreate, EventoUpdate

logger = logging.getLogger(__name__)

class EventService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_all_events(self):
        """Lista todos los eventos - sin relaciones."""
        try:
            result = await self.db.execute(select(Evento))
            return list(result.scalars().all())
        except Exception as e:
            logger.error(f"Error getting events: {e}")
            return []

    async def create_event(self, event_data, user_id: int):
        """Crea un evento."""
        try:
            nuevo = Evento(
                nombre=event_data.nombre,
                fecha=event_data.fecha,
                valor_publico=event_data.valor_publico,
                usuario_id=user_id
            )
            self.db.add(nuevo)
            await self.db.commit()
            await self.db.refresh(nuevo)
            return nuevo
        except Exception as e:
            logger.error(f"Error creating event: {e}")
            await self.db.rollback()
            raise HTTPException(500, str(e))

    async def get_event_by_id(self, event_id: UUID):
        """Obtiene un evento por ID."""
        result = await self.db.execute(select(Evento).where(Evento.id == event_id))
        return result.scalar_one_or_none()

    async def update_event(self, event_id: UUID, event_data):
        """Actualiza un evento."""
        evento = await self.get_event_by_id(event_id)
        if not evento:
            raise HTTPException(404, "Evento no encontrado")
        if evento.ejecutado or evento.cancelado:
            raise HTTPException(400, "No se puede editar")
        
        if event_data.nombre:
            evento.nombre = event_data.nombre
        if event_data.fecha:
            evento.fecha = event_data.fecha
        if event_data.valor_publico is not None:
            evento.valor_publico = event_data.valor_publico
        
        await self.db.commit()
        await self.db.refresh(evento)
        return evento

    async def delete_event(self, event_id: UUID, user_id: int):
        """Elimina un evento."""
        evento = await self.get_event_by_id(event_id)
        if not evento:
            raise HTTPException(404, "Evento no encontrado")
        await self.db.delete(evento)
        await self.db.commit()

    async def execute_event(self, event_id: UUID, user_id: int):
        """Ejecuta un evento (marca como ejecutado)."""
        evento = await self.get_event_by_id(event_id)
        if not evento or evento.ejecutado:
            raise HTTPException(400, "Evento no válido o ya ejecutado")
        evento.ejecutado = True
        await self.db.commit()
        return evento

    async def cancel_event(self, event_id: UUID):
        """Cancela un evento."""
        evento = await self.get_event_by_id(event_id)
        if not evento:
            raise HTTPException(404, "Evento no encontrado")
        evento.cancelado = True
        evento.ejecutado = False
        await self.db.commit()
        return evento

    async def reactivate_event(self, event_id: UUID):
        """Reactiva un evento cancelado."""
        evento = await self.get_event_by_id(event_id)
        if not evento:
            raise HTTPException(404, "Evento no encontrado")
        if not evento.cancelado:
            raise HTTPException(400, "El evento no está cancelado")
        evento.cancelado = False
        evento.ejecutado = False
        await self.db.commit()
        return evento