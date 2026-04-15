# src/operations/services/recipe_service.py
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from fastapi import HTTPException, status
from uuid import UUID

from src.models import Receta, RecetaIngrediente
from src.inventory.services.stock_service import StockService

class RecipeService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.stock_service = StockService(db)

    async def execute_recipe_consumption(self, receta_id: UUID, cantidad_receta: int, user_id: UUID):
        """
        Ejecuta el consumo de todos los ingredientes de una receta.
        Si un ingrediente falla, la transacción completa se revierte.
        """
        # 1. Obtener la receta
        receta = await self.db.get(Receta, receta_id)
        if not receta:
            raise HTTPException(status_code=404, detail="Receta no encontrada")

        # 2. Obtener ingredientes
        stmt = select(RecetaIngrediente).where(RecetaIngrediente.receta_id == receta_id)
        result = await self.db.execute(stmt)
        ingredientes = result.scalars().all()

        try:
            for ing in ingredientes:
                cantidad_a_descontar = ing.cantidad * cantidad_receta
                
                # Delegamos al StockService asíncrono (sin commit interno)
                await self.stock_service.consume_stock_fifo(
                    producto_id=ing.producto_id,
                    bodega_id=ing.bodega_id,
                    cantidad_total=cantidad_a_descontar,
                    user_id=user_id
                )
            
            # Commit único para toda la receta (Atomicidad)
            await self.db.commit()
            return {
                "status": "success", 
                "message": f"Consumo de {cantidad_receta}x {receta.nombre} registrado con éxito."
            }
            
        except HTTPException as e:
            await self.db.rollback()
            raise e 
        except Exception as e:
            await self.db.rollback()
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, 
                detail=f"Error inesperado procesando la receta: {str(e)}"
            )

    async def check_recipe_availability(self, receta_id: UUID, cantidad_receta: int):
        """
        Simula el consumo consultando el caché de stock actual.
        """
        stmt = select(RecetaIngrediente).where(RecetaIngrediente.receta_id == receta_id)
        result = await self.db.execute(stmt)
        ingredientes = result.scalars().all()
        
        reporte = []
        todo_disponible = True
        
        for ing in ingredientes:
            needed = ing.cantidad * cantidad_receta
            
            # Usamos el nuevo método asíncrono del StockService
            stock_actual = await self.stock_service.get_stock_actual(ing.producto_id, ing.bodega_id)
            
            disponible = stock_actual >= needed
            if not disponible: 
                todo_disponible = False
            
            reporte.append({
                "producto_id": ing.producto_id,
                "necesario": needed,
                "disponible": stock_actual,
                "suficiente": disponible
            })
        
        return {"puede_producir": todo_disponible, "ingredientes": reporte}