"""add_color_icon_to_categorias_recetas

Revision ID: 0017
Revises: 0016
Create Date: 2026-04-30

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '0017'
down_revision: Union[str, None] = '0016'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add color and icono columns to categorias_recetas table in operations schema
    op.add_column(
        'categorias_recetas',
        sa.Column('color', sa.String(length=20), nullable=True),
        schema='operations'
    )
    op.add_column(
        'categorias_recetas',
        sa.Column('icono', sa.String(length=50), nullable=True),
        schema='operations'
    )


def downgrade() -> None:
    op.drop_column('categorias_recetas', 'icono', schema='operations')
    op.drop_column('categorias_recetas', 'color', schema='operations')
