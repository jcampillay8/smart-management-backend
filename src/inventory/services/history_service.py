# src/inventory/services/history_service.py
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload
from sqlalchemy import select
from uuid import UUID
from datetime import date
from src.models import RegistroStock

class HistoryService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_consumption_log(self, log_date: date, bodega_id: UUID = None):
        """
        Obtiene el historial detallado de consumos de forma asíncrona.
        Carga relaciones (producto, bodega, usuario) en una sola consulta SQL.
        """
        query = (
            select(RegistroStock)
            .options(
                joinedload(RegistroStock.producto),
                joinedload(RegistroStock.bodega),
                joinedload(RegistroStock.usuario)
            )
            .where(
                RegistroStock.tipo_movimiento == "consumo",
                RegistroStock.fecha_recuento == log_date
            )
        )

        # Filtro de bodega flexible
        if bodega_id and str(bodega_id) != "all":
            query = query.where(RegistroStock.bodega_id == bodega_id)

        result = await self.db.execute(query.order_by(RegistroStock.created_at.desc()))
        return result.scalars().all()