# src/settings/router.py
from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select as sa_select
from sqlalchemy.orm import selectinload
from typing import Annotated, List
from uuid import UUID

from src.dependencies import get_async_session, get_current_user, require_role
from src.models import ConfiguracionRestaurante, User, AppRole
from src.inventory.models import AreaOperativa, AreaOperativaBodega, AreaOperativaUsuario, AreaOperativaReceta, Bodega
from src.settings.schemas import (
    ConfiguracionRestauranteOut, ConfiguracionRestauranteUpdate,
    AreaOperativaCreate, AreaOperativaUpdate, AreaOperativaOut
)
from src.registration.services import ImageSaver

settings_router = APIRouter(prefix="/settings", tags=["Settings"])


# ─── Helpers ──────────────────────────────────────────────────────────────────

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


def _area_to_out(area: AreaOperativa) -> AreaOperativaOut:
    return AreaOperativaOut(
        id=area.id,
        nombre=area.nombre,
        bodega_consumo_id=area.bodega_consumo_id,
        bodegas_ids=[b.id for b in area.bodegas],
        usuarios_ids=[u.id for u in area.usuarios],
    )


# ─── Restaurant ───────────────────────────────────────────────────────────────

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
    image_url = await image_saver.save_user_image(file, "restaurant_logo")
    if not image_url:
        raise HTTPException(status_code=500, detail="Error al procesar la imagen")
    config.logo_url = image_url
    await db_session.commit()
    await db_session.refresh(config)
    return config


# ─── Áreas Operativas ─────────────────────────────────────────────────────────

@settings_router.get("/areas", response_model=List[AreaOperativaOut])
async def list_areas(
    current_user: User = Depends(get_current_user),
    db_session: AsyncSession = Depends(get_async_session),
):
    """Admins get all areas; other roles get only their assigned areas."""
    query = (
        sa_select(AreaOperativa)
        .options(
            selectinload(AreaOperativa.bodegas),
            selectinload(AreaOperativa.usuarios),
        )
    )
    if current_user.role != AppRole.ADMIN:
        # Filter to only areas where this user is assigned
        query = query.join(
            AreaOperativaUsuario,
            AreaOperativaUsuario.area_operativa_id == AreaOperativa.id
        ).where(AreaOperativaUsuario.user_id == current_user.id)

    result = await db_session.execute(query)
    areas = result.scalars().unique().all()
    return [_area_to_out(a) for a in areas]


@settings_router.get("/areas/{area_id}", response_model=AreaOperativaOut)
async def get_area(
    area_id: UUID,
    current_user: User = Depends(get_current_user),
    db_session: AsyncSession = Depends(get_async_session),
):
    result = await db_session.execute(
        sa_select(AreaOperativa)
        .options(selectinload(AreaOperativa.bodegas), selectinload(AreaOperativa.usuarios))
        .where(AreaOperativa.id == area_id)
    )
    area = result.scalar_one_or_none()
    if not area:
        raise HTTPException(status_code=404, detail="Área operativa no encontrada")
    # Non-admins can only see their areas
    if current_user.role != AppRole.ADMIN:
        if current_user.id not in [u.id for u in area.usuarios]:
            raise HTTPException(status_code=403, detail="Sin acceso a esta área operativa")
    return _area_to_out(area)


@settings_router.post("/areas", response_model=AreaOperativaOut, status_code=201)
async def create_area(
    data: AreaOperativaCreate,
    _admin: User = Depends(require_role([AppRole.ADMIN])),
    db_session: AsyncSession = Depends(get_async_session),
):
    # Validate bodega_consumo exists
    bodega = await db_session.get(Bodega, data.bodega_consumo_id)
    if not bodega:
        raise HTTPException(status_code=422, detail="Bodega de consumo no existe")

    area = AreaOperativa(nombre=data.nombre, bodega_consumo_id=data.bodega_consumo_id)
    db_session.add(area)
    await db_session.flush()  # get area.id

    # Associate bodegas
    for bid in data.bodegas_ids:
        db_session.add(AreaOperativaBodega(area_operativa_id=area.id, bodega_id=bid))

    # Associate usuarios
    for uid in data.usuarios_ids:
        db_session.add(AreaOperativaUsuario(area_operativa_id=area.id, user_id=uid))

    await db_session.commit()

    result = await db_session.execute(
        sa_select(AreaOperativa)
        .options(selectinload(AreaOperativa.bodegas), selectinload(AreaOperativa.usuarios))
        .where(AreaOperativa.id == area.id)
    )
    return _area_to_out(result.scalar_one())


@settings_router.put("/areas/{area_id}", response_model=AreaOperativaOut)
async def update_area(
    area_id: UUID,
    data: AreaOperativaUpdate,
    _admin: User = Depends(require_role([AppRole.ADMIN])),
    db_session: AsyncSession = Depends(get_async_session),
):
    result = await db_session.execute(sa_select(AreaOperativa).where(AreaOperativa.id == area_id))
    area = result.scalar_one_or_none()
    if not area:
        raise HTTPException(status_code=404, detail="Área operativa no encontrada")

    bodega = await db_session.get(Bodega, data.bodega_consumo_id)
    if not bodega:
        raise HTTPException(status_code=422, detail="Bodega de consumo no existe")

    area.nombre = data.nombre
    area.bodega_consumo_id = data.bodega_consumo_id

    # Re-sync bodegas
    await db_session.execute(
        AreaOperativaBodega.__table__.delete().where(
            AreaOperativaBodega.__table__.c.area_operativa_id == area_id
        )
    )
    for bid in data.bodegas_ids:
        db_session.add(AreaOperativaBodega(area_operativa_id=area.id, bodega_id=bid))

    # Re-sync usuarios
    await db_session.execute(
        AreaOperativaUsuario.__table__.delete().where(
            AreaOperativaUsuario.__table__.c.area_operativa_id == area_id
        )
    )
    for uid in data.usuarios_ids:
        db_session.add(AreaOperativaUsuario(area_operativa_id=area.id, user_id=uid))

    await db_session.commit()

    result = await db_session.execute(
        sa_select(AreaOperativa)
        .options(selectinload(AreaOperativa.bodegas), selectinload(AreaOperativa.usuarios))
        .where(AreaOperativa.id == area_id)
    )
    return _area_to_out(result.scalar_one())


@settings_router.delete("/areas/{area_id}", status_code=204)
async def delete_area(
    area_id: UUID,
    _admin: User = Depends(require_role([AppRole.ADMIN])),
    db_session: AsyncSession = Depends(get_async_session),
):
    result = await db_session.execute(sa_select(AreaOperativa).where(AreaOperativa.id == area_id))
    area = result.scalar_one_or_none()
    if not area:
        raise HTTPException(status_code=404, detail="Área operativa no encontrada")
    await db_session.delete(area)
    await db_session.commit()
