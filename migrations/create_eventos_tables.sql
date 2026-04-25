-- Migration script to create eventos tables
-- Run this SQL on your PostgreSQL database

-- Schema check (use your schema name, commonly 'easy_stock' or 'public')
DO $$ 
BEGIN
    -- Create schema if not exists (optional - remove if using public)
    -- CREATE SCHEMA IF NOT EXISTS easy_stock;
    
    -- Create eventos table
    CREATE TABLE IF NOT EXISTS eventos (
        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        nombre VARCHAR(200) NOT NULL,
        fecha DATE NOT NULL,
        ejecutado BOOLEAN DEFAULT FALSE,
        cancelado BOOLEAN DEFAULT FALSE,
        usuario_id INTEGER NOT NULL,
        valor_publico NUMERIC(10, 2),
        created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
    );
    
    -- Create evento_productos table
    CREATE TABLE IF NOT EXISTS evento_productos (
        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        evento_id UUID NOT NULL REFERENCES eventos(id) ON DELETE CASCADE,
        producto_id UUID NOT NULL,
        bodega_id UUID NOT NULL,
        cantidad NUMERIC(10, 2) NOT NULL
    );
    
    -- Create evento_recetas table
    CREATE TABLE IF NOT EXISTS evento_recetas (
        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        evento_id UUID NOT NULL REFERENCES eventos(id) ON DELETE CASCADE,
        receta_id UUID NOT NULL,
        cantidad INTEGER DEFAULT 1
    );
    
    RAISE NOTICE 'Eventos tables created successfully';
END $$;