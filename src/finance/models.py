import uuid
from datetime import date, datetime
from typing import Optional, List

from sqlalchemy import String, Numeric, Boolean, Date, Integer, ForeignKey, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.database import BaseModel
from src.config import settings


class CategoriaGasto(BaseModel):
    __tablename__ = "categorias_gasto"
    __table_args__ = {"schema": settings.DB_SCHEMA}

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    nombre: Mapped[str] = mapped_column(String(200), nullable=False)
    descripcion: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    activo: Mapped[bool] = mapped_column(Boolean, default=True)

    gastos: Mapped[List["GastoOperativo"]] = relationship(back_populates="categoria")


class GastoOperativo(BaseModel):
    __tablename__ = "gastos_operativos"
    __table_args__ = {"schema": settings.DB_SCHEMA}

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    categoria_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey(f"{settings.DB_SCHEMA}.categorias_gasto.id", ondelete="SET NULL"),
        nullable=True
    )
    usuario_id: Mapped[int] = mapped_column(Integer, nullable=False)
    monto: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False)
    fecha_gasto: Mapped[date] = mapped_column(Date, nullable=False)
    es_fijo: Mapped[bool] = mapped_column(Boolean, default=False)
    descripcion: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    proveedor: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    numero_documento: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    metodo_pago: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)

    categoria: Mapped[Optional["CategoriaGasto"]] = relationship(back_populates="gastos")
