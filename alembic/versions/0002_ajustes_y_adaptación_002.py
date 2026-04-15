"""Ajustes y Adaptación 002

Revision ID: 0002
Revises: 0001
Create Date: 2026-04-15 13:09:46.070697

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '0002'
down_revision: Union[str, None] = '0001'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    
    # 1. Crear la tabla de relación de productos en eventos
    op.create_table('evento_productos',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('evento_id', sa.Uuid(), nullable=False),
        sa.Column('producto_id', sa.Uuid(), nullable=False),
        sa.Column('bodega_id', sa.Uuid(), nullable=False),
        sa.Column('cantidad', sa.Numeric(precision=10, scale=2), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('is_deleted', sa.Boolean(), nullable=False),
        sa.ForeignKeyConstraint(['bodega_id'], ['operations.bodegas.id'], ),
        sa.ForeignKeyConstraint(['evento_id'], ['operations.eventos.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['producto_id'], ['operations.productos.id'], ),
        sa.PrimaryKeyConstraint('id'),
        schema='operations'
    )

    # 2. Agregar nuevas columnas a tablas existentes
    op.add_column('eventos', sa.Column('valor_publico', sa.Numeric(precision=10, scale=2), nullable=True), schema='operations')
    op.add_column('producto_bodegas', sa.Column('stock_actual', sa.Numeric(precision=10, scale=2), server_default='0', nullable=False), schema='operations')

    # 3. CORRECCIÓN CRÍTICA: Alterar el tipo ENUM con CAST
    # Usamos execute directo para evitar el conflicto de UndefinedObjectError
    # Esto asume que el tipo 'tipomovimiento' YA EXISTE en el esquema 'operations' desde la migración 0001.
    op.execute(
        "ALTER TABLE operations.registros_stock "
        "ALTER COLUMN tipo_movimiento TYPE operations.tipomovimiento "
        "USING tipo_movimiento::text::operations.tipomovimiento"
    )


def downgrade() -> None:
    """Downgrade schema."""
    # Revertimos el cambio de columna (opcional, usualmente en dev volvemos a 0001)
    op.drop_column('producto_bodegas', 'stock_actual', schema='operations')
    op.drop_column('eventos', 'valor_publico', schema='operations')
    op.drop_table('evento_productos', schema='operations')
    
    # Para el downgrade del ENUM, si es necesario:
    op.execute(
        "ALTER TABLE operations.registros_stock "
        "ALTER COLUMN tipo_movimiento TYPE operations.tipomovimiento "
        "USING tipo_movimiento::text::operations.tipomovimiento"
    )