# src/operations/routers/conteo_router.py
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete
from src.database import get_async_session
from src.operations import models, schemas
from src.dependencies import get_current_user
from typing import List

router = APIRouter(tags=["Conteos"])

@router.post("/", response_model=schemas.ConteoInventario)
async def create_conteo(conteo: schemas.ConteoInventarioCreate, db: AsyncSession = Depends(get_async_session), current_user = Depends(get_current_user)):
    db_conteo = models.ConteoInventario(
        bodega_id=conteo.bodega_id,
        usuario_id=current_user.id,
        estado=conteo.estado
    )
    db.add(db_conteo)
    await db.commit()
    await db.refresh(db_conteo)
    return db_conteo

@router.get("/", response_model=List[schemas.ConteoInventario])
async def list_conteos(db: AsyncSession = Depends(get_async_session)):
    stmt = select(models.ConteoInventario)
    result = await db.execute(stmt)
    return result.scalars().all()

@router.get("/{conteo_id}", response_model=schemas.ConteoInventario)
async def get_conteo(conteo_id: str, db: AsyncSession = Depends(get_async_session)):
    stmt = select(models.ConteoInventario).filter(models.ConteoInventario.id == conteo_id)
    result = await db.execute(stmt)
    db_conteo = result.scalar_one_or_none()
    if not db_conteo:
        raise HTTPException(status_code=404, detail="Conteo not found")
    return db_conteo

@router.patch("/{conteo_id}", response_model=schemas.ConteoInventario)
async def update_conteo(conteo_id: str, conteo_update: schemas.ConteoInventarioUpdate, db: AsyncSession = Depends(get_async_session)):
    stmt = select(models.ConteoInventario).filter(models.ConteoInventario.id == conteo_id)
    result = await db.execute(stmt)
    db_conteo = result.scalar_one_or_none()
    if not db_conteo:
        raise HTTPException(status_code=404, detail="Conteo not found")
    
    if conteo_update.estado:
        db_conteo.estado = conteo_update.estado
    if conteo_update.completed_at:
        db_conteo.completed_at = conteo_update.completed_at
        
    await db.commit()
    await db.refresh(db_conteo)
    return db_conteo

@router.post("/{conteo_id}/items", response_model=List[schemas.ConteoItem])
async def add_conteo_items(conteo_id: str, items: List[schemas.ConteoItemCreate], db: AsyncSession = Depends(get_async_session)):
    db_items = []
    for item in items:
        db_item = models.ConteoItem(
            conteo_id=conteo_id,
            producto_id=item.producto_id,
            cantidad_contada=item.cantidad_contada,
            fecha_vencimiento=item.fecha_vencimiento
        )
        db_items.append(db_item)
    db.add_all(db_items)
    await db.commit()
    return db_items

@router.delete("/{conteo_id}")
async def delete_conteo(conteo_id: str, db: AsyncSession = Depends(get_async_session)):
    await db.execute(delete(models.ConteoItem).filter(models.ConteoItem.conteo_id == conteo_id))
    await db.execute(delete(models.ConteoInventario).filter(models.ConteoInventario.id == conteo_id))
    await db.commit()
    return {"status": "success"}
