# src/purchases/router.py
import uuid
from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from src.database import get_async_session
from src.dependencies import get_current_user
from src.models import User
from src.purchases import models, schemas
from src.inventory.models import ProductoBodega

router = APIRouter(prefix="/purchases", tags=["Purchases"])

@router.post("/", response_model=schemas.Compra)
async def create_purchase(
    purchase: schemas.CompraCreate,
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user)
):
    db_purchase = models.Compra(
        **purchase.model_dump(exclude={"items"}),
        usuario_id=current_user.id
    )
    db.add(db_purchase)
    await db.flush()

    for item in purchase.items:
        db_item = models.CompraItem(
            **item.model_dump(),
            compra_id=db_purchase.id
        )
        db.add(db_item)
        
        # If the purchase is "realizada", update stock
        if purchase.estado == "realizada" and item.bodega_id:
            stmt = select(ProductoBodega).where(
                ProductoBodega.producto_id == item.producto_id,
                ProductoBodega.bodega_id == item.bodega_id
            )
            result = await db.execute(stmt)
            pb = result.scalar_one_or_none()
            if pb:
                pb.stock_actual += item.cantidad
            else:
                new_pb = ProductoBodega(
                    producto_id=item.producto_id,
                    bodega_id=item.bodega_id,
                    stock_actual=item.cantidad
                )
                db.add(new_pb)

    await db.commit()
    await db.refresh(db_purchase)
    return db_purchase

@router.get("/", response_model=List[schemas.Compra])
async def list_purchases(
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user)
):
    stmt = select(models.Compra).order_by(models.Compra.fecha.desc())
    result = await db.execute(stmt)
    return result.scalars().all()

@router.get("/{purchase_id}", response_model=schemas.Compra)
async def get_purchase(
    purchase_id: uuid.UUID,
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user)
):
    stmt = select(models.Compra).where(models.Compra.id == purchase_id)
    result = await db.execute(stmt)
    db_purchase = result.scalar_one_or_none()
    if not db_purchase:
        raise HTTPException(status_code=404, detail="Purchase not found")
    return db_purchase

@router.patch("/{purchase_id}", response_model=schemas.Compra)
async def update_purchase(
    purchase_id: uuid.UUID,
    purchase_update: schemas.CompraUpdate,
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user)
):
    stmt = select(models.Compra).where(models.Compra.id == purchase_id)
    result = await db.execute(stmt)
    db_purchase = result.scalar_one_or_none()
    if not db_purchase:
        raise HTTPException(status_code=404, detail="Purchase not found")
    
    update_data = purchase_update.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(db_purchase, key, value)
    
    await db.commit()
    await db.refresh(db_purchase)
    return db_purchase

from src.purchases.ai_service import scan_invoice_ai

@router.post("/scan-invoice")
async def scan_invoice(
    request: schemas.ScanInvoiceRequest,
    current_user: User = Depends(get_current_user)
):
    return await scan_invoice_ai(request.imageBase64, request.mimeType)
