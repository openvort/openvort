"""Add target_type, target_id, pinned, hidden to chat_sessions

Revision ID: 002
Revises: 001
Create Date: 2026-03-03
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "002"
down_revision: Union[str, None] = "001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("chat_sessions", sa.Column("target_type", sa.String(16), server_default="ai", nullable=False))
    op.add_column("chat_sessions", sa.Column("target_id", sa.String(32), server_default="", nullable=False))
    op.add_column("chat_sessions", sa.Column("pinned", sa.Boolean(), server_default=sa.text("false"), nullable=False))
    op.add_column("chat_sessions", sa.Column("hidden", sa.Boolean(), server_default=sa.text("false"), nullable=False))
    op.create_index("ix_chat_sessions_target", "chat_sessions", ["user_id", "target_type", "target_id"])


def downgrade() -> None:
    op.drop_index("ix_chat_sessions_target", table_name="chat_sessions")
    op.drop_column("chat_sessions", "hidden")
    op.drop_column("chat_sessions", "pinned")
    op.drop_column("chat_sessions", "target_id")
    op.drop_column("chat_sessions", "target_type")
