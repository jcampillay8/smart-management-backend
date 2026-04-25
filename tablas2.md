# Tablas de Base de Datos - Easy Stock 2 (Backend FastAPI)

> Documentación de los modelos SQLAlchemy del proyecto FastAPI.
> Schema: Configurable via `settings.DB_SCHEMA` (default: `public`)

---

## 1. Autenticación y Usuarios

### 1.1 `users`
Usuario principal del sistema.

| Campo | Tipo | Notas |
|------|------|-------|
| `id` | INTEGER | PK, autoincrement |
| `guid` | UUID | Unique, default=uuid.uuid4 |
| `username` | STRING(150) | Unique |
| `email` | STRING(254) | Unique |
| `password` | STRING(128) | Hash BCrypt |
| `first_name` | STRING(150) | Default "" |
| `last_name` | STRING(150) | Default "" |
| `occupation` | STRING(150) | Nullable |
| `native_language` | STRING(50) | Default "Spanish" |
| `has_completed_onboarding` | BOOLEAN | Default false |
| `user_image` | STRING(1048) | Nullable |
| `settings` | JSONB | Default {} |
| `is_superuser` | BOOLEAN | Default false |
| `is_deleted` | BOOLEAN | Default false |
| `has_accepted_terms` | BOOLEAN | Default false |
| `last_login` | DATETIME | Nullable |
| `role` | app_role | Default "user" |

**Enum**: `app_role` = `('admin', 'user', 'supervisor')`

---

### 1.2 `user_session_history`
Historial de sesiones de usuario.

| Campo | Tipo | Notas |
|------|------|-------|
| `id` | INTEGER | PK |
| `user_id` | INTEGER | FK → users.id |
| `login_time` | DATETIME | Default now() |
| `logout_time` | DATETIME | Nullable |
| `ip_address` | STRING(45) | Nullable |
| `user_agent` | STRING(500) | Nullable |

**Índices**: `idx_session_user_id`, `idx_session_login_time`

---

### 1.3 `refresh_tokens`
Tokens de refresh JWT.

| Campo | Tipo | Notas |
|------|------|-------|
| `id` | INTEGER | PK |
| `user_id` | INTEGER | FK → users.id |
| `token` | STRING(500) | Unique |
| `expires_at` | DATETIME | Nullable |
| `is_revoked` | BOOLEAN | Default false |
| `ip_address` | STRING(45) | Nullable |
| `user_agent` | STRING(500) | Nullable |

---

### 1.4 `password_reset_tokens`
Tokens para restablecer contraseña.

| Campo | Tipo | Notas |
|------|------|-------|
| `id` | INTEGER | PK |
| `user_id` | INTEGER | FK → users.id |
| `token` | STRING(255) | Unique |
| `expires_at` | DATETIME | Nullable |
| `is_used` | BOOLEAN | Default false |

---

### 1.5 `email_confirmation_tokens`
Tokens de confirmación de email.

| Campo | Tipo | Notas |
|------|------|-------|
| `id` | INTEGER | PK |
| `user_email` | STRING(255) | |
| `token` | STRING(255) | Unique |
| `expires_at` | DATETIME | |
| `is_used` | BOOLEAN | Default false |

---

### 1.6 `chats`
Chats del usuario (para IA).

| Campo | Tipo | Notas |
|------|------|-------|
| `id` | INTEGER | PK |
| `guid` | UUID | |
| `title` | STRING(150) | |
| `system_prompt` | STRING(2000) | |
| `is_tts_enabled` | BOOLEAN | Default false |
| `selected_voice` | STRING(50) | Nullable |

---

### 1.7 `messages`
Mensajes de chat.

| Campo | Tipo | Notas |
|------|------|-------|
| `id` | INTEGER | PK |
| `guid` | UUID | Unique |
| `role` | message_role | `'user'` / `'assistant'` |
| `content` | STRING(5000) | |
| `chat_id` | INTEGER | FK → chats.id |
| `user_id` | INTEGER | FK → users.id |

---

## 2. Permisos

### 2.1 `permisos_merma`
Permisosdelegados de merma.

| Campo | Tipo | Notas |
|------|------|-------|
| `id` | UUID | PK |
| `user_id` | INTEGER | FK → users.id |
| `otorgado_por` | INTEGER | FK → users.id |
| `created_at` | DATETIME | Default now() |

---

### 2.2 `permisos_inventario` 🆕
Permisosdelegados de inventario.

| Campo | Tipo | Notas |
|------|------|-------|
| `id` | UUID | PK |
| `user_id` | INTEGER | FK → users.id, Unique |
| `otorgado_por` | INTEGER | FK → users.id |
| `created_at` | DATETIME | Default now() |

---

### 2.3 `permisos_gestion_productos` 🆕
Permisosdelegados de gestión de productos.

| Campo | Tipo | Notas |
|------|------|-------|
| `id` | UUID | PK |
| `user_id` | INTEGER | FK → users.id, Unique |
| `otorgado_por` | INTEGER | FK → users.id |
| `created_at` | DATETIME | Default now() |

---

### 2.4 `permisos_gestion_usuarios`
Permisosdelegados de gestión de usuarios.

| Campo | Tipo | Notas |
|------|------|-------|
| `id` | UUID | PK |
| `user_id` | INTEGER | FK → users.id, Unique |
| `otorgado_por` | INTEGER | FK → users.id |
| `created_at` | DATETIME | Default now() |

---

## 3. Catálogo

### 3.1 `categorias`
Categorías de productos.

| Campo | Tipo | Notas |
|------|------|-------|
| `id` | UUID | PK |
| `nombre` | STRING(100) | NOT NULL |

---

### 3.2 `productos`
Catálogo de productos.

| Campo | Tipo | Notas |
|------|------|-------|
| `id` | UUID | PK |
| `nombre` | STRING(200) | NOT NULL |
| `categoria_id` | UUID | FK → categorias |
| `unidad` | STRING(50) | Default "unidad" |
| `costo_unitario` | NUMERIC(10,2) | Default 0.0 |
| `iva_incluido` | BOOLEAN | Default true |
| `iva_porcentaje` | NUMERIC(5,2) | Default 19.0 |
| `codigo_barra` | STRING(100) | Nullable |
| `factor_conversion` | NUMERIC(10,4) | Default 1.0 |
| `unidad_conversion` | STRING(50) | Nullable |
| `imagen_url` | STRING(1000) | Nullable |
| `precio_venta` | NUMERIC(10,2) | Default 0.0 |
| `marca` | STRING(100) | Nullable |
| `proveedor` | STRING(200) | Nullable |

---

### 3.3 `bodegas`
Bodegas físicas.

| Campo | Tipo | Notas |
|------|------|-------|
| `id` | UUID | PK |
| `nombre` | STRING(100) | NOT NULL |
| `icono` | STRING(50) | Nullable 🆕 |

---

### 3.4 `producto_bodegas`
Configuración de producto por bodega.

| Campo | Tipo | Notas |
|------|------|-------|
| `id` | UUID | PK |
| `producto_id` | UUID | FK → productos |
| `bodega_id` | UUID | FK → bodegas |
| `stock_minimo` | NUMERIC(10,2) | Default 0.0 |
| `stock_actual` | NUMERIC(10,2) | Default 0.0 |
| `coordenada_letra` | STRING(10) | Nullable |
| `coordenada_numero` | STRING(10) | Nullable |

**Unique**: `(producto_id, bodega_id)`

---

## 4. Movimientos de Stock

### 4.1 `registros_stock`
**TABLA CENTRAL** - Todos los movimientos.

| Campo | Tipo | Notas |
|------|------|-------|
| `id` | UUID | PK |
| `producto_id` | UUID | FK → productos |
| `bodega_id` | UUID | FK → bodegas |
| `cantidad` | NUMERIC(10,2) | NOT NULL |
| `tipo_movimiento` | tipo_movimiento | NOT NULL |
| `motivo_merma` | STRING(255) | Nullable |
| `descripcion_merma` | STRING(500) | Nullable |
| `fecha_recuento` | DATE | Default current_date |
| `fecha_vencimiento` | DATE | Nullable |
| `usuario_id` | INTEGER | FK → users |
| `evento_id` | UUID | FK → eventos, Nullable |
| `transfer_id` | STRING(100) | Nullable |

**Enum**: `tipo_movimiento` = `('conteo', 'consumo', 'merma', 'entrada', 'ajuste_positivo', 'ajuste_negativo', 'transferencia')`

---

### 4.2 `conteos_inventario`
Sesiones formales de inventario.

| Campo | Tipo | Notas |
|------|------|-------|
| `id` | UUID | PK |
| `bodega_id` | UUID | FK → bodegas |
| `usuario_id` | INTEGER | FK → users |
| `nombre` | STRING(200) | Nullable 🆕 |
| `estado` | STRING(50) | Default "en_progreso" |
| `created_at` | DATETIME | Default now() |
| `completed_at` | DATETIME | Nullable |

---

### 4.3 `conteo_items`
Items de inventario.

| Campo | Tipo | Notas |
|------|------|-------|
| `id` | UUID | PK |
| `conteo_id` | UUID | FK → conteos_inventario |
| `producto_id` | UUID | FK → productos |
| `cantidad_contada` | NUMERIC(10,2) | Default 0.0 |
| `fecha_vencimiento` | DATE | Nullable |
| `created_at` | DATETIME | Default now() |

---

## 5. Recetas

### 5.1 `categorias_recetas`
Categorías de recetas.

| Campo | Tipo | Notas |
|------|------|-------|
| `id` | UUID | PK |
| `nombre` | STRING(100) | Unique, NOT NULL |
| `created_at` | DATETIME | Default now() |

---

### 5.2 `recetas`
Recetas del menú.

| Campo | Tipo | Notas |
|------|------|-------|
| `id` | UUID | PK |
| `nombre` | STRING(200) | NOT NULL |
| `precio` | NUMERIC(10,2) | Default 0.0 |
| `is_active` | BOOLEAN | Default true |
| `iva_porcentaje` | NUMERIC(5,2) | Default 19.0 🆕 |
| `iva_incluido` | BOOLEAN | Default true 🆕 |
| `imagen_url` | STRING(1000) | Nullable |
| `categoria_receta_id` | UUID | FK → categorias_recetas, Nullable |

---

### 5.3 `receta_ingredientes`
Ingredientes de receta.

| Campo | Tipo | Notas |
|------|------|-------|
| `id` | UUID | PK |
| `receta_id` | UUID | FK → recetas |
| `producto_id` | UUID | FK → productos |
| `bodega_id` | UUID | FK → bodegas |
| `cantidad` | NUMERIC(10,2) | Default 0.0 |

---

### 5.4 `ventas_recetas`
Registro de ventas.

| Campo | Tipo | Notas |
|------|------|-------|
| `id` | UUID | PK |
| `receta_id` | UUID | FK → recetas |
| `cantidad` | INTEGER | Default 1 |
| `precio_unitario` | NUMERIC(10,2) | Default 0.0 |
| `usuario_id` | INTEGER | FK → users |

---

## 6. Eventos

### 6.1 `eventos`
Eventos programados.

| Campo | Tipo | Notas |
|------|------|-------|
| `id` | UUID | PK |
| `nombre` | STRING(200) | NOT NULL |
| `fecha` | DATE | NOT NULL |
| `ejecutado` | BOOLEAN | Default false |
| `cancelado` | BOOLEAN | Default false |
| `usuario_id` | INTEGER | FK → users |
| `valor_publico` | NUMERIC(10,2) | Nullable |

---

### 6.2 `evento_productos`
Productos del evento.

| Campo | Tipo | Notas |
|------|------|-------|
| `id` | UUID | PK |
| `evento_id` | UUID | FK → eventos |
| `producto_id` | UUID | FK → productos |
| `bodega_id` | UUID | FK → bodegas |
| `cantidad` | NUMERIC(10,2) | NOT NULL |

---

### 6.3 `evento_recetas`
Recetas del evento.

| Campo | Tipo | Notas |
|------|------|-------|
| `id` | UUID | PK |
| `evento_id` | UUID | FK → eventos |
| `receta_id` | UUID | FK → recetas |
| `cantidad` | INTEGER | Default 1 |

---

## 7. Compras

### 7.1 `compras`
Órdenes de compra.

| Campo | Tipo | Notas |
|------|------|-------|
| `id` | UUID | PK |
| `usuario_id` | INTEGER | FK → users |
| `estado` | STRING(50) | Default "pendiente" |
| `pedido_realizado` | BOOLEAN | Default false 🆕 |
| `fecha` | DATE | Default current_date |
| `total` | NUMERIC(10,2) | Default 0.0 |
| `factura_url` | STRING(1000) | Nullable |
| `proveedor` | STRING(200) | Nullable |
| `notas` | STRING(1000) | Nullable |
| `created_at` | DATETIME | Default now() |
| `updated_at` | DATETIME | Default now() |

---

### 7.2 `compra_items`
Items de compra.

| Campo | Tipo | Notas |
|------|------|-------|
| `id` | UUID | PK |
| `compra_id` | UUID | FK → compras |
| `producto_id` | UUID | FK → productos |
| `bodega_id` | UUID | FK → bodegas, Nullable |
| `cantidad` | NUMERIC(10,2) | Default 0.0 |
| `precio_unitario` | NUMERIC(10,2) | Default 0.0 |
| `created_at` | DATETIME | Default now() |

---

## 8. Configuración

### 8.1 `configuracion_restaurante`
Configuración global.

| Campo | Tipo | Notas |
|------|------|-------|
| `id` | UUID | PK |
| `nombre` | STRING(200) | NOT NULL |
| `logo_url` | STRING(1000) | Nullable |
| `dias_alerta_vencimiento` | NUMERIC(5,0) | Default 5 🆕 |

---

## 9. Soporte y Sugerencias 🆕

### 9.1 `tickets_soporte`
Tickets de soporte técnico.

| Campo | Tipo | Notas |
|------|------|-------|
| `id` | UUID | PK |
| `usuario_id` | INTEGER | FK → users |
| `asunto` | STRING(500) | NOT NULL |
| `descripcion` | STRING(2000) | NOT NULL |
| `estado` | STRING(50) | Default "abierto" |
| `created_at` | DATETIME | Default now() |
| `updated_at` | DATETIME | Default now() |

---

### 9.2 `sugerencias`
Sugerencias de usuarios.

| Campo | Tipo | Notas |
|------|------|-------|
| `id` | UUID | PK |
| `usuario_id` | INTEGER | FK → users |
| `contenido` | STRING(2000) | NOT NULL |
| `estado` | STRING(50) | Default "recibida" |
| `created_at` | DATETIME | Default now() |

---

## 10. AI Management

### 10.1 `llm_request_logs`
Logs de requests a IA.

| Campo | Tipo | Notas |
|------|------|-------|
| `id` | UUID | PK |
| `user_id` | INTEGER | FK → users, Nullable |
| `model` | STRING(100) | |
| `prompt_tokens` | INTEGER | |
| `completion_tokens` | INTEGER | |
| `total_tokens` | INTEGER | |
| `latency_ms` | INTEGER | |
| `created_at` | DATETIME | Default now() |

---

## 11. Comparación: Original vs FastAPI (Actualizado)

| Tabla Original | Tabla FastAPI | Estado |
|--------------|--------------|--------|
| `user_roles` | users.role (enum) | ✅ Refactorizado |
| `permisos_merma` | permisos_merma | ✅ |
| `permisos_inventario` | permisos_inventario | ✅ Agregado |
| `permisos_gestion_productos` | permisos_gestion_productos | ✅ Agregado |
| `permisos_gestion_usuarios` | permisos_gestion_usuarios | ✅ |
| `categorias` | categorias | ✅ |
| `productos` | productos | ✅ |
| `bodegas` | bodegas | ✅ + icono |
| `producto_bodegas` | producto_bodegas | ✅ |
| `registros_stock` | registros_stock | ✅ |
| `conteos_inventario` | conteos_inventario | ✅ + nombre |
| `conteo_items` | conteo_items | ✅ |
| `recetas` | recetas | ✅ + iva |
| `receta_ingredientes` | receta_ingredientes | ✅ |
| `ventas_recetas` | ventas_recetas | ✅ |
| `eventos` | eventos | ✅ |
| `evento_productos` | evento_productos | ✅ |
| `evento_recetas` | evento_recetas | ✅ |
| `compras` | compras | ✅ + pedido_realizado |
| `compra_items` | compra_items | ✅ |
| `configuracion_restaurante` | configuracion_restaurante | ✅ + dias_alerta |
| `tickets_soporte` | tickets_soporte | ✅ Agregado |
| `sugerencias` | sugerencias | ✅ Agregado |
| `categorias_recetas` | categorias_recetas | ✅ |

---

*Documentación actualizada tras la migración de paridad de campos.*
*🆕 = Campo/tabla agregado en esta migración*