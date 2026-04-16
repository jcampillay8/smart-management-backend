# src/analytics/models.py
from sqlalchemy import Column, String, Float, ForeignKey, Date, DateTime, Boolean, func
from sqlalchemy.dialects.postgresql import UUID
from src.database import Base

# Nota: Estos modelos suelen representar Vistas de SQL (View) 
# que crearemos en la base de datos para no recalcular todo en cada request.

class VistaStockResumen(Base):
    """
    Esta "tabla" representa una vista que consolida el stock actual.
    Ayuda a que Analiticas.tsx cargue mucho más rápido.
    """
    __tablename__ = "v_stock_resumen"
    __table_args__ = {"extend_existing": True}

    # Definimos las columnas que la vista SQL expondrá
    producto_id = Column(UUID(as_uuid=True), primary_key=True)
    nombre_producto = Column(String)
    bodega_id = Column(UUID(as_uuid=True), primary_key=True)
    nombre_bodega = Column(String)
    categoria_nombre = Column(String)
    unidad = Column(String)
    
    cantidad_total = Column(Float) # Suma de todos los movimientos
    stock_minimo = Column(Float)
    costo_unitario = Column(Float)
    
    # Útil para Alertas de Vencimiento
    proximo_vencimiento = Column(Date)
    cantidad_vencida = Column(Float)

class ReporteMensualCache(Base):
    """
    Para Informes.tsx. 
    Guarda resultados ya calculados para no saturar la CPU.
    """
    __tablename__ = "analytics_reporte_cache"

    id = Column(UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid())
    mes = Column(Integer, primary_key=True) # 1-12
    anio = Column(Integer, primary_key=True)
    
    total_ventas = Column(Float, default=0.0)
    total_mermas = Column(Float, default=0.0)
    costo_inventario_valorizado = Column(Float, default=0.0)
    
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())