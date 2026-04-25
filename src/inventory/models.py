# src/inventory/models.py
import uuid
from datetime import datetime
from typing import List, Optional
from sqlalchemy import String, ForeignKey, Numeric, DateTime, func, UniqueConstraint, text, Boolean
from sqlalchemy.orm import Mapped, mapped_column, relationship
from src.database import BaseModel
from src.config import settings

class Categoria(BaseModel):
    __tablename__ = "categorias"
    __table_args__ = ({'schema': settings.DB_SCHEMA})

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    nombre: Mapped[str] = mapped_column(String(100), nullable=False)

    productos: Mapped[List["Producto"]] = relationship(back_populates="categoria")

class Producto(BaseModel):
    __tablename__ = "productos"
    __table_args__ = ({'schema': settings.DB_SCHEMA})

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    nombre: Mapped[str] = mapped_column(String(200), nullable=False)
    categoria_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey(f"{settings.DB_SCHEMA}.categorias.id", ondelete="CASCADE")
    )
    unidad: Mapped[str] = mapped_column(String(50), default="unidad")
    costo_unitario: Mapped[float] = mapped_column(Numeric(10, 2), default=0.0)
    
    # --- AJUSTE IVA ---
    iva_incluido: Mapped[bool] = mapped_column(Boolean, default=True, server_default=text("true"))
    iva_porcentaje: Mapped[float] = mapped_column(Numeric(5, 2), default=19.0, server_default=text("19.0"))
    
    # Nuevos campos del proyecto original
    codigo_barra: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    factor_conversion: Mapped[float] = mapped_column(Numeric(10, 4), default=1.0, server_default=text("1.0"))
    unidad_conversion: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    imagen_url: Mapped[Optional[str]] = mapped_column(String(1000), nullable=True)
    precio_venta: Mapped[float] = mapped_column(Numeric(10, 2), default=0.0, server_default=text("0.0"))
    marca: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    proveedor: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)

    # Relaciones
    categoria: Mapped["Categoria"] = relationship(back_populates="productos")
    bodegas_config: Mapped[List["ProductoBodega"]] = relationship(back_populates="producto", cascade="all, delete-orphan")
    
class Bodega(BaseModel):
    __tablename__ = "bodegas"
    __table_args__ = ({'schema': settings.DB_SCHEMA})

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    nombre: Mapped[str] = mapped_column(String(100), nullable=False)
    icono: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)

    productos_config: Mapped[List["ProductoBodega"]] = relationship(back_populates="bodega")

class ProductoBodega(BaseModel):
    """Refactorización: Stock mínimo específico por bodega"""
    __tablename__ = "producto_bodegas"
    __table_args__ = (
        UniqueConstraint("producto_id", "bodega_id", name="uix_producto_bodega"),
        {'schema': settings.DB_SCHEMA}
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    producto_id: Mapped[uuid.UUID] = mapped_column(ForeignKey(f"{settings.DB_SCHEMA}.productos.id", ondelete="CASCADE"))
    bodega_id: Mapped[uuid.UUID] = mapped_column(ForeignKey(f"{settings.DB_SCHEMA}.bodegas.id", ondelete="CASCADE"))
    stock_minimo: Mapped[float] = mapped_column(Numeric(10, 2), default=0.0)
    stock_actual: Mapped[float] = mapped_column(Numeric(10, 2), default=0.0)
    
    # Nuevos campos del proyecto original
    coordenada_letra: Mapped[Optional[str]] = mapped_column(String(10), nullable=True)
    coordenada_numero: Mapped[Optional[str]] = mapped_column(String(10), nullable=True)

    producto: Mapped["Producto"] = relationship(back_populates="bodegas_config")
    bodega: Mapped["Bodega"] = relationship(back_populates="productos_config")