# StockRegistro.tsx - Mapeo de Datos: Original → FastAPI

> Este documento mapea los datos que la vista StockRegistro.tsx necesita para funcionar.
> Primero: Identificar qué datos se necesitan.
> Segundo: Mapear a tablas originales.
> Tercero: Definir los endpoints FastAPI correspondientes.

---

## 1. Datos que la Vista Necesita (Carga Inicial)

### 1.1 Liste de Categorías

| Aspecto | Detalle |
|---------|---------|
| **Necesita** | Listar todas las categorías para filtros |
| **Tabla Original** | `categorias` |
| **Campos Usados** | `id`, `nombre` |
| **Query Original** | `supabase.from("categorias").select("*").order("nombre")` |

**📍 Endpoint FastAPI a crear:**
```
GET /inventory/categories
Response: List[CategoriaOut]
```

---

### 1.2 Liste de Productos

| Aspecto | Detalle |
|---------|---------|
| **Necesita** | Catálogo completo de productos |
| **Tabla Original** | `productos` |
| **Campos Usados** | `id`, `nombre`, `categoria_id`, `unidad`, `stock_minimo`, `costo_unitario`, `codigo_barra` |
| **Query Original** | `supabase.from("productos").select("*").order("nombre")` |

**📍 Endpoint FastAPI a crear:**
```
GET /inventory/products
Response: List[ProductoOut]
```

---

### 1.3 Liste de Bodegas

| Aspecto | Detalle |
|---------|---------|
| **Necesita** | Listar todas las bodegas disponibles |
| **Tabla Original** | `bodegas` |
| **Campos Usados** | `id`, `nombre` |
| **Query Original** | `supabase.from("bodegas").select("id, nombre")` |

**📍 Endpoint FastAPI a crear:**
```
GET /inventory/bodegas
Response: List[BodegaOut]
```

---

### 1.4 Registros de Stock (Historial)

| Aspecto | Detalle |
|---------|---------|
| **Necesita** | Todos los movimientos de stock para calcular inventario |
| **Tabla Original** | `registros_stock` |
| **Campos Usados** | `producto_id`, `bodega_id`, `cantidad`, `tipo_movimiento`, `created_at`, `fecha_vencimiento`, `descripcion_merma` |
| **Query Original** | `supabase.from("registros_stock").select("producto_id, fecha_vencimiento, cantidad, tipo_movimiento, created_at, bodega_id, descripcion_merma").order("created_at", { ascending: true })` |
| **⚠️ IMPORTANTE** | Esta query es la base para `buildInventorySnapshot()` |

**📍 Endpoint FastAPI a crear:**
```
GET /inventory/stock/status?bodega_id=uuid
GET /inventory/history/?fecha_desde=date&fecha_hasta=date
Response: Snapshot del inventario actual
```

---

### 1.5 Configuración Producto-Bodega

| Aspecto | Detalle |
|---------|---------|
| **Necesita** | Stock mínimo específico por bodega y coordenadas |
| **Tabla Original** | `producto_bodegas` |
| **Campos Usados** | `producto_id`, `bodega_id`, `stock_minimo`, `coordenada_letra`, `coordenada_numero` |
| **Query Original** | `supabase.from("producto_bodegas").select("producto_id, bodega_id, stock_minimo, coordenada_letra, coordenada_numero")` |

**📍 Endpoint FastAPI a crear:**
```
GET /inventory/product-setup?bodega_id=uuid
Response: List[ProductoBodegaOut]
```

---

## 2. Operaciones de Escritura (INSERT)

### 2.1 Guardar Conteos (Conteo/Inventario)

| Aspecto | Detalle |
|---------|---------|
| **Necesita** | Guardar cambios de inventario (tipo: "conteo") |
| **Tabla Original** | `registros_stock` |
| **Campos a Enviar** | `producto_id`, `cantidad`, `fecha_recuento`, `fecha_vencimiento`, `tipo_movimiento: "conteo"`, `bodega_id` |

**📍 Endpoint FastAPI a crear:**
```
POST /inventory/stock/bulk-movements
Body: { movements: [...] }
```

---

### 2.2 Registrar Merma

| Aspecto | Detalle |
|---------|---------|
| **Necesita** | Registrar una merma (tipo: "merma") |
| **Tabla Original** | `registros_stock` |
| **Campos a Enviar** | `producto_id`, `cantidad`, `fecha_recuento`, `fecha_vencimiento`, `tipo_movimiento: "merma"`, `motivo_merma`, `descripcion_merma`, `bodega_id` |

**📍 Endpoint FastAPI a crear:**
```
POST /inventory/mermas
Body: { producto_id, cantidad, fecha_recuento, fecha_vencimiento, motivo_merma, descripcion_merma, bodega_id }
```

---

### 2.3 Añadir Stock (Entrada)

| Aspecto | Detalle |
|---------|---------|
| **Necesita** | Registrar entrada de productos (tipo: "entrada") |
| **Tabla Original** | `registros_stock` |
| **Campos a Enviar** | `producto_id`, `cantidad`, `fecha_recuento`, `fecha_vencimiento`, `tipo_movimiento: "entrada"`, `bodega_id` |

**📍 Endpoint FastAPI ya creado:**
```
POST /inventory/stock/consume (reutilizable para entradas)
```

---

### 2.4 Transferencia entre Bodegas

| Aspecto | Detalle |
|---------|---------|
| **Necesita** | Transferir productos entre bodegas |
| **Tabla Original** | `registros_stock` (2 registros: entrada + salida) |
| **Campos a Enviar** | Registro 1: `tipo_movimiento: "transferencia"`, `bodega_id: destino`, `transfer_id`<br/>Registro 2: `tipo_movimiento: "transferencia"`, `bodega_id: origen`, `transfer_id`, `descripcion_merma: "salida"` |

**📍 Endpoint FastAPI a crear:**
```
POST /inventory/stock/transfer
Body: { items: [...], origen_id, destino_id }
```

---

## 3. Resumen: Endpoints Necesarios para StockRegistro

| # | Endpoint | Método | Tabla(s) | Estado |
|---|----------|--------|----------|--------|
| 1 | `/inventory/categories` | GET | categorias | ✅ Ya existe |
| 2 | `/inventory/products` | GET | productos | ✅ Ya existe |
| 3 | `/inventory/bodegas` | GET | bodegas | ✅ Ya existe |
| 4 | `/inventory/stock/status` | GET | registros_stock | ⚠️ Necesita ajuste |
| 5 | `/inventory/history/` | GET | registros_stock | ⚠️ Ya existe (corregido) |
| 6 | `/inventory/stock/bulk-movements` | POST | registros_stock | ⚠️ Verificar |
| 7 | `/inventory/stock/transfer` | POST | registros_stock | ❌ Falta crear |
| 8 | `/inventory/mermas` | POST | registros_stock | ❌ Falta crear |
| 9 | `/inventory/product-setup` | GET | producto_bodegas | ⚠️ Verificar |

---

## 4. Detalle de Queries del Frontend (Original)

### 4.1 loadData() - Línea 262-269

```typescript
const [catRes, prodRes, recordsRes, bodRes, pbRes] = await Promise.all([
  supabase.from("categorias").select("*").order("nombre"),
  supabase.from("productos").select("*").order("nombre"),
  supabase.from("registros_stock")
    .select("producto_id, fecha_vencimiento, cantidad, tipo_movimiento, created_at, bodega_id, descripcion_merma")
    .order("created_at", { ascending: true }),
  supabase.from("bodegas").select("id, nombre"),
  supabase.from("producto_bodegas").select("producto_id, bodega_id, stock_minimo, coordenada_letra, coordenada_numero"),
]);
```

**Equivalente FastAPI:** Puede ser 1 solo endpoint que retorna todo:
```
GET /inventory/stock/data?bodega_id=uuid
Response: {
  categorias: [...],
  productos: [...],
  registros_stock: [...],
  bodegas: [...],
  producto_bodegas: [...]
}
```

---

### 4.2 saveRecords() - Línea 443

```typescript
const { error } = await supabase.from("registros_stock").insert(records);
```

**Equivalente FastAPI:**
```
POST /inventory/stock/bulk-movements
```

---

### 4.3 confirmMerma() - Línea 620

```typescript
const { error } = await supabase.from("registros_stock").insert({
  producto_id, cantidad, fecha_recuento, fecha_vencimiento,
  usuario_id, tipo_movimiento: "merma", motivo_merma,
  descripcion_merma, bodega_id
});
```

**Equivalente FastAPI:**
```
POST /inventory/mermas
```

---

### 4.4 executeAddStock() - Línea 694

```typescript
const { error } = await supabase.from("registros_stock").insert(inserts);
```

**Equivalente FastAPI:**
```
POST /inventory/stock/bulk-movements (tipo: "entrada")
```

---

### 4.5 handleTransfer() - Línea 886, 916

```typescript
await supabase.from("registros_stock").insert(inserts); // entrada
await supabase.from("registros_stock").insert(inserts); // salida
```

**Equivalente FastAPI:**
```
POST /inventory/stock/transfer
```

---

## 5. Schema de los Datos a retornar en el Endpoint Principal

Para que StockRegistro del Frontend funcione correctamente, el endpoint principal debe retornar:

```typescript
interface StockDataResponse {
  // Categorías
  categorias: Categoria[]
  
  // Productos
  productos: Producto[]
  
  // Movimientos históricos (para buildInventorySnapshot)
  movimientos: RegistroStock[]
  
  // Bodegas
  bodegas: Bodega[]
  
  // Configuración producto-bodega
  producto_bodegas: ProductoBodega[]
}

interface Categoria {
  id: string;
  nombre: string;
}

interface Producto {
  id: string;
  nombre: string;
  categoria_id: string;
  unidad: string;
  stock_minimo: number;
  costo_unitario?: number;
  codigo_barra?: string;
}

interface RegistroStock {
  producto_id: string;
  bodega_id: string;
  cantidad: number;
  tipo_movimiento: string;
  fecha_recuento: string;
  fecha_vencimiento: string;
  created_at: string;
  descripcion_merma?: string;
}

interface Bodega {
  id: string;
  nombre: string;
}

interface ProductoBodega {
  producto_id: string;
  bodega_id: string;
  stock_minimo: number;
  coordenada_letra?: string;
  coordenada_numero?: string;
}
```

---

*Documento para mapear datos de StockRegistro.tsx a endpoints FastAPI.*
*Última actualización: Abril 2026*