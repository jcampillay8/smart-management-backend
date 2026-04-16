# src/inventory/services/catalog_service.py
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, or_
from sqlalchemy.orm import selectinload
from uuid import UUID
from typing import List, Optional
from src.inventory.models import Categoria, Producto, Bodega, ProductoBodega
from src.inventory.schemas import CategoriaCreate, ProductoCreate, BodegaCreate, ProductoBodegaCreate

class CatalogService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_categories(self) -> List[Categoria]:
        """Obtiene todas las categorías para los filtros del frontend."""
        result = await self.db.execute(select(Categoria).order_by(Categoria.nombre))
        return result.scalars().all()

    async def get_bodegas(self) -> List[Bodega]:
        """Obtiene la lista de bodegas disponibles."""
        result = await self.db.execute(select(Bodega).order_by(Bodega.nombre))
        return result.scalars().all()

    async def get_products(
        self, 
        categoria_id: Optional[UUID] = None, 
        bodega_id: Optional[UUID] = None,
        search: Optional[str] = None
    ) -> List[Producto]:
        """
        Obtiene la lista de productos aplicando filtros opcionales.
        """
        # 1. Base de la consulta con Eager Loading para evitar MissingGreenlet
        stmt = (
            select(Producto)
            .options(
                selectinload(Producto.bodegas_config),
                selectinload(Producto.categoria)
            )
            .order_by(Producto.nombre)
        )

        # 2. Filtro por Categoría (Exacto)
        if categoria_id:
            stmt = stmt.where(Producto.categoria_id == categoria_id)

        # 3. Filtro por Búsqueda (Case-Insensitive)
        if search:
            # Busca coincidencias parciales en el nombre del producto
            stmt = stmt.where(Producto.nombre.ilike(f"%{search}%"))

        # 4. Filtro por Bodega
        # Si se envía bodega_id, filtramos los productos que tengan 
        # configuración específica en esa bodega.
        if bodega_id:
            stmt = stmt.join(Producto.bodegas_config).where(
                ProductoBodega.bodega_id == bodega_id
            )

        result = await self.db.execute(stmt)
        return result.scalars().all()

    async def create_category(self, data: CategoriaCreate) -> Categoria:
        nueva_cat = Categoria(nombre=data.nombre)
        self.db.add(nueva_cat)
        await self.db.commit()
        await self.db.refresh(nueva_cat)
        return nueva_cat

    async def create_bodega(self, data: BodegaCreate) -> Bodega:
        nueva_bodega = Bodega(nombre=data.nombre)
        self.db.add(nueva_bodega)
        await self.db.commit()
        await self.db.refresh(nueva_bodega)
        return nueva_bodega

    async def create_product(self, data: ProductoCreate) -> Producto:
        # 1. Crear producto
        product_data = data.model_dump(exclude={'bodegas_config'})
        nuevo_prod = Producto(**product_data)
        self.db.add(nuevo_prod)
        await self.db.flush() # Para obtener el nuevo_prod.id sin terminar la transacción

        # 2. Si vienen bodegas configuradas, crearlas de inmediato
        if data.bodegas_config:
            for config_data in data.bodegas_config:
                nueva_conf = ProductoBodega(
                    producto_id=nuevo_prod.id,
                    bodega_id=config_data.bodega_id,
                    stock_minimo=config_data.stock_minimo,
                    stock_actual=0.0
                )
                self.db.add(nueva_conf)

        await self.db.commit()
        return await self.get_product_by_id(nuevo_prod.id)

    async def link_product_to_bodega(self, data: ProductoBodegaCreate) -> ProductoBodega:
        """Asocia un producto a una bodega con stock mínimo."""
        config = ProductoBodega(**data.model_dump(), stock_actual=0.0)
        self.db.add(config)
        await self.db.commit()
        await self.db.refresh(config)
        return config

    # === CATEGORÍAS (Update & Delete) ===
    async def update_category(self, categoria_id: UUID, data: CategoriaCreate) -> Categoria:
        result = await self.db.execute(select(Categoria).where(Categoria.id == categoria_id))
        db_cat = result.scalar_one()
        db_cat.nombre = data.nombre
        await self.db.commit()
        await self.db.refresh(db_cat)
        return db_cat

    async def delete_category(self, categoria_id: UUID):
        # El frontend sugiere mover productos a "Sin categoría" o eliminar. 
        # Aquí ejecutamos la eliminación directa (asegúrate de que en el modelo
        # la relación no tenga restricción de integridad fuerte o maneja el cambio de ID).
        result = await self.db.execute(select(Categoria).where(Categoria.id == categoria_id))
        db_cat = result.scalar_one()
        await self.db.delete(db_cat)
        await self.db.commit()

    # === PRODUCTOS (Update & Upsert de Bodegas) ===
    async def update_product(self, producto_id: UUID, data: ProductoCreate) -> Producto:
        # 1. Obtener producto existente
        stmt = (
            select(Producto)
            .options(selectinload(Producto.bodegas_config))
            .where(Producto.id == producto_id)
        )
        result = await self.db.execute(stmt)
        db_prod = result.scalar_one()

        # 2. Actualizar campos base
        for key, value in data.model_dump(exclude={'bodegas_config'}).items():
            setattr(db_prod, key, value)

        # 3. Manejar Configuración de Bodegas (Mínimos)
        if data.bodegas_config:
            # Borramos configuraciones actuales para simplificar (o puedes hacer un merge)
            from sqlalchemy import delete
            await self.db.execute(
                delete(ProductoBodega).where(ProductoBodega.producto_id == producto_id)
            )
            
            # Insertamos las nuevas
            for config in data.bodegas_config:
                nueva_conf = ProductoBodega(
                    producto_id=producto_id,
                    bodega_id=config.bodega_id,
                    stock_minimo=config.stock_minimo,
                    stock_actual=0.0 # O preservar el anterior si existe
                )
                self.db.add(nueva_conf)

        await self.db.commit()
        
        # Recargar con relaciones para el response_model
        return await self.get_product_by_id(producto_id)

    async def get_product_by_id(self, producto_id: UUID) -> Producto:
        stmt = (
            select(Producto)
            .options(selectinload(Producto.bodegas_config), selectinload(Producto.categoria))
            .where(Producto.id == producto_id)
        )
        result = await self.db.execute(stmt)
        return result.scalar_one()

    async def delete_product(self, producto_id: UUID):
        result = await self.db.execute(select(Producto).where(Producto.id == producto_id))
        db_prod = result.scalar_one()
        await self.db.delete(db_prod)
        await self.db.commit()