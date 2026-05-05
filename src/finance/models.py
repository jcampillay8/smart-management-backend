# src/finance/models.py
import uuid
import enum
from datetime import date
from typing import Optional
from sqlalchemy import String, Numeric, Boolean, Date, Integer, ForeignKey, Enum
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from src.database import BaseModel
from src.config import settings

class CategoriaGasto(str, enum.Enum):
    LUZ = "luz"
    AGUA = "agua"
    GAS = "gas"
    ARRIENDO = "arriendo"
    INTERNET = "internet"
    OTRO = "otro"

class GastoOperativo(BaseModel):
    __tablename__ = "gastos_operativos"
    __table_args__ = {"schema": settings.DB_SCHEMA}

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    
    nombre: Mapped[str] = mapped_column(String(255), nullable=False) 
    categoria: Mapped[CategoriaGasto] = mapped_column(
        Enum(CategoriaGasto, schema=settings.DB_SCHEMA, name="categoria_gasto_enum"),
        nullable=False
    )
    monto: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False)
    fecha_gasto: Mapped[date] = mapped_column(Date, nullable=False)
    es_fijo: Mapped[bool] = mapped_column(Boolean, default=True)
    estado_pago: Mapped[str] = mapped_column(String(50), default="pagado")
    usuario_id: Mapped[int] = mapped_column(Integer, nullable=False)
    
    # Nuevos campos según Fase 2.2
    bodega_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), 
        ForeignKey(f"{settings.DB_SCHEMA}.bodegas.id", ondelete="SET NULL"),
        nullable=True
    )
    descripcion: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    
    # Relación opcional con Bodega
    bodega: Mapped[Optional["Bodega"]] = relationship("src.inventory.models.Bodega")
