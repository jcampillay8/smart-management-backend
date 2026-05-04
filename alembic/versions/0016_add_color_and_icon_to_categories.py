"""add_color_and_icon_to_categories

Revision ID: 0016
Revises: 0015
Create Date: 2026-04-29 18:30:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '0016'
down_revision: Union[str, None] = '0015'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add color and icono columns to categorias table in operations schema
    op.add_column('categorias', sa.Column('color', sa.String(length=20), nullable=True), schema='operations')
    op.add_column('categorias', sa.Column('icono', sa.String(length=50), nullable=True), schema='operations')


def downgrade() -> None:
    # Remove color and icono columns from categorias table in operations schema
    op.drop_column('categorias', 'icono', schema='operations')
    op.drop_column('categorias', 'color', schema='operations')
