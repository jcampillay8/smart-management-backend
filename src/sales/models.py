# src/sales/models.py
import uuid
from typing import List # <--- IMPORTANTE para Mapped[List[...]]
from sqlalchemy import String, ForeignKey, Numeric, Integer, Boolean, text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from src.database import BaseModel
from src.config import settings

class Receta(BaseModel):
    __tablename__ = "recetas"
    __table_args__ = ({'schema': settings.DB_SCHEMA})

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    nombre: Mapped[str] = mapped_column(String(200), nullable=False)
    precio: Mapped[float] = mapped_column(Numeric(10, 2), default=0.0)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, server_default=text("true"))
    
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