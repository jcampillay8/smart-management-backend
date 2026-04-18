# src/settings/router.py
from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select as sa_select
from typing import Annotated

from src.dependencies import get_async_session, get_current_user, require_role
from src.models import ConfiguracionRestaurante, User, AppRole
from src.settings.schemas import ConfiguracionRestauranteOut, ConfiguracionRestauranteUpdate
from src.registration.services import ImageSaver

settings_router = APIRouter(prefix="/settings", tags=["Settings"])

async def get_or_create_config(db_session: AsyncSession) -> ConfiguracionRestaurante:
    query = sa_select(ConfiguracionRestaurante).limit(1)
    result = await db_session.execute(query)
    config = result.scalar_one_or_none()
    
    if not config:
        config = ConfiguracionRestaurante(nombre="Mi Restaurante")
        db_session.add(config)
        await db_session.commit()
        await db_session.refresh(config)
    return config

@settings_router.get("/restaurant", response_model=ConfiguracionRestauranteOut)
async def get_restaurant_config(
    current_user: User = Depends(get_current_user),
    db_session: AsyncSession = Depends(get_async_session),
):
    return await get_or_create_config(db_session)

@settings_router.put("/restaurant", response_model=ConfiguracionRestauranteOut)
async def update_restaurant_config(
    data: ConfiguracionRestauranteUpdate,
    current_admin: User = Depends(require_role([AppRole.ADMIN])),
    db_session: AsyncSession = Depends(get_async_session),
):
    config = await get_or_create_config(db_session)
    config.nombre = data.nombre
    await db_session.commit()
    await db_session.refresh(config)
    return config

@settings_router.post("/restaurant/logo", response_model=ConfiguracionRestauranteOut)
async def upload_restaurant_logo(
    file: UploadFile = File(...),
    current_admin: User = Depends(require_role([AppRole.ADMIN])),
    db_session: AsyncSession = Depends(get_async_session),
):
    if not file.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="El archivo debe ser una imagen")
        
    config = await get_or_create_config(db_session)
    image_saver = ImageSaver(db_session=db_session)
    # Usamos "restaurant_logo" fijo para que reemplace siempre el archivo anterior
    image_url = await image_saver.save_user_image(file, "restaurant_logo")
    
    if not image_url:
        raise HTTPException(status_code=500, detail="Error al procesar la imagen")
        
    config.logo_url = image_url
    await db_session.commit()
    await db_session.refresh(config)
    return config
