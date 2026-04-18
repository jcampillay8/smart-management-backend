# src/operations/routers/event_router.py
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from uuid import UUID
from typing import List

from src.database import get_async_session
from src.operations.schemas import EventoCreate, EventoOut
from src.operations.services.event_service import EventService
from src.authentication.dependencies import get_current_user # Ajusta según tu auth
from src.models import User

router = APIRouter()

@router.post("/", response_model=EventoOut, status_code=status.HTTP_201_CREATED)
async def create_event(
    event_data: EventoCreate, 
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user)
):
    """Crea un evento y procesa automáticamente productos y recetas."""
    return await EventService(db).create_event(event_data, current_user.id)

@router.get("/", response_model=List[EventoOut])
async def list_events(
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user)
):
    """Lista todos los eventos (aquí podrías filtrar por usuario o rol)."""
    # Nota: Si quieres cargar los productos, asegúrate de que el modelo tenga lazy='joined' 
    # o haz el join explícito en el service.
    return await EventService(db).get_all_events()

@router.post("/{event_id}/execute", response_model=EventoOut)
async def execute_event(
    event_id: UUID,
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user)
):
    """
    Consolida el evento: genera los registros de stock de consumo real
    y marca el evento como ejecutado.
    """
    return await EventService(db).execute_event(event_id, current_user.id)

@router.patch("/{event_id}/cancel", response_model=EventoOut)
async def cancel_event(
    event_id: UUID,
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user)
):
    """Cancela un evento y revierte consumos si ya fue ejecutado."""
    return await EventService(db).cancel_event(event_id)