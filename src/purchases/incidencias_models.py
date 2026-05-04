# src/purchases/incidencias_models.py
import uuid
from typing import Optional
from datetime import datetime
from sqlalchemy import String, ForeignKey, DateTime, Boolean, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy import text

from src.database import BaseModel
from src.config import settings


class NotificacionIncidencia(BaseModel):
    __tablename__ = "notificaciones_incidencia"
    __table_args__ = ({'schema': settings.DB_SCHEMA})

    # No tiene is_deleted porque es inmutable
    is_deleted = None

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    compra_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey(f"{settings.DB_SCHEMA}.compras.id", ondelete="CASCADE")
    )
    tipo: Mapped[str] = mapped_column(String(100), nullable=False)  # diferencia_cantidad | rechazada | etc.
    titulo: Mapped[str] = mapped_column(String(500), nullable=False)
    detalle: Mapped[Optional[dict]] = mapped_column(JSONB, server_default=text("'{}'::jsonb"), nullable=True)
    resuelto: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    created_by: Mapped[Optional[int]] = mapped_column(
        ForeignKey(f"{settings.DB_SCHEMA}.users.id", ondelete="SET NULL"), nullable=True
    )

    compra: Mapped["Compra"] = relationship("src.purchases.models.Compra")
    creador: Mapped[Optional["User"]] = relationship("src.models.User", foreign_keys=[created_by])


class PlantillaEmail(BaseModel):
    __tablename__ = "plantillas_email"
    __table_args__ = ({'schema': settings.DB_SCHEMA})

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    nombre: Mapped[str] = mapped_column(String(200), nullable=False)
    asunto: Mapped[str] = mapped_column(String(500), nullable=False)
    cuerpo: Mapped[str] = mapped_column(String(5000), nullable=False)
    created_by: Mapped[Optional[int]] = mapped_column(
        ForeignKey(f"{settings.DB_SCHEMA}.users.id", ondelete="SET NULL"), nullable=True
    )

    creador: Mapped[Optional["User"]] = relationship("src.models.User", foreign_keys=[created_by])
