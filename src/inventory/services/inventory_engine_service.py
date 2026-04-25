# # src/inventory/services/inventory_engine_service.py
import polars as pl
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import List, Optional, Dict, Any
from uuid import UUID
from src.models import RegistroStock 

class InventoryEngineService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_stock_snapshot(self, bodega_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Calcula el saldo actual agrupado por producto y lote usando Polars.
        """
        # 1. Traer historial de la DB de forma asíncrona
        stmt = select(RegistroStock)
        if bodega_id and bodega_id != "all":
            try:
                stmt = stmt.where(RegistroStock.bodega_id == UUID(bodega_id))
            except ValueError:
                # Si el UUID no es válido, podrías lanzar un error o ignorar el filtro
                pass
            
        result = await self.db.execute(stmt)
        records = result.scalars().all()

        if not records:
            return []

        # 2. Convertir a lista de dicts
        data = [
            {
                "producto_id": str(r.producto_id),
                "bodega_id": str(r.bodega_id),
                "cantidad": float(r.cantidad),
                "tipo_movimiento": r.tipo_movimiento.lower() if r.tipo_movimiento else "",
                "fecha_vencimiento": r.fecha_vencimiento.isoformat() if r.fecha_vencimiento else None
            }
            for r in records
        ]

        # 3. Procesamiento con Polars
        df = pl.DataFrame(data)

        if df.is_empty():
            return []

        # Lógica de signos HORECA
        suman = ["entrada", "ajuste_positivo", "devolucion", "conteo", "recuento"]
        
        # 4. Cálculo del Snapshot
        snapshot = (
            df.with_columns(
                pl.when(pl.col("tipo_movimiento").is_in(suman))
                .then(pl.col("cantidad"))
                .otherwise(-pl.col("cantidad"))
                .alias("cantidad_neta")
            )
            .group_by(["producto_id", "bodega_id", "fecha_vencimiento"])
            .agg(pl.col("cantidad_neta").sum().alias("stock_actual"))
            # Filtramos stock <= 0 (opcional, dependiendo de si quieres ver quiebres)
            .filter(pl.col("stock_actual") > 0)
            .sort(["producto_id", "fecha_vencimiento"])
        )

        return snapshot.to_dicts()