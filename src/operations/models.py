# src/operations/models.py
import uuid
import enum
from typing import List, Optional
from datetime import datetime, date
from sqlalchemy import String, ForeignKey, Numeric, DateTime, Date, Enum, Boolean, func
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
    valor_publico: Mapped[Optional[float]] = mapped_column(Numeric(10, 2)) # Lo vimos en la Parte 3

    # Relación con los productos específicos del evento
    productos: Mapped[List["EventoProducto"]] = relationship(back_populates="evento", cascade="all, delete-orphan")

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
    bodega: Mapped["Bodega"] = relationship("src.inventory.models.Bodega") # <--- AGREGAR ESTO