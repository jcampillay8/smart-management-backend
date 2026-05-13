# src/inventory/services/stock_service.py
import logging
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, delete
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

    async def return_stock_masivo(self, items: List[EventoProducto], event_id: UUID):
        """
        USO: Revertir consumos de un evento cancelado.
        Devuelve el stock y elimina los registros de consumo asociados.
        """
        stmt = select(RegistroStock).where(RegistroStock.evento_id == event_id)
        result = await self.db.execute(stmt)
        registros = result.scalars().all()
        
        for reg in registros:
            stmt_pb = select(ProductoBodega).where(
                ProductoBodega.producto_id == reg.producto_id,
                ProductoBodega.bodega_id == reg.bodega_id
            ).with_for_update()
            result_pb = await self.db.execute(stmt_pb)
            prod_bodega = result_pb.scalar_one_or_none()
            
            if prod_bodega:
                prod_bodega.stock_actual += abs(float(reg.cantidad))
        
        for reg in registros:
            await self.db.delete(reg)

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
                    # Lógica de Conteo Lote-Aware:
                    # Si el front envía una fecha, comparamos contra el stock de ESE lote específico.
                    # Si no hay fecha, comparamos contra el stock TOTAL de la bodega (comportamiento original).
                    if mov.fecha_vencimiento:
                        stmt_lote = select(func.sum(RegistroStock.cantidad)).where(
                            RegistroStock.producto_id == mov.producto_id,
                            RegistroStock.bodega_id == mov.bodega_id,
                            RegistroStock.fecha_vencimiento == mov.fecha_vencimiento
                        )
                        res_lote = await self.db.execute(stmt_lote)
                        stock_lote_actual = Decimal(str(res_lote.scalar() or "0.0"))
                        
                        diferencia = cant_mov - stock_lote_actual
                        prod_bodega.stock_actual += diferencia
                        cantidad_para_historial = diferencia
                    else:
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
            prod_bodega.stock_actual -= Decimal(str(record.cantidad))

    async def update_consumption(self, record: RegistroStock, data: "RegistroStockUpdate", user_id: int):
        """
        Modifica un registro de consumo, generando trazabilidad.
        """
        stmt = select(ProductoBodega).where(
            ProductoBodega.producto_id == record.producto_id,
            ProductoBodega.bodega_id == record.bodega_id
        ).with_for_update()
        
        result = await self.db.execute(stmt)
        prod_bodega = result.scalar_one_or_none()
        
        if not prod_bodega:
            raise HTTPException(status_code=404, detail="Configuración Producto/Bodega no encontrada.")
            
        nueva_cantidad = -abs(float(data.cantidad))
        diferencia = Decimal(str(nueva_cantidad)) - Decimal(str(record.cantidad))
        
        if prod_bodega.stock_actual + diferencia < 0:
            raise HTTPException(status_code=400, detail="Stock insuficiente para realizar esta modificación.")

        # Actualizar stock
        prod_bodega.stock_actual += diferencia
        
        # Registrar auditoría en el mismo registro
        record.cantidad_anterior = record.cantidad
        record.cantidad = nueva_cantidad
        record.modificado_por = user_id
        record.modificado_at = datetime.now()
        
        if data.motivo_merma is not None:
            record.motivo_merma = data.motivo_merma
        if data.descripcion_merma is not None:
            record.descripcion_merma = data.descripcion_merma
            
        await self.db.commit()
        await self.db.refresh(record)
        return record

    async def delete_consumption(self, record: RegistroStock, user_id: int):
        """
        Elimina un registro y genera trazabilidad creando un registro tipo eliminacion.
        """
        await self.revert_stock_movement(record)
        
        # Crear registro de auditoría
        audit_record = RegistroStock(
            producto_id=record.producto_id,
            bodega_id=record.bodega_id,
            usuario_id=user_id,
            cantidad=abs(float(record.cantidad)), # La reversión suma el stock devuelto
            tipo_movimiento="eliminacion",
            fecha_recuento=date.today(),
            registro_origen_id=record.id
        )
        self.db.add(audit_record)
        
        # Eliminar el registro original (la BD debe permitir registro_origen_id apuntando a algo borrado si no hay constraint FK, lo cual no lo hay según models.py)
        await self.db.delete(record)
        await self.db.commit()

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
        user_id: int,
        receta_id: Optional[UUID] = None
    ):
        """
        Descuenta stock para la preparación de una receta siguiendo la lógica FIFO.
        Prioriza lotes con vencimiento más próximo y excluye productos vencidos.
        """
        # 1. Buscar y bloquear el stock consolidado de la bodega
        stmt_pb = select(ProductoBodega).where(
            ProductoBodega.producto_id == producto_id,
            ProductoBodega.bodega_id == bodega_id
        ).with_for_update()
        
        result_pb = await self.db.execute(stmt_pb)
        prod_bodega = result_pb.scalar_one_or_none()

        if not prod_bodega:
            raise HTTPException(
                status_code=404, 
                detail=f"Producto {producto_id} no configurado en bodega {bodega_id}"
            )

        if float(prod_bodega.stock_actual) < cantidad_total:
            raise HTTPException(
                status_code=400,
                detail=f"Stock total insuficiente para el producto {producto_id}"
            )

        # 2. Identificar lotes disponibles (FIFO: vencimiento más cercano primero, nulos al final)
        today = date.today()
        stmt_lots = (
            select(RegistroStock.fecha_vencimiento, func.sum(RegistroStock.cantidad))
            .where(
                RegistroStock.producto_id == producto_id,
                RegistroStock.bodega_id == bodega_id,
                # Solo productos no vencidos (o sin fecha)
                (RegistroStock.fecha_vencimiento >= today) | (RegistroStock.fecha_vencimiento.is_(None))
            )
            .group_by(RegistroStock.fecha_vencimiento)
            .having(func.sum(RegistroStock.cantidad) > 0)
            .order_by(RegistroStock.fecha_vencimiento.asc().nulls_last())
        )
        
        result_lots = await self.db.execute(stmt_lots)
        lots = result_lots.all() # Lista de (fecha_vencimiento, stock_del_lote)

        if not lots:
            raise HTTPException(
                status_code=400,
                detail=f"No hay lotes vigentes (no vencidos) para el producto {producto_id}"
            )

        # 3. Descontar secuencialmente de los lotes
        quedan_por_descontar = Decimal(str(cantidad_total))
        
        for lot_vencimiento, lot_stock in lots:
            if quedan_por_descontar <= 0:
                break
            
            lot_stock_dec = Decimal(str(lot_stock))
            a_descontar_de_este_lote = min(lot_stock_dec, quedan_por_descontar)
            
            # Registrar movimiento para este lote específico
            nuevo_registro = RegistroStock(
                producto_id=producto_id,
                bodega_id=bodega_id,
                usuario_id=user_id,
                cantidad=-abs(float(a_descontar_de_este_lote)),
                tipo_movimiento="consumo",
                fecha_recuento=today,
                fecha_vencimiento=lot_vencimiento,
                transfer_id=f"RECETA_ID:{receta_id}" if receta_id else "RECETA_CONSUME"
            )
            self.db.add(nuevo_registro)
            
            quedan_por_descontar -= a_descontar_de_este_lote

        if quedan_por_descontar > 0:
             # Esto pasaría si el stock total (prod_bodega) es mayor al stock de lotes vigentes
             raise HTTPException(
                status_code=400,
                detail=f"Stock insuficiente en lotes vigentes para {producto_id}. (Verifique productos vencidos)"
            )

        # 4. Actualizar el stock consolidado
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

        transfer_id = str(uuid.uuid4())
        
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

    async def undo_last_movements(self, user_id: int) -> int:
        """
        Revierte el último grupo de movimientos del usuario.
        - Busca los registros más recientes (últimos 2 minutos) del usuario que no sean
          'reversion' ni 'redo'.
        - Por cada uno, crea un movimiento inverso (tipo='reversion') vinculado al original.
        - Actualiza el cache de ProductoBodega.
        """
        from datetime import datetime, timedelta, timezone
        from uuid import uuid4

        cutoff = datetime.now(timezone.utc) - timedelta(minutes=2)

        stmt = (
            select(RegistroStock)
            .where(
                RegistroStock.usuario_id == user_id,
                RegistroStock.created_at >= cutoff,
                RegistroStock.tipo_movimiento.notin_(["reversion", "redo"])
            )
            .order_by(RegistroStock.created_at.desc())
        )
        result = await self.db.execute(stmt)
        registros = result.scalars().all()

        if not registros:
            return 0

        # Group by the most recent "batch" — same session window (within 30s of the most recent)
        if registros:
            latest_time = registros[0].created_at
            # Make sure latest_time is timezone-aware
            if latest_time.tzinfo is None:
                from datetime import timezone as tz
                latest_time = latest_time.replace(tzinfo=tz.utc)
            batch_cutoff = latest_time - timedelta(seconds=30)
            batch = [r for r in registros if (
                (r.created_at.replace(tzinfo=tz.utc) if r.created_at.tzinfo is None else r.created_at)
                >= batch_cutoff
            )]
        else:
            batch = registros

        count = 0
        for reg in batch:
            # Fetch product bodega cache
            stmt_pb = select(ProductoBodega).where(
                ProductoBodega.producto_id == reg.producto_id,
                ProductoBodega.bodega_id == reg.bodega_id,
            ).with_for_update()
            result_pb = await self.db.execute(stmt_pb)
            prod_bodega = result_pb.scalar_one_or_none()

            # The inverse quantity reverses the original movement
            inverse_qty = -float(reg.cantidad)

            reversion = RegistroStock(
                producto_id=reg.producto_id,
                bodega_id=reg.bodega_id,
                usuario_id=user_id,
                cantidad=inverse_qty,
                tipo_movimiento="reversion",
                fecha_recuento=reg.fecha_recuento,
                registro_origen_id=reg.id,
            )
            self.db.add(reversion)

            if prod_bodega:
                prod_bodega.stock_actual = Decimal(str(float(prod_bodega.stock_actual) + inverse_qty))

            count += 1

        await self.db.commit()
        return count

    async def redo_last_movements(self, user_id: int) -> int:
        """
        Re-aplica el último grupo de 'reversion' del usuario.
        - Busca los registros más recientes de tipo='reversion' del usuario (últimos 2 min).
        - Por cada uno, crea un movimiento 'redo' que re-aplica la cantidad original.
        """
        from datetime import datetime, timedelta, timezone as tz

        cutoff = datetime.now(tz.utc) - timedelta(minutes=2)

        stmt = (
            select(RegistroStock)
            .where(
                RegistroStock.usuario_id == user_id,
                RegistroStock.created_at >= cutoff,
                RegistroStock.tipo_movimiento == "reversion",
            )
            .order_by(RegistroStock.created_at.desc())
        )
        result = await self.db.execute(stmt)
        reversiones = result.scalars().all()

        if not reversiones:
            return 0

        latest_time = reversiones[0].created_at
        if latest_time.tzinfo is None:
            latest_time = latest_time.replace(tzinfo=tz.utc)
        batch_cutoff = latest_time - timedelta(seconds=30)
        batch = [r for r in reversiones if (
            (r.created_at.replace(tzinfo=tz.utc) if r.created_at.tzinfo is None else r.created_at)
            >= batch_cutoff
        )]

        count = 0
        for rev in batch:
            stmt_pb = select(ProductoBodega).where(
                ProductoBodega.producto_id == rev.producto_id,
                ProductoBodega.bodega_id == rev.bodega_id,
            ).with_for_update()
            result_pb = await self.db.execute(stmt_pb)
            prod_bodega = result_pb.scalar_one_or_none()

            # Re-applying the original = negating the reversion
            redo_qty = -float(rev.cantidad)

            redo_reg = RegistroStock(
                producto_id=rev.producto_id,
                bodega_id=rev.bodega_id,
                usuario_id=user_id,
                cantidad=redo_qty,
                tipo_movimiento="redo",
                fecha_recuento=rev.fecha_recuento,
                registro_origen_id=rev.registro_origen_id,
            )
            self.db.add(redo_reg)

            if prod_bodega:
                prod_bodega.stock_actual = Decimal(str(float(prod_bodega.stock_actual) + redo_qty))

            count += 1

        await self.db.commit()
        return count