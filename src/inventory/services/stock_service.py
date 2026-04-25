# src/inventory/services/stock_service.py
import logging
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from fastapi import HTTPException, status
from uuid import UUID
from datetime import datetime, date
from typing import List, Optional
from decimal import Decimal

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
        Procesa múltiples movimientos manuales (conteo, entrada, merma, transferencia).
        Asegura compatibilidad entre tipos Decimal (DB) y float (JSON).
        """
        try:
            for mov in movements:
                # 1. Convertir cantidad del movimiento a Decimal de forma segura
                cant_mov = Decimal(str(mov.cantidad))
                
                # 2. Buscar (y bloquear para actualización) la configuración de bodega
                stmt = select(ProductoBodega).where(
                    ProductoBodega.producto_id == mov.producto_id,
                    ProductoBodega.bodega_id == mov.bodega_id
                ).with_for_update()
                
                result = await self.db.execute(stmt)
                prod_bodega = result.scalar_one_or_none()

                # Si no existe configuración, la creamos (o podrías lanzar error según tu preferencia)
                if not prod_bodega:
                    prod_bodega = ProductoBodega(
                        producto_id=mov.producto_id,
                        bodega_id=mov.bodega_id,
                        stock_actual=Decimal("0.0")
                    )
                    self.db.add(prod_bodega)
                    # Forzamos flush para que el objeto tenga estado en la sesión
                    await self.db.flush()

                # 3. Lógica de Stock y cantidad para el Historial
                cantidad_para_historial = cant_mov

                if mov.tipo_movimiento == "conteo":
                    # La diferencia es lo que realmente "entró" o "salió" para llegar al nuevo valor
                    diferencia = cant_mov - prod_bodega.stock_actual
                    prod_bodega.stock_actual = cant_mov
                    cantidad_para_historial = diferencia 

                elif mov.tipo_movimiento in ["entrada", "ajuste_positivo"]:
                    prod_bodega.stock_actual += cant_mov
                    # En entradas, la cantidad en el historial es positiva

                else: 
                    # merma, salida, transferencia, consumo, ajuste_negativo
                    # Forzamos que la resta sea efectiva en stock_actual
                    # Si el front envía 10 para una merma, restamos 10.
                    # Si el front ya envía -10, hay que tener cuidado con no duplicar el signo.
                    # Asumiremos que el front envía valores absolutos (positivos) y aquí restamos:
                    valor_absoluto = abs(cant_mov)
                    prod_bodega.stock_actual -= valor_absoluto
                    cantidad_para_historial = -valor_absoluto # Guardamos como negativo en historial

                # 4. Preparar datos para RegistroStock (Historial)
                data_historial = mov.model_dump()
                data_historial["cantidad"] = float(cantidad_para_historial) # Convertimos a float para el schema de salida
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

    async def consume_stock_fifo(
        self, 
        producto_id: UUID, 
        bodega_id: UUID, 
        cantidad_total: float, 
        user_id: int,  # Cambiado de usuario_id a user_id
        receta_id: Optional[UUID] = None
    ):
        """
        Descuenta stock para la preparación de una receta.
        Acepta 'cantidad_total' y 'user_id' según los envía el router de operaciones.
        """
        # 1. Buscar y bloquear el stock de la bodega
        stmt = select(ProductoBodega).where(
            ProductoBodega.producto_id == producto_id,
            ProductoBodega.bodega_id == bodega_id
        ).with_for_update()
        
        result = await self.db.execute(stmt)
        prod_bodega = result.scalar_one_or_none()

        if not prod_bodega:
            raise HTTPException(
                status_code=404, 
                detail=f"Producto {producto_id} no configurado en bodega {bodega_id}"
            )

        # 2. Registrar el movimiento en el historial
        nuevo_registro = RegistroStock(
            producto_id=producto_id,
            bodega_id=bodega_id,
            usuario_id=user_id, # Aquí usamos el valor recibido
            cantidad=-abs(float(cantidad_total)),
            tipo_movimiento="consumo",
            fecha_recuento=date.today(),
            transfer_id=f"RECETA_ID:{receta_id}" if receta_id else "RECETA_CONSUME"
        )
        self.db.add(nuevo_registro)

        # 3. Actualizar el stock actual
        prod_bodega.stock_actual -= Decimal(str(cantidad_total))
        
        # Mantenemos la transacción abierta para el router principal
        await self.db.flush()

    async def transfer_stock(
        self,
        producto_id: UUID,
        bodega_origen_id: UUID,
        bodega_destino_id: UUID,
        cantidad: float,
        user_id: int,
        fecha_recuento: date
    ):
        """Transfiere stock de una bodega a otra."""
        if bodega_origen_id == bodega_destino_id:
            raise HTTPException(status_code=400, detail="Origen y destino no pueden ser iguales")

        if cantidad <= 0:
            raise HTTPException(status_code=400, detail="La cantidad debe ser mayor a 0")

        stmt_origen = select(ProductoBodega).where(
            ProductoBodega.producto_id == producto_id,
            ProductoBodega.bodega_id == bodega_origen_id
        ).with_for_update()
        
        result = await self.db.execute(stmt_origen)
        prod_origen = result.scalar_one_or_none()

        if not prod_origen:
            raise HTTPException(status_code=404, detail="Producto no configurado en bodega origen")

        if prod_origen.stock_actual < cantidad:
            raise HTTPException(status_code=400, detail="Stock insuficiente en bodega origen")

        stmt_destino = select(ProductoBodega).where(
            ProductoBodega.producto_id == producto_id,
            ProductoBodega.bodega_id == bodega_destino_id
        ).with_for_update()
        
        result = await self.db.execute(stmt_destino)
        prod_destino = result.scalar_one_or_none()

        if not prod_destino:
            prod_destino = ProductoBodega(
                producto_id=producto_id,
                bodega_id=bodega_destino_id,
                stock_actual=0.0
            )
            self.db.add(prod_destino)
            await self.db.flush()

        prod_origen.stock_actual -= Decimal(str(cantidad))
        prod_destino.stock_actual += Decimal(str(cantidad))

        transfer_id = UUID()
        
        reg_salida = RegistroStock(
            producto_id=producto_id,
            bodega_id=bodega_origen_id,
            usuario_id=user_id,
            cantidad=-cantidad,
            tipo_movimiento="transferencia",
            fecha_recuento=fecha_recuento,
            transfer_id=transfer_id
        )
        self.db.add(reg_salida)

        reg_entrada = RegistroStock(
            producto_id=producto_id,
            bodega_id=bodega_destino_id,
            usuario_id=user_id,
            cantidad=cantidad,
            tipo_movimiento="transferencia",
            fecha_recuento=fecha_recuento,
            transfer_id=transfer_id
        )
        self.db.add(reg_entrada)

        await self.db.commit()

        return {"message": "Transferencia completada", "transfer_id": str(transfer_id)}