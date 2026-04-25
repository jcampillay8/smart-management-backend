"""add eventos table

Revision ID: 0011
Revises: 0010
Create Date: 2026-04-25

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '0011'
down_revision = '0010'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create eventos table
    op.create_table('eventos',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False, server_default=sa.text('gen_random_uuid()')),
        sa.Column('nombre', sa.String(length=200), nullable=False),
        sa.Column('fecha', sa.Date(), nullable=False),
        sa.Column('ejecutado', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('cancelado', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('usuario_id', sa.Integer(), nullable=False),
        sa.Column('valor_publico', sa.Numeric(precision=10, scale=2), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )
    
    # Create evento_productos table
    op.create_table('evento_productos',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False, server_default=sa.text('gen_random_uuid()')),
        sa.Column('evento_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('producto_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('bodega_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('cantidad', sa.Numeric(precision=10, scale=2), nullable=False),
        sa.ForeignKeyConstraint(['evento_id'], ['eventos.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    
    # Create evento_recetas table
    op.create_table('evento_recetas',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False, server_default=sa.text('gen_random_uuid()')),
        sa.Column('evento_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('receta_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('cantidad', sa.Integer(), nullable=False, server_default='1'),
        sa.ForeignKeyConstraint(['evento_id'], ['eventos.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )


def downgrade() -> None:
    op.drop_table('evento_recetas')
    op.drop_table('evento_productos')
    op.drop_table('eventos')
