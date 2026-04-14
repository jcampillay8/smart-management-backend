import os
import logging
import httpx
from typing import Dict, Any, List, Optional
from pydantic import EmailStr
from jinja2 import Environment, FileSystemLoader, TemplateNotFound
from fastapi_mail import FastMail, ConnectionConfig, MessageSchema, MessageType
from fastapi.encoders import jsonable_encoder

from src.config import settings

log = logging.getLogger(__name__)

# Configuración de rutas de plantillas
current_dir = os.path.dirname(os.path.abspath(__file__))
templates_path = os.path.normpath(os.path.join(current_dir, '..', 'templates', 'emails'))

# Configuración Global desde Settings
PROVIDER = (getattr(settings, "EMAIL_PROVIDER", "smtp")).lower()
EMAIL_FROM = settings.email_from_resolved
RESEND_API_KEY = settings.RESEND_API_KEY.get_secret_value() if settings.RESEND_API_KEY else None

# Configuración SMTP para FastMail
smtp_conf = None
if PROVIDER == "smtp":
    smtp_conf = ConnectionConfig(
        MAIL_USERNAME=settings.MAIL_USERNAME,
        MAIL_PASSWORD=settings.MAIL_PASSWORD,
        MAIL_FROM=settings.MAIL_FROM,
        MAIL_PORT=settings.MAIL_PORT,
        MAIL_SERVER=settings.MAIL_SERVER,
        MAIL_FROM_NAME=settings.MAIL_FROM_NAME,
        MAIL_STARTTLS=settings.MAIL_STARTTLS,
        MAIL_SSL_TLS=settings.MAIL_SSL_TLS,
        USE_CREDENTIALS=settings.USE_CREDENTIALS,
        VALIDATE_CERTS=settings.VALIDATE_CERTS,
        TEMPLATE_FOLDER=templates_path,
    )

class EmailService:
    def __init__(self):
        self.provider = PROVIDER
        self.template_env = Environment(loader=FileSystemLoader(templates_path))
        if self.provider == "smtp":
            self.fm = FastMail(smtp_conf)
        log.info("EmailService iniciado [Modo: %s]", self.provider)

    def _render_template(self, template_name: str, template_vars: Dict[str, Any] | None) -> str:
        try:
            template = self.template_env.get_template(template_name)
            # Variables globales para todos los correos
            vars = {
                "app_name": "OppyChat",
                "support_email": settings.SUPPORT_EMAIL,
                **(template_vars or {})
            }
            return template.render(**vars)
        except TemplateNotFound:
            log.error("Plantilla '%s' no encontrada en %s", template_name, templates_path)
            raise

    async def send_email(
        self,
        subject: str,
        recipients: List[EmailStr],
        template_name: str,
        template_vars: Dict[str, Any] | None = None
    ) -> bool:
        """
        Método genérico para enviar correos usando Resend o SMTP.
        """
        html_content = self._render_template(template_name, template_vars)

        # --- Lógica para RESEND ---
        if self.provider == "resend":
            if not RESEND_API_KEY:
                log.error("RESEND_API_KEY no detectada en entorno.")
                return False

            payload = {
                "from": EMAIL_FROM,
                "to": [str(r) for r in recipients],
                "subject": subject,
                "html": html_content,
            }

            try:
                async with httpx.AsyncClient(timeout=10) as client:
                    resp = await client.post(
                        "https://api.resend.com/emails",
                        json=payload,
                        headers={"Authorization": f"Bearer {RESEND_API_KEY}"},
                    )
                if resp.status_code >= 300:
                    log.error("Error Resend API: %s", resp.text)
                    return False
                return True
            except Exception as e:
                log.error("Fallo de conexión con Resend: %s", e)
                return False

        # --- Lógica para SMTP ---
        elif self.provider == "smtp":
            try:
                message = MessageSchema(
                    subject=subject,
                    recipients=[str(r) for r in recipients],
                    body=html_content,
                    subtype=MessageType.html
                )
                await self.fm.send_message(message)
                return True
            except Exception as e:
                log.error("Fallo de envío SMTP: %s", e)
                return False
        
        return False

    # --- MÉTODOS DE FLUJO ESPECÍFICOS ---

    async def send_verification_email(self, email: str, user_name: str, token: str):
        """Envía el correo con el link para activar la cuenta."""
        confirmation_url = f"{settings.API_URL}/confirm-email/{token}"
        await self.send_email(
            subject="Activa tu cuenta de OppyChat",
            recipients=[email],
            template_name="email_confirmation.html",
            template_vars={
                "user_name": user_name,
                "confirmation_url": confirmation_url,
                "expiration_minutes": 1440 # 24 horas por ejemplo
            }
        )

    async def send_password_reset_email(self, email: str, user_name: str, token: str):
        """Envía el correo para cambiar la contraseña olvidada."""
        reset_url = f"{settings.API_URL}/reset-password?token={token}"
        await self.send_email(
            subject="Restablece tu contraseña de OppyChat",
            recipients=[email],
            template_name="password_reset.html",
            template_vars={
                "user_name": user_name,
                "reset_url": reset_url,
                "expiration_minutes": settings.PASSWORD_RESET_TOKEN_EXPIRE_MINUTES
            }
        )

# Instancia global para importar en los routers
email_service = EmailService()