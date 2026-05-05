# src/purchases/router.py
import uuid
from typing import List, Optional
from datetime import date
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from src.database import get_async_session
from src.dependencies import get_current_user
from src.models import User
from src.purchases import models, schemas
from src.inventory.models import ProductoBodega
from src.purchases.services import get_purchase_service, PurchaseService
from src.purchases.ai_service import scan_invoice_ai

router = APIRouter(prefix="/purchases", tags=["Purchases"])

@router.post("/", response_model=schemas.Compra)
async def create_purchase(
    purchase: schemas.CompraCreate,
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user)
):
    service = await get_purchase_service(db)
    return await service.create_purchase(
        purchase.model_dump(),
        [item.model_dump() for item in purchase.items],
        current_user.id
    )

@router.get("/", response_model=List[schemas.Compra])
async def list_purchases(
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user)
):
    service = await get_purchase_service(db)
    return await service.list_purchases()

@router.get("/{purchase_id}", response_model=schemas.Compra)
async def get_purchase(
    purchase_id: uuid.UUID,
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user)
):
    service = await get_purchase_service(db)
    result = await service.get_purchase(str(purchase_id))
    if not result:
        raise HTTPException(status_code=404, detail="Purchase not found")
    return result

@router.patch("/{purchase_id}", response_model=schemas.Compra)
async def update_purchase(
    purchase_id: uuid.UUID,
    purchase_update: schemas.CompraUpdate,
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user)
):
    service = await get_purchase_service(db)
    update_data = {k: v for k, v in purchase_update.model_dump(exclude_unset=True).items()}
    result = await service.update_purchase(str(purchase_id), update_data)
    if not result:
        raise HTTPException(status_code=404, detail="Purchase not found")
    return result

@router.patch("/{purchase_id}/cancel", response_model=schemas.Compra)
async def cancel_purchase(
    purchase_id: uuid.UUID,
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user)
):
    service = await get_purchase_service(db)
    result = await service.cancel_purchase(str(purchase_id))
    if not result:
        raise HTTPException(status_code=404, detail="Compra no encontrada")
    return result

@router.patch("/{purchase_id}/restore", response_model=schemas.Compra)
async def restore_purchase(
    purchase_id: uuid.UUID,
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user)
):
    service = await get_purchase_service(db)
    result = await service.restore_purchase(str(purchase_id))
    if not result:
        raise HTTPException(status_code=404, detail="Compra no encontrada")
    return result

@router.patch("/{purchase_id}/pedido", response_model=schemas.Compra)
async def mark_pedido(
    purchase_id: uuid.UUID,
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user)
):
    service = await get_purchase_service(db)
    result = await service.mark_pedido(str(purchase_id))
    if not result:
        raise HTTPException(status_code=404, detail="Compra no encontrada")
    return result

@router.post("/{purchase_id}/receive", response_model=schemas.Compra)
async def receive_purchase(
    purchase_id: uuid.UUID,
    reception: schemas.ReceptionCreate,
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user)
):
    service = await get_purchase_service(db)
    result = await service.mark_received(str(purchase_id))
    if not result:
        raise HTTPException(status_code=404, detail="Compra no encontrada")
    return result

# Supplier Performance Endpoints
@router.get("/fill-rate", tags=["Supplier Performance"])
async def get_fill_rate(
    fecha_inicio: Optional[date] = None,
    fecha_fin: Optional[date] = None,
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user)
):
    service = await get_purchase_service(db)
    return await service.get_fill_rate_by_proveedor(fecha_inicio, fecha_fin)

@router.get("/price-variation", tags=["Supplier Performance"])
async def get_price_variation(
    dias_atras: int = 90,
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user)
):
    service = await get_purchase_service(db)
    return await service.get_variacion_precios_by_proveedor(dias_atras)

@router.get("/upcoming-payments", tags=["Supplier Performance"])
async def get_upcoming_payments(
    dias_adelante: int = 7,
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user)
):
    service = await get_purchase_service(db)
    return await service.get_calendario_pagos(dias_adelante)

# AI Invoice Scan
@router.post("/scan-invoice")
async def scan_invoice(
    request: schemas.ScanInvoiceRequest,
    current_user: User = Depends(get_current_user)
):
    return await scan_invoice_ai(request.imageBase64, request.mimeType)

# ======================
# PROVEEDORES
# ======================
@router.get("/suppliers/", response_model=List[schemas.ProveedorOut])
async def list_proveedores(
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user)
):
    """Lista todos los proveedores ordenados por nombre de empresa"""
    stmt = select(models.Proveedor).order_by(models.Proveedor.nombre_empresa)
    result = await db.execute(stmt)
    return result.scalars().all()

@router.post("/suppliers/", response_model=schemas.ProveedorOut, status_code=status.HTTP_201_CREATED)
async def create_proveedor(
    proveedor: schemas.ProveedorCreate,
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user)
):
    """Crea un nuevo proveedor"""
    db_proveedor = models.Proveedor(**proveedor.model_dump())
    db.add(db_proveedor)
    await db.commit()
    await db.refresh(db_proveedor)
    return db_proveedor

@router.get("/suppliers/{proveedor_id}", response_model=schemas.ProveedorOut)
async def get_proveedor(
    proveedor_id: uuid.UUID,
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user)
):
    """Obtiene un proveedor por su ID"""
    stmt = select(models.Proveedor).where(models.Proveedor.id == proveedor_id)
    result = await db.execute(stmt)
    db_proveedor = result.scalar_one_or_none()
    if not db_proveedor:
        raise HTTPException(status_code=404, detail="Proveedor no encontrado")
    return db_proveedor

@router.put("/suppliers/{proveedor_id}", response_model=schemas.ProveedorOut)
async def update_proveedor(
    proveedor_id: uuid.UUID,
    proveedor_update: schemas.ProveedorUpdate,
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user)
):
    """Actualiza un proveedor existente"""
    stmt = select(models.Proveedor).where(models.Proveedor.id == proveedor_id)
    result = await db.execute(stmt)
    db_proveedor = result.scalar_one_or_none()
    if not db_proveedor:
        raise HTTPException(status_code=404, detail="Proveedor no encontrado")
    
    update_data = proveedor_update.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(db_proveedor, key, value)
    
    await db.commit()
    await db.refresh(db_proveedor)
    return db_proveedor

@router.delete("/suppliers/{proveedor_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_proveedor(
    proveedor_id: uuid.UUID,
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user)
):
    """Elimina un proveedor"""
    stmt = select(models.Proveedor).where(models.Proveedor.id == proveedor_id)
    result = await db.execute(stmt)
    db_proveedor = result.scalar_one_or_none()
    if not db_proveedor:
        raise HTTPException(status_code=404, detail="Proveedor no encontrado")
    
    await db.delete(db_proveedor)
    await db.commit()
    return None

# ======================
# PLANTILLAS EMAIL
# ======================
from src.purchases.incidencias_models import PlantillaEmail

@router.get("/email-templates/", response_model=List[schemas.PlantillaEmailOut])
async def list_plantillas_email(
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user)
):
    stmt = select(PlantillaEmail).order_by(PlantillaEmail.nombre)
    result = await db.execute(stmt)
    return result.scalars().all()

@router.post("/email-templates/", response_model=schemas.PlantillaEmailOut, status_code=status.HTTP_201_CREATED)
async def create_plantilla_email(
    plantilla: schemas.PlantillaEmailCreate,
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user)
):
    db_plantilla = PlantillaEmail(
        **plantilla.model_dump(),
        created_by=current_user.id
    )
    db.add(db_plantilla)
    await db.commit()
    await db.refresh(db_plantilla)
    return db_plantilla

@router.put("/email-templates/{plantilla_id}", response_model=schemas.PlantillaEmailOut)
async def update_plantilla_email(
    plantilla_id: uuid.UUID,
    plantilla_update: schemas.PlantillaEmailUpdate,
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user)
):
    stmt = select(PlantillaEmail).where(PlantillaEmail.id == plantilla_id)
    result = await db.execute(stmt)
    db_plantilla = result.scalar_one_or_none()
    if not db_plantilla:
        raise HTTPException(status_code=404, detail="Plantilla no encontrada")
    
    update_data = plantilla_update.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(db_plantilla, key, value)
    
    await db.commit()
    await db.refresh(db_plantilla)
    return db_plantilla

@router.delete("/email-templates/{plantilla_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_plantilla_email(
    plantilla_id: uuid.UUID,
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user)
):
    stmt = select(PlantillaEmail).where(PlantillaEmail.id == plantilla_id)
    result = await db.execute(stmt)
    db_plantilla = result.scalar_one_or_none()
    if not db_plantilla:
        raise HTTPException(status_code=404, detail="Plantilla no encontrada")
    
    await db.delete(db_plantilla)
    await db.commit()
    return None
