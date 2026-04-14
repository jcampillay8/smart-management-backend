# src/authentication/user_details_router.py
from fastapi import APIRouter, Depends, HTTPException, status
from typing import Annotated
import logging

from src.models import User
from src.dependencies import get_current_user, get_async_session
from sqlalchemy.ext.asyncio import AsyncSession
from src.authentication.schemas import UserPublicSchema

logger = logging.getLogger(__name__)

user_details_router = APIRouter(prefix="/user", tags=["User Details"])

@user_details_router.get("/profile/", response_model=UserPublicSchema)
async def read_current_user_profile(
    current_user: Annotated[User, Depends(get_current_user)],
):
    """
    Retorna el perfil del usuario actual.
    El esquema UserPublicSchema se encarga de inyectar 'show_tour' si no existe.
    """
    return current_user 

@user_details_router.post("/accept-terms/", status_code=status.HTTP_200_OK)
async def accept_terms(
    current_user: Annotated[User, Depends(get_current_user)],
    db_session: Annotated[AsyncSession, Depends(get_async_session)],
):
    """
    Endpoint simple para marcar que el usuario aceptó los términos.
    No crea bots ni chats por ahora.
    """
    if current_user.has_accepted_terms:
        return {"message": "Términos ya aceptados previamente."}

    try:
        current_user.has_accepted_terms = True
        # Solo actualizamos el flag en la base de datos
        await db_session.commit()
        return {"message": "Términos aceptados exitosamente."}
        
    except Exception as e:
        await db_session.rollback()
        logger.error(f"Error al aceptar términos para usuario {current_user.id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error interno al procesar la solicitud."
        )