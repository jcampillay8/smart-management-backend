# src/authentication/user_details_router.py
from fastapi import APIRouter, Depends, HTTPException, status
from typing import Annotated
import logging

from src.models import User, AppRole, PermisoMerma
from src.dependencies import get_current_user, get_async_session, require_role
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select as sa_select
from src.authentication.schemas import UserPublicSchema
from pydantic import BaseModel

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

class RoleUpdateSchema(BaseModel):
    role: AppRole

@user_details_router.put("/admin/{user_id}/role", status_code=status.HTTP_200_OK)
async def update_user_role(
    user_id: int,
    data: RoleUpdateSchema,
    current_admin: Annotated[User, Depends(require_role([AppRole.ADMIN]))],
    db_session: Annotated[AsyncSession, Depends(get_async_session)],
):
    user = await db_session.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")
    
    user.role = data.role
    await db_session.commit()
    return {"message": f"Rol actualizado a {data.role.value}"}

@user_details_router.post("/admin/{user_id}/merma-permission", status_code=status.HTTP_200_OK)
async def add_merma_permission(
    user_id: int,
    current_admin: Annotated[User, Depends(require_role([AppRole.ADMIN]))],
    db_session: Annotated[AsyncSession, Depends(get_async_session)],
):
    user = await db_session.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")
        
    query = sa_select(PermisoMerma).where(PermisoMerma.user_id == user_id)
    result = await db_session.execute(query)
    if result.scalar_one_or_none():
        return {"message": "El usuario ya tiene este permiso"}
        
    nuevo_permiso = PermisoMerma(user_id=user_id, otorgado_por=current_admin.id)
    db_session.add(nuevo_permiso)
    await db_session.commit()
    return {"message": "Permiso de merma otorgado"}

@user_details_router.delete("/admin/{user_id}/merma-permission", status_code=status.HTTP_200_OK)
async def remove_merma_permission(
    user_id: int,
    current_admin: Annotated[User, Depends(require_role([AppRole.ADMIN]))],
    db_session: Annotated[AsyncSession, Depends(get_async_session)],
):
    query = sa_select(PermisoMerma).where(PermisoMerma.user_id == user_id)
    result = await db_session.execute(query)
    permiso = result.scalar_one_or_none()
    
    if not permiso:
        return {"message": "El usuario no tenía este permiso"}
        
    await db_session.delete(permiso)
    await db_session.commit()
    return {"message": "Permiso de merma revocado"}

@user_details_router.get("/admin/all/", response_model=list[UserPublicSchema])
async def get_all_users(
    current_admin: Annotated[User, Depends(require_role([AppRole.ADMIN]))],
    db_session: Annotated[AsyncSession, Depends(get_async_session)],
):
    query = sa_select(User).order_by(User.id)
    result = await db_session.execute(query)
    return result.scalars().all()