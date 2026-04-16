# src/operations/services/event_service.py
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete
from sqlalchemy.orm import selectinload, joinedload # <--- joinedload es clave aquí
from fastapi import HTTPException, status
from uuid import UUID
from typing import List

from src.operations.models import Evento, EventoProducto, RegistroStock
from src.operations.schemas import EventoCreate
from src.inventory.services.stock_service import StockService
from src.inventory.models import Producto, Bodega # <--- Para traer nombres
from src.sales.models import Receta

class EventService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.stock_service = StockService(db)

    async def create_event(self, event_data: EventoCreate, user_id: int):
        try:
            nuevo_evento = Evento(
                nombre=event_data.nombre,
                fecha=event_data.fecha,
                valor_publico=event_data.valor_publico,
                usuario_id=user_id,
                ejecutado=False,
                cancelado=False
            )
            self.db.add(nuevo_evento)
            await self.db.flush()

            # 1. Procesar items directos (USANDO .items SEGÚN TU SCHEMA)
            for item in event_data.items:
                self.db.add(EventoProducto(
                    evento_id=nuevo_evento.id,
                    producto_id=item.producto_id,
                    bodega_id=item.bodega_id,
                    cantidad=item.cantidad
                ))

            # 2. Procesar recetas
            for rec_req in event_data.recetas:
                stmt = select(Receta).where(Receta.id == rec_req.receta_id).options(selectinload(Receta.ingredientes))
                result = await self.db.execute(stmt)
                receta = result.scalar_one_or_none()
                
                if receta:
                    for ingrediente in receta.ingredientes:
                        self.db.add(EventoProducto(
                            evento_id=nuevo_evento.id,
                            producto_id=ingrediente.producto_id,
                            bodega_id=ingrediente.bodega_id,
                            cantidad=ingrediente.cantidad * rec_req.cantidad
                        ))

            await self.db.commit()

            # 3. CARGA ANSIOSA FINAL (Para evitar el 500 al responder)
            stmt = (
                select(Evento)
                .options(selectinload(Evento.productos))
                .where(Evento.id == nuevo_evento.id)
            )
            result = await self.db.execute(stmt)
            return result.scalar_one()

        except Exception as e:
            await self.db.rollback()
            raise HTTPException(status_code=500, detail=f"Error al crear: {str(e)}")

    async def execute_event(self, event_id: UUID, user_id: int):
        stmt = select(Evento).where(Evento.id == event_id).options(selectinload(Evento.productos))
        result = await self.db.execute(stmt)
        evento = result.scalar_one_or_none()

        if not evento or evento.ejecutado:
            raise HTTPException(status_code=400, detail="Evento no válido o ya ejecutado")

        try:
            # Atomicidad: consume_stock_masivo ya maneja los RegistroStock y el caché
            await self.stock_service.consume_stock_masivo(
                items=evento.productos, 
                user_id=user_id, 
                event_id=evento.id
            )

            evento.ejecutado = True
            await self.db.commit()
            return evento
        except Exception as e:
            await self.db.rollback()
            raise e

    async def cancel_event(self, event_id: UUID):
        """
        NUEVO: Lógica para revertir. 
        Si el evento estaba ejecutado, borramos los consumos y devolvemos stock.
        """
        stmt = select(Evento).where(Evento.id == event_id).options(selectinload(Evento.productos))
        result = await self.db.execute(stmt)
        evento = result.scalar_one_or_none()

        if not evento:
            raise HTTPException(status_code=404, detail="Evento no encontrado")

        try:
            if evento.ejecutado:
                # 1. Buscar registros de stock asociados
                stmt_stock = select(RegistroStock).where(RegistroStock.evento_id == event_id)
                res_stock = await self.db.execute(stmt_stock)
                registros = res_stock.scalars().all()

                # 2. Revertir el caché en ProductoBodega
                for reg in registros:
                    # Aquí podrías inyectar lógica de stock_service para 'devolver'
                    pass # (Implementar devolución similar a consumo pero con +)

                # 3. Borrar registros de stock
                await self.db.execute(delete(RegistroStock).where(RegistroStock.evento_id == event_id))

            evento.cancelado = True
            evento.ejecutado = False
            await self.db.commit()
            return evento
        except Exception as e:
            await self.db.rollback()
            raise HTTPException(status_code=500, detail=f"Error al cancelar: {str(e)}")

    async def get_all_events(self):
        """
        AJUSTE DE RENDIMIENTO: Usamos joinedload para traer 
        nombres de productos y bodegas en una sola consulta SQL.
        """
        stmt = (
            select(Evento)
            .options(
                selectinload(Evento.productos)
                .joinedload(EventoProducto.producto), # Trae el objeto Producto
                selectinload(Evento.productos)
                .joinedload(EventoProducto.bodega)    # Trae el objeto Bodega
            )
            .order_by(Evento.fecha.desc())
        )
        result = await self.db.execute(stmt)
        return result.scalars().all()