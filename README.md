# Migration 01

-- Enum for roles
CREATE TYPE public.app_role AS ENUM ('admin', 'user');

-- User roles table
CREATE TABLE public.user_roles (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID REFERENCES auth.users(id) ON DELETE CASCADE NOT NULL,
  role app_role NOT NULL,
  UNIQUE (user_id, role)
);
ALTER TABLE public.user_roles ENABLE ROW LEVEL SECURITY;

-- Security definer function to check roles
CREATE OR REPLACE FUNCTION public.has_role(_user_id UUID, _role app_role)
RETURNS BOOLEAN
LANGUAGE sql
STABLE
SECURITY DEFINER
SET search_path = public
AS $$
  SELECT EXISTS (
    SELECT 1 FROM public.user_roles
    WHERE user_id = _user_id AND role = _role
  )
$$;

-- RLS for user_roles
CREATE POLICY "Users can read own roles" ON public.user_roles
  FOR SELECT TO authenticated
  USING (auth.uid() = user_id);

-- Categorias table
CREATE TABLE public.categorias (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  nombre TEXT NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
ALTER TABLE public.categorias ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Authenticated can read categorias" ON public.categorias
  FOR SELECT TO authenticated USING (true);

CREATE POLICY "Admins can insert categorias" ON public.categorias
  FOR INSERT TO authenticated
  WITH CHECK (public.has_role(auth.uid(), 'admin'));

CREATE POLICY "Admins can update categorias" ON public.categorias
  FOR UPDATE TO authenticated
  USING (public.has_role(auth.uid(), 'admin'));

CREATE POLICY "Admins can delete categorias" ON public.categorias
  FOR DELETE TO authenticated
  USING (public.has_role(auth.uid(), 'admin'));

-- Productos table
CREATE TABLE public.productos (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  nombre TEXT NOT NULL,
  categoria_id UUID NOT NULL REFERENCES public.categorias(id) ON DELETE CASCADE,
  unidad TEXT NOT NULL DEFAULT 'unidad',
  stock_minimo NUMERIC NOT NULL DEFAULT 0,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
ALTER TABLE public.productos ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Authenticated can read productos" ON public.productos
  FOR SELECT TO authenticated USING (true);

CREATE POLICY "Admins can insert productos" ON public.productos
  FOR INSERT TO authenticated
  WITH CHECK (public.has_role(auth.uid(), 'admin'));

CREATE POLICY "Admins can update productos" ON public.productos
  FOR UPDATE TO authenticated
  USING (public.has_role(auth.uid(), 'admin'));

CREATE POLICY "Admins can delete productos" ON public.productos
  FOR DELETE TO authenticated
  USING (public.has_role(auth.uid(), 'admin'));

-- Registros de stock table
CREATE TABLE public.registros_stock (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  producto_id UUID NOT NULL REFERENCES public.productos(id) ON DELETE CASCADE,
  cantidad NUMERIC NOT NULL,
  fecha_recuento DATE NOT NULL DEFAULT CURRENT_DATE,
  fecha_vencimiento DATE,
  usuario_id UUID NOT NULL REFERENCES auth.users(id),
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
ALTER TABLE public.registros_stock ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Authenticated can read registros" ON public.registros_stock
  FOR SELECT TO authenticated USING (true);

CREATE POLICY "Authenticated can insert registros" ON public.registros_stock
  FOR INSERT TO authenticated
  WITH CHECK (auth.uid() = usuario_id);

-- View for latest stock per product
CREATE OR REPLACE VIEW public.stock_actual AS
SELECT DISTINCT ON (producto_id)
  producto_id,
  cantidad,
  fecha_recuento,
  fecha_vencimiento,
  usuario_id
FROM public.registros_stock
ORDER BY producto_id, created_at DESC;

-- Trigger to auto-assign 'user' role on signup
CREATE OR REPLACE FUNCTION public.handle_new_user()
RETURNS TRIGGER
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
BEGIN
  INSERT INTO public.user_roles (user_id, role)
  VALUES (NEW.id, 'user');
  RETURN NEW;
END;
$$;

CREATE TRIGGER on_auth_user_created
  AFTER INSERT ON auth.users
  FOR EACH ROW EXECUTE FUNCTION public.handle_new_user();

# Migration 02
-- Fix security definer view by setting it to security invoker
ALTER VIEW public.stock_actual SET (security_invoker = on);

# Migration 03

-- Add tipo_movimiento and motivo_merma to registros_stock
ALTER TABLE public.registros_stock
  ADD COLUMN tipo_movimiento text NOT NULL DEFAULT 'conteo',
  ADD COLUMN motivo_merma text;

-- Add validation trigger for motivo_merma
CREATE OR REPLACE FUNCTION public.validate_motivo_merma()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
  IF NEW.tipo_movimiento != 'merma' AND NEW.motivo_merma IS NOT NULL THEN
    NEW.motivo_merma := NULL;
  END IF;
  IF NEW.tipo_movimiento = 'merma' AND NEW.motivo_merma IS NULL THEN
    RAISE EXCEPTION 'motivo_merma is required when tipo_movimiento is merma';
  END IF;
  RETURN NEW;
END;
$$;

CREATE TRIGGER trg_validate_motivo_merma
  BEFORE INSERT OR UPDATE ON public.registros_stock
  FOR EACH ROW
  EXECUTE FUNCTION public.validate_motivo_merma();

# Migration 04 

-- Fix search_path for validate_motivo_merma
CREATE OR REPLACE FUNCTION public.validate_motivo_merma()
RETURNS trigger
LANGUAGE plpgsql
SECURITY INVOKER
SET search_path = public
AS $$
BEGIN
  IF NEW.tipo_movimiento != 'merma' AND NEW.motivo_merma IS NOT NULL THEN
    NEW.motivo_merma := NULL;
  END IF;
  IF NEW.tipo_movimiento = 'merma' AND NEW.motivo_merma IS NULL THEN
    RAISE EXCEPTION 'motivo_merma is required when tipo_movimiento is merma';
  END IF;
  RETURN NEW;
END;
$$;

# Migration 05
ALTER TYPE public.app_role ADD VALUE IF NOT EXISTS 'supervisor';

# Migration 06
-- Create permissions table for user merma access
CREATE TABLE public.permisos_merma (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id uuid NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
  otorgado_por uuid NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
  created_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE(user_id)
);

ALTER TABLE public.permisos_merma ENABLE ROW LEVEL SECURITY;

-- Only admins/supervisors can manage permissions
CREATE POLICY "Admins and supervisors can manage permisos_merma"
ON public.permisos_merma
FOR ALL
TO authenticated
USING (
  public.has_role(auth.uid(), 'admin') OR public.has_role(auth.uid(), 'supervisor')
)
WITH CHECK (
  public.has_role(auth.uid(), 'admin') OR public.has_role(auth.uid(), 'supervisor')
);

-- All authenticated users can read their own permissions
CREATE POLICY "Users can read own permisos_merma"
ON public.permisos_merma
FOR SELECT
TO authenticated
USING (auth.uid() = user_id);

-- Add UPDATE policy on registros_stock for admins/supervisors
CREATE POLICY "Admins and supervisors can update registros"
ON public.registros_stock
FOR UPDATE
TO authenticated
USING (
  public.has_role(auth.uid(), 'admin') OR public.has_role(auth.uid(), 'supervisor')
);

-- Add DELETE policy on registros_stock for admins/supervisors
CREATE POLICY "Admins and supervisors can delete registros"
ON public.registros_stock
FOR DELETE
TO authenticated
USING (
  public.has_role(auth.uid(), 'admin') OR public.has_role(auth.uid(), 'supervisor')
);

-- Function to check if user has merma permission
CREATE OR REPLACE FUNCTION public.has_merma_permission(_user_id uuid)
RETURNS boolean
LANGUAGE sql
STABLE
SECURITY DEFINER
SET search_path = public
AS $$
  SELECT 
    public.has_role(_user_id, 'admin') 
    OR public.has_role(_user_id, 'supervisor')
    OR EXISTS (
      SELECT 1 FROM public.permisos_merma WHERE user_id = _user_id
    )
$$;

######################################################################################
######################################################################################
######################################################################################

# Migration 07
-- Allow admins to read all user roles (for config page)
CREATE POLICY "Admins can read all user_roles"
ON public.user_roles
FOR SELECT
TO authenticated
USING (public.has_role(auth.uid(), 'admin'));

-- Allow admins to update user roles
CREATE POLICY "Admins can update user_roles"
ON public.user_roles
FOR UPDATE
TO authenticated
USING (public.has_role(auth.uid(), 'admin'));

# Migration 08

-- Update stock_actual view to account for consumo and merma deductions
DROP VIEW IF EXISTS public.stock_actual;

CREATE VIEW public.stock_actual AS
WITH ultimo_conteo AS (
  SELECT DISTINCT ON (producto_id)
    producto_id, cantidad, fecha_recuento, fecha_vencimiento, usuario_id, created_at
  FROM public.registros_stock
  WHERE tipo_movimiento = 'conteo'
  ORDER BY producto_id, created_at DESC
),
deducciones AS (
  SELECT uc.producto_id, COALESCE(SUM(rs.cantidad), 0) as total_deducido
  FROM ultimo_conteo uc
  LEFT JOIN public.registros_stock rs ON rs.producto_id = uc.producto_id
    AND rs.tipo_movimiento IN ('consumo', 'merma')
    AND rs.created_at > uc.created_at
  GROUP BY uc.producto_id
)
SELECT
  uc.producto_id,
  uc.cantidad - COALESCE(d.total_deducido, 0) as cantidad,
  uc.fecha_recuento,
  uc.fecha_vencimiento,
  uc.usuario_id
FROM ultimo_conteo uc
LEFT JOIN deducciones d ON d.producto_id = uc.producto_id;

# Migration 09

-- Fix security definer view warning by explicitly setting security invoker
ALTER VIEW public.stock_actual SET (security_invoker = on);

# Migration 10

CREATE OR REPLACE FUNCTION public.get_user_emails()
RETURNS TABLE(user_id uuid, email text)
LANGUAGE sql
STABLE SECURITY DEFINER
SET search_path TO 'public'
AS $$
  SELECT au.id AS user_id, au.email::text AS email
  FROM auth.users au
  WHERE public.has_role(auth.uid(), 'admin') OR public.has_role(auth.uid(), 'supervisor')
$$;

# Migration 11
ALTER TABLE public.productos ADD COLUMN costo_unitario numeric NOT NULL DEFAULT 0;

# Migration 12

-- Eventos table
CREATE TABLE public.eventos (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  nombre text NOT NULL,
  fecha date NOT NULL,
  ejecutado boolean NOT NULL DEFAULT false,
  usuario_id uuid NOT NULL,
  created_at timestamp with time zone NOT NULL DEFAULT now()
);

-- Evento items (productos por evento)
CREATE TABLE public.evento_productos (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  evento_id uuid NOT NULL REFERENCES public.eventos(id) ON DELETE CASCADE,
  producto_id uuid NOT NULL REFERENCES public.productos(id) ON DELETE CASCADE,
  cantidad numeric NOT NULL,
  UNIQUE(evento_id, producto_id)
);

-- RLS on eventos
ALTER TABLE public.eventos ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Authenticated can read eventos"
  ON public.eventos FOR SELECT TO authenticated
  USING (true);

CREATE POLICY "Authenticated can insert eventos"
  ON public.eventos FOR INSERT TO authenticated
  WITH CHECK (auth.uid() = usuario_id);

CREATE POLICY "Authenticated can update own eventos"
  ON public.eventos FOR UPDATE TO authenticated
  USING (auth.uid() = usuario_id OR has_role(auth.uid(), 'admin'::app_role));

CREATE POLICY "Admins can delete eventos"
  ON public.eventos FOR DELETE TO authenticated
  USING (has_role(auth.uid(), 'admin'::app_role));

-- RLS on evento_productos
ALTER TABLE public.evento_productos ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Authenticated can read evento_productos"
  ON public.evento_productos FOR SELECT TO authenticated
  USING (true);

CREATE POLICY "Authenticated can insert evento_productos"
  ON public.evento_productos FOR INSERT TO authenticated
  WITH CHECK (EXISTS (
    SELECT 1 FROM public.eventos e WHERE e.id = evento_id AND e.usuario_id = auth.uid()
  ));

CREATE POLICY "Owner or admin can update evento_productos"
  ON public.evento_productos FOR UPDATE TO authenticated
  USING (EXISTS (
    SELECT 1 FROM public.eventos e WHERE e.id = evento_id AND (e.usuario_id = auth.uid() OR has_role(auth.uid(), 'admin'::app_role))
  ));

CREATE POLICY "Owner or admin can delete evento_productos"
  ON public.evento_productos FOR DELETE TO authenticated
  USING (EXISTS (
    SELECT 1 FROM public.eventos e WHERE e.id = evento_id AND (e.usuario_id = auth.uid() OR has_role(auth.uid(), 'admin'::app_role))
  ));

# Migration 13

ALTER TABLE public.registros_stock ADD COLUMN descripcion_merma text;
ALTER TABLE public.registros_stock ADD COLUMN evento_id uuid REFERENCES public.eventos(id) ON DELETE SET NULL;

CREATE POLICY "Users can delete own event consumo records"
ON public.registros_stock
FOR DELETE
TO authenticated
USING (
  usuario_id = auth.uid() 
  AND tipo_movimiento = 'consumo' 
  AND evento_id IS NOT NULL
);

# Migration 14 
ALTER TABLE public.eventos ADD COLUMN cancelado boolean NOT NULL DEFAULT false;

# Migration 15

-- Create bodegas table
CREATE TABLE public.bodegas (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  nombre text NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now()
);

ALTER TABLE public.bodegas ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Authenticated can read bodegas" ON public.bodegas FOR SELECT TO authenticated USING (true);
CREATE POLICY "Admins can insert bodegas" ON public.bodegas FOR INSERT TO authenticated WITH CHECK (has_role(auth.uid(), 'admin'::app_role));
CREATE POLICY "Admins can update bodegas" ON public.bodegas FOR UPDATE TO authenticated USING (has_role(auth.uid(), 'admin'::app_role));
CREATE POLICY "Admins can delete bodegas" ON public.bodegas FOR DELETE TO authenticated USING (has_role(auth.uid(), 'admin'::app_role));

-- Seed default bodegas
INSERT INTO public.bodegas (nombre) VALUES ('Bodega Principal'), ('Bodega Tránsito');

-- Add bodega_id and transfer_id to registros_stock
ALTER TABLE public.registros_stock ADD COLUMN bodega_id uuid REFERENCES public.bodegas(id);
ALTER TABLE public.registros_stock ADD COLUMN transfer_id uuid;

-- Set existing records to Bodega Principal
UPDATE public.registros_stock SET bodega_id = (SELECT id FROM public.bodegas WHERE nombre = 'Bodega Principal' LIMIT 1) WHERE bodega_id IS NULL;

-- Make bodega_id NOT NULL going forward
ALTER TABLE public.registros_stock ALTER COLUMN bodega_id SET NOT NULL;

-- Update stock_actual view to include bodega_id
DROP VIEW IF EXISTS public.stock_actual;
CREATE VIEW public.stock_actual AS
WITH ultimo_conteo AS (
  SELECT DISTINCT ON (producto_id, bodega_id) 
    producto_id, bodega_id, cantidad, fecha_recuento, fecha_vencimiento, usuario_id, created_at
  FROM registros_stock
  WHERE tipo_movimiento = 'conteo'
  ORDER BY producto_id, bodega_id, created_at DESC
),
deducciones AS (
  SELECT uc.producto_id, uc.bodega_id,
    COALESCE(SUM(rs.cantidad), 0) AS total_deducido
  FROM ultimo_conteo uc
  LEFT JOIN registros_stock rs 
    ON rs.producto_id = uc.producto_id 
    AND rs.bodega_id = uc.bodega_id
    AND rs.tipo_movimiento IN ('consumo', 'merma')
    AND rs.created_at > uc.created_at
  GROUP BY uc.producto_id, uc.bodega_id
)
SELECT uc.producto_id, uc.bodega_id,
  uc.cantidad - COALESCE(d.total_deducido, 0) AS cantidad,
  uc.fecha_recuento, uc.fecha_vencimiento, uc.usuario_id
FROM ultimo_conteo uc
LEFT JOIN deducciones d ON d.producto_id = uc.producto_id AND d.bodega_id = uc.bodega_id;

# Migration 16

-- Recetas table
CREATE TABLE public.recetas (
  id UUID NOT NULL DEFAULT gen_random_uuid() PRIMARY KEY,
  nombre TEXT NOT NULL,
  precio NUMERIC NOT NULL DEFAULT 0,
  created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now()
);

ALTER TABLE public.recetas ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Authenticated can read recetas" ON public.recetas FOR SELECT TO authenticated USING (true);
CREATE POLICY "Admins can insert recetas" ON public.recetas FOR INSERT TO authenticated WITH CHECK (has_role(auth.uid(), 'admin'));
CREATE POLICY "Admins can update recetas" ON public.recetas FOR UPDATE TO authenticated USING (has_role(auth.uid(), 'admin'));
CREATE POLICY "Admins can delete recetas" ON public.recetas FOR DELETE TO authenticated USING (has_role(auth.uid(), 'admin'));

-- Receta ingredientes table
CREATE TABLE public.receta_ingredientes (
  id UUID NOT NULL DEFAULT gen_random_uuid() PRIMARY KEY,
  receta_id UUID NOT NULL REFERENCES public.recetas(id) ON DELETE CASCADE,
  producto_id UUID NOT NULL REFERENCES public.productos(id) ON DELETE CASCADE,
  bodega_id UUID NOT NULL REFERENCES public.bodegas(id),
  cantidad NUMERIC NOT NULL DEFAULT 0
);

ALTER TABLE public.receta_ingredientes ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Authenticated can read receta_ingredientes" ON public.receta_ingredientes FOR SELECT TO authenticated USING (true);
CREATE POLICY "Admins can insert receta_ingredientes" ON public.receta_ingredientes FOR INSERT TO authenticated WITH CHECK (has_role(auth.uid(), 'admin'));
CREATE POLICY "Admins can update receta_ingredientes" ON public.receta_ingredientes FOR UPDATE TO authenticated USING (has_role(auth.uid(), 'admin'));
CREATE POLICY "Admins can delete receta_ingredientes" ON public.receta_ingredientes FOR DELETE TO authenticated USING (has_role(auth.uid(), 'admin'));

-- Ventas de recetas
CREATE TABLE public.ventas_recetas (
  id UUID NOT NULL DEFAULT gen_random_uuid() PRIMARY KEY,
  receta_id UUID NOT NULL REFERENCES public.recetas(id) ON DELETE CASCADE,
  cantidad INTEGER NOT NULL DEFAULT 1,
  precio_unitario NUMERIC NOT NULL DEFAULT 0,
  usuario_id UUID NOT NULL,
  created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now()
);

ALTER TABLE public.ventas_recetas ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Authenticated can read ventas_recetas" ON public.ventas_recetas FOR SELECT TO authenticated USING (true);
CREATE POLICY "Authenticated can insert ventas_recetas" ON public.ventas_recetas FOR INSERT TO authenticated WITH CHECK (auth.uid() = usuario_id);
CREATE POLICY "Admins can delete ventas_recetas" ON public.ventas_recetas FOR DELETE TO authenticated USING (has_role(auth.uid(), 'admin'));

# Migration 17

-- Create producto_bodegas junction table for per-bodega stock minimums
CREATE TABLE public.producto_bodegas (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  producto_id uuid NOT NULL,
  bodega_id uuid NOT NULL,
  stock_minimo numeric NOT NULL DEFAULT 0,
  UNIQUE(producto_id, bodega_id)
);

ALTER TABLE public.producto_bodegas ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Authenticated can read producto_bodegas"
  ON public.producto_bodegas FOR SELECT TO authenticated
  USING (true);

CREATE POLICY "Admins can insert producto_bodegas"
  ON public.producto_bodegas FOR INSERT TO authenticated
  WITH CHECK (has_role(auth.uid(), 'admin'::app_role));

CREATE POLICY "Admins can update producto_bodegas"
  ON public.producto_bodegas FOR UPDATE TO authenticated
  USING (has_role(auth.uid(), 'admin'::app_role));

CREATE POLICY "Admins can delete producto_bodegas"
  ON public.producto_bodegas FOR DELETE TO authenticated
  USING (has_role(auth.uid(), 'admin'::app_role));

-- Add bodega_id to evento_productos for per-bodega event product tracking
ALTER TABLE public.evento_productos ADD COLUMN bodega_id uuid;

-- Migrate existing stock_minimo data: for each product, find which bodegas it has records in and create entries
INSERT INTO public.producto_bodegas (producto_id, bodega_id, stock_minimo)
SELECT DISTINCT rs.producto_id, rs.bodega_id, p.stock_minimo
FROM public.registros_stock rs
JOIN public.productos p ON p.id = rs.producto_id
WHERE rs.bodega_id IS NOT NULL
ON CONFLICT (producto_id, bodega_id) DO NOTHING;
