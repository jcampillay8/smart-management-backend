# src/purchases/models.py
import uuid
from typing import List, Optional
from datetime import datetime, date

from sqlalchemy import Column, String, Numeric, Boolean, Date, Integer, ForeignKey, DateTime
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship, Mapped, mapped_column
from src.database import BaseModel
from src.config import settings


class Proveedor(BaseModel):
    __tablename__ = "proveedores"
    __table_args__ = {"schema": settings.DB_SCHEMA}

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    nombre_empresa: Mapped[str] = mapped_column(String(255), nullable=False)
    rut: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    nombre_contacto: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    telefono: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    direccion: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    email: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)


class Compra(BaseModel):
    __tablename__ = "compras"
    __table_args__ = {"schema": settings.DB_SCHEMA}

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    usuario_id: Mapped[int] = mapped_column(Integer, nullable=False)
    estado: Mapped[str] = mapped_column(String(50), default="pendiente")
    pedido_realizado: Mapped[bool] = mapped_column(Boolean, default=False)
    fecha: Mapped[date] = mapped_column(Date, nullable=False)
    total: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False)
    factura_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    proveedor: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    notas: Mapped[Optional[str]] = mapped_column(String(1000), nullable=True)

    items: Mapped[List["CompraItem"]] = relationship(back_populates="compra", cascade="all, delete-orphan")


class CompraItem(BaseModel):
    __tablename__ = "compra_items"
    __table_args__ = {"schema": settings.DB_SCHEMA}

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    compra_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey(f"{settings.DB_SCHEMA}.compras.id", ondelete="CASCADE"))
    producto_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    bodega_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), nullable=True)
    cantidad: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False)
    precio_unitario: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False)

    compra: Mapped["Compra"] = relationship(back_populates="items")