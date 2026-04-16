# src/inventory/services/history_service.py
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload
from sqlalchemy import select, and_
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

    async def get_filtered_history(
        self, 
        bodega_id: str = "all",
        producto_id: str = "all",
        tipo_movimiento: str = "all",
        fecha_desde: Optional[date] = None,
        fecha_hasta: Optional[date] = None
    ) -> List[RegistroStock]:
        """
        Obtiene el historial detallado con filtros dinámicos.
        Reemplaza la lógica de filtrado manual del frontend.
        """
        # Query base con relaciones cargadas para nombres y emails
        query = (
            select(RegistroStock)
            .options(
                joinedload(RegistroStock.producto),
                joinedload(RegistroStock.bodega),
                joinedload(RegistroStock.usuario)
            )
        )

        filters = []

        # Filtro de Bodega (UUID o "all")
        if bodega_id != "all":
            filters.append(RegistroStock.bodega_id == UUID(bodega_id))
        
        # Filtro de Producto (UUID o "all")
        if producto_id != "all":
            filters.append(RegistroStock.producto_id == UUID(producto_id))

        # Filtro de Tipo (merma, consumo, etc.)
        if tipo_movimiento != "all":
            filters.append(RegistroStock.tipo_movimiento == tipo_movimiento)

        # Filtros de Rango de Fechas
        if fecha_desde:
            filters.append(RegistroStock.fecha_recuento >= fecha_desde)
        if fecha_hasta:
            filters.append(RegistroStock.fecha_recuento <= fecha_hasta)

        if filters:
            query = query.where(and_(*filters))

        # Ordenar y limitar para rendimiento (máximo 500 como en el front original)
        result = await self.db.execute(
            query.order_by(RegistroStock.created_at.desc()).limit(500)
        )
        
        registros = result.scalars().all()

        # Mapeo de nombres para que lleguen listos al frontend
        for r in registros:
            r.nombre_producto = r.producto.nombre if r.producto else "—"
            r.nombre_bodega = r.bodega.nombre if r.bodega else "—"
            # Extraemos el nombre del usuario desde el email si existe
            if r.usuario and r.usuario.email:
                r.user_display_name = r.usuario.email.split('@')[0]
            else:
                r.user_display_name = "Sistema"

        return registros