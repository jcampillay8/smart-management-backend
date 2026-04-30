# src/finance/models.py
import uuid
from datetime import date
from sqlalchemy import String, Numeric, Boolean, Date, Integer
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column
from src.database import BaseModel
from src.config import settings

class GastoOperativo(BaseModel):
    __tablename__ = "gastos_operativos"
    __table_args__ = {"schema": settings.DB_SCHEMA}

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    
    nombre: Mapped[str] = mapped_column(String(255), nullable=False) 
    categoria: Mapped[str] = mapped_column(String(100), nullable=False) 
    monto: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False)
    fecha_gasto: Mapped[date] = mapped_column(Date, nullable=False)
    es_fijo: Mapped[bool] = mapped_column(Boolean, default=True)
    estado_pago: Mapped[str] = mapped_column(String(50), default="pagado")
    usuario_id: Mapped[int] = mapped_column(Integer, nullable=False)
