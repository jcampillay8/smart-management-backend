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
                # Soportar múltiples IDs separados por comas
                ids = [UUID(id.strip()) for id in bodega_id.split(",") if id.strip()]
                if len(ids) == 1:
                    stmt = stmt.where(RegistroStock.bodega_id == ids[0])
                else:
                    stmt = stmt.where(RegistroStock.bodega_id.in_(ids))
            except ValueError:
                # Si algún UUID no es válido, ignoramos el filtro o podrías registrar el error
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
        
        # 4. Cálculo del Snapshot (Sumamos directamente porque StockService ya aplica el signo negativo a consumos/mermas)
        snapshot = (
            df.group_by(["producto_id", "bodega_id", "fecha_vencimiento"])
            .agg(pl.col("cantidad").sum().alias("stock_actual"))
            # Filtramos stock <= 0 (opcional, dependiendo de si quieres ver quiebres)
            .filter(pl.col("stock_actual") > 0)
            .sort(["producto_id", "fecha_vencimiento"])
        )

        return snapshot.to_dicts()