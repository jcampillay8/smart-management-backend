# src/authentication/user_details_router.py
from fastapi import APIRouter, Depends, HTTPException, status
from typing import Annotated, Optional
import logging

from src.models import User, AppRole, PermisoMerma
from src.dependencies import get_current_user, get_async_session, require_role
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select as sa_select
from src.authentication.schemas import UserPublicSchema
from pydantic import BaseModel

logger = logging.getLogger(__name__)

user_details_router = APIRouter(prefix="/user", tags=["User Details"])

@user_details_router.get("/profile", response_model=UserPublicSchema, response_model_by_alias=True)
async def read_current_user_profile(
    current_user: Annotated[User, Depends(get_current_user)],
):
    """
    Retorna el perfil del usuario actual.
    El esquema UserPublicSchema se encarga de inyectar 'show_tour' si no existe.
    """
    return current_user 

class ProfileUpdateSchema(BaseModel):
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    occupation: Optional[str] = None
    user_image: Optional[str] = None

@user_details_router.put("/profile", response_model=UserPublicSchema, response_model_by_alias=True)
async def update_current_user_profile(
    data: ProfileUpdateSchema,
    current_user: Annotated[User, Depends(get_current_user)],
    db_session: Annotated[AsyncSession, Depends(get_async_session)],
):
    """Actualiza los datos de perfil del usuario actual."""
    if data.first_name is not None:
        current_user.first_name = data.first_name
    if data.last_name is not None:
        current_user.last_name = data.last_name
    if data.occupation is not None:
        current_user.occupation = data.occupation
    if data.user_image is not None:
        current_user.user_image = data.user_image
    
    await db_session.commit()
    await db_session.refresh(current_user)
    return current_user
@user_details_router.post("/accept-terms", status_code=status.HTTP_200_OK)
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
    current_user: Annotated[User, Depends(require_role([AppRole.ADMIN, AppRole.PROPIETARIO]))],
    db_session: Annotated[AsyncSession, Depends(get_async_session)],
):
    user = await db_session.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")
    
    # Logic for role promotion
    if data.role == AppRole.PROPIETARIO:
        if current_user.role != AppRole.PROPIETARIO:
            raise HTTPException(status_code=403, detail="Solo el Propietario puede nombrar nuevos Propietarios")
    
    if data.role == AppRole.ADMIN:
        if current_user.role != AppRole.PROPIETARIO:
            raise HTTPException(status_code=403, detail="Solo el Propietario puede nombrar Administradores")

    # If target is currently an Admin or Owner, only Owner can demote them
    if user.role in [AppRole.ADMIN, AppRole.PROPIETARIO] and current_user.role != AppRole.PROPIETARIO:
        raise HTTPException(status_code=403, detail="Solo el Propietario puede modificar el rol de un Administrador o Propietario")

    user.role = data.role
    await db_session.commit()
    return {"message": f"Rol actualizado a {data.role.value}"}

@user_details_router.delete("/admin/{user_id}", status_code=status.HTTP_200_OK)
async def delete_user(
    user_id: int,
    current_user: Annotated[User, Depends(require_role([AppRole.PROPIETARIO]))],
    db_session: Annotated[AsyncSession, Depends(get_async_session)],
):
    """Permite al Propietario eliminar cualquier usuario."""
    user = await db_session.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")
    
    if user.id == current_user.id:
        raise HTTPException(status_code=400, detail="No puedes eliminarte a ti mismo")

    await db_session.delete(user)
    await db_session.commit()
    return {"message": "Usuario eliminado exitosamente"}

@user_details_router.post("/admin/{user_id}/merma-permission", status_code=status.HTTP_200_OK)
async def add_merma_permission(
    user_id: int,
    current_admin: Annotated[User, Depends(require_role([AppRole.ADMIN, AppRole.PROPIETARIO]))],
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
    current_admin: Annotated[User, Depends(require_role([AppRole.ADMIN, AppRole.PROPIETARIO]))],
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

@user_details_router.get("/admin/all", response_model=list[UserPublicSchema], response_model_by_alias=True)
async def get_all_users(
    current_user: Annotated[User, Depends(require_role([AppRole.ADMIN, AppRole.PROPIETARIO]))],
    db_session: Annotated[AsyncSession, Depends(get_async_session)],
):
    query = sa_select(User).order_by(User.id)
    result = await db_session.execute(query)
    return result.scalars().all()