"""Nuevas funcionalidades: notas, incidencias, plantillas email, auditoria registros stock

Revision ID: 0013
Revises: 0012
Create Date: 2026-04-28

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = '0013'
down_revision: Union[str, None] = '0012'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Ampliar enum TipoMovimiento con nuevos valores
    op.execute("ALTER TYPE operations.tipomovimiento ADD VALUE IF NOT EXISTS 'compra'")
    op.execute("ALTER TYPE operations.tipomovimiento ADD VALUE IF NOT EXISTS 'modificacion'")
    op.execute("ALTER TYPE operations.tipomovimiento ADD VALUE IF NOT EXISTS 'eliminacion'")

    # 2. Nuevas columnas en registros_stock
    op.add_column('registros_stock',
        sa.Column('cantidad_anterior', sa.Numeric(precision=10, scale=2), nullable=True),
        schema='operations'
    )
    op.add_column('registros_stock',
        sa.Column('receta_consumo_id', sa.String(length=100), nullable=True),
        schema='operations'
    )
    op.add_column('registros_stock',
        sa.Column('receta_id', sa.Uuid(), nullable=True),
        schema='operations'
    )
    op.add_column('registros_stock',
        sa.Column('registro_origen_id', sa.Uuid(), nullable=True),
        schema='operations'
    )
    op.add_column('registros_stock',
        sa.Column('modificado_por', sa.Integer(), nullable=True),
        schema='operations'
    )
    op.add_column('registros_stock',
        sa.Column('modificado_at', sa.DateTime(timezone=True), nullable=True),
        schema='operations'
    )
    # FKs para las nuevas columnas de registros_stock
    op.create_foreign_key(
        'fk_registros_stock_receta_id', 'registros_stock', 'recetas',
        ['receta_id'], ['id'], source_schema='operations', referent_schema='operations',
        ondelete='SET NULL'
    )
    op.create_foreign_key(
        'fk_registros_stock_modificado_por', 'registros_stock', 'users',
        ['modificado_por'], ['id'], source_schema='operations', referent_schema='operations',
        ondelete='SET NULL'
    )

    # 3. Nueva columna en compras
    op.add_column('compras',
        sa.Column('tiene_incidencia', sa.Boolean(), nullable=False, server_default='false'),
        schema='operations'
    )

    # 4. Nuevas columnas en users (perfil visible)
    op.add_column('users',
        sa.Column('nombre_visible', sa.String(length=200), nullable=True),
        schema='operations'
    )
    op.add_column('users',
        sa.Column('avatar_url', sa.String(length=1000), nullable=True),
        schema='operations'
    )

    # 5. Crear enum urgencianota
    op.execute("""
        DO $$
        BEGIN
            IF NOT EXISTS (SELECT 1 FROM pg_type t JOIN pg_namespace n ON n.oid = t.typnamespace
                           WHERE t.typname = 'urgencianota' AND n.nspname = 'operations') THEN
                CREATE TYPE operations.urgencianota AS ENUM ('alta', 'media', 'baja');
            END IF;
        END $$;
    """)

    # 6. Tabla notas
    op.create_table('notas',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('autor_id', sa.Integer(), nullable=False),
        sa.Column('contenido', sa.String(length=2000), nullable=False),
        sa.Column('urgencia', postgresql.ENUM('alta', 'media', 'baja', name='urgencianota', schema='operations', create_type=False), nullable=False, server_default='media'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('is_deleted', sa.Boolean(), nullable=False, server_default='false'),
        sa.ForeignKeyConstraint(['autor_id'], ['operations.users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        schema='operations'
    )

    # 7. Tabla nota_menciones
    op.create_table('nota_menciones',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('nota_id', sa.Uuid(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('is_deleted', sa.Boolean(), nullable=False, server_default='false'),
        sa.ForeignKeyConstraint(['nota_id'], ['operations.notas.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['user_id'], ['operations.users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        schema='operations'
    )

    # 8. Tabla notificaciones_incidencia
    op.create_table('notificaciones_incidencia',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('compra_id', sa.Uuid(), nullable=False),
        sa.Column('tipo', sa.String(length=100), nullable=False),
        sa.Column('titulo', sa.String(length=500), nullable=False),
        sa.Column('detalle', postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'{}'::jsonb"), nullable=True),
        sa.Column('resuelto', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('created_by', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['compra_id'], ['operations.compras.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['created_by'], ['operations.users.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
        schema='operations'
    )

    # 9. Tabla plantillas_email
    op.create_table('plantillas_email',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('nombre', sa.String(length=200), nullable=False),
        sa.Column('asunto', sa.String(length=500), nullable=False),
        sa.Column('cuerpo', sa.String(length=5000), nullable=False),
        sa.Column('created_by', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('is_deleted', sa.Boolean(), nullable=False, server_default='false'),
        sa.ForeignKeyConstraint(['created_by'], ['operations.users.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
        schema='operations'
    )


def downgrade() -> None:
    op.drop_table('plantillas_email', schema='operations')
    op.drop_table('notificaciones_incidencia', schema='operations')
    op.drop_table('nota_menciones', schema='operations')
    op.drop_table('notas', schema='operations')
    op.execute("DROP TYPE IF EXISTS operations.urgencianota")

    op.drop_column('users', 'avatar_url', schema='operations')
    op.drop_column('users', 'nombre_visible', schema='operations')
    op.drop_column('compras', 'tiene_incidencia', schema='operations')

    op.drop_constraint('fk_registros_stock_modificado_por', 'registros_stock', schema='operations', type_='foreignkey')
    op.drop_constraint('fk_registros_stock_receta_id', 'registros_stock', schema='operations', type_='foreignkey')
    op.drop_column('registros_stock', 'modificado_at', schema='operations')
    op.drop_column('registros_stock', 'modificado_por', schema='operations')
    op.drop_column('registros_stock', 'registro_origen_id', schema='operations')
    op.drop_column('registros_stock', 'receta_id', schema='operations')
    op.drop_column('registros_stock', 'receta_consumo_id', schema='operations')
    op.drop_column('registros_stock', 'cantidad_anterior', schema='operations')
