# src/notes/models.py
import uuid
from typing import Optional, List
from datetime import datetime
from sqlalchemy import String, ForeignKey, DateTime, Enum, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
import enum

from src.database import BaseModel
from src.config import settings


class UrgenciaNota(str, enum.Enum):
    ALTA = "alta"
    MEDIA = "media"
    BAJA = "baja"


class Nota(BaseModel):
    __tablename__ = "notas"
    __table_args__ = ({'schema': settings.DB_SCHEMA})

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    autor_id: Mapped[int] = mapped_column(ForeignKey(f"{settings.DB_SCHEMA}.users.id", ondelete="CASCADE"))
    titulo: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    contenido: Mapped[str] = mapped_column(String(2000), nullable=False)
    urgencia: Mapped[UrgenciaNota] = mapped_column(
        Enum(UrgenciaNota, schema=settings.DB_SCHEMA, name="urgencianota"),
        default=UrgenciaNota.MEDIA,
        server_default="media"
    )
    fecha: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    autor: Mapped["User"] = relationship("src.models.User", foreign_keys=[autor_id])
    menciones: Mapped[List["NotaMencion"]] = relationship(back_populates="nota", cascade="all, delete-orphan")


class NotaMencion(BaseModel):
    __tablename__ = "nota_menciones"
    __table_args__ = ({'schema': settings.DB_SCHEMA})

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    nota_id: Mapped[uuid.UUID] = mapped_column(ForeignKey(f"{settings.DB_SCHEMA}.notas.id", ondelete="CASCADE"))
    user_id: Mapped[int] = mapped_column(ForeignKey(f"{settings.DB_SCHEMA}.users.id", ondelete="CASCADE"))

    nota: Mapped["Nota"] = relationship(back_populates="menciones")
    usuario: Mapped["User"] = relationship("src.models.User", foreign_keys=[user_id])
