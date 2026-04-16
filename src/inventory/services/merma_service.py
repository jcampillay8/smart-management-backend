# src/inventory/services/merma_service.py
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from sqlalchemy.orm import joinedload
from fastapi import HTTPException
from datetime import datetime, timedelta
from decimal import Decimal
from uuid import UUID

from src.operations.models import RegistroStock, TipoMovimiento
from src.inventory.models import ProductoBodega
from src.operations.schemas import RegistroStockCreate

class MermaService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def registrar_merma(self, data: RegistroStockCreate, user_id: int):
        """
        Registra una merma, resta el stock de la bodega y 
        guarda los motivos/descripciones específicos.
        """
        # 1. Bloqueo de fila para evitar inconsistencias de stock (Race conditions)
        stmt = select(ProductoBodega).where(
            ProductoBodega.producto_id == data.producto_id,
            ProductoBodega.bodega_id == data.bodega_id
        ).with_for_update()
        
        result = await self.db.execute(stmt)
        prod_bodega = result.scalar_one_or_none()

        if not prod_bodega:
            raise HTTPException(
                status_code=404, 
                detail="El producto no está registrado en la bodega seleccionada"
            )

        # 2. Validar que haya suficiente stock para mermar
        if prod_bodega.stock_actual < Decimal(str(data.cantidad)):
            raise HTTPException(
                status_code=400, 
                detail=f"Stock insuficiente para mermar. Disponible: {prod_bodega.stock_actual}"
            )

        # 3. Crear el registro de movimiento (Cantidad negativa para la DB)
        nueva_merma = RegistroStock(
            producto_id=data.producto_id,
            bodega_id=data.bodega_id,
            usuario_id=user_id,
            cantidad=-abs(data.cantidad),  # Siempre resta
            tipo_movimiento=TipoMovimiento.MERMA,
            motivo_merma=data.motivo_merma,
            descripcion_merma=data.descripcion_merma,
            fecha_vencimiento=data.fecha_vencimiento,
            fecha_recuento=data.fecha_recuento,
            evento_id=data.evento_id
        )

        # 4. Actualizar stock físico en ProductoBodega
        prod_bodega.stock_actual -= Decimal(str(data.cantidad))

        self.db.add(nueva_merma)
        
        try:
            await self.db.commit()
            await self.db.refresh(nueva_merma)
            return nueva_merma
        except Exception as e:
            await self.db.rollback()
            raise HTTPException(status_code=500, detail=f"Error al registrar merma: {str(e)}")

    async def obtener_historial_mermas(self, skip: int = 0, limit: int = 50):
        """
        Retorna los registros de tipo MERMA con relaciones cargadas 
        y asigna los nombres para el esquema de salida.
        """
        stmt = (
            select(RegistroStock)
            .options(
                joinedload(RegistroStock.producto),
                joinedload(RegistroStock.bodega)
            )
            .where(RegistroStock.tipo_movimiento == TipoMovimiento.MERMA)
            .order_by(RegistroStock.created_at.desc())
            .offset(skip)
            .limit(limit)
        )
        
        result = await self.db.execute(stmt)
        registros = result.scalars().all()

        # Mapeo manual: asignamos los nombres de los objetos relacionados
        # a los atributos que espera el RegistroStockOut
        for r in registros:
            # Usamos getattr o validación simple por si alguna relación fallara
            r.nombre_producto = r.producto.nombre if r.producto else "Producto no encontrado"
            r.nombre_bodega = r.bodega.nombre if r.bodega else "Bodega no encontrada"
            
        return registros

    async def obtener_stats_mermas(self):
        """
        Calcula estadísticas básicas para los gráficos de Recharts.
        """
        hace_7_dias = datetime.now() - timedelta(days=7)
        
        stmt = select(
            func.date(RegistroStock.created_at).label("fecha"),
            func.sum(func.abs(RegistroStock.cantidad)).label("total")
        ).where(
            RegistroStock.tipo_movimiento == TipoMovimiento.MERMA,
            RegistroStock.created_at >= hace_7_dias
        ).group_by(func.date(RegistroStock.created_at))

        result = await self.db.execute(stmt)
        return [{"fecha": r.fecha, "cantidad": float(r.total)} for r in result.all()]