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
from src.inventory.models import ProductoBodega, Producto

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

@router.patch("/{purchase_id}/cancel", response_model=schemas.Compra)
async def cancel_purchase(
    purchase_id: uuid.UUID,
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user)
):
    stmt = select(models.Compra).where(models.Compra.id == purchase_id)
    result = await db.execute(stmt)
    db_purchase = result.scalar_one_or_none()
    if not db_purchase:
        raise HTTPException(status_code=404, detail="Compra no encontrada")
    
    db_purchase.estado = "cancelada"
    await db.commit()
    await db.refresh(db_purchase)
    return db_purchase

@router.patch("/{purchase_id}/restore", response_model=schemas.Compra)
async def restore_purchase(
    purchase_id: uuid.UUID,
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user)
):
    stmt = select(models.Compra).where(models.Compra.id == purchase_id)
    result = await db.execute(stmt)
    db_purchase = result.scalar_one_or_none()
    if not db_purchase:
        raise HTTPException(status_code=404, detail="Compra no encontrada")
    
    db_purchase.estado = "pendiente"
    db_purchase.pedido_realizado = False
    await db.commit()
    await db.refresh(db_purchase)
    return db_purchase

@router.patch("/{purchase_id}/pedido", response_model=schemas.Compra)
async def mark_pedido(
    purchase_id: uuid.UUID,
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user)
):
    stmt = select(models.Compra).where(models.Compra.id == purchase_id)
    result = await db.execute(stmt)
    db_purchase = result.scalar_one_or_none()
    if not db_purchase:
        raise HTTPException(status_code=404, detail="Compra no encontrada")
    
    db_purchase.pedido_realizado = True
    await db.commit()
    await db.refresh(db_purchase)
    return db_purchase

@router.post("/{purchase_id}/receive", response_model=schemas.Compra)
async def receive_purchase(
    purchase_id: uuid.UUID,
    reception: schemas.ReceptionCreate,
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user)
):
    stmt = select(models.Compra).where(models.Compra.id == purchase_id)
    result = await db.execute(stmt)
    db_purchase = result.scalar_one_or_none()
    if not db_purchase:
        raise HTTPException(status_code=404, detail="Compra no encontrada")
    
    if reception.action == "reject_order":
        db_purchase.estado = "cancelada"
        db_purchase.tiene_incidencia = True
    else:
        db_purchase.estado = "realizada"
    
    # Obtener items originales para saber las bodegas
    items_stmt = select(models.CompraItem).where(models.CompraItem.compra_id == purchase_id)
    items_result = await db.execute(items_stmt)
    original_items = {str(item.producto_id): item for item in items_result.scalars().all()}
    
    for item in reception.items:
        original = original_items.get(str(item.producto_id))
        if original and original.bodega_id:
            # Actualizar stock
            stock_stmt = select(ProductoBodega).where(
                ProductoBodega.producto_id == item.producto_id,
                ProductoBodega.bodega_id == original.bodega_id
            )
            stock_result = await db.execute(stock_stmt)
            pb = stock_result.scalar_one_or_none()
            
            if reception.action != "reject_order":
                # Obtener cantidad anterior para el registro
                qty_before = pb.stock_actual if pb else 0.0

                if pb:
                    pb.stock_actual += item.cantidad_recibida
                else:
                    new_pb = ProductoBodega(
                        producto_id=item.producto_id,
                        bodega_id=original.bodega_id,
                        stock_actual=item.cantidad_recibida
                    )
                    db.add(new_pb)
                
                # Actualizar costo en el producto
                prod_stmt = select(Producto).where(Producto.id == item.producto_id)
                prod_result = await db.execute(prod_stmt)
                prod = prod_result.scalar_one_or_none()
                if prod:
                    prod.costo_unitario = item.costo_neto
                
                # Crear registro de stock para el historial
                from src.operations.models import RegistroStock, TipoMovimiento
                from datetime import date
                registro = RegistroStock(
                    producto_id=item.producto_id,
                    bodega_id=original.bodega_id,
                    cantidad=item.cantidad_recibida,
                    tipo_movimiento=TipoMovimiento.COMPRA,
                    usuario_id=current_user.id,
                    cantidad_anterior=qty_before,
                    fecha_recuento=date.today()
                )
                db.add(registro)
    
    if reception.action in ["modify_order", "reject_order"]:
        # Buscar email del proveedor
        prov_stmt = select(models.Proveedor).where(models.Proveedor.nombre_empresa == db_purchase.proveedor)
        prov_result = await db.execute(prov_stmt)
        prov = prov_result.scalar_one_or_none()
        
        if prov and prov.email:
            from src.email.email_service import email_service
            subject = f"Incidencia en Pedido - {db_purchase.fecha}"
            template = "reception_discrepancy.html"
            template_vars = {
                "proveedor_nombre": prov.nombre_empresa,
                "fecha": str(db_purchase.fecha),
                "accion": "Modificación de Pedido" if reception.action == "modify_order" else "Rechazo de Pedido",
                "items": [
                    {
                        "nombre": original_items.get(str(i.producto_id)).producto_nombre if original_items.get(str(i.producto_id)) else "Producto",
                        "pedido": original_items.get(str(i.producto_id)).cantidad if original_items.get(str(i.producto_id)) else 0,
                        "recibido": i.cantidad_recibida
                    } for i in reception.items if original_items.get(str(i.producto_id)) and original_items.get(str(i.producto_id)).cantidad != i.cantidad_recibida
                ]
            }
            await email_service.send_email(subject, [prov.email], template, template_vars)

    await db.commit()
    await db.refresh(db_purchase)
    return db_purchase

@router.post("/{purchase_id}/incidencia", response_model=schemas.Compra)
async def register_incidencia(
    purchase_id: uuid.UUID,
    incidencia: schemas.IncidenciaCreate,
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user)
):
    stmt = select(models.Compra).where(models.Compra.id == purchase_id)
    result = await db.execute(stmt)
    db_purchase = result.scalar_one_or_none()
    if not db_purchase:
        raise HTTPException(status_code=404, detail="Compra no encontrada")
    
    # Marcamos la compra con incidencia
    db_purchase.tiene_incidencia = True
    
    # Creamos la notificación de incidencia vinculada (Nota/Alerta)
    # Como las notificaciones viven en operations/models.py, debemos crearla
    from src.purchases.incidencias_models import NotificacionIncidencia
    
    notif = NotificacionIncidencia(
        compra_id=db_purchase.id,
        tipo=incidencia.tipo,
        titulo=incidencia.titulo,
        detalle=incidencia.detalle,
        resuelta=False
    )
    db.add(notif)
    
    await db.commit()
    await db.refresh(db_purchase)
    return db_purchase


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
