1. Gestión de Acceso y Usuarios
    - user_roles
    - permisos_merma

2. Catálogo de Productos y Bodegas
    - categorias
    - productos
    - bodegoas
    - producto_bodega

3. Operaciones de Inventario (Corazón del Sistema)
    - registros_stock
    - stock_actual

4. Eventos y Planificación
    - eventos
    - evento_productos

5. Producción y Ventas (Recetas)
    - recetas
    - receta_ingredientes
    - ventas_recetas

# ALEMBIC

docker exec -it easy-backend alembic revision --autogenerate -m "add_missing_tables_and_fields"

docker exec -it easy-backend alembic upgrade head


