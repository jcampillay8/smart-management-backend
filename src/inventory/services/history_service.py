# src/inventory/services/history_service.py
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload
from sqlalchemy import select
from uuid import UUID
from typing import Optional, List
from datetime import date
# IMPORTANTE: Asegúrate de importar desde el archivo correcto
from src.operations.models import RegistroStock 

class HistoryService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_consumption_log(self, log_date: date, bodega_id: Optional[UUID] = None) -> List[RegistroStock]:
        """
        Obtiene el historial detallado de movimientos de inventario.
        Carga relaciones (producto, bodega, usuario) para evitar Lazy Loading.
        """
        query = (
            select(RegistroStock)
            .options(
                joinedload(RegistroStock.producto),
                joinedload(RegistroStock.bodega),
                joinedload(RegistroStock.usuario)
            )
            .where(
                # Eliminamos el filtro fijo de "consumo" para que puedas ver 
                # todos los movimientos (entradas, mermas, etc.) del día.
                RegistroStock.fecha_recuento == log_date
            )
        )

        # Filtro de bodega flexible
        # Nota: Algunos clientes mandan el UUID o el string "all"
        if bodega_id and str(bodega_id) != "all":
            query = query.where(RegistroStock.bodega_id == bodega_id)

        # Ordenamos por los más recientes primero
        result = await self.db.execute(query.order_by(RegistroStock.created_at.desc()))
        return result.scalars().all()