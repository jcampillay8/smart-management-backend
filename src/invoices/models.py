import uuid
from datetime import datetime
from typing import Optional, List

from sqlalchemy import String, Text, Float, Boolean, Integer, ForeignKey, DateTime
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from src.database import BaseModel
from src.config import settings


class Invoice(BaseModel):
    __tablename__ = "invoices"
    __table_args__ = {"schema": settings.DB_SCHEMA}

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey(f"{settings.DB_SCHEMA}.users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    filename: Mapped[str] = mapped_column(String(500), nullable=False, index=True)
    file_path: Mapped[str] = mapped_column(String(1000), nullable=True)
    file_type: Mapped[str] = mapped_column(String(10), nullable=False)

    vendor_name: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    vendor_tax_id: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    vendor_fiscal_address: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    vendor_country: Mapped[Optional[str]] = mapped_column(String(5), nullable=True)

    invoice_number: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    invoice_date: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    total_amount: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    tax_amount: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    currency: Mapped[str] = mapped_column(String(10), default="CLP")

    transaction_type: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    category: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    goods_services_type: Mapped[Optional[str]] = mapped_column(String(10), nullable=True)

    confidence_score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    audit_flags: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    line_items_data: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    raw_extracted_data: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    country_detection_method: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    country_confidence: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    gemini_tokens_used: Mapped[int] = mapped_column(Integer, default=0)
    gemini_cost_usd: Mapped[float] = mapped_column(Float, default=0.0)
    gemini_model_used: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    gemini_processing_time: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    processed: Mapped[bool] = mapped_column(Boolean, default=False)

    def to_dict(self) -> dict:
        line_items = []
        if self.line_items_data:
            import json
            try:
                line_items = json.loads(self.line_items_data)
            except (json.JSONDecodeError, TypeError):
                line_items = []

        audit = []
        if self.audit_flags:
            import json
            try:
                audit = json.loads(self.audit_flags)
            except (json.JSONDecodeError, TypeError):
                audit = []

        return {
            "id": str(self.id),
            "user_id": self.user_id,
            "filename": self.filename,
            "file_path": self.file_path,
            "file_type": self.file_type,
            "vendor_name": self.vendor_name,
            "vendor_tax_id": self.vendor_tax_id,
            "vendor_fiscal_address": self.vendor_fiscal_address,
            "vendor_country": self.vendor_country,
            "invoice_number": self.invoice_number,
            "invoice_date": self.invoice_date.isoformat() if self.invoice_date else None,
            "total_amount": float(self.total_amount) if self.total_amount else None,
            "tax_amount": float(self.tax_amount) if self.tax_amount else None,
            "currency": self.currency,
            "transaction_type": self.transaction_type,
            "category": self.category,
            "description": self.description,
            "goods_services_type": self.goods_services_type,
            "confidence_score": float(self.confidence_score) if self.confidence_score else None,
            "audit_flags": audit,
            "line_items": line_items,
            "country_detection_method": self.country_detection_method,
            "country_confidence": float(self.country_confidence) if self.country_confidence else None,
            "gemini_tokens_used": self.gemini_tokens_used,
            "gemini_cost_usd": self.gemini_cost_usd,
            "gemini_model_used": self.gemini_model_used,
            "gemini_processing_time": self.gemini_processing_time,
            "processed": self.processed,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }


class InvoiceSetting(BaseModel):
    __tablename__ = "invoice_settings"
    __table_args__ = {"schema": settings.DB_SCHEMA}

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    key: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    value: Mapped[str] = mapped_column(Text, nullable=True)
    type: Mapped[str] = mapped_column(String(20), default="string")
    category: Mapped[str] = mapped_column(String(50), default="general")
    description: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    user_id: Mapped[Optional[int]] = mapped_column(
        Integer,
        ForeignKey(f"{settings.DB_SCHEMA}.users.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )


class Notification(BaseModel):
    __tablename__ = "invoice_notifications"
    __table_args__ = {"schema": settings.DB_SCHEMA}

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey(f"{settings.DB_SCHEMA}.users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    type: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=True)
    data: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    read: Mapped[bool] = mapped_column(Boolean, default=False)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "type": self.type,
            "title": self.title,
            "message": self.message,
            "data": self.data,
            "read": self.read,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class WebhookEndpoint(BaseModel):
    __tablename__ = "invoice_webhook_endpoints"
    __table_args__ = {"schema": settings.DB_SCHEMA}

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey(f"{settings.DB_SCHEMA}.users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    url: Mapped[str] = mapped_column(String(2000), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    events: Mapped[str] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    def to_dict(self) -> dict:
        events_list = []
        if self.events:
            import json
            try:
                events_list = json.loads(self.events)
            except (json.JSONDecodeError, TypeError):
                events_list = []

        return {
            "id": str(self.id),
            "url": self.url,
            "description": self.description,
            "events": events_list,
            "is_active": self.is_active,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
