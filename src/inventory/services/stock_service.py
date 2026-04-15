# src/inventory/services/stock_service.py
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from fastapi import HTTPException, status
from uuid import UUID
from datetime import datetime, date
from typing import List, Optional

from src.operations.models import RegistroStock, Evento, EventoProducto
from src.inventory.models import ProductoBodega
from src.inventory.schemas import RegistroStockCreate

class StockService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_stock_actual(self, producto_id: UUID, bodega_id: UUID) -> float:
        """Obtiene el stock actual desde la tabla de caché ProductoBodega."""
        stmt = select(ProductoBodega.stock_actual).where(
            ProductoBodega.producto_id == producto_id,
            ProductoBodega.bodega_id == bodega_id
        )
        result = await self.db.execute(stmt)
        stock = result.scalar()
        return float(stock) if stock is not None else 0.0

    async def get_projected_stock(self, producto_id: UUID, bodega_id: UUID, hasta_fecha: date, exclude_event_id: Optional[UUID] = None) -> float:
        """
        Cálculo de Stock Proyectado:
        Stock Actual - SUM(cantidades en eventos agendados NO ejecutados ni cancelados).
        """
        # 1. Obtener base actual
        stock_actual = await self.get_stock_actual(producto_id, bodega_id)

        # 2. Consultar lo comprometido en la tabla de eventos
        stmt = (
            select(func.sum(EventoProducto.cantidad))
            .join(Evento, Evento.id == EventoProducto.evento_id)
            .where(
                EventoProducto.producto_id == producto_id,
                EventoProducto.bodega_id == bodega_id,
                Evento.fecha <= hasta_fecha,
                Evento.ejecutado == False,
                Evento.cancelado == False
            )
        )
        
        if exclude_event_id:
            stmt = stmt.where(Evento.id != exclude_event_id)

        result = await self.db.execute(stmt)
        comprometido = result.scalar() or 0.0

        return float(stock_actual) - float(comprometido)

    async def consume_stock_masivo(self, items: List[EventoProducto], user_id: int, event_id: UUID):
        """
        Procesa una lista de items (de un evento o receta).
        IMPORTANTE: No realiza commit. Permite atomicidad controlada desde el Service llamador.
        """
        for item in items:
            # Buscar el registro de caché para actualizar
            stmt = select(ProductoBodega).where(
                ProductoBodega.producto_id == item.producto_id,
                ProductoBodega.bodega_id == item.bodega_id
            ).with_for_update() # Bloqueo de fila para evitar condiciones de carrera
            
            result = await self.db.execute(stmt)
            prod_bodega = result.scalar_one_or_none()

            if not prod_bodega:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Producto {item.producto_id} no configurado en bodega {item.bodega_id}"
                )

            # Opcional: Validar si permites stock negativo
            # if prod_bodega.stock_actual < item.cantidad:
            #     raise HTTPException(...)

            # 1. Crear el registro histórico del movimiento
            nuevo_registro = RegistroStock(
                producto_id=item.producto_id,
                bodega_id=item.bodega_id,
                usuario_id=user_id,
                cantidad=item.cantidad,
                tipo_movimiento="consumo",
                fecha_recuento=date.today(),
                evento_id=event_id # Trazabilidad cruzada
            )
            self.db.add(nuevo_registro)

            # 2. Descontar del caché
            prod_bodega.stock_actual -= float(item.cantidad)

    async def register_consumption(self, data: RegistroStockCreate, user_id: int):
        """Registro manual de consumo (usado por Consumo.tsx)."""
        stmt = select(ProductoBodega).where(
            ProductoBodega.producto_id == data.producto_id,
            ProductoBodega.bodega_id == data.bodega_id
        ).with_for_update()
        
        result = await self.db.execute(stmt)
        prod_bodega = result.scalar_one_or_none()

        if not prod_bodega:
            raise HTTPException(status_code=404, detail="Producto/Bodega no configurado.")

        if prod_bodega.stock_actual < data.cantidad:
            raise HTTPException(status_code=400, detail="Stock insuficiente.")

        try:
            nuevo_movimiento = RegistroStock(
                producto_id=data.producto_id,
                bodega_id=data.bodega_id,
                usuario_id=user_id,
                cantidad=data.cantidad,
                tipo_movimiento="consumo",
                fecha_recuento=data.fecha_recuento or date.today(),
                descripcion_merma=data.descripcion_merma
            )
            self.db.add(nuevo_movimiento)
            prod_bodega.stock_actual -= float(data.cantidad)
            
            await self.db.commit()
            await self.db.refresh(nuevo_movimiento)
            return nuevo_movimiento
        except Exception as e:
            await self.db.rollback()
            raise HTTPException(status_code=500, detail=str(e))

    async def get_inventory_log(self, date_filter: date, bodega_id: Optional[UUID] = None):
        """Historial de movimientos asíncrono."""
        query = select(RegistroStock).where(RegistroStock.fecha_recuento == date_filter)
        if bodega_id:
            query = query.where(RegistroStock.bodega_id == bodega_id)
            
        result = await self.db.execute(query.order_by(RegistroStock.created_at.desc()))
        return result.scalars().all()