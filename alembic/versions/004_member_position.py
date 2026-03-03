"""Add position column to members table

Revision ID: 004
Revises: 003
Create Date: 2026-03-03
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "004"
down_revision: Union[str, None] = "003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("members", sa.Column("position", sa.String(64), server_default="", nullable=False))


def downgrade() -> None:
    op.drop_column("members", "position")
