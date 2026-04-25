# src/operations/routers/event_router.py
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from uuid import UUID
from typing import List

from src.database import get_async_session
from src.operations.schemas import EventoCreate, EventoUpdate, EventoOut
from src.operations.services.event_service import EventService
from src.models import User
from src.authentication.dependencies import get_current_user

router = APIRouter()

@router.get("/", response_model=List[EventoOut], name="list_events")
async def list_events(db: AsyncSession = Depends(get_async_session)):
    """Lista todos los eventos."""
    return await EventService(db).get_all_events()

@router.post("/", response_model=EventoOut, status_code=status.HTTP_201_CREATED, name="create_event")
async def create_event(
    event_data: EventoCreate, 
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user)
):
    """Crea un evento."""
    return await EventService(db).create_event(event_data, current_user.id)

@router.put("/{event_id}", response_model=EventoOut)
async def update_event(
    event_id: UUID,
    event_data: EventoUpdate,
    db: AsyncSession = Depends(get_async_session)
):
    """Actualiza un evento."""
    return await EventService(db).update_event(event_id, event_data)

@router.delete("/{event_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_event(
    event_id: UUID,
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user)
):
    """Elimina un evento."""
    await EventService(db).delete_event(event_id, current_user.id)

@router.post("/{event_id}/execute", response_model=EventoOut)
async def execute_event(
    event_id: UUID,
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user)
):
    """Ejecuta un evento."""
    return await EventService(db).execute_event(event_id, current_user.id)

@router.patch("/{event_id}/cancel", response_model=EventoOut)
async def cancel_event(event_id: UUID, db: AsyncSession = Depends(get_async_session)):
    """Cancela un evento."""
    return await EventService(db).cancel_event(event_id)

@router.patch("/{event_id}/reactivate", response_model=EventoOut)
async def reactivate_event(event_id: UUID, db: AsyncSession = Depends(get_async_session)):
    """Reactiva un evento."""
    return await EventService(db).reactivate_event(event_id)