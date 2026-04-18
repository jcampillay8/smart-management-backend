# src/sales/services/sales_service.py
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete
from sqlalchemy.orm import selectinload
from fastapi import HTTPException, status
from uuid import UUID
from typing import List

from src.sales.models import Receta, RecetaIngrediente, VentaReceta
from src.sales.schemas import RecetaCreate, VentaRecetaCreate
from src.inventory.services.stock_service import StockService

class SalesService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.stock_service = StockService(db)

    # ==========================================
    # GESTIÓN DE CATÁLOGO (RECETAS)
    # ==========================================

    async def get_all_recipes(self) -> List[Receta]:
        stmt = (
            select(Receta)
            .options(
                selectinload(Receta.ingredientes).selectinload(RecetaIngrediente.producto)
            )
            .order_by(Receta.nombre)
        )
        result = await self.db.execute(stmt)
        return result.scalars().all()

    async def create_recipe(self, data: RecetaCreate) -> Receta:
        try:
            nueva_receta = Receta(
                nombre=data.nombre,
                precio=data.precio
            )
            self.db.add(nueva_receta)
            await self.db.flush()

            for ing in data.ingredientes:
                nuevo_ing = RecetaIngrediente(
                    receta_id=nueva_receta.id,
                    producto_id=ing.producto_id,
                    bodega_id=ing.bodega_id,
                    cantidad=ing.cantidad
                )
                self.db.add(nuevo_ing)
            
            await self.db.commit()
            return await self.get_recipe_with_details(nueva_receta.id)
        except Exception as e:
            await self.db.rollback()
            raise HTTPException(status_code=500, detail=f"Error al crear receta: {str(e)}")

    async def update_recipe(self, receta_id: UUID, data: RecetaCreate) -> Receta:
        db_receta = await self.db.get(Receta, receta_id)
        if not db_receta:
            raise HTTPException(status_code=404, detail="Receta no encontrada")

        try:
            db_receta.nombre = data.nombre
            db_receta.precio = data.precio

            await self.db.execute(
                delete(RecetaIngrediente).where(RecetaIngrediente.receta_id == receta_id)
            )

            for ing in data.ingredientes:
                nuevo_ing = RecetaIngrediente(
                    receta_id=receta_id,
                    producto_id=ing.producto_id,
                    bodega_id=ing.bodega_id,
                    cantidad=ing.cantidad
                )
                self.db.add(nuevo_ing)

            await self.db.commit()
            return await self.get_recipe_with_details(receta_id)
        except Exception as e:
            await self.db.rollback()
            raise HTTPException(status_code=500, detail=f"Error al actualizar: {str(e)}")

    async def delete_recipe(self, receta_id: UUID):
        receta = await self.db.get(Receta, receta_id)
        if not receta:
            raise HTTPException(status_code=404, detail="Receta no encontrada")
        await self.db.delete(receta)
        await self.db.commit()
        return {"status": "success", "message": "Receta eliminada"}

    async def get_recipe_with_details(self, receta_id: UUID) -> Receta:
        stmt = (
            select(Receta)
            .options(
                selectinload(Receta.ingredientes).selectinload(RecetaIngrediente.producto)
            )
            .where(Receta.id == receta_id)
        )
        result = await self.db.execute(stmt)
        return result.scalar_one()

    # ==========================================
    # OPERACIONES DE VENTA Y STOCK
    # ==========================================

    async def register_sale(self, data: VentaRecetaCreate, user_id: int) -> VentaReceta:
        """
        Registra una venta y descuenta stock de forma atómica.
        """
        receta = await self.db.get(Receta, data.receta_id)
        if not receta:
            raise HTTPException(status_code=404, detail="Receta no encontrada")

        try:
            # 1. Descontar stock de ingredientes
            stmt = select(RecetaIngrediente).where(RecetaIngrediente.receta_id == data.receta_id)
            result = await self.db.execute(stmt)
            ingredientes = result.scalars().all()

            for ing in ingredientes:
                cantidad_total = ing.cantidad * data.cantidad
                await self.stock_service.consume_stock_fifo(
                    producto_id=ing.producto_id,
                    bodega_id=ing.bodega_id,
                    cantidad_total=cantidad_total,
                    user_id=user_id
                )

            # 2. Registrar la venta
            nueva_venta = VentaReceta(
                receta_id=data.receta_id,
                cantidad=data.cantidad,
                precio_unitario=data.precio_unitario,
                usuario_id=user_id
            )
            self.db.add(nueva_venta)
            
            # 3. Commit de toda la operación
            await self.db.commit()
            await self.db.refresh(nueva_venta)
            return nueva_venta

        except Exception as e:
            await self.db.rollback()
            # Si el error ya es una HTTPException, la relanzamos
            if isinstance(e, HTTPException):
                raise e
            raise HTTPException(status_code=500, detail=f"Error en la venta: {str(e)}")

    async def check_availability(self, receta_id: UUID, cantidad: int):
        stmt = select(RecetaIngrediente).where(RecetaIngrediente.receta_id == receta_id)
        result = await self.db.execute(stmt)
        ingredientes = result.scalars().all()
        
        reporte = []
        todo_disponible = True
        
        for ing in ingredientes:
            needed = ing.cantidad * cantidad
            stock_actual = await self.stock_service.get_stock_actual(ing.producto_id, ing.bodega_id)
            disponible = stock_actual >= needed
            if not disponible: todo_disponible = False
            
            reporte.append({
                "producto_id": ing.producto_id,
                "necesario": needed,
                "disponible": stock_actual,
                "suficiente": disponible
            })
        
        return {"puede_vender": todo_disponible, "detalle": reporte}
