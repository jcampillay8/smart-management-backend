import io
import json
import logging
import os
import time
import re
import asyncio
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any
from collections import defaultdict

from sqlalchemy import select, func, and_
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import WebSocket

from src.config import settings
from src.invoices.models import Invoice, InvoiceSetting, Notification, WebhookEndpoint

logger = logging.getLogger(__name__)


class CostControlService:
    MODEL_COSTS = {
        "gemini-2.5-flash": {"input": 0.00030, "output": 0.00250},
        "gemini-2.5-flash-lite": {"input": 0.00015, "output": 0.00060},
        "gemini-2.5-pro": {"input": 0.00125, "output": 0.01000},
    }

    def __init__(self):
        self.daily_limit_usd = float(os.getenv("GEMINI_DAILY_LIMIT_USD", "10.0"))
        self.hourly_limit_requests = int(os.getenv("GEMINI_HOURLY_LIMIT_REQUESTS", "100"))
        self.request_history: List[datetime] = []

    def check_rate_limits(self) -> dict:
        now = datetime.utcnow()
        cutoff = now - timedelta(hours=1)
        self.request_history = [t for t in self.request_history if t > cutoff]
        return {
            "allowed": len(self.request_history) < self.hourly_limit_requests,
            "requests_this_hour": len(self.request_history),
            "limit": self.hourly_limit_requests,
        }

    async def check_daily_cost_limit(self, db: AsyncSession, user_id: int) -> dict:
        today = datetime.utcnow().date()
        query = select(func.coalesce(func.sum(Invoice.gemini_cost_usd), 0)).where(
            Invoice.user_id == user_id,
            func.date(Invoice.created_at) == today,
        )
        result = await db.execute(query)
        today_cost = float(result.scalar() or 0.0)
        return {
            "allowed": today_cost < self.daily_limit_usd,
            "today_cost": today_cost,
            "limit": self.daily_limit_usd,
        }

    async def can_process_request(self, db: AsyncSession, user_id: int) -> dict:
        rate = self.check_rate_limits()
        if not rate["allowed"]:
            return {"allowed": False, "reason": "rate_limit", "detail": rate}

        cost = await self.check_daily_cost_limit(db, user_id)
        if not cost["allowed"]:
            return {"allowed": False, "reason": "daily_cost", "detail": cost}

        return {"allowed": True}

    def record_request_start(self) -> float:
        self.request_history.append(datetime.utcnow())
        return time.time()

    def calculate_cost(self, model: str, input_tokens: int, output_tokens: int) -> float:
        prices = self.MODEL_COSTS.get(model, self.MODEL_COSTS["gemini-2.5-flash"])
        input_cost = (input_tokens / 1000) * prices["input"]
        output_cost = (output_tokens / 1000) * prices["output"]
        return input_cost + output_cost

    async def record_gemini_usage(
        self,
        db: AsyncSession,
        invoice: Invoice,
        model: str,
        input_tokens: int,
        output_tokens: int,
        start_time: float,
    ) -> None:
        elapsed = time.time() - start_time
        cost = self.calculate_cost(model, input_tokens, output_tokens)
        invoice.gemini_tokens_used = input_tokens + output_tokens
        invoice.gemini_cost_usd = cost
        invoice.gemini_model_used = model
        invoice.gemini_processing_time = elapsed
        db.add(invoice)
        await db.commit()

    async def get_cost_statistics(self, db: AsyncSession, user_id: int) -> dict:
        today = datetime.utcnow().date()
        today_start = datetime.combine(today, datetime.min.time())

        base = select(Invoice).where(Invoice.user_id == user_id, Invoice.processed == True)

        total_cost_q = select(func.coalesce(func.sum(Invoice.gemini_cost_usd), 0)).where(
            Invoice.user_id == user_id, Invoice.processed == True
        )
        total_tokens_q = select(func.coalesce(func.sum(Invoice.gemini_tokens_used), 0)).where(
            Invoice.user_id == user_id, Invoice.processed == True
        )
        total_requests_q = select(func.count(Invoice.id)).where(
            Invoice.user_id == user_id, Invoice.processed == True
        )
        today_cost_q = select(func.coalesce(func.sum(Invoice.gemini_cost_usd), 0)).where(
            Invoice.user_id == user_id, Invoice.processed == True,
            Invoice.created_at >= today_start
        )
        today_requests_q = select(func.count(Invoice.id)).where(
            Invoice.user_id == user_id, Invoice.processed == True,
            Invoice.created_at >= today_start
        )

        total_cost = float((await db.execute(total_cost_q)).scalar() or 0.0)
        total_tokens = int((await db.execute(total_tokens_q)).scalar() or 0)
        total_requests = int((await db.execute(total_requests_q)).scalar() or 0)
        today_cost = float((await db.execute(today_cost_q)).scalar() or 0.0)
        today_requests = int((await db.execute(today_requests_q)).scalar() or 0)

        model_rows = await db.execute(
            select(
                Invoice.gemini_model_used,
                func.count(Invoice.id),
                func.coalesce(func.sum(Invoice.gemini_cost_usd), 0),
                func.coalesce(func.sum(Invoice.gemini_tokens_used), 0),
            ).where(
                Invoice.user_id == user_id,
                Invoice.processed == True,
                Invoice.gemini_model_used.isnot(None),
            ).group_by(Invoice.gemini_model_used)
        )
        model_breakdown = {}
        for row in model_rows:
            model_breakdown[row[0]] = {
                "requests": int(row[1]),
                "cost": float(row[2]),
                "tokens": int(row[3]),
                "avg_cost": float(row[2]) / int(row[1]) if int(row[1]) > 0 else 0,
            }

        seven_days_ago = today - timedelta(days=7)
        weekly_rows = await db.execute(
            select(
                func.date(Invoice.created_at),
                func.count(Invoice.id),
                func.coalesce(func.sum(Invoice.gemini_cost_usd), 0),
            ).where(
                Invoice.user_id == user_id,
                Invoice.processed == True,
                func.date(Invoice.created_at) >= seven_days_ago,
            ).group_by(func.date(Invoice.created_at))
        )
        weekly_breakdown = [
            {"date": str(row[0]), "cost": float(row[2]), "requests": int(row[1])}
            for row in weekly_rows
        ]

        return {
            "total_cost": total_cost,
            "total_tokens": total_tokens,
            "total_requests": total_requests,
            "avg_cost_per_request": total_cost / total_requests if total_requests > 0 else 0,
            "daily": {
                "cost": today_cost,
                "requests": today_requests,
                "limit": self.daily_limit_usd,
                "remaining": max(0, self.daily_limit_usd - today_cost),
            },
            "rate_limits": self.check_rate_limits(),
            "model_breakdown": model_breakdown,
            "weekly_breakdown": weekly_breakdown,
        }

    async def get_cost_alerts(self, db: AsyncSession, user_id: int) -> list:
        alerts = []
        stats = await self.get_cost_statistics(db, user_id)
        daily = stats["daily"]
        if daily["cost"] > 0 and daily["limit"] > 0:
            pct = (daily["cost"] / daily["limit"]) * 100
            if pct >= 100:
                alerts.append({"severity": "critical", "message": f"Límite diario de costos alcanzado (${daily['cost']:.2f} USD)"})
            elif pct >= 80:
                alerts.append({"severity": "warning", "message": f"Costo diario al {pct:.0f}% del límite (${daily['cost']:.2f} USD)"})
        rate = stats["rate_limits"]
        if rate["requests_this_hour"] > 0 and rate["limit"] > 0:
            pct = (rate["requests_this_hour"] / rate["limit"]) * 100
            if pct >= 90:
                alerts.append({"severity": "warning", "message": f"Límite de peticiones por hora al {pct:.0f}%"})
        return alerts


class GeminiInvoiceProcessor:
    def __init__(self):
        self.default_model = "gemini-2.5-flash"
        self.cost_control = CostControlService()

    async def _get_api_key(self, db: AsyncSession, user_id: int) -> Optional[str]:
        query = select(InvoiceSetting).where(
            InvoiceSetting.key == "gemini_api_key",
            InvoiceSetting.user_id == user_id,
        )
        result = await db.execute(query)
        setting = result.scalar_one_or_none()
        if setting and setting.value:
            return setting.value
        query = select(InvoiceSetting).where(
            InvoiceSetting.key == "gemini_api_key",
            InvoiceSetting.user_id.is_(None),
        )
        result = await db.execute(query)
        setting = result.scalar_one_or_none()
        if setting and setting.value:
            return setting.value
        return settings.GEMINI_API_KEY

    async def _get_model_name(self, db: AsyncSession, user_id: int) -> str:
        query = select(InvoiceSetting).where(
            InvoiceSetting.key == "gemini_model",
            InvoiceSetting.user_id == user_id,
        )
        result = await db.execute(query)
        setting = result.scalar_one_or_none()
        if setting and setting.value:
            return setting.value
        query = select(InvoiceSetting).where(
            InvoiceSetting.key == "gemini_model",
            InvoiceSetting.user_id.is_(None),
        )
        result = await db.execute(query)
        setting = result.scalar_one_or_none()
        return setting.value if setting and setting.value else self.default_model

    @staticmethod
    def encode_image(image_path: str, max_width: int = 2000, quality: int = 85) -> Optional[str]:
        from PIL import Image
        try:
            with Image.open(image_path) as img:
                if img.mode in ("RGBA", "LA", "P"):
                    img = img.convert("RGB")
                if img.width > max_width:
                    ratio = max_width / img.width
                    new_height = int(img.height * ratio)
                    img = img.resize((max_width, new_height), Image.Resampling.LANCZOS)
                buffer = io.BytesIO()
                img.save(buffer, format="JPEG", quality=quality, optimize=True)
                buffer.seek(0)
                import base64
                return base64.b64encode(buffer.getvalue()).decode()
        except Exception as e:
            logger.error(f"Error encoding image: {e}")
            return None

    @staticmethod
    def extract_text_from_pdf(pdf_path: str) -> str:
        from PyPDF2 import PdfReader
        try:
            reader = PdfReader(pdf_path)
            text = []
            for page in reader.pages:
                extracted = page.extract_text()
                if extracted:
                    text.append(extracted)
            return "\n".join(text)
        except Exception as e:
            logger.error(f"Error extracting PDF text: {e}")
            return ""

    @staticmethod
    def _pdf_to_images(pdf_path: str, dpi: int = 200) -> list:
        import fitz
        from PIL import Image
        images = []
        try:
            doc = fitz.open(pdf_path)
            for page in doc:
                pix = page.get_pixmap(dpi=dpi)
                img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
                images.append(img)
            doc.close()
        except Exception as e:
            logger.error(f"Error converting PDF to images: {e}")
        return images

    @staticmethod
    def _clean_string(value: Any) -> Optional[str]:
        if value is None:
            return None
        cleaned = str(value).strip()
        return cleaned if cleaned and cleaned.lower() not in ("none", "null", "n/a", "") else None

    @staticmethod
    def _clean_number(value: Any) -> Optional[float]:
        if value is None:
            return None
        cleaned = str(value).replace("$", "").replace(",", "").replace(".", "").strip()
        try:
            return float(cleaned)
        except (ValueError, TypeError):
            return None

    @staticmethod
    def _clean_currency(value: Any) -> str:
        if not value:
            return "CLP"
        mapping = {"$": "CLP", "usd": "USD", "eur": "EUR", "clp": "CLP", "uf": "UF"}
        cleaned = str(value).strip().upper()
        for key, val in mapping.items():
            if key in cleaned.lower():
                return val
        return "CLP"

    @staticmethod
    def _validate_date(date_str: Any) -> Optional[str]:
        if not date_str:
            return None
        formats = ["%Y-%m-%d", "%d/%m/%Y", "%m/%d/%Y", "%d-%m-%Y", "%Y/%m/%d"]
        cleaned = str(date_str).strip()
        for fmt in formats:
            try:
                dt = datetime.strptime(cleaned, fmt)
                return dt.strftime("%Y-%m-%d")
            except ValueError:
                continue
        return None

    @staticmethod
    def _validate_transaction_type(value: Any) -> str:
        if not value:
            return "expense"
        keywords = {"income": "income", "ingreso": "income", "venta": "income", "sale": "income",
                     "expense": "expense", "gasto": "expense", "compra": "expense", "purchase": "expense",
                     "costo": "expense"}
        cleaned = str(value).strip().lower()
        for key, val in keywords.items():
            if key in cleaned:
                return val
        return "expense"

    @staticmethod
    def _validate_line_items(items: Any) -> list:
        if not items or not isinstance(items, list):
            return []
        validated = []
        for item in items:
            if not isinstance(item, dict):
                continue
            description = str(item.get("description") or item.get("nombre") or "")
            quantity = float(item.get("quantity") or item.get("cantidad") or 1)
            unit_price = float(item.get("unit_price") or item.get("precio_unitario") or item.get("price") or 0)
            total = float(item.get("total") or item.get("subtotal") or 0)
            if not total and quantity and unit_price:
                total = quantity * unit_price
            validated.append({
                "description": description,
                "quantity": quantity,
                "unit_price": unit_price,
                "total": total,
            })
        return validated

    @staticmethod
    def _smart_country_detection(extracted: dict) -> dict:
        country = extracted.get("vendor_country")
        tax_id = extracted.get("vendor_tax_id")
        currency = extracted.get("currency")

        method = extracted.get("country_detection_method") or "ai"
        confidence = extracted.get("country_confidence") or 0.5

        chile_rut_pattern = re.compile(r'^\d{7,8}-[\dkK]$')

        if tax_id and chile_rut_pattern.match(str(tax_id)):
            country = "CHL"
            method = "tax_id_pattern"
            confidence = 0.95

        if not country or country == "N/A":
            if currency == "CLP":
                country = "CHL"
                method = "currency"
                confidence = 0.85
            elif currency == "USD":
                country = "USA"
                method = "currency"
                confidence = 0.6
            else:
                country = "CHL"
                method = "default"
                confidence = 0.5

        return {
            "vendor_country": country,
            "country_detection_method": method,
            "country_confidence": confidence,
        }

    @staticmethod
    def _validate_country_code(country: Optional[str]) -> bool:
        valid = {"CHL", "ARG", "PER", "BOL", "COL", "ECU", "MEX", "BRA", "URY", "PRY",
                 "VEN", "USA", "ESP", "DEU", "FRA", "ITA", "GBR", "CAN", "AUS", "CHN"}
        return country in valid if country else False

    def _validate_and_clean_data(self, extracted: dict) -> dict:
        if "error" in extracted:
            return extracted

        for field in ["vendor_name", "vendor_tax_id", "vendor_fiscal_address", "invoice_number", "description"]:
            if field in extracted:
                extracted[field] = self._clean_string(extracted.get(field))

        for num_field in ["total_amount", "tax_amount"]:
            if num_field in extracted:
                extracted[num_field] = self._clean_number(extracted.get(num_field))

        if "currency" in extracted:
            extracted["currency"] = self._clean_currency(extracted["currency"])

        if "invoice_date" in extracted:
            extracted["invoice_date"] = self._validate_date(extracted.get("invoice_date"))

        if "transaction_type" in extracted:
            extracted["transaction_type"] = self._validate_transaction_type(extracted.get("transaction_type"))

        if "line_items" in extracted:
            extracted["line_items"] = self._validate_line_items(extracted.get("line_items"))

        country_info = self._smart_country_detection(extracted)
        extracted.update(country_info)

        return extracted

    def _build_image_prompt(self) -> str:
        return """Eres un asistente experto en facturación chilena. Extrae la información de esta factura en formato JSON.

REGLAS ESTRICTAS:
1. Los montos deben ser números sin formato (no uses $, puntos, ni comas)
2. Las fechas deben estar en formato ISO (YYYY-MM-DD)
3. El RUT debe incluir guión (ej: 12345678-9)
4. IVA siempre es 19% para Chile. Calcula: Neto = Total / 1.19, IVA = Total - Neto
5. Si no ves moneda, asume CLP

CAMPOS A EXTRAER:
- vendor_name: Nombre del proveedor (persona o empresa) que emite la factura
- vendor_tax_id: RUT del proveedor con guión
- vendor_fiscal_address: Dirección fiscal del proveedor
- vendor_country: Código ISO 3166-1 alpha-3 del país (CHL para Chile)
- invoice_number: Número de factura o folio DTE
- invoice_date: Fecha de emisión (YYYY-MM-DD)
- total_amount: Monto total de la factura (con IVA incluido)
- tax_amount: Monto del IVA (19%)
- currency: Moneda (CLP, USD, EUR, UF)
- transaction_type: "expense" si es una compra/gasto, "income" si es un ingreso/venta
- category: Categoría del gasto (alimentos, insumos, servicios, transporte, etc.)
- description: Descripción breve del concepto de la factura
- goods_services_type: Tipo de bien o servicio según SII (01-11)
- line_items: Array de productos/servicios con:
  - description: Nombre del producto
  - quantity: Cantidad
  - unit_price: Precio unitario (neto, sin IVA)
  - total: Subtotal del ítem
- audit_warnings: Array de strings con advertencias detectadas (datos faltantes, IVA anómalo, fechas extrañas, etc.)
- confidence: Score de confianza general del 0.0 al 1.0

DEVUELVE SOLO EL JSON, sin markdown ni texto adicional."""

    def _build_pdf_prompt(self) -> str:
        return """Eres un asistente experto en facturación chilena. Extrae la información de esta factura en formato JSON.

CAMPOS:
- vendor_name: Nombre del proveedor
- vendor_tax_id: RUT del proveedor
- vendor_fiscal_address: Dirección del proveedor
- vendor_country: Código ISO del país (CHL para Chile)
- invoice_number: Número de factura o folio DTE
- invoice_date: Fecha de emisión (YYYY-MM-DD)
- total_amount: Monto total
- tax_amount: IVA (19%)
- currency: CLP, USD, EUR
- transaction_type: "expense" o "income"
- category: Categoría del gasto
- description: Descripción breve
- line_items: Array con description, quantity, unit_price, total
- audit_warnings: Advertencias detectadas
- confidence: Score 0.0-1.0

DEVUELVE SOLO EL JSON."""

    async def process_invoice(
        self,
        db: AsyncSession,
        invoice: Invoice,
        user_id: int,
    ) -> dict:
        api_key = await self._get_api_key(db, user_id)
        if not api_key or "demo" in api_key.lower():
            return {
                "error": "API key de Gemini no configurada",
                "vendor_name": "Error en procesamiento",
                "total_amount": None,
                "transaction_type": "expense",
                "category": "error",
                "confidence": 0.0,
            }

        check = await self.cost_control.can_process_request(db, user_id)
        if not check["allowed"]:
            return {
                "error": f"Límite alcanzado: {check.get('reason', 'unknown')}",
                "vendor_name": "Límite alcanzado",
                "total_amount": None,
                "transaction_type": "expense",
                "category": "error",
                "confidence": 0.0,
            }

        model_name = await self._get_model_name(db, user_id)
        start_time = self.cost_control.record_request_start()

        try:
            import google.generativeai as genai
            genai.configure(api_key=api_key)

            if invoice.file_type == "image":
                prompt = self._build_image_prompt()
                model = genai.GenerativeModel(
                    model_name=model_name,
                    system_instruction=prompt,
                    generation_config={"temperature": 0.1, "max_output_tokens": 8192, "response_mime_type": "application/json"},
                )

                from PIL import Image
                image = Image.open(invoice.file_path)
                response = await model.generate_content_async([prompt, image])

                input_tokens = 0
                output_tokens = 0
                usage = getattr(response, 'usage_metadata', None)
                if usage:
                    input_tokens = getattr(usage, 'prompt_token_count', 0) or 0
                    output_tokens = getattr(usage, 'candidates_token_count', 0) or 0

                raw_text = response.text.strip()
                raw_text = re.sub(r'^```(?:json)?\s*', '', raw_text)
                raw_text = re.sub(r'\s*```$', '', raw_text)

            elif invoice.file_type == "pdf":
                pdf_text = self.extract_text_from_pdf(invoice.file_path)
                prompt_image = self._build_image_prompt()
                model = genai.GenerativeModel(
                    model_name=model_name,
                    system_instruction=prompt_image,
                    generation_config={"temperature": 0.1, "max_output_tokens": 8192, "response_mime_type": "application/json"},
                )

                if pdf_text.strip() and len(pdf_text.strip()) > 50:
                    prompt_pdf = self._build_pdf_prompt()
                    full_prompt = f"{prompt_pdf}\n\nTEXTO DE LA FACTURA:\n{pdf_text[:15000]}"
                    response = await model.generate_content_async(full_prompt)
                else:
                    images = self._pdf_to_images(invoice.file_path)
                    if images:
                        response = await model.generate_content_async([prompt_image, *images])
                    else:
                        return {"error": "No se pudo extraer texto ni imágenes del PDF"}

                input_tokens = 0
                output_tokens = 0
                usage = getattr(response, 'usage_metadata', None)
                if usage:
                    input_tokens = getattr(usage, 'prompt_token_count', 0) or 0
                    output_tokens = getattr(usage, 'candidates_token_count', 0) or 0

                raw_text = response.text.strip()
                raw_text = re.sub(r'^```(?:json)?\s*', '', raw_text)
                raw_text = re.sub(r'\s*```$', '', raw_text)
            else:
                return {"error": f"Tipo de archivo no soportado: {invoice.file_type}"}

            try:
                extracted = json.loads(raw_text)
            except json.JSONDecodeError:
                logger.warning(f"Initial JSON parse failed, trying regex extraction. Raw: {raw_text[:200]}")
                json_match = re.search(r'\{.*\}', raw_text, re.DOTALL)
                if json_match:
                    try:
                        extracted = json.loads(json_match.group())
                    except json.JSONDecodeError:
                        logger.error(f"Regex JSON parse also failed: {raw_text[:500]}")
                        return {"error": "Error al parsear la respuesta de Gemini"}
                else:
                    logger.error(f"No JSON found in Gemini response: {raw_text[:500]}")
                    return {"error": "Error al parsear la respuesta de Gemini"}

            extracted = self._validate_and_clean_data(extracted)
            extracted["gemini_model_used"] = model_name

            await self.cost_control.record_gemini_usage(
                db, invoice, model_name, input_tokens, output_tokens, start_time
            )

            await self._log_llm_usage(db, user_id, model_name, input_tokens, output_tokens, start_time, True)

            return extracted

        except Exception as e:
            logger.error(f"Error processing invoice with Gemini: {e}")
            await self._log_llm_usage(db, user_id, model_name, 0, 0, start_time, False, str(e))
            return {
                "error": f"Error de procesamiento: {str(e)}",
                "vendor_name": "Error en procesamiento",
                "total_amount": None,
                "transaction_type": "expense",
                "category": "error",
                "confidence": 0.0,
            }

    async def _log_llm_usage(
        self,
        db: AsyncSession,
        user_id: int,
        model_name: str,
        input_tokens: int,
        output_tokens: int,
        start_time: float,
        success: bool,
        error_msg: str = None,
    ) -> None:
        try:
            from src.ai_management.models import LLMRequestLog
            elapsed_ms = int((time.time() - start_time) * 1000)
            log_entry = LLMRequestLog(
                user_id=user_id,
                caller="invoices",
                model_name=model_name,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                total_tokens=input_tokens + output_tokens,
                estimated_cost=self.cost_control.calculate_cost(model_name, input_tokens, output_tokens),
                request_duration_ms=elapsed_ms,
                api_success=success,
                error_message=error_msg,
            )
            db.add(log_entry)
            await db.commit()
        except Exception as e:
            logger.warning(f"Failed to log LLM usage: {e}")

    async def process_finance_chat(
        self,
        query: str,
        context_data: list,
        user_id: int,
    ) -> str:
        api_key = settings.GEMINI_API_KEY
        if not api_key or "demo" in api_key.lower():
            return "El chat financiero no está disponible. Configura la API key de Gemini."

        try:
            import google.generativeai as genai
            genai.configure(api_key=api_key)

            system_prompt = """Eres el CFO virtual de una empresa chilena. Tienes acceso a datos de facturación.
Responde preguntas sobre finanzas, gastos, ingresos y tendencias usando los datos proporcionados.
Sé conciso, profesional y da respuestas en español con datos concretos.
Si no tienes suficiente información, indícalo claramente."""

            context_str = json.dumps(context_data, ensure_ascii=False, indent=2)
            full_prompt = f"{system_prompt}\n\nDATOS DE FACTURAS:\n{context_str}\n\nPREGUNTA: {query}"

            model = genai.GenerativeModel(
                model_name="gemini-2.5-flash",
                system_instruction=system_prompt,
                generation_config={"temperature": 0.3, "max_output_tokens": 500},
            )
            response = await model.generate_content_async(full_prompt)
            return response.text.strip()
        except Exception as e:
            logger.error(f"Error in finance chat: {e}")
            return f"Error al procesar tu consulta: {str(e)}"


class ExportService:
    @staticmethod
    def _format_date(dt) -> str:
        if hasattr(dt, 'strftime'):
            return dt.strftime("%Y-%m-%d")
        return str(dt) if dt else ""

    @staticmethod
    def _to_number(val) -> float:
        try:
            return float(val) if val else 0.0
        except (ValueError, TypeError):
            return 0.0

    @staticmethod
    def _fmt_amount(val) -> str:
        return f"{ExportService._to_number(val):.2f}"

    def export_csv_generic(self, invoices: List[Invoice]) -> str:
        import csv
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(["ID", "Fecha", "Proveedor", "RUT", "Folio DTE", "Categoria",
                          "Descripcion", "Neto", "IVA", "Total", "Moneda", "Estado", "Alertas"])
        for inv in invoices:
            d = inv.to_dict()
            total = self._to_number(d.get("total_amount"))
            tax = self._to_number(d.get("tax_amount"))
            neto = total - tax if total and tax else total
            writer.writerow([
                d.get("id"), d.get("invoice_date"), d.get("vendor_name"),
                d.get("vendor_tax_id"), d.get("invoice_number"), d.get("category"),
                d.get("description"), self._fmt_amount(neto), self._fmt_amount(tax),
                self._fmt_amount(total), d.get("currency"),
                "Procesado" if d.get("processed") else "Pendiente",
                "; ".join(d.get("audit_flags", [])) if d.get("audit_flags") else ""
            ])
        return output.getvalue()

    def export_json(self, invoices: List[Invoice]) -> str:
        return json.dumps([inv.to_dict() for inv in invoices], ensure_ascii=False, indent=2)

    def export_quickbooks(self, invoices: List[Invoice]) -> str:
        import csv
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(["BillNo", "Vendor", "TransactionDate", "DueDate", "Total", "Account", "LineAmount", "LineDescription"])
        for inv in invoices:
            d = inv.to_dict()
            writer.writerow([
                d.get("invoice_number"), d.get("vendor_name"), d.get("invoice_date"),
                d.get("invoice_date"), self._fmt_amount(d.get("total_amount")),
                "Cost of Goods Sold", self._fmt_amount(d.get("total_amount")), d.get("description")
            ])
        return output.getvalue()

    def export_quickbooks_bills(self, invoices: List[Invoice]) -> str:
        import csv
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(["BillNo", "Vendor", "TransactionDate", "DueDate", "Account",
                          "LineAmount", "LineDescription", "Total", "TaxCode"])
        for inv in invoices:
            d = inv.to_dict()
            writer.writerow([
                d.get("invoice_number"), d.get("vendor_name"), d.get("invoice_date"),
                d.get("invoice_date"), "Cost of Goods Sold",
                self._fmt_amount(d.get("total_amount")), d.get("description"),
                self._fmt_amount(d.get("total_amount")), "IVA"
            ])
        return output.getvalue()

    def export_xero_bills(self, invoices: List[Invoice]) -> str:
        import csv
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(["ContactName", "InvoiceNumber", "InvoiceDate", "DueDate",
                          "Description", "Quantity", "UnitAmount", "AccountCode", "TaxType", "Currency"])
        for inv in invoices:
            d = inv.to_dict()
            writer.writerow([
                d.get("vendor_name"), d.get("invoice_number"), d.get("invoice_date"),
                d.get("invoice_date"), d.get("description"), 1,
                self._fmt_amount(d.get("total_amount")), "500", "IVA", d.get("currency", "CLP")
            ])
        return output.getvalue()

    def export_odoo_vendor_bills(self, invoices: List[Invoice]) -> str:
        import csv
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(["move_type", "partner_id/name", "invoice_date", "invoice_date_due",
                          "ref", "currency_id/name", "invoice_line_ids/description",
                          "invoice_line_ids/quantity", "invoice_line_ids/price_unit",
                          "invoice_line_ids/account_id"])
        for inv in invoices:
            d = inv.to_dict()
            writer.writerow([
                "in_invoice", d.get("vendor_name"), d.get("invoice_date"),
                d.get("invoice_date"), d.get("invoice_number"), d.get("currency", "CLP"),
                d.get("description"), 1, self._fmt_amount(d.get("total_amount")),
                "500000"
            ])
        return output.getvalue()

    def export_contaplus(self, invoices: List[Invoice]) -> str:
        import csv
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(["Fecha", "Cuenta", "Concepto", "Debe", "Haber", "Documento"])
        for inv in invoices:
            d = inv.to_dict()
            total = self._to_number(d.get("total_amount"))
            tax = self._to_number(d.get("tax_amount"))
            neto = total - tax
            writer.writerow([d.get("invoice_date"), "601000", f"Compra: {d.get('vendor_name')}",
                              self._fmt_amount(neto), "0", d.get("invoice_number")])
            if tax > 0:
                writer.writerow([d.get("invoice_date"), "470000", f"IVA: {d.get('vendor_name')}",
                                  self._fmt_amount(tax), "0", d.get("invoice_number")])
            writer.writerow([d.get("invoice_date"), "400000", f"Proveedor: {d.get('vendor_name')}",
                              "0", self._fmt_amount(total), d.get("invoice_number")])
        return output.getvalue()

    def export_sii_libro_compras(self, invoices: List[Invoice], report_rut: Optional[str] = None) -> str:
        import csv
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(["TipoDocumento", "Folio", "RUTProveedor", "RazonSocial", "FechaDocumento",
                          "FechaRecepcion", "FechaPago", "MontoNeto", "IVA", "MontoExento",
                          "MontoTotal", "IVARetenido", "IVAUSoComun", "CodigoSII", "FormaPago", "Estado"])
        for inv in invoices:
            d = inv.to_dict()
            total = self._to_number(d.get("total_amount"))
            tax = self._to_number(d.get("tax_amount"))
            neto = total - tax
            writer.writerow([
                "Factura", d.get("invoice_number"), d.get("vendor_tax_id"),
                d.get("vendor_name"), d.get("invoice_date"), d.get("invoice_date"),
                d.get("invoice_date"), self._fmt_amount(neto), self._fmt_amount(tax), "0",
                self._fmt_amount(total), "0", "0", "01", "Contado", "Procesado"
            ])
        return output.getvalue()

    def export_sii_libro_ventas(self, invoices: List[Invoice], report_rut: Optional[str] = None) -> str:
        import csv
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(["TipoDocumento", "Folio", "RUTCliente", "RazonSocial", "FechaDocumento",
                          "MontoNeto", "IVA", "MontoExento", "MontoTotal", "IVARetenido", "CodigoSII", "Estado"])
        for inv in invoices:
            d = inv.to_dict()
            total = self._to_number(d.get("total_amount"))
            tax = self._to_number(d.get("tax_amount"))
            neto = total - tax
            writer.writerow([
                "Factura", d.get("invoice_number"), d.get("vendor_tax_id"),
                d.get("vendor_name"), d.get("invoice_date"), self._fmt_amount(neto),
                self._fmt_amount(tax), "0", self._fmt_amount(total), "0", "01", "Procesado"
            ])
        return output.getvalue()

    def export_excel_generic(self, invoices: List[Invoice]) -> bytes:
        from openpyxl import Workbook
        wb = Workbook()
        ws = wb.active
        ws.title = "Facturas"
        headers = ["ID", "Fecha", "Proveedor", "RUT", "Folio DTE", "Categoria",
                    "Descripcion", "Neto", "IVA", "Total", "Moneda", "Estado", "Alertas"]
        ws.append(headers)
        for inv in invoices:
            d = inv.to_dict()
            total = self._to_number(d.get("total_amount"))
            tax = self._to_number(d.get("tax_amount"))
            neto = total - tax if total and tax else total
            ws.append([
                d.get("id"), d.get("invoice_date"), d.get("vendor_name"),
                d.get("vendor_tax_id"), d.get("invoice_number"), d.get("category"),
                d.get("description"), neto, tax, total, d.get("currency"),
                "Procesado" if d.get("processed") else "Pendiente",
                "; ".join(d.get("audit_flags", [])) if d.get("audit_flags") else ""
            ])
        buffer = io.BytesIO()
        wb.save(buffer)
        buffer.seek(0)
        return buffer.getvalue()


class WebSocketManager:
    def __init__(self):
        self.active_connections: list = []
        self.notification_count = 0

    async def connect(self, websocket: WebSocket, user_id: int) -> None:
        await websocket.accept()
        self.active_connections.append({"websocket": websocket, "user_id": user_id})
        await self.send_personal_message(
            {"type": "connection_established", "message": "Conectado", "timestamp": datetime.utcnow().isoformat()},
            websocket,
        )

    def disconnect(self, websocket: WebSocket) -> None:
        self.active_connections = [
            c for c in self.active_connections if c["websocket"] != websocket
        ]

    async def send_personal_message(self, message: dict, websocket: WebSocket) -> None:
        try:
            await websocket.send_json(message)
        except Exception as e:
            logger.warning(f"Error sending WS message: {e}")

    async def broadcast(self, message: dict, user_id: int) -> None:
        self.notification_count += 1
        for conn in self.active_connections:
            if conn["user_id"] == user_id:
                await self.send_personal_message(message, conn["websocket"])

    async def notify_processing_complete(self, invoice_id: str, result: dict, user_id: int) -> None:
        await self.broadcast({
            "type": "processing_complete",
            "invoice_id": invoice_id,
            "success": "error" not in result,
            "vendor_name": result.get("vendor_name"),
            "total_amount": result.get("total_amount"),
            "currency": result.get("currency"),
            "category": result.get("category"),
            "transaction_type": result.get("transaction_type"),
        }, user_id)

    async def notify_invoice_uploaded(self, invoice_id: str, filename: str, user_id: int) -> None:
        await self.broadcast({
            "type": "invoice_uploaded",
            "invoice_id": invoice_id,
            "filename": filename,
        }, user_id)

    async def notify_statistics_update(self, stats: dict, user_id: int) -> None:
        await self.broadcast({
            "type": "statistics_update",
            "stats": stats,
        }, user_id)

    async def notify_cost_alert(self, alert_info: dict, user_id: int) -> None:
        await self.broadcast({
            "type": "cost_alert",
            "severity": alert_info.get("severity", "warning"),
            "message": alert_info.get("message", ""),
        }, user_id)

    async def send_heartbeat(self) -> None:
        message = {
            "type": "heartbeat",
            "connections": len(self.active_connections),
            "notifications_sent": self.notification_count,
        }
        for conn in self.active_connections:
            await self.send_personal_message(message, conn["websocket"])

    def get_status(self) -> dict:
        return {
            "active_connections": len(self.active_connections),
            "notifications_sent": self.notification_count,
            "status": "running",
        }


websocket_manager = WebSocketManager()


class WebhookSender:
    def __init__(self):
        self.timeout = 5

    async def trigger_event(
        self,
        db: AsyncSession,
        event_name: str,
        data: dict,
        user_id: int,
    ) -> dict:
        import requests

        query = select(WebhookEndpoint).where(
            WebhookEndpoint.user_id == user_id,
            WebhookEndpoint.is_active == True,
        )
        result = await db.execute(query)
        endpoints = result.scalars().all()

        matching = []
        for ep in endpoints:
            events_list = []
            if ep.events:
                try:
                    events_list = json.loads(ep.events)
                except (json.JSONDecodeError, TypeError):
                    events_list = []
            if "*" in events_list or event_name in events_list:
                matching.append(ep)

        if not matching:
            return {"status": "no_subscribers"}

        results = []
        payload = {
            "event": event_name,
            "timestamp": datetime.utcnow().isoformat(),
            "data": data,
        }

        for ep in matching:
            try:
                resp = requests.post(
                    ep.url,
                    json=payload,
                    timeout=self.timeout,
                    headers={
                        "Content-Type": "application/json",
                        "User-Agent": "InvoiceFlow-Chile-Webhook/1.0",
                        "X-InvoiceFlow-Chile-Event": event_name,
                    },
                )
                results.append({
                    "endpoint_id": str(ep.id),
                    "url": ep.url,
                    "status_code": resp.status_code,
                    "success": resp.ok,
                })
            except Exception as e:
                results.append({
                    "endpoint_id": str(ep.id),
                    "url": ep.url,
                    "success": False,
                    "error": str(e),
                })

        return {"status": "completed", "results": results}


async def heartbeat_task():
    while True:
        await asyncio.sleep(30)
        try:
            await websocket_manager.send_heartbeat()
        except Exception as e:
            logger.warning(f"Heartbeat error: {e}")
