"""add implicit cast from varchar/text to approle enum

PostgreSQL does not have an implicit assignment cast from varchar/text
to enum types. SQL clients like DataGrip use the extended query protocol
and bind parameters as varchar, causing:
  ERROR: column "role" is of type operations.approle
         but expression is of type character varying

This migration adds the missing implicit cast so that
  UPDATE users SET role = 'ADMIN'  -- works in any SQL client

Revision ID: 0023
Revises: 0022
Create Date: 2026-05-14 12:10:00.000000

"""
from typing import Sequence, Union

from alembic import op


revision: str = '0023'
down_revision: Union[str, None] = '0022'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("CREATE CAST (character varying AS operations.approle) WITH INOUT AS ASSIGNMENT")
    op.execute("CREATE CAST (text AS operations.approle) WITH INOUT AS ASSIGNMENT")


def downgrade() -> None:
    op.execute("DROP CAST IF EXISTS (character varying AS operations.approle)")
    op.execute("DROP CAST IF EXISTS (text AS operations.approle)")
