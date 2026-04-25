# src/purchases/models.py
import uuid
from datetime import datetime, date
from typing import List, Optional
from sqlalchemy import String, ForeignKey, Numeric, DateTime, Date, func, text, Boolean
from sqlalchemy.orm import Mapped, mapped_column, relationship
from src.database import BaseModel
from src.config import settings

class Compra(BaseModel):
    __tablename__ = "compras"
    __table_args__ = ({'schema': settings.DB_SCHEMA})

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    usuario_id: Mapped[int] = mapped_column(ForeignKey(f"{settings.DB_SCHEMA}.users.id"))
    estado: Mapped[str] = mapped_column(String(50), default="pendiente")
    pedido_realizado: Mapped[bool] = mapped_column(Boolean, default=False, server_default=text("false"))
    fecha: Mapped[date] = mapped_column(Date, server_default=func.current_date())
    total: Mapped[float] = mapped_column(Numeric(10, 2), default=0.0)
    factura_url: Mapped[Optional[str]] = mapped_column(String(1000), nullable=True)
    proveedor: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    notas: Mapped[Optional[str]] = mapped_column(String(1000), nullable=True)
    
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    usuario: Mapped["User"] = relationship("src.models.User")
    items: Mapped[List["CompraItem"]] = relationship(back_populates="compra", cascade="all, delete-orphan")

class CompraItem(BaseModel):
    __tablename__ = "compra_items"
    __table_args__ = ({'schema': settings.DB_SCHEMA})

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    compra_id: Mapped[uuid.UUID] = mapped_column(ForeignKey(f"{settings.DB_SCHEMA}.compras.id", ondelete="CASCADE"))
    producto_id: Mapped[uuid.UUID] = mapped_column(ForeignKey(f"{settings.DB_SCHEMA}.productos.id"))
    bodega_id: Mapped[Optional[uuid.UUID]] = mapped_column(ForeignKey(f"{settings.DB_SCHEMA}.bodegas.id"), nullable=True)
    cantidad: Mapped[float] = mapped_column(Numeric(10, 2), default=0.0)
    precio_unitario: Mapped[float] = mapped_column(Numeric(10, 2), default=0.0)
    
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    compra: Mapped["Compra"] = relationship(back_populates="items")
    producto: Mapped["Producto"] = relationship("src.inventory.models.Producto")
    bodega: Mapped[Optional["Bodega"]] = relationship("src.inventory.models.Bodega")
