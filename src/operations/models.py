# src/operations/models.py
import uuid
import enum
from typing import List, Optional
from datetime import datetime, date
from sqlalchemy import String, ForeignKey, Numeric, DateTime, Date, Enum, Boolean, func, Integer, text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from src.database import BaseModel
from src.config import settings

class TipoMovimiento(str, enum.Enum):
    CONTEO = "conteo"
    CONSUMO = "consumo"
    MERMA = "merma"
    ENTRADA = "entrada"
    AJUSTE_POSITIVO = "ajuste_positivo"
    AJUSTE_NEGATIVO = "ajuste_negativo"
    TRANSFERENCIA = "transferencia"

class RegistroStock(BaseModel):
    __tablename__ = "registros_stock"
    __table_args__ = ({'schema': settings.DB_SCHEMA})

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    producto_id: Mapped[uuid.UUID] = mapped_column(ForeignKey(f"{settings.DB_SCHEMA}.productos.id", ondelete="CASCADE"))
    bodega_id: Mapped[uuid.UUID] = mapped_column(ForeignKey(f"{settings.DB_SCHEMA}.bodegas.id"))
    cantidad: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False)
    
    tipo_movimiento: Mapped[TipoMovimiento] = mapped_column(
        Enum(TipoMovimiento, schema=settings.DB_SCHEMA), 
        nullable=False
    )
    
    motivo_merma: Mapped[Optional[str]] = mapped_column(String(255))
    descripcion_merma: Mapped[Optional[str]] = mapped_column(String(500))
    
    fecha_recuento: Mapped[date] = mapped_column(Date, server_default=func.current_date())
    fecha_vencimiento: Mapped[Optional[date]] = mapped_column(Date)
    
    usuario_id: Mapped[int] = mapped_column(ForeignKey(f"{settings.DB_SCHEMA}.users.id"))
    evento_id: Mapped[Optional[uuid.UUID]] = mapped_column(ForeignKey(f"{settings.DB_SCHEMA}.eventos.id", ondelete="SET NULL"))
    transfer_id: Mapped[Optional[str]] = mapped_column(String(100))

    # --- RELACIONES ---
    # Importante: Usamos strings para las rutas de los modelos para evitar importaciones circulares
    producto: Mapped["Producto"] = relationship("src.inventory.models.Producto")
    usuario: Mapped["User"] = relationship("src.models.User")
    evento: Mapped[Optional["Evento"]] = relationship("Evento")
    
    # NUEVA RELACIÓN: Esto es lo que faltaba para el history_service
    bodega: Mapped["Bodega"] = relationship("src.inventory.models.Bodega")

class Evento(BaseModel):
    __tablename__ = "eventos"
    __table_args__ = ({'schema': settings.DB_SCHEMA})

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    nombre: Mapped[str] = mapped_column(String(200), nullable=False)
    fecha: Mapped[date] = mapped_column(Date, nullable=False)
    ejecutado: Mapped[bool] = mapped_column(Boolean, default=False)
    cancelado: Mapped[bool] = mapped_column(Boolean, default=False)
    usuario_id: Mapped[int] = mapped_column(ForeignKey(f"{settings.DB_SCHEMA}.users.id"))
    valor_publico: Mapped[Optional[float]] = mapped_column(Numeric(10, 2)) 

    # Relación con los productos específicos del evento
    productos: Mapped[List["EventoProducto"]] = relationship(back_populates="evento", cascade="all, delete-orphan")
    recetas: Mapped[List["EventoReceta"]] = relationship(back_populates="evento", cascade="all, delete-orphan")

class EventoReceta(BaseModel):
    __tablename__ = "evento_recetas"
    __table_args__ = ({'schema': settings.DB_SCHEMA})

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    evento_id: Mapped[uuid.UUID] = mapped_column(ForeignKey(f"{settings.DB_SCHEMA}.eventos.id", ondelete="CASCADE"))
    receta_id: Mapped[uuid.UUID] = mapped_column(ForeignKey(f"{settings.DB_SCHEMA}.recetas.id", ondelete="CASCADE"))
    cantidad: Mapped[int] = mapped_column(Integer, default=1, server_default=text("1"))

    evento: Mapped["Evento"] = relationship(back_populates="recetas")
    receta: Mapped["Receta"] = relationship("src.sales.models.Receta")

class EventoProducto(BaseModel):
    __tablename__ = "evento_productos"
    __table_args__ = ({'schema': settings.DB_SCHEMA})

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    evento_id: Mapped[uuid.UUID] = mapped_column(ForeignKey(f"{settings.DB_SCHEMA}.eventos.id", ondelete="CASCADE"))
    producto_id: Mapped[uuid.UUID] = mapped_column(ForeignKey(f"{settings.DB_SCHEMA}.productos.id"))
    bodega_id: Mapped[uuid.UUID] = mapped_column(ForeignKey(f"{settings.DB_SCHEMA}.bodegas.id"))
    cantidad: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False)

    # Relaciones
    evento: Mapped["Evento"] = relationship(back_populates="productos")
    
    # IMPORTANTE: Asegúrate de importar Bodega de src.inventory.models
    producto: Mapped["Producto"] = relationship("src.inventory.models.Producto")
    bodega: Mapped["Bodega"] = relationship("src.inventory.models.Bodega")

class ConteoInventario(BaseModel):
    __tablename__ = "conteos_inventario"
    __table_args__ = ({'schema': settings.DB_SCHEMA})

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    bodega_id: Mapped[uuid.UUID] = mapped_column(ForeignKey(f"{settings.DB_SCHEMA}.bodegas.id"))
    usuario_id: Mapped[int] = mapped_column(ForeignKey(f"{settings.DB_SCHEMA}.users.id"))
    nombre: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    estado: Mapped[str] = mapped_column(String(50), default="en_progreso")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))

    bodega: Mapped["Bodega"] = relationship("src.inventory.models.Bodega")
    usuario: Mapped["User"] = relationship("src.models.User")
    items: Mapped[List["ConteoItem"]] = relationship(back_populates="conteo", cascade="all, delete-orphan")

class ConteoItem(BaseModel):
    __tablename__ = "conteo_items"
    __table_args__ = ({'schema': settings.DB_SCHEMA})

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    conteo_id: Mapped[uuid.UUID] = mapped_column(ForeignKey(f"{settings.DB_SCHEMA}.conteos_inventario.id", ondelete="CASCADE"))
    producto_id: Mapped[uuid.UUID] = mapped_column(ForeignKey(f"{settings.DB_SCHEMA}.productos.id"))
    cantidad_contada: Mapped[float] = mapped_column(Numeric(10, 2), default=0.0)
    fecha_vencimiento: Mapped[Optional[date]] = mapped_column(Date)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    conteo: Mapped["ConteoInventario"] = relationship(back_populates="items")
    producto: Mapped["Producto"] = relationship("src.inventory.models.Producto")