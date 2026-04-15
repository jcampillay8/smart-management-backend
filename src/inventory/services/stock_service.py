# src/inventory/services/stock_service.py
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from fastapi import HTTPException, status
from uuid import UUID
from datetime import datetime, date

from src.models import RegistroStock, ProductoBodega
from src.inventory.schemas import RegistroStockCreate

class StockService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_stock_actual(self, producto_id: UUID, bodega_id: UUID) -> float:
        """
        Obtiene el stock disponible en el caché (ProductoBodega) de forma asíncrona.
        """
        stmt = select(ProductoBodega.stock_actual).where(
            ProductoBodega.producto_id == producto_id,
            ProductoBodega.bodega_id == bodega_id
        )
        result = await self.db.execute(stmt)
        stock = result.scalar()
        return float(stock) if stock is not None else 0.0

    async def register_consumption(self, data: RegistroStockCreate, user_id: UUID):
        """
        Registra un consumo manual y actualiza el stock actual.
        Lógica asíncrona equivalente a handleConfirmConsumo de Consumo.tsx.
        """
        # 1. Validar existencia y stock en caché
        stmt = select(ProductoBodega).where(
            ProductoBodega.producto_id == data.producto_id,
            ProductoBodega.bodega_id == data.bodega_id
        )
        result = await self.db.execute(stmt)
        prod_bodega = result.scalar_one_or_none()

        if not prod_bodega:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="El producto no está configurado en esta bodega."
            )

        if prod_bodega.stock_actual < data.cantidad:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Stock insuficiente. Disponible: {prod_bodega.stock_actual}"
            )

        try:
            # 2. Crear el registro de movimiento
            nuevo_movimiento = RegistroStock(
                producto_id=data.producto_id,
                bodega_id=data.bodega_id,
                usuario_id=user_id,
                cantidad=data.cantidad,
                tipo_movimiento="consumo",
                fecha_recuento=data.fecha_recuento or date.today(),
                fecha_vencimiento=data.fecha_vencimiento,
                descripcion_merma=data.descripcion_merma,
                # created_at se maneja por server_default en BaseModel, 
                # pero podemos explicitarlo si no quieres esperar al flush
                created_at=datetime.now()
            )
            self.db.add(nuevo_movimiento)

            # 3. Actualizar caché (Capa lógica sobre SQLAlchemy)
            prod_bodega.stock_actual -= data.cantidad
            
            # 4. Persistencia asíncrona
            await self.db.commit()
            await self.db.refresh(nuevo_movimiento)
            return nuevo_movimiento

        except Exception as e:
            await self.db.rollback()
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Error en la transacción: {str(e)}"
            )

    async def consume_stock_fifo(self, producto_id: UUID, bodega_id: UUID, cantidad_total: float, user_id: UUID):
        """
        Lógica para consumo automático (Recetas). 
        IMPORTANTE: No hace commit. El commit lo gestiona RecipeService para 
        mantener la atomicidad de todos los ingredientes de la receta.
        """
        stmt = select(ProductoBodega).where(
            ProductoBodega.producto_id == producto_id,
            ProductoBodega.bodega_id == bodega_id
        )
        result = await self.db.execute(stmt)
        prod_bodega = result.scalar_one_or_none()

        if not prod_bodega or prod_bodega.stock_actual < cantidad_total:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, 
                detail=f"Stock insuficiente para producto_id {producto_id}. Requerido: {cantidad_total}"
            )

        # Preparar el registro del movimiento
        nuevo_registro = RegistroStock(
            producto_id=producto_id,
            bodega_id=bodega_id,
            usuario_id=user_id,
            cantidad=cantidad_total,
            tipo_movimiento="consumo",
            fecha_recuento=date.today()
        )
        
        self.db.add(nuevo_registro)
        
        # Actualizar caché en la sesión (se enviará con el commit del RecipeService)
        prod_bodega.stock_actual -= cantidad_total
        return nuevo_registro

    async def get_inventory_log(self, date_filter: date, bodega_id: UUID = None):
        """
        Obtiene el historial de movimientos de forma asíncrona.
        """
        query = select(RegistroStock).where(RegistroStock.fecha_recuento == date_filter)
        
        if bodega_id:
            query = query.where(RegistroStock.bodega_id == bodega_id)
            
        result = await self.db.execute(query.order_by(RegistroStock.created_at.desc()))
        return result.scalars().all()