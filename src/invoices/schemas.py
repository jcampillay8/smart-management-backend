import uuid
from datetime import datetime
from typing import Optional, List, Any
from pydantic import BaseModel, ConfigDict


class LineItemOut(BaseModel):
    description: Optional[str] = None
    quantity: Optional[float] = None
    unit_price: Optional[float] = None
    total: Optional[float] = None
    iva_included: Optional[bool] = False


class InvoiceOut(BaseModel):
    id: str
    user_id: int
    filename: str
    file_path: Optional[str] = None
    file_type: str
    vendor_name: Optional[str] = None
    vendor_tax_id: Optional[str] = None
    vendor_fiscal_address: Optional[str] = None
    vendor_country: Optional[str] = None
    invoice_number: Optional[str] = None
    invoice_date: Optional[str] = None
    total_amount: Optional[float] = None
    tax_amount: Optional[float] = None
    currency: str = "CLP"
    transaction_type: Optional[str] = None
    category: Optional[str] = None
    description: Optional[str] = None
    goods_services_type: Optional[str] = None
    confidence_score: Optional[float] = None
    audit_flags: List[str] = []
    line_items: List[LineItemOut] = []
    country_detection_method: Optional[str] = None
    country_confidence: Optional[float] = None
    gemini_tokens_used: int = 0
    gemini_cost_usd: float = 0.0
    gemini_model_used: Optional[str] = None
    gemini_processing_time: Optional[float] = None
    processed: bool = False
    created_at: Optional[str] = None
    updated_at: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class InvoiceUpdate(BaseModel):
    vendor_name: Optional[str] = None
    vendor_tax_id: Optional[str] = None
    vendor_fiscal_address: Optional[str] = None
    vendor_country: Optional[str] = None
    invoice_number: Optional[str] = None
    invoice_date: Optional[str] = None
    total_amount: Optional[float] = None
    tax_amount: Optional[float] = None
    currency: Optional[str] = None
    transaction_type: Optional[str] = None
    category: Optional[str] = None
    description: Optional[str] = None
    goods_services_type: Optional[str] = None


class BulkActionRequest(BaseModel):
    invoice_ids: List[str]


class ExportRequest(BaseModel):
    invoice_ids: List[str]
    format: str = "csv"


class WebhookPushRequest(BaseModel):
    invoice_ids: List[str]
    event: str = "invoices.exported"


class WebhookCreate(BaseModel):
    url: str
    description: Optional[str] = ""
    events: List[str] = ["invoice.processed"]


class WebhookOut(BaseModel):
    id: str
    url: str
    description: Optional[str] = None
    events: List[str] = []
    is_active: bool = True
    created_at: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class SettingUpdate(BaseModel):
    key: str
    value: Any
    category: Optional[str] = "general"
    type: Optional[str] = "string"


class SettingOut(BaseModel):
    key: str
    value: Any
    type: str
    category: str
    description: Optional[str] = None
    source: str = "default"


class NotificationOut(BaseModel):
    id: int
    type: str
    title: str
    message: Optional[str] = None
    data: Optional[str] = None
    read: bool
    created_at: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class ChatRequest(BaseModel):
    query: str


class ChatResponse(BaseModel):
    answer: str


class StatisticsOut(BaseModel):
    queue: dict
    performance: dict
    audit: dict
    costs: dict
    financial: dict


class InvoiceListResponse(BaseModel):
    invoices: List[InvoiceOut]
    total: int
