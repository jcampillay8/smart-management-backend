# src/operations/routers/event_router.py
from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession
from uuid import UUID
from typing import List

from src.database import get_async_session
from src.operations.schemas import EventoCreate, EventoOut
from src.sales.services.event_service import EventService
from src.authentication.dependencies import get_current_user
from src.models import User

router = APIRouter(prefix="/events", tags=["Operations - Events"])

@router.post("/", response_model=EventoOut, status_code=status.HTTP_201_CREATED)
async def create_event(
    event_data: EventoCreate,
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user)
):
    service = EventService(db)
    return await service.create_event(event_data, current_user.id)

@router.get("/", response_model=List[EventoOut])
async def list_events(db: AsyncSession = Depends(get_async_session)):
    service = EventService(db)
    return await service.get_all_events()

@router.post("/{event_id}/execute", response_model=EventoOut)
async def execute_event(
    event_id: UUID,
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user)
):
    service = EventService(db)
    return await service.execute_event(event_id, current_user.id)

@router.delete("/{event_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_event(event_id: UUID, db: AsyncSession = Depends(get_async_session)):
    # Lógica simple de eliminación
    stmt = select(Evento).where(Evento.id == event_id)
    result = await db.execute(stmt)
    evento = result.scalar_one_or_none()
    if evento:
        await db.delete(evento)
        await db.commit()
    return None