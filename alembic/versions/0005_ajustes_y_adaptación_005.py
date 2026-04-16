"""Ajustes y Adaptación 005

Revision ID: 0005
Revises: 0004
Create Date: 2026-04-16 11:51:05.450655

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '0005'
down_revision: Union[str, None] = '0004'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

def upgrade() -> None:
    # 1. Limpieza preventiva y creación del tipo en MAYÚSCULAS
    op.execute("""
        DO $$ 
        BEGIN 
            -- Eliminar el tipo si existe para empezar de cero
            IF EXISTS (SELECT 1 FROM pg_type t JOIN pg_namespace n ON n.oid = t.typnamespace WHERE t.typname = 'tipomovimiento' AND n.nspname = 'operations') THEN
                -- Para borrarlo, primero debemos asegurar que ninguna columna lo use
                ALTER TABLE operations.registros_stock ALTER COLUMN tipo_movimiento TYPE VARCHAR(50);
                DROP TYPE operations.tipomovimiento;
            END IF;
            
            -- Crear el tipo con valores en MAYÚSCULAS
            CREATE TYPE operations.tipomovimiento AS ENUM (
                'CONTEO', 'CONSUMO', 'MERMA', 'ENTRADA', 'AJUSTE_POSITIVO', 'AJUSTE_NEGATIVO', 'TRANSFERENCIA'
            );
        END $$;
    """)

    # 2. Convertir la columna forzando a MAYÚSCULAS para que coincida con el nuevo Enum
    op.execute("""
        ALTER TABLE operations.registros_stock 
        ALTER COLUMN tipo_movimiento TYPE operations.tipomovimiento 
        USING UPPER(tipo_movimiento)::operations.tipomovimiento
    """)

def downgrade() -> None:
    op.execute("ALTER TABLE operations.registros_stock ALTER COLUMN tipo_movimiento TYPE VARCHAR(50)")
    op.execute("DROP TYPE IF EXISTS operations.tipomovimiento")