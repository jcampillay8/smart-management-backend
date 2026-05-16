# src/notes/router.py
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload
from typing import List

from src.dependencies import get_async_session, get_current_user
from src.models import User
from src.notes.models import Nota, NotaMencion
from src.notes.schemas import NotaCreate, NotaUpdate, NotaOut

notes_router = APIRouter(prefix="/notes", tags=["Notes"])


@notes_router.get("", response_model=List[NotaOut])
async def list_notas(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_session),
):
    result = await db.execute(
        select(Nota)
        .where(Nota.is_deleted == False)
        .options(selectinload(Nota.autor), selectinload(Nota.menciones))
        .order_by(Nota.created_at.desc())
        .limit(100)
    )
    return result.scalars().all()


@notes_router.post("", response_model=NotaOut, status_code=status.HTTP_201_CREATED)
async def create_nota(
    data: NotaCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_session),
):
    nota = Nota(
        autor_id=current_user.id,
        titulo=data.titulo,
        contenido=data.contenido,
        urgencia=data.urgencia,
        fecha=data.fecha,
    )
    db.add(nota)
    await db.flush()

    # Agregar menciones
    for user_id in data.menciones:
        mencion = NotaMencion(nota_id=nota.id, user_id=user_id)
        db.add(mencion)

    await db.commit()
    await db.refresh(nota)

    result = await db.execute(
        select(Nota)
        .where(Nota.id == nota.id)
        .options(selectinload(Nota.autor), selectinload(Nota.menciones))
    )
    return result.scalar_one()


@notes_router.put("/{nota_id}", response_model=NotaOut)
async def update_nota(
    nota_id: str,
    data: NotaUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_session),
):
    result = await db.execute(select(Nota).where(Nota.id == nota_id, Nota.is_deleted == False))
    nota = result.scalar_one_or_none()
    if not nota:
        raise HTTPException(status_code=404, detail="Nota no encontrada")
    if nota.autor_id != current_user.id:
        raise HTTPException(status_code=403, detail="No tienes permiso para editar esta nota")

    if data.titulo is not None:
        nota.titulo = data.titulo
    if data.contenido is not None:
        nota.contenido = data.contenido
    if data.urgencia is not None:
        nota.urgencia = data.urgencia
    if data.fecha is not None:
        nota.fecha = data.fecha

    if data.menciones is not None:
        # Eliminar menciones anteriores y recrear
        old = await db.execute(select(NotaMencion).where(NotaMencion.nota_id == nota.id))
        for m in old.scalars().all():
            db.delete(m)
        for user_id in data.menciones:
            db.add(NotaMencion(nota_id=nota.id, user_id=user_id))

    await db.commit()

    result = await db.execute(
        select(Nota)
        .where(Nota.id == nota.id)
        .options(selectinload(Nota.autor), selectinload(Nota.menciones))
    )
    return result.scalar_one()


@notes_router.delete("/{nota_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_nota(
    nota_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_session),
):
    result = await db.execute(select(Nota).where(Nota.id == nota_id, Nota.is_deleted == False))
    nota = result.scalar_one_or_none()
    if not nota:
        raise HTTPException(status_code=404, detail="Nota no encontrada")
    if nota.autor_id != current_user.id:
        raise HTTPException(status_code=403, detail="No tienes permiso para eliminar esta nota")

    nota.is_deleted = True
    await db.commit()
