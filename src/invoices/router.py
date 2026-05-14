import json
import os
import io
import shutil
import uuid
from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, WebSocket, WebSocketDisconnect, status
from fastapi.responses import StreamingResponse
from sqlalchemy import select, desc, or_, func, and_
from sqlalchemy.ext.asyncio import AsyncSession

from src.database import get_async_session
from src.dependencies import get_current_user
from src.models import User
from src.invoices import models, schemas
from src.invoices.services import (
    GeminiInvoiceProcessor,
    ExportService,
    WebSocketManager,
    WebhookSender,
    CostControlService,
    websocket_manager,
    heartbeat_task,
)
from src.invoices.utils import (
    get_file_type,
    validate_file_extension,
    safe_filename,
    parse_date,
)

router = APIRouter(prefix="/invoices", tags=["Invoices"])

gemini_processor = GeminiInvoiceProcessor()
export_service = ExportService()
cost_control = CostControlService()
webhook_sender = WebhookSender()

UPLOAD_DIR = "uploads/invoices"
os.makedirs(UPLOAD_DIR, exist_ok=True)


@router.post("/upload")
async def upload_invoices(
    files: List[UploadFile] = File(...),
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user),
):
    results = []
    for file in files:
        try:
            if not validate_file_extension(file.filename):
                results.append({
                    "filename": file.filename,
                    "success": False,
                    "error": f"Tipo de archivo no permitido",
                })
                continue

            saved_name = safe_filename(file.filename)
            file_path = os.path.join(UPLOAD_DIR, saved_name)

            contents = await file.read()
            with open(file_path, "wb") as f:
                f.write(contents)

            file_type = get_file_type(file.filename)

            invoice = models.Invoice(
                user_id=current_user.id,
                filename=file.filename,
                file_path=file_path,
                file_type=file_type,
            )
            db.add(invoice)
            await db.commit()
            await db.refresh(invoice)

            results.append({
                "filename": file.filename,
                "success": True,
                "invoice_id": str(invoice.id),
                "message": "Archivo subido correctamente",
            })

            await websocket_manager.notify_invoice_uploaded(
                str(invoice.id), file.filename, current_user.id
            )

        except Exception as e:
            results.append({
                "filename": file.filename,
                "success": False,
                "error": str(e),
            })

    return {"results": results}


@router.post("/{invoice_id}/process")
async def process_invoice(
    invoice_id: uuid.UUID,
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user),
):
    query = select(models.Invoice).where(
        models.Invoice.id == invoice_id,
        models.Invoice.user_id == current_user.id,
    )
    result = await db.execute(query)
    invoice = result.scalar_one_or_none()

    if not invoice:
        raise HTTPException(status_code=404, detail="Factura no encontrada")

    if invoice.processed:
        return {"message": "Factura ya procesada", "invoice": invoice.to_dict()}

    extracted_data = await gemini_processor.process_invoice(db, invoice, current_user.id)

    if extracted_data and "error" not in extracted_data:
        invoice.vendor_name = extracted_data.get("vendor_name")
        invoice.invoice_number = extracted_data.get("invoice_number")

        date_str = extracted_data.get("invoice_date")
        if date_str:
            parsed = parse_date(date_str)
            if parsed:
                invoice.invoice_date = parsed

        invoice.total_amount = extracted_data.get("total_amount")
        invoice.tax_amount = extracted_data.get("tax_amount")
        invoice.currency = extracted_data.get("currency", "CLP")
        invoice.transaction_type = extracted_data.get("transaction_type")
        invoice.category = extracted_data.get("category")
        invoice.description = extracted_data.get("description")
        invoice.confidence_score = extracted_data.get("confidence")
        invoice.goods_services_type = extracted_data.get("goods_services_type")
        invoice.vendor_country = extracted_data.get("vendor_country")
        invoice.vendor_tax_id = extracted_data.get("vendor_tax_id")
        invoice.vendor_fiscal_address = extracted_data.get("vendor_fiscal_address")
        invoice.country_detection_method = extracted_data.get("country_detection_method")
        invoice.country_confidence = extracted_data.get("country_confidence")

        line_items = extracted_data.get("line_items", [])
        invoice.line_items_data = json.dumps(line_items, ensure_ascii=False)

        audit = extracted_data.get("audit_warnings", [])
        invoice.audit_flags = json.dumps(audit, ensure_ascii=False) if audit else "[]"

        invoice.raw_extracted_data = json.dumps(extracted_data, ensure_ascii=False)
        invoice.processed = True

        db.add(invoice)
        await db.commit()
        await db.refresh(invoice)

        await websocket_manager.notify_processing_complete(
            str(invoice.id), extracted_data, current_user.id
        )

        try:
            await webhook_sender.trigger_event(
                db, "invoice.processed", invoice.to_dict(), current_user.id
            )
        except Exception as e:
            import logging
            logging.getLogger(__name__).warning(f"Webhook error: {e}")

        return {
            "message": "Factura procesada exitosamente",
            "invoice": invoice.to_dict(),
            "extracted_data": extracted_data,
        }
    else:
        error_msg = extracted_data.get("error", "Error desconocido") if extracted_data else "Error desconocido"
        return {"message": "Error al procesar la factura", "error": error_msg}


@router.get("", response_model=schemas.InvoiceListResponse)
async def list_invoices(
    skip: int = 0,
    limit: int = 100,
    transaction_type: Optional[str] = None,
    category: Optional[str] = None,
    search: Optional[str] = None,
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user),
):
    query = select(models.Invoice).where(models.Invoice.user_id == current_user.id)

    if transaction_type:
        query = query.where(models.Invoice.transaction_type == transaction_type)
    if category:
        query = query.where(models.Invoice.category == category)
    if search:
        pattern = f"%{search}%"
        query = query.where(
            or_(
                models.Invoice.vendor_name.ilike(pattern),
                models.Invoice.invoice_number.ilike(pattern),
                models.Invoice.description.ilike(pattern),
            )
        )

    count_query = select(func.count()).select_from(query.subquery())
    total = (await db.execute(count_query)).scalar() or 0

    query = query.order_by(desc(models.Invoice.created_at)).offset(skip).limit(limit)
    result = await db.execute(query)
    invoices = result.scalars().all()

    return {
        "invoices": [inv.to_dict() for inv in invoices],
        "total": total,
    }


@router.get("/export/csv")
async def export_csv(
    transaction_type: Optional[str] = None,
    category: Optional[str] = None,
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user),
):
    query = select(models.Invoice).where(
        models.Invoice.user_id == current_user.id,
        models.Invoice.processed == True,
    )
    if transaction_type:
        query = query.where(models.Invoice.transaction_type == transaction_type)
    if category:
        query = query.where(models.Invoice.category == category)

    query = query.order_by(desc(models.Invoice.created_at))
    result = await db.execute(query)
    invoices = result.scalars().all()

    output = export_service.export_csv_generic(invoices)
    return StreamingResponse(
        io.StringIO(output),
        media_type="text/csv",
        headers={
            "Content-Disposition": f"attachment; filename=facturas_{datetime.utcnow().strftime('%Y%m%d')}.csv"
        },
    )


@router.get("/export/sii/compras")
async def export_sii_compras(
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user),
):
    query = select(models.Invoice).where(
        models.Invoice.user_id == current_user.id,
        models.Invoice.processed == True,
    ).order_by(desc(models.Invoice.created_at))
    result = await db.execute(query)
    invoices = result.scalars().all()

    output = export_service.export_sii_libro_compras(invoices)
    return StreamingResponse(
        io.StringIO(output),
        media_type="text/csv",
        headers={
            "Content-Disposition": f"attachment; filename=libro_compras_sii_{datetime.utcnow().strftime('%Y%m%d')}.csv"
        },
    )


@router.get("/export/sii/ventas")
async def export_sii_ventas(
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user),
):
    query = select(models.Invoice).where(
        models.Invoice.user_id == current_user.id,
        models.Invoice.processed == True,
    ).order_by(desc(models.Invoice.created_at))
    result = await db.execute(query)
    invoices = result.scalars().all()

    output = export_service.export_sii_libro_ventas(invoices)
    return StreamingResponse(
        io.StringIO(output),
        media_type="text/csv",
        headers={
            "Content-Disposition": f"attachment; filename=libro_ventas_sii_{datetime.utcnow().strftime('%Y%m%d')}.csv"
        },
    )


@router.get("/stats")
async def get_statistics(
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user),
):
    base_query = select(models.Invoice).where(models.Invoice.user_id == current_user.id)

    total = (await db.execute(select(func.count()).select_from(base_query.subquery()))).scalar() or 0
    processed = (await db.execute(
        select(func.count()).where(
            models.Invoice.user_id == current_user.id,
            models.Invoice.processed == True,
        )
    )).scalar() or 0
    pending = total - processed

    today = datetime.utcnow().date()
    today_start = datetime.combine(today, datetime.min.time())
    daily_processed = (await db.execute(
        select(func.count()).where(
            models.Invoice.user_id == current_user.id,
            models.Invoice.processed == True,
            models.Invoice.created_at >= today_start,
        )
    )).scalar() or 0

    avg_confidence = (await db.execute(
        select(func.coalesce(func.avg(models.Invoice.confidence_score), 0)).where(
            models.Invoice.user_id == current_user.id,
            models.Invoice.processed == True,
            models.Invoice.confidence_score.isnot(None),
        )
    )).scalar() or 0.0

    cost_stats = await cost_control.get_cost_statistics(db, current_user.id)
    avg_cost = cost_stats["avg_cost_per_request"] if processed > 0 else 0

    alerts = await cost_control.get_cost_alerts(db, current_user.id)

    income_sum = (await db.execute(
        select(func.coalesce(func.sum(models.Invoice.total_amount), 0)).where(
            models.Invoice.user_id == current_user.id,
            models.Invoice.processed == True,
            models.Invoice.transaction_type == "income",
        )
    )).scalar() or 0.0

    expense_sum = (await db.execute(
        select(func.coalesce(func.sum(models.Invoice.total_amount), 0)).where(
            models.Invoice.user_id == current_user.id,
            models.Invoice.processed == True,
            models.Invoice.transaction_type == "expense",
        )
    )).scalar() or 0.0

    audit_alert_count = (await db.execute(
        select(func.count()).where(
            models.Invoice.user_id == current_user.id,
            models.Invoice.processed == True,
            models.Invoice.audit_flags.isnot(None),
            models.Invoice.audit_flags != "[]",
        )
    )).scalar() or 0

    stats_data = {
        "queue": {
            "total": total,
            "processed": processed,
            "pending": pending,
            "processing_rate": (processed / total * 100) if total > 0 else 0,
        },
        "performance": {
            "daily_processed": daily_processed,
            "avg_confidence": float(avg_confidence),
            "avg_cost_per_doc": avg_cost,
        },
        "audit": {
            "total_alerts": audit_alert_count,
        },
        "costs": cost_stats,
        "financial": {
            "income": float(income_sum),
            "expense": float(expense_sum),
            "net": float(income_sum - expense_sum),
        },
        "alerts": alerts,
    }

    await websocket_manager.notify_statistics_update(stats_data, current_user.id)
    return stats_data


@router.get("/categories")
async def get_categories(
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user),
):
    query = select(models.Invoice.category).distinct().where(
        models.Invoice.user_id == current_user.id,
        models.Invoice.category.isnot(None),
        models.Invoice.category != "",
    )
    result = await db.execute(query)
    return [row[0] for row in result]


@router.get("/settings")
async def get_settings(
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user),
):
    default_query = select(models.InvoiceSetting).where(
        models.InvoiceSetting.user_id.is_(None)
    )
    defaults = (await db.execute(default_query)).scalars().all()

    user_query = select(models.InvoiceSetting).where(
        models.InvoiceSetting.user_id == current_user.id
    )
    user_settings = (await db.execute(user_query)).scalars().all()

    user_map = {s.key: s for s in user_settings}
    result = {}

    for setting in defaults:
        resolved = user_map.get(setting.key) or setting
        cat = resolved.category or "general"
        if cat not in result:
            result[cat] = []
        result[cat].append({
            "key": resolved.key,
            "value": resolved.value,
            "type": resolved.type,
            "description": resolved.description,
            "category": cat,
            "source": "user" if resolved.key in user_map else "default",
        })

    return result


@router.post("/settings")
async def update_settings(
    updates: List[schemas.SettingUpdate],
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user),
):
    try:
        updated_count = 0
        for update in updates:
            str_value = str(update.value)

            query = select(models.InvoiceSetting).where(
                models.InvoiceSetting.key == update.key,
                models.InvoiceSetting.user_id == current_user.id,
            )
            result = await db.execute(query)
            setting = result.scalar_one_or_none()

            if setting:
                setting.value = str_value
                setting.type = update.type or setting.type
                setting.category = update.category or setting.category
                updated_count += 1
            else:
                new_setting = models.InvoiceSetting(
                    key=update.key,
                    value=str_value,
                    type=update.type or "string",
                    category=update.category or "general",
                    description=f"Configuración: {update.key}",
                    user_id=current_user.id,
                )
                db.add(new_setting)
                updated_count += 1

        await db.commit()
        return {"status": "success", "updated": updated_count}
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/notifications")
async def get_notifications(
    limit: int = 20,
    unread_only: bool = False,
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user),
):
    query = select(models.Notification).where(
        models.Notification.user_id == current_user.id,
    )
    if unread_only:
        query = query.where(models.Notification.read == False)
    query = query.order_by(desc(models.Notification.created_at)).limit(limit)
    result = await db.execute(query)
    notifications = result.scalars().all()
    return [n.to_dict() for n in notifications]


@router.post("/notifications/{notification_id}/read")
async def mark_notification_read(
    notification_id: int,
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user),
):
    query = select(models.Notification).where(
        models.Notification.id == notification_id,
        models.Notification.user_id == current_user.id,
    )
    result = await db.execute(query)
    notification = result.scalar_one_or_none()
    if not notification:
        raise HTTPException(status_code=404, detail="Notificación no encontrada")
    notification.read = True
    db.add(notification)
    await db.commit()
    return {"status": "success"}


@router.post("/notifications/read-all")
async def mark_all_notifications_read(
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user),
):
    query = select(models.Notification).where(
        models.Notification.user_id == current_user.id,
        models.Notification.read == False,
    )
    result = await db.execute(query)
    for notification in result.scalars().all():
        notification.read = True
        db.add(notification)
    await db.commit()
    return {"status": "success"}


@router.get("/webhooks")
async def get_webhooks(
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user),
):
    query = select(models.WebhookEndpoint).where(
        models.WebhookEndpoint.user_id == current_user.id,
    )
    result = await db.execute(query)
    webhooks = result.scalars().all()
    return {"webhooks": [w.to_dict() for w in webhooks]}


@router.post("/webhooks")
async def create_webhook(
    webhook_data: schemas.WebhookCreate,
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user),
):
    wh = models.WebhookEndpoint(
        url=webhook_data.url,
        description=webhook_data.description,
        events=json.dumps(webhook_data.events),
        is_active=True,
        user_id=current_user.id,
    )
    db.add(wh)
    await db.commit()
    await db.refresh(wh)
    return {"webhook": wh.to_dict()}


@router.delete("/webhooks/{webhook_id}")
async def delete_webhook(
    webhook_id: uuid.UUID,
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user),
):
    query = select(models.WebhookEndpoint).where(
        models.WebhookEndpoint.id == webhook_id,
        models.WebhookEndpoint.user_id == current_user.id,
    )
    result = await db.execute(query)
    wh = result.scalar_one_or_none()
    if not wh:
        raise HTTPException(status_code=404, detail="Webhook no encontrado")
    await db.delete(wh)
    await db.commit()
    return {"status": "success"}


@router.post("/webhooks/{webhook_id}/test")
async def test_webhook(
    webhook_id: uuid.UUID,
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user),
):
    query = select(models.WebhookEndpoint).where(
        models.WebhookEndpoint.id == webhook_id,
        models.WebhookEndpoint.user_id == current_user.id,
    )
    result = await db.execute(query)
    wh = result.scalar_one_or_none()
    if not wh:
        raise HTTPException(status_code=404, detail="Webhook no encontrado")

    result = await webhook_sender.trigger_event(
        db, "test.event", {"ping": True}, current_user.id
    )
    return {"status": "sent", "result": result}


@router.post("/invoices/push-webhook")
async def push_invoices_webhook(
    payload: schemas.WebhookPushRequest,
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user),
):
    if not payload.invoice_ids:
        raise HTTPException(status_code=400, detail="No se seleccionaron facturas")

    ids = []
    for i in payload.invoice_ids:
        try:
            ids.append(uuid.UUID(i))
        except ValueError:
            continue

    query = select(models.Invoice).where(
        models.Invoice.id.in_(ids),
        models.Invoice.user_id == current_user.id,
    )
    result = await db.execute(query)
    invoices = result.scalars().all()

    if not invoices:
        raise HTTPException(status_code=404, detail="No se encontraron facturas")

    data = {
        "count": len(invoices),
        "invoices": [inv.to_dict() for inv in invoices],
    }
    result = await webhook_sender.trigger_event(
        db, payload.event, data, current_user.id
    )
    return {"status": "sent", "result": result}


@router.post("/chat")
async def chat_finance(
    request: schemas.ChatRequest,
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user),
):
    try:
        query = select(models.Invoice).where(
            models.Invoice.processed == True,
            models.Invoice.user_id == current_user.id,
        ).order_by(desc(models.Invoice.invoice_date)).limit(50)
        result = await db.execute(query)
        invoices = result.scalars().all()

        context_data = []
        for inv in invoices:
            d = inv.to_dict()
            context_data.append({
                "fecha": d.get("invoice_date"),
                "proveedor": d.get("vendor_name"),
                "total": d.get("total_amount"),
                "moneda": d.get("currency"),
                "tipo": d.get("transaction_type"),
                "categoria": d.get("category"),
            })

        if not context_data:
            return {"answer": "No hay facturas registradas. Sube algunas para poder consultar."}

        answer = await gemini_processor.process_finance_chat(request.query, context_data, current_user.id)
        return {"answer": answer}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error procesando consulta: {str(e)}")


@router.get("/ws/status")
async def websocket_status():
    return websocket_manager.get_status()


@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    db = None
    try:
        async for session in get_async_session():
            db = session
            break

        token = websocket.cookies.get("access_token") or websocket.query_params.get("token")
        if not token:
            await websocket.close(code=1008)
            return

        from jose import jwt as jose_jwt, JWTError
        try:
            payload = jose_jwt.decode(token, settings.JWT_ACCESS_SECRET_KEY, algorithms=[settings.ENCRYPTION_ALGORITHM])
            login_identifier: str = payload.get("sub")
            if not login_identifier:
                await websocket.close(code=1008)
                return
        except (JWTError, Exception):
            await websocket.close(code=1008)
            return

        from src.authentication.services import get_user_by_login_identifier
        user = await get_user_by_login_identifier(db, login_identifier=login_identifier)
        if not user or user.is_deleted:
            await websocket.close(code=1008)
            return

        await websocket_manager.connect(websocket, user.id)
        try:
            while True:
                data = await websocket.receive_text()
                if data == "ping":
                    await websocket_manager.send_personal_message(
                        {"type": "pong", "message": "Conexión activa"},
                        websocket,
                    )
        except WebSocketDisconnect:
            websocket_manager.disconnect(websocket)
    except Exception:
        try:
            await websocket.close(code=1011)
        except Exception:
            pass


@router.get("/{invoice_id}", response_model=schemas.InvoiceOut)
async def get_invoice(
    invoice_id: uuid.UUID,
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user),
):
    query = select(models.Invoice).where(
        models.Invoice.id == invoice_id,
        models.Invoice.user_id == current_user.id,
    )
    result = await db.execute(query)
    invoice = result.scalar_one_or_none()
    if not invoice:
        raise HTTPException(status_code=404, detail="Factura no encontrada")
    return invoice.to_dict()


@router.put("/{invoice_id}", response_model=schemas.InvoiceOut)
async def update_invoice(
    invoice_id: uuid.UUID,
    update_data: schemas.InvoiceUpdate,
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user),
):
    query = select(models.Invoice).where(
        models.Invoice.id == invoice_id,
        models.Invoice.user_id == current_user.id,
    )
    result = await db.execute(query)
    invoice = result.scalar_one_or_none()
    if not invoice:
        raise HTTPException(status_code=404, detail="Factura no encontrada")

    update_fields = update_data.model_dump(exclude_unset=True)

    if "invoice_date" in update_fields and update_fields["invoice_date"]:
        parsed = parse_date(update_fields["invoice_date"])
        if parsed:
            invoice.invoice_date = parsed

    for field in [
        "vendor_name", "invoice_number", "total_amount", "tax_amount",
        "currency", "transaction_type", "category", "description",
        "vendor_country", "vendor_tax_id", "vendor_fiscal_address",
        "goods_services_type",
    ]:
        if field in update_fields:
            setattr(invoice, field, update_fields[field])

    db.add(invoice)
    await db.commit()
    await db.refresh(invoice)
    return invoice.to_dict()


@router.delete("/{invoice_id}")
async def delete_invoice(
    invoice_id: uuid.UUID,
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user),
):
    query = select(models.Invoice).where(
        models.Invoice.id == invoice_id,
        models.Invoice.user_id == current_user.id,
    )
    result = await db.execute(query)
    invoice = result.scalar_one_or_none()
    if not invoice:
        raise HTTPException(status_code=404, detail="Factura no encontrada")

    if invoice.file_path and os.path.exists(invoice.file_path):
        os.remove(invoice.file_path)

    await db.delete(invoice)
    await db.commit()
    return {"message": "Factura eliminada exitosamente"}


@router.post("/bulk-delete")
async def bulk_delete_invoices(
    action: schemas.BulkActionRequest,
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user),
):
    if not action.invoice_ids:
        return {"message": "No se seleccionaron facturas", "count": 0}

    ids = []
    for i in action.invoice_ids:
        try:
            ids.append(uuid.UUID(i))
        except ValueError:
            continue

    query = select(models.Invoice).where(
        models.Invoice.id.in_(ids),
        models.Invoice.user_id == current_user.id,
    )
    result = await db.execute(query)
    invoices = result.scalars().all()

    count = 0
    for invoice in invoices:
        try:
            if invoice.file_path and os.path.exists(invoice.file_path):
                os.remove(invoice.file_path)
            await db.delete(invoice)
            count += 1
        except Exception as e:
            import logging
            logging.getLogger(__name__).error(f"Error deleting invoice {invoice.id}: {e}")

    await db.commit()
    return {"message": "Facturas eliminadas exitosamente", "count": count}


@router.post("/bulk-process")
async def bulk_process_invoices(
    action: schemas.BulkActionRequest,
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user),
):
    if not action.invoice_ids:
        return {"message": "No se seleccionaron facturas", "count": 0}

    ids = []
    for i in action.invoice_ids:
        try:
            ids.append(uuid.UUID(i))
        except ValueError:
            continue

    query = select(models.Invoice).where(
        models.Invoice.id.in_(ids),
        models.Invoice.processed == False,
        models.Invoice.user_id == current_user.id,
    )
    result = await db.execute(query)
    invoices = result.scalars().all()

    success_count = 0
    errors = []

    for invoice in invoices:
        try:
            extracted_data = await gemini_processor.process_invoice(db, invoice, current_user.id)

            if extracted_data and "error" not in extracted_data:
                invoice.vendor_name = extracted_data.get("vendor_name")
                invoice.invoice_number = extracted_data.get("invoice_number")
                date_str = extracted_data.get("invoice_date")
                if date_str:
                    parsed = parse_date(date_str)
                    if parsed:
                        invoice.invoice_date = parsed
                invoice.total_amount = extracted_data.get("total_amount")
                invoice.tax_amount = extracted_data.get("tax_amount")
                invoice.currency = extracted_data.get("currency", "CLP")
                invoice.transaction_type = extracted_data.get("transaction_type")
                invoice.category = extracted_data.get("category")
                invoice.description = extracted_data.get("description")
                invoice.confidence_score = extracted_data.get("confidence")
                invoice.goods_services_type = extracted_data.get("goods_services_type")
                line_items = extracted_data.get("line_items", [])
                invoice.line_items_data = json.dumps(line_items, ensure_ascii=False)
                audit = extracted_data.get("audit_warnings", [])
                invoice.audit_flags = json.dumps(audit, ensure_ascii=False) if audit else "[]"
                invoice.raw_extracted_data = json.dumps(extracted_data, ensure_ascii=False)
                invoice.processed = True
                db.add(invoice)
                success_count += 1

                await webhook_sender.trigger_event(
                    db, "invoice.processed", invoice.to_dict(), current_user.id
                )
            else:
                errors.append(f"ID {invoice.id}: {extracted_data.get('error', 'Error desconocido')}")

        except Exception as e:
            errors.append(f"ID {invoice.id}: {str(e)}")

    await db.commit()
    return {
        "message": f"Procesamiento completado. {success_count} exitosos.",
        "success_count": success_count,
        "errors": errors,
    }


@router.get("/{invoice_id}/optimized-image")
async def get_optimized_image(
    invoice_id: uuid.UUID,
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user),
):
    query = select(models.Invoice).where(
        models.Invoice.id == invoice_id,
        models.Invoice.user_id == current_user.id,
    )
    result = await db.execute(query)
    invoice = result.scalar_one_or_none()
    if not invoice:
        raise HTTPException(status_code=404, detail="Factura no encontrada")

    if invoice.file_type != "image":
        raise HTTPException(status_code=400, detail="La factura no es una imagen")

    if not os.path.exists(invoice.file_path):
        raise HTTPException(status_code=404, detail="Archivo no encontrado")

    from fastapi.concurrency import run_in_threadpool
    optimized_data = await run_in_threadpool(
        GeminiInvoiceProcessor.encode_image, invoice.file_path
    )
    if not optimized_data:
        raise HTTPException(status_code=500, detail="Error al optimizar imagen")

    return {"optimized_image": optimized_data}


@router.post("/export")
async def export_invoices(
    action: schemas.ExportRequest,
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user),
):
    if not action.invoice_ids:
        raise HTTPException(status_code=400, detail="No se seleccionaron facturas")

    ids = []
    for i in action.invoice_ids:
        try:
            ids.append(uuid.UUID(i))
        except ValueError:
            continue

    query = select(models.Invoice).where(
        models.Invoice.id.in_(ids),
        models.Invoice.user_id == current_user.id,
    )
    result = await db.execute(query)
    invoices = result.scalars().all()

    if not invoices:
        raise HTTPException(status_code=404, detail="No se encontraron facturas")

    timestamp = datetime.utcnow().strftime("%Y%m%d%H%M")
    filename = f"export_{action.format}_{timestamp}"
    media_type = "text/csv"

    try:
        if action.format == "quickbooks":
            output = export_service.export_quickbooks(invoices)
            filename += ".csv"
        elif action.format == "quickbooks_bills":
            output = export_service.export_quickbooks_bills(invoices)
            filename += ".csv"
        elif action.format == "xero":
            output = export_service.export_xero_bills(invoices)
            filename += ".csv"
        elif action.format == "odoo":
            output = export_service.export_odoo_vendor_bills(invoices)
            filename += ".csv"
        elif action.format == "contaplus":
            output = export_service.export_contaplus(invoices)
            filename += ".csv"
        elif action.format == "json":
            output = export_service.export_json(invoices)
            media_type = "application/json"
            filename += ".json"
        elif action.format == "sii_compras":
            output = export_service.export_sii_libro_compras(invoices)
            filename += ".csv"
        elif action.format == "sii_ventas":
            output = export_service.export_sii_libro_ventas(invoices)
            filename += ".csv"
        elif action.format == "excel":
            output = export_service.export_excel_generic(invoices)
            media_type = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            filename += ".xlsx"
        else:
            output = export_service.export_csv_generic(invoices)
            filename += ".csv"

        if media_type in ["application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"]:
            return StreamingResponse(
                io.BytesIO(output),
                media_type=media_type,
                headers={"Content-Disposition": f"attachment; filename={filename}"},
            )
        return StreamingResponse(
            io.StringIO(output),
            media_type=media_type,
            headers={"Content-Disposition": f"attachment; filename={filename}"},
        )
    except Exception as e:
        import logging
        logging.getLogger(__name__).error(f"Export error: {e}")
        raise HTTPException(status_code=500, detail=f"Error generando exportación: {str(e)}")
