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
        # 1. Creamos el objeto base (sin incluir bodegas_config del dict)
        product_data = data.model_dump(exclude={'bodegas_config'})
        nuevo_prod = Producto(**product_data)
        self.db.add(nuevo_prod)
        await self.db.commit()
        
        # 2. Volvemos a consultar el producto cargando explícitamente las relaciones
        # Esto evita el error de MissingGreenlet al serializar para el response
        stmt = (
            select(Producto)
            .options(
                selectinload(Producto.bodegas_config),
                selectinload(Producto.categoria)
            )
            .where(Producto.id == nuevo_prod.id)
        )
        
        result = await self.db.execute(stmt)
        return result.scalar_one()

    async def link_product_to_bodega(self, data: ProductoBodegaCreate) -> ProductoBodega:
        """Asocia un producto a una bodega con stock mínimo."""
        config = ProductoBodega(**data.model_dump(), stock_actual=0.0)
        self.db.add(config)
        await self.db.commit()
        await self.db.refresh(config)
        return config