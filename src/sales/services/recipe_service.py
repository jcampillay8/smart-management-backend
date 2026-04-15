# src/sales/services/recipe_service.py
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from fastapi import HTTPException, status
from uuid import UUID
from typing import List

from src.sales.models import Receta, RecetaIngrediente
from src.sales.schemas import RecetaCreate

class RecipeService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_recipe(self, data: RecetaCreate) -> Receta:
        """Crea una receta con sus ingredientes base."""
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
            await self.db.refresh(nueva_receta)
            return nueva_receta
        except Exception as e:
            await self.db.rollback()
            raise HTTPException(status_code=500, detail=f"Error al crear receta: {str(e)}")

    async def get_all_recipes(self) -> List[Receta]:
        """Obtiene todas las recetas con sus ingredientes cargados."""
        stmt = select(Receta).options(selectinload(Receta.ingredientes))
        result = await self.db.execute(stmt)
        return result.scalars().all()