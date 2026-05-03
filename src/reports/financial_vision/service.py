# src/reports/financial_vision/service.py
from datetime import date, timedelta
from typing import List, Dict
from sqlalchemy import select, func, and_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.database import async_session_maker
from src.config import settings
from src.sales.models import Receta, RecetaIngrediente, VentaReceta
from src.inventory.models import Producto
from src.finance.models import GastoOperativo, CategoriaGasto
from src.purchases.models import CompraItem, Proveedor
from src.purchases.models import Compra
from src.finance.models import GastoOperativo

class FinancialVisionService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.schema = settings.DB_SCHEMA

    async def get_matriz_menu(
        self, 
        fecha_inicio: date = None, 
        fecha_fin: date = None
    ) -> List[Dict]:
        """
        1. Matriz de Ingeniería de Menú
        Clasificación: Estrellas, Caballos de batalla, Puzzles, Perros
        """
        if not fecha_inicio:
            fecha_inicio = date.today() - timedelta(days=30)
        if not fecha_fin:
            fecha_fin = date.today()
        
        # Obtener recetas con sus ingredientes
        query_recetas = (
            select(Receta)
            .options(selectinload(Receta.ingredientes).selectinload(RecetaIngrediente.producto))
        )
        result_recetas = await self.session.execute(query_recetas)
        recetas = result_recetas.scalars().all()
        
        # Obtener ventas del período
        query_ventas = (
            select(VentaReceta.receta_id, func.sum(VentaReceta.cantidad).label('total_vendido'))
            .where(VentaReceta.receta_id.isnot(None))
            .group_by(VentaReceta.receta_id)
        )
        if fecha_inicio:
            # Asumimos que hay relación con alguna tabla que tenga fecha, sino usamos receta_id
            pass
        result_ventas = await self.session.execute(query_ventas)
        ventas_dict = {str(row.receta_id): int(row.total_vendido or 0) for row in result_ventas.all()}
        
        matriz = []
        for receta in recetas:
            # Calcular costo de receta
            costo_receta = 0.0
            if receta.ingredientes:
                for ingrediente in receta.ingredientes:
                    if ingrediente.producto:
                        costo_receta += float(ingrediente.cantidad) * float(ingrediente.producto.costo_unitario)
            
            precio_venta = float(receta.precio or 0)
            margen = precio_venta - costo_receta
            margen_porcentaje = (margen / precio_venta * 100) if precio_venta > 0 else 0
            
            cantidad_vendida = ventas_dict.get(str(receta.id), 0)
            
            # Clasificación (simplificada: basada en cantidad vendida y margen)
            if cantidad_vendida >= 10 and margen >= 0:
                categoria = "Estrellas"
            elif cantidad_vendida >= 10 and margen < 0:
                categoria = "Caballos de batalla"
            elif cantidad_vendida < 10 and margen >= 0:
                categoria = "Puzzles"
            else:
                categoria = "Perros"
            
            matriz.append({
                'receta_id': str(receta.id),
                'nombre': receta.nombre,
                'precio_venta': precio_venta,
                'costo_receta': round(costo_receta, 2),
                'margen': round(margen, 2),
                'margen_porcentaje': round(margen_porcentaje, 2),
                'cantidad_vendida': cantidad_vendida,
                'categoria': categoria
            })
        
        return sorted(matriz, key=lambda x: x['cantidad_vendida'], reverse=True)

    async def get_break_even(
        self, 
        fecha_inicio: date = None, 
        fecha_fin: date = None
    ) -> Dict:
        """
        2. Punto de Equilibrio (Break-even)
        Fórmula: Gastos_Fijos / Margen_Promedio
        """
        if not fecha_inicio:
            fecha_inicio = date.today() - timedelta(days=30)
        if not fecha_fin:
            fecha_fin = date.today()
        
        # Obtener gastos fijos del período
        query_gastos = (
            select(func.sum(GastoOperativo.monto))
            .where(
                and_(
                    GastoOperativo.fecha_gasto.between(fecha_inicio, fecha_fin),
                    GastoOperativo.es_fijo == True
                )
            )
        )
        result_gastos = await self.session.execute(query_gastos)
        gastos_fijos = float(result_gastos.scalar() or 0.0)
        
        # Obtener margen promedio de ventas (simplificado)
        # Por ahora asumimos un margen promedio del 60% como estimación
        margen_promedio = 0.6  # Esto debería calcularse dinámicamente
        
        punto_equilibrio = gastos_fijos / margen_promedio if margen_promedio > 0 else 0
        
        # Ventas actuales
        query_ventas = select(func.sum(VentaReceta.cantidad * VentaReceta.precio_unitario))
        result_ventas = await self.session.execute(query_ventas)
        ventas_actuales = float(result_ventas.scalar() or 0.0)
        
        porcentaje_cubierto = (ventas_actuales / punto_equilibrio * 100) if punto_equilibrio > 0 else 0
        
        return {
            'gastos_fijos': gastos_fijos,
            'margen_promedio': margen_promedio,
            'punto_equilibrio': round(punto_equilibrio, 2),
            'ventas_actuales': ventas_actuales,
            'porcentaje_cubierto': round(porcentaje_cubierto, 2)
        }

    async def get_prime_cost(
        self, 
        fecha_inicio: date = None, 
        fecha_fin: date = None
    ) -> Dict:
        """
        3. Prime Cost: (Costo_Alimentos + Costo_Labor) / Ventas
        """
        if not fecha_inicio:
            fecha_inicio = date.today() - timedelta(days=30)
        if not fecha_fin:
            fecha_fin = date.today()
        
        # Costo Alimentos (compras del período)
        query_compras = (
            select(func.sum(CompraItem.cantidad * CompraItem.precio_unitario))
            .join(CompraItem.compra)
            .where(Compra.fecha.between(fecha_inicio, fecha_fin))
        )
        result_compras = await self.session.execute(query_compras)
        costo_alimentos = float(result_compras.scalar() or 0.0)
        
        # Costo Labor (por ahora 0, requiere módulo RRHH)
        costo_labor = 0.0
        
        total_prime_cost = costo_alimentos + costo_labor
        
        # Ventas totales
        query_ventas = select(func.sum(VentaReceta.cantidad * VentaReceta.precio_unitario))
        result_ventas = await self.session.execute(query_ventas)
        ventas_totales = float(result_ventas.scalar() or 0.0)
        
        prime_cost_porcentaje = (total_prime_cost / ventas_totales * 100) if ventas_totales > 0 else 0
        
        return {
            'costo_alimentos': costo_alimentos,
            'costo_labor': costo_labor,
            'total_prime_cost': round(total_prime_cost, 2),
            'ventas_totales': ventas_totales,
            'prime_cost_porcentaje': round(prime_cost_porcentaje, 2)
        }

    async def get_variacion_precios(
        self, 
        dias_atras: int = 90
    ) -> List[Dict]:
        """
        4. Variación de precios (inflación interna)
        Compara precios más recientes vs históricos
        """
        fecha_corte = date.today() - timedelta(days=dias_atras)
        
        # Obtener productos con sus proveedores
        query = (
            select(
                CompraItem.producto_id, 
                Producto.nombre, 
                Proveedor.nombre_empresa,
                CompraItem.precio_unitario  # <--- AGREGAR ESTA LÍNEA
            )
            .join(Compra, Compra.id == CompraItem.compra_id)
            .join(Producto, Producto.id == CompraItem.producto_id)
            .outerjoin(Proveedor, Proveedor.id == Producto.proveedor_id)
            .where(Compra.fecha >= fecha_corte)
            .order_by(CompraItem.producto_id, Compra.fecha.desc())
        )
        
        result = await self.session.execute(query)
        rows = result.all()
        
        # Agrupar por producto para comparar precios
        productos_dict = {}
        for row in rows:
            p_id = str(row.producto_id)
            if p_id not in productos_dict:
                productos_dict[p_id] = {
                    'producto_id': p_id,
                    'nombre': row.nombre,
                    'proveedor_nombre': row.nombre_empresa,
                    'precios': []
                }
            productos_dict[p_id]['precios'].append(float(row.precio_unitario))
        
        variaciones = []
        for p_id, data in productos_dict.items():
            if len(data['precios']) >= 2:
                precio_anterior = data['precios'][-1]  # El más antiguo
                precio_actual = data['precios'][0]   # El más reciente
                porcentaje_cambio = ((precio_actual - precio_anterior) / precio_anterior * 100) if precio_anterior > 0 else 0
                
                if abs(porcentaje_cambio) > 5:  # Solo mostrar cambios > 5%
                    variaciones.append({
                        'producto_id': p_id,
                        'nombre': data['nombre'],
                        'proveedor_nombre': data['proveedor_nombre'],
                        'precio_anterior': precio_anterior,
                        'precio_actual': precio_actual,
                        'porcentaje_cambio': round(porcentaje_cambio, 2)
                    })
        
        return sorted(variaciones, key=lambda x: abs(x['porcentaje_cambio']), reverse=True)

# Función factory
def get_financial_vision_service(session: AsyncSession) -> FinancialVisionService:
    return FinancialVisionService(session)
