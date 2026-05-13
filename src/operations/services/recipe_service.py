# src/operations/services/recipe_service.py
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete, func, case
from sqlalchemy.orm import selectinload
from fastapi import HTTPException, status
from uuid import UUID
from typing import List, Optional
from datetime import datetime, timedelta

# Importamos modelos y esquemas
from src.sales.models import Receta, RecetaIngrediente, CategoriaReceta, VentaReceta
from src.inventory.models import AreaOperativa, AreaOperativaReceta, Bodega, ProductoBodega
from src.operations.schemas import RecetaCreate, CategoriaRecetaCreate
from src.inventory.services.stock_service import StockService

class RecipeService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.stock_service = StockService(db)

    # =========================================================================
    # SECCIÓN: GESTIÓN DE RECETAS (Para Gestion.tsx)
    # =========================================================================

    async def get_all_recipes(self, area_id: Optional[UUID] = None) -> List[Receta]:
        """
        Obtiene todas las recetas cargando sus ingredientes e info de producto.
        Si se pasa area_id, calcula disponibilidad por bodega y consumo histórico.
        """
        stmt = (
            select(Receta)
            .options(
                selectinload(Receta.ingredientes).selectinload(RecetaIngrediente.producto),
                selectinload(Receta.areas_operativas)
            )
            .order_by(Receta.nombre)
        )
        result = await self.db.execute(stmt)
        recipes = result.scalars().all()

        # 1. Mapear IDs de áreas operativas
        for r in recipes:
            r.areas_operativas_ids = [a.id for a in r.areas_operativas]

        # Si no hay area_id, retornamos básico
        if not area_id:
            return recipes

        # 2. Cargar Bodegas del Área Seleccionada
        area_stmt = (
            select(AreaOperativa)
            .options(selectinload(AreaOperativa.bodegas))
            .where(AreaOperativa.id == area_id)
        )
        area_res = await self.db.execute(area_stmt)
        area = area_res.scalar_one_or_none()
        
        if not area:
            return recipes

        bodegas = area.bodegas
        bodega_ids = [b.id for b in bodegas]

        # 3. Obtener Stock Actual de todos los productos involucrados en las recetas para estas bodegas
        # Optimizamos trayendo todo el stock relevante de una vez
        todos_producto_ids = set()
        for r in recipes:
            for ing in r.ingredientes:
                todos_producto_ids.add(ing.producto_id)
        
        stock_stmt = select(ProductoBodega).where(
            ProductoBodega.producto_id.in_(list(todos_producto_ids)),
            ProductoBodega.bodega_id.in_(bodega_ids)
        )
        stock_res = await self.db.execute(stock_stmt)
        stocks = stock_res.scalars().all()
        
        # Mapeo: (producto_id, bodega_id) -> stock_actual
        stock_map = {(s.producto_id, s.bodega_id): s.stock_actual for s in stocks}

        # 4. Calcular Consumo Histórico (Global por Receta)
        now = datetime.utcnow()
        h24 = now - timedelta(days=1)
        d7 = now - timedelta(days=7)
        d30 = now - timedelta(days=30)

        consumo_stmt = select(
            VentaReceta.receta_id,
            func.sum(VentaReceta.cantidad).label("total"),
            func.sum(case((VentaReceta.created_at >= h24, VentaReceta.cantidad), else_=0)).label("dia"),
            func.sum(case((VentaReceta.created_at >= d7, VentaReceta.cantidad), else_=0)).label("semana"),
            func.sum(case((VentaReceta.created_at >= d30, VentaReceta.cantidad), else_=0)).label("mes")
        ).group_by(VentaReceta.receta_id)
        
        consumo_res = await self.db.execute(consumo_stmt)
        consumo_data = {row.receta_id: row for row in consumo_res.all()}

        # 5. Inyectar cálculos en cada receta
        for r in recipes:
            # Disponibilidad por bodega
            disp_list = []
            for b in bodegas:
                can_make = float('inf')
                if not r.ingredientes:
                    can_make = 0
                else:
                    for ing in r.ingredientes:
                        stock_ing = stock_map.get((ing.producto_id, b.id), 0)
                        if ing.cantidad > 0:
                            possible = stock_ing // ing.cantidad
                            if possible < can_make:
                                can_make = possible
                        else:
                            can_make = 0
                
                disp_list.append({
                    "bodega_id": b.id,
                    "bodega_nombre": b.nombre,
                    "cantidad": int(can_make) if can_make != float('inf') else 0
                })
            
            r.disponibilidad_por_bodega = disp_list
            
            # Consumo
            stats = consumo_data.get(r.id)
            r.consumo_diario = float(stats.dia) if stats else 0
            r.consumo_semanal = float(stats.semana) if stats else 0
            r.consumo_mensual = float(stats.mes) if stats else 0

        return recipes

    async def create_recipe(self, data: RecetaCreate) -> Receta:
        """
        Crea la definición de una nueva receta y sus ingredientes asociados.
        """
        try:
            nueva_receta = Receta(
                nombre=data.nombre,
                precio=data.precio,
                iva_incluido=data.iva_incluido,
                iva_porcentaje=data.iva_porcentaje,
                categoria_receta_id=data.categoria_receta_id
            )
            self.db.add(nueva_receta)
            await self.db.flush()

            # 1. Asociar Áreas Operativas
            for aid in data.areas_operativas_ids:
                self.db.add(AreaOperativaReceta(receta_id=nueva_receta.id, area_operativa_id=aid))

            # 2. Asociar Ingredientes (Sin bodega_id)
            for ing in data.ingredientes:
                nuevo_ing = RecetaIngrediente(
                    receta_id=nueva_receta.id,
                    producto_id=ing.producto_id,
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
        Actualiza los datos de la receta, ingredientes y áreas operativas.
        """
        db_receta = await self.db.get(Receta, receta_id)
        if not db_receta:
            raise HTTPException(status_code=404, detail="Receta no encontrada")

        try:
            db_receta.nombre = data.nombre
            db_receta.precio = data.precio
            db_receta.iva_incluido = data.iva_incluido
            db_receta.iva_porcentaje = data.iva_porcentaje
            db_receta.categoria_receta_id = data.categoria_receta_id

            # 1. Refrescar Áreas Operativas
            await self.db.execute(
                delete(AreaOperativaReceta).where(AreaOperativaReceta.receta_id == receta_id)
            )
            for aid in data.areas_operativas_ids:
                self.db.add(AreaOperativaReceta(receta_id=receta_id, area_operativa_id=aid))

            # 2. Refrescar Ingredientes
            await self.db.execute(
                delete(RecetaIngrediente).where(RecetaIngrediente.receta_id == receta_id)
            )
            for ing in data.ingredientes:
                nuevo_ing = RecetaIngrediente(
                    receta_id=receta_id,
                    producto_id=ing.producto_id,
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
        return {"status": "success", "message": "Receta eliminada correctamente"}

    async def get_recipe_with_details(self, receta_id: UUID) -> Receta:
        stmt = (
            select(Receta)
            .options(
                selectinload(Receta.ingredientes).selectinload(RecetaIngrediente.producto),
                selectinload(Receta.areas_operativas)
            )
            .where(Receta.id == receta_id)
        )
        result = await self.db.execute(stmt)
        r = result.scalar_one()
        r.areas_operativas_ids = [a.id for a in r.areas_operativas]
        return r

    # =========================================================================
    # SECCIÓN: OPERACIONES DE STOCK (Ejecución de Receta)
    # =========================================================================

    async def execute_recipe_consumption(self, receta_id: UUID, cantidad_receta: int, user_id: int, area_id: UUID):
        """
        Ejecuta el consumo usando la bodega_consumo del área operativa seleccionada.
        """
        # Validar área operativa y obtener su bodega de consumo
        area = await self.db.get(AreaOperativa, area_id)
        if not area:
            raise HTTPException(status_code=404, detail="Área operativa no encontrada")
        
        bodega_consumo_id = area.bodega_consumo_id

        # Obtenemos ingredientes
        stmt = select(RecetaIngrediente).where(RecetaIngrediente.receta_id == receta_id)
        result = await self.db.execute(stmt)
        ingredientes = result.scalars().all()

        try:
            for ing in ingredientes:
                cantidad_a_descontar = ing.cantidad * cantidad_receta
                await self.stock_service.consume_stock_fifo(
                    producto_id=ing.producto_id,
                    bodega_id=bodega_consumo_id,
                    cantidad_total=cantidad_a_descontar,
                    user_id=user_id
                )
            await self.db.commit()
            return {"status": "success", "message": "Consumo registrado"}
        except Exception as e:
            await self.db.rollback()
            raise HTTPException(status_code=500, detail=str(e))

    async def check_recipe_availability(self, receta_id: UUID, cantidad_receta: int, area_id: UUID):
        """
        Consulta disponibilidad en la bodega_consumo del área seleccionada.
        """
        area = await self.db.get(AreaOperativa, area_id)
        if not area:
            raise HTTPException(status_code=404, detail="Área operativa no encontrada")
        
        bodega_id = area.bodega_consumo_id

        stmt = select(RecetaIngrediente).where(RecetaIngrediente.receta_id == receta_id)
        result = await self.db.execute(stmt)
        ingredientes = result.scalars().all()
        
        reporte = []
        todo_disponible = True
        
        for ing in ingredientes:
            needed = ing.cantidad * cantidad_receta
            stock_actual = await self.stock_service.get_stock_actual(ing.producto_id, bodega_id)
            disponible = stock_actual >= needed
            if not disponible: todo_disponible = False
            reporte.append({
                "producto_id": ing.producto_id,
                "necesario": needed,
                "disponible": stock_actual,
                "suficiente": disponible
            })
        
        return {"puede_producir": todo_disponible, "ingredientes": reporte}

    async def get_all_ingredients(self):
        stmt = select(RecetaIngrediente)
        result = await self.db.execute(stmt)
        return result.scalars().all()

    # =========================================================================
    # SECCIÓN: CATEGORÍAS DE RECETAS
    # =========================================================================

    async def get_recipe_categories(self) -> List[CategoriaReceta]:
        result = await self.db.execute(select(CategoriaReceta).order_by(CategoriaReceta.nombre))
        return result.scalars().all()

    async def create_recipe_category(self, data: CategoriaRecetaCreate) -> CategoriaReceta:
        nueva_cat = CategoriaReceta(nombre=data.nombre, color=data.color, icono=data.icono)
        self.db.add(nueva_cat)
        await self.db.commit()
        await self.db.refresh(nueva_cat)
        return nueva_cat

    async def update_recipe_category(self, id: UUID, data: CategoriaRecetaCreate) -> CategoriaReceta:
        cat = await self.db.get(CategoriaReceta, id)
        if not cat: raise HTTPException(status_code=404, detail="Categoría no encontrada")
        cat.nombre = data.nombre
        cat.color = data.color
        cat.icono = data.icono
        await self.db.commit()
        await self.db.refresh(cat)
        return cat

    async def delete_recipe_category(self, id: UUID):
        cat = await self.db.get(CategoriaReceta, id)
        if not cat: raise HTTPException(status_code=404, detail="Categoría no encontrada")
        await self.db.delete(cat)
        await self.db.commit()
        return {"status": "success"}
