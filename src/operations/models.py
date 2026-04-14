# src/operations/models.py
import uuid
import enum
from typing import Optional # <--- IMPORTANTE
from datetime import datetime, date
from sqlalchemy import String, ForeignKey, Numeric, DateTime, Date, Enum, Boolean, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from src.database import BaseModel
from src.config import settings

class TipoMovimiento(str, enum.Enum):
    CONTEO = "conteo"
    CONSUMO = "consumo"
    MERMA = "merma"

class RegistroStock(BaseModel):
    __tablename__ = "registros_stock"
    __table_args__ = ({'schema': settings.DB_SCHEMA})

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    producto_id: Mapped[uuid.UUID] = mapped_column(ForeignKey(f"{settings.DB_SCHEMA}.productos.id", ondelete="CASCADE"))
    bodega_id: Mapped[uuid.UUID] = mapped_column(ForeignKey(f"{settings.DB_SCHEMA}.bodegas.id"))
    cantidad: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False)
    tipo_movimiento: Mapped[TipoMovimiento] = mapped_column(Enum(TipoMovimiento), nullable=False)
    
    motivo_merma: Mapped[Optional[str]] = mapped_column(String(255))
    descripcion_merma: Mapped[Optional[str]] = mapped_column(String(500))
    
    fecha_recuento: Mapped[date] = mapped_column(Date, server_default=func.current_date())
    fecha_vencimiento: Mapped[Optional[date]] = mapped_column(Date)
    
    usuario_id: Mapped[int] = mapped_column(ForeignKey(f"{settings.DB_SCHEMA}.users.id"))
    evento_id: Mapped[Optional[uuid.UUID]] = mapped_column(ForeignKey(f"{settings.DB_SCHEMA}.eventos.id", ondelete="SET NULL"))
    transfer_id: Mapped[Optional[str]] = mapped_column(String(100))

    # Relaciones para facilitar consultas (lazy loading por defecto)
    producto: Mapped["Producto"] = relationship("src.inventory.models.Producto")
    usuario: Mapped["User"] = relationship("src.models.User")
    evento: Mapped[Optional["Evento"]] = relationship("Evento")

class Evento(BaseModel):
    __tablename__ = "eventos"
    __table_args__ = ({'schema': settings.DB_SCHEMA})

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    nombre: Mapped[str] = mapped_column(String(200), nullable=False)
    fecha: Mapped[date] = mapped_column(Date, nullable=False)
    ejecutado: Mapped[bool] = mapped_column(Boolean, default=False)
    cancelado: Mapped[bool] = mapped_column(Boolean, default=False)
    usuario_id: Mapped[int] = mapped_column(ForeignKey(f"{settings.DB_SCHEMA}.users.id"))