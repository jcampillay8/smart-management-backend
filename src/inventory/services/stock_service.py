# src/inventory/services/stock_service.py
import logging
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from fastapi import HTTPException, status
from uuid import UUID
from datetime import datetime, date
from typing import List, Optional

from src.operations.models import RegistroStock, Evento, EventoProducto
from src.inventory.models import ProductoBodega
from src.inventory.schemas import RegistroStockCreate

# Configuración de logging para trazabilidad de errores
logger = logging.getLogger(__name__)

class StockService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_stock_actual(self, producto_id: UUID, bodega_id: UUID) -> float:
        """
        Obtiene el stock disponible actualmente en la tabla de caché ProductoBodega.
        """
        stmt = select(ProductoBodega.stock_actual).where(
            ProductoBodega.producto_id == producto_id,
            ProductoBodega.bodega_id == bodega_id
        )
        result = await self.db.execute(stmt)
        stock = result.scalar()
        return float(stock) if stock is not None else 0.0

    async def get_projected_stock(self, producto_id: UUID, bodega_id: UUID, hasta_fecha: date, exclude_event_id: Optional[UUID] = None) -> float:
        """
        Calcula el stock proyectado: Stock Actual - Cantidades comprometidas en eventos futuros.
        """
        stock_actual = await self.get_stock_actual(producto_id, bodega_id)

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
        USO: Operaciones automáticas (Ejecución de Eventos/Recetas).
        Procesa una lista de items vinculados a un evento específico.
        IMPORTANTE: No realiza commit para permitir transacciones atómicas externas.
        """
        for item in items:
            stmt = select(ProductoBodega).where(
                ProductoBodega.producto_id == item.producto_id,
                ProductoBodega.bodega_id == item.bodega_id
            ).with_for_update()
            
            result = await self.db.execute(stmt)
            prod_bodega = result.scalar_one_or_none()

            if not prod_bodega:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Producto {item.producto_id} no configurado en bodega {item.bodega_id}"
                )

            # Registro histórico con trazabilidad al evento
            nuevo_registro = RegistroStock(
                producto_id=item.producto_id,
                bodega_id=item.bodega_id,
                usuario_id=user_id,
                cantidad=-abs(float(item.cantidad)), # Consumo siempre resta
                tipo_movimiento="consumo",
                fecha_recuento=date.today(),
                evento_id=event_id 
            )
            self.db.add(nuevo_registro)

            # Actualización de stock en caché
            prod_bodega.stock_actual -= float(item.cantidad)

    async def create_movements(self, movements: List[RegistroStockCreate], user_id: int):
        """
        USO: Interfaz de Usuario (StockRegistro.tsx).
        Procesa múltiples movimientos manuales (conteo, entrada, merma, transferencia).
        """
        try:
            for mov in movements:
                stmt = select(ProductoBodega).where(
                    ProductoBodega.producto_id == mov.producto_id,
                    ProductoBodega.bodega_id == mov.bodega_id
                ).with_for_update()
                
                result = await self.db.execute(stmt)
                prod_bodega = result.scalar_one_or_none()

                if not prod_bodega:
                    prod_bodega = ProductoBodega(
                        producto_id=mov.producto_id,
                        bodega_id=mov.bodega_id,
                        stock_actual=0.0
                    )
                    self.db.add(prod_bodega)

                cantidad_para_historial = mov.cantidad

                if mov.tipo_movimiento == "conteo":
                    # El conteo sobreescribe el stock. Registramos la diferencia en el historial.
                    diferencia = float(mov.cantidad) - float(prod_bodega.stock_actual)
                    prod_bodega.stock_actual = float(mov.cantidad)
                    cantidad_para_historial = diferencia 

                elif mov.tipo_movimiento in ["entrada", "ajuste_positivo"]:
                    prod_bodega.stock_actual += float(mov.cantidad)

                else: # merma, salida, transferencia, consumo, ajuste_negativo
                    prod_bodega.stock_actual += float(mov.cantidad)

                # Preparar datos para RegistroStock (Historial)
                data_historial = mov.model_dump()
                data_historial["cantidad"] = cantidad_para_historial
                data_historial["usuario_id"] = user_id

                self.db.add(RegistroStock(**data_historial))

            await self.db.commit()
            return True
        except Exception as e:
            await self.db.rollback()
            logger.error(f"Error en bulk movements: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, 
                detail=f"Error al procesar inventario: {str(e)}"
            )

    async def register_consumption(self, data: RegistroStockCreate, user_id: int):
        """
        Registro manual de consumo individual (Usado por Consumo.tsx).
        """
        stmt = select(ProductoBodega).where(
            ProductoBodega.producto_id == data.producto_id,
            ProductoBodega.bodega_id == data.bodega_id
        ).with_for_update()
        
        result = await self.db.execute(stmt)
        prod_bodega = result.scalar_one_or_none()

        if not prod_bodega:
            raise HTTPException(status_code=404, detail="Configuración Producto/Bodega no encontrada.")

        if prod_bodega.stock_actual < data.cantidad:
            raise HTTPException(status_code=400, detail="Stock insuficiente para realizar el consumo.")

        try:
            nuevo_movimiento = RegistroStock(
                producto_id=data.producto_id,
                bodega_id=data.bodega_id,
                usuario_id=user_id,
                cantidad=-abs(float(data.cantidad)),
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

    async def revert_stock_movement(self, record: RegistroStock):
        """
        Revierte el impacto de un movimiento de stock en la bodega.
        Si se eliminó un consumo (-5), esto sumará 5. Si se eliminó una entrada (+10), restará 10.
        """
        stmt = select(ProductoBodega).where(
            ProductoBodega.producto_id == record.producto_id,
            ProductoBodega.bodega_id == record.bodega_id
        ).with_for_update()
        
        result = await self.db.execute(stmt)
        prod_bodega = result.scalar_one_or_none()
        
        if prod_bodega:
            prod_bodega.stock_actual -= float(record.cantidad)

    async def get_inventory_log(self, date_filter: date, bodega_id: Optional[UUID] = None):
        """
        Obtiene el log de movimientos para una fecha y bodega específica.
        """
        query = select(RegistroStock).where(RegistroStock.fecha_recuento == date_filter)
        if bodega_id:
            query = query.where(RegistroStock.bodega_id == bodega_id)
            
        result = await self.db.execute(query.order_by(RegistroStock.created_at.desc()))
        return result.scalars().all()