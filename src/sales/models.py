# src/sales/models.py
import uuid
from datetime import datetime
from typing import List, Optional # <--- IMPORTANTE para Mapped[List[...]]
from sqlalchemy import String, ForeignKey, Numeric, Integer, Boolean, text, DateTime, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from src.database import BaseModel
from src.config import settings

class CategoriaReceta(BaseModel):
    __tablename__ = "categorias_recetas"
    __table_args__ = ({'schema': settings.DB_SCHEMA})

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    nombre: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

class Receta(BaseModel):
    __tablename__ = "recetas"
    __table_args__ = ({'schema': settings.DB_SCHEMA})

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    nombre: Mapped[str] = mapped_column(String(200), nullable=False)
    precio: Mapped[float] = mapped_column(Numeric(10, 2), default=0.0)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, server_default=text("true"))
    iva_porcentaje: Mapped[float] = mapped_column(Numeric(5, 2), default=19.0, server_default=text("19.0"))
    iva_incluido: Mapped[bool] = mapped_column(Boolean, default=True, server_default=text("true"))
    imagen_url: Mapped[Optional[str]] = mapped_column(String(1000), nullable=True)
    categoria_receta_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        ForeignKey(f"{settings.DB_SCHEMA}.categorias_recetas.id", ondelete="SET NULL"),
        nullable=True
    )

    # Relación uno-a-muchos con ingredientes
    ingredientes: Mapped[List["RecetaIngrediente"]] = relationship(
        back_populates="receta", 
        cascade="all, delete-orphan"
    )

class RecetaIngrediente(BaseModel):
    __tablename__ = "receta_ingredientes"
    __table_args__ = ({'schema': settings.DB_SCHEMA})

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    receta_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey(f"{settings.DB_SCHEMA}.recetas.id", ondelete="CASCADE")
    )
    producto_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey(f"{settings.DB_SCHEMA}.productos.id", ondelete="CASCADE")
    )
    bodega_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey(f"{settings.DB_SCHEMA}.bodegas.id")
    )
    cantidad: Mapped[float] = mapped_column(Numeric(10, 2), default=0.0)
    
    # Relaciones
    receta: Mapped["Receta"] = relationship(back_populates="ingredientes")
    producto: Mapped["Producto"] = relationship("src.inventory.models.Producto")

class VentaReceta(BaseModel):
    __tablename__ = "ventas_recetas"
    __table_args__ = ({'schema': settings.DB_SCHEMA})

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    receta_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey(f"{settings.DB_SCHEMA}.recetas.id", ondelete="RESTRICT")
    )
    cantidad: Mapped[int] = mapped_column(Integer, default=1)
    precio_unitario: Mapped[float] = mapped_column(Numeric(10, 2), default=0.0)
    usuario_id: Mapped[int] = mapped_column(
        ForeignKey(f"{settings.DB_SCHEMA}.users.id")
    )
    
    # Relaciones
    receta: Mapped["Receta"] = relationship()
    usuario: Mapped["User"] = relationship("src.models.User")