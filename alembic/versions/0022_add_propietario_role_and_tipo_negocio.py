"""add PROPIETARIO role to approle enum and tipo_negocio column

Revision ID: 0022
Revises: 0021
Create Date: 2026-05-14 11:30:48.037313

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '0022'
down_revision: Union[str, None] = '0021'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("ALTER TABLE operations.configuracion_restaurante ADD COLUMN IF NOT EXISTS tipo_negocio VARCHAR(100)")

    op.execute("COMMIT")
    op.execute("ALTER TYPE operations.approle ADD VALUE IF NOT EXISTS 'PROPIETARIO' AFTER 'SUPERVISOR'")
    op.execute("BEGIN")


def downgrade() -> None:
    op.execute("ALTER TABLE operations.configuracion_restaurante DROP COLUMN IF EXISTS tipo_negocio")
