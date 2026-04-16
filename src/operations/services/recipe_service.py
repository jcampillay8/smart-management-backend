# src/operations/services/recipe_service.py
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete
from sqlalchemy.orm import selectinload
from fastapi import HTTPException, status
from uuid import UUID
from typing import List, Optional

# Importamos modelos y esquemas
from src.operations.models import Receta, RecetaIngrediente
from src.operations.schemas import RecetaCreate
from src.inventory.services.stock_service import StockService

class RecipeService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.stock_service = StockService(db)

    # =========================================================================
    # SECCIÓN: GESTIÓN DE RECETAS (Para Gestion.tsx)
    # =========================================================================

    async def get_all_recipes(self) -> List[Receta]:
        """
        Obtiene todas las recetas cargando sus ingredientes y la info del producto.
        Utilizado para llenar la tabla en Gestion.tsx.
        """
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
        """
        Crea la definición de una nueva receta y sus ingredientes asociados.
        """
        try:
            nueva_receta = Receta(
                nombre=data.nombre,
                precio=data.precio,
                iva_incluido=data.iva_incluido,
                iva_porcentaje=data.iva_porcentaje
            )
            self.db.add(nueva_receta)
            await self.db.flush()  # Obtenemos el ID generado

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
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Error al crear la receta: {str(e)}"
            )

    async def update_recipe(self, receta_id: UUID, data: RecetaCreate) -> Receta:
        """
        Actualiza los datos de la receta y refresca la lista de ingredientes.
        Sigue la estrategia de 'Borrar y Reinsertar' ingredientes para mayor simplicidad.
        """
        # 1. Buscar receta existente
        db_receta = await self.db.get(Receta, receta_id)
        if not db_receta:
            raise HTTPException(status_code=404, detail="Receta no encontrada")

        try:
            # 2. Actualizar campos base
            db_receta.nombre = data.nombre
            db_receta.precio = data.precio
            db_receta.iva_incluido = data.iva_incluido
            db_receta.iva_porcentaje = data.iva_porcentaje

            # 3. Eliminar ingredientes antiguos
            await self.db.execute(
                delete(RecetaIngrediente).where(RecetaIngrediente.receta_id == receta_id)
            )

            # 4. Insertar nuevos ingredientes
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
        """Elimina una receta de la base de datos."""
        receta = await self.db.get(Receta, receta_id)
        if not receta:
            raise HTTPException(status_code=404, detail="Receta no encontrada")
        
        await self.db.delete(receta)
        await self.db.commit()
        return {"status": "success", "message": "Receta eliminada correctamente"}

    async def get_recipe_with_details(self, receta_id: UUID) -> Receta:
        """Helper para retornar una receta con sus relaciones cargadas."""
        stmt = (
            select(Receta)
            .options(
                selectinload(Receta.ingredientes).selectinload(RecetaIngrediente.producto)
            )
            .where(Receta.id == receta_id)
        )
        result = await self.db.execute(stmt)
        return result.scalar_one()

    # =========================================================================
    # SECCIÓN: OPERACIONES DE STOCK (Ejecución de Receta)
    # =========================================================================

    async def execute_recipe_consumption(self, receta_id: UUID, cantidad_receta: int, user_id: int):
        """
        Ejecuta el consumo real de stock para una venta o producción.
        Usa lógica FIFO y es atómico (todo o nada).
        """
        receta = await self.db.get(Receta, receta_id)
        if not receta:
            raise HTTPException(status_code=404, detail="Receta no encontrada")

        # Obtenemos ingredientes
        stmt = select(RecetaIngrediente).where(RecetaIngrediente.receta_id == receta_id)
        result = await self.db.execute(stmt)
        ingredientes = result.scalars().all()

        try:
            for ing in ingredientes:
                cantidad_a_descontar = ing.cantidad * cantidad_receta
                
                # Consumimos stock delegando al StockService
                await self.stock_service.consume_stock_fifo(
                    producto_id=ing.producto_id,
                    bodega_id=ing.bodega_id,
                    cantidad_total=cantidad_a_descontar,
                    user_id=user_id
                )
            
            await self.db.commit()
            return {
                "status": "success", 
                "message": f"Consumo de {cantidad_receta}x {receta.nombre} registrado con éxito."
            }
        except Exception as e:
            await self.db.rollback()
            raise HTTPException(status_code=500, detail=str(e))

    async def check_recipe_availability(self, receta_id: UUID, cantidad_receta: int):
        """
        Consulta si hay stock suficiente para producir una cantidad de la receta.
        Útil para el frontend antes de confirmar una venta.
        """
        stmt = select(RecetaIngrediente).where(RecetaIngrediente.receta_id == receta_id)
        result = await self.db.execute(stmt)
        ingredientes = result.scalars().all()
        
        reporte = []
        todo_disponible = True
        
        for ing in ingredientes:
            needed = ing.cantidad * cantidad_receta
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