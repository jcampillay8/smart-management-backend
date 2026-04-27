"""add proveedores table

Revision ID: 0012
Revises: 0011
Create Date: 2026-04-27

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '0012'
down_revision = '0011'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table('proveedores',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False, server_default=sa.text('gen_random_uuid()')),
        sa.Column('nombre_empresa', sa.String(length=255), nullable=False),
        sa.Column('rut', sa.String(length=20), nullable=True),
        sa.Column('nombre_contacto', sa.String(length=255), nullable=True),
        sa.Column('telefono', sa.String(length=50), nullable=True),
        sa.Column('direccion', sa.String(length=500), nullable=True),
        sa.Column('email', sa.String(length=255), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        schema='operations'
    )
    op.create_index(op.f('ix_proveedores_nombre_empresa'), 'proveedores', ['nombre_empresa'], unique=False, schema='operations')


def downgrade() -> None:
    op.drop_index(op.f('ix_proveedores_nombre_empresa'), table_name='proveedores', schema='operations')
    op.drop_table('proveedores', schema='operations')