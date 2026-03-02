"""initial schema

Revision ID: 001
Revises:
Create Date: 2026-03-02
"""
import uuid
from datetime import datetime, timezone
from typing import Sequence, Union

from alembic import op
from sqlalchemy import text

import openvort.auth.models  # noqa: F401
import openvort.contacts.models  # noqa: F401
import openvort.core.setup  # noqa: F401
import openvort.db.models  # noqa: F401

try:
    import openvort.plugins.vortflow.models  # noqa: F401
except ImportError:
    pass
try:
    import openvort.plugins.vortgit.models  # noqa: F401
except ImportError:
    pass
try:
    import openvort.plugins.report.models  # noqa: F401
except ImportError:
    pass

from openvort.db.engine import Base

revision: str = "001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    Base.metadata.create_all(bind=bind)
    _seed_admin(bind)


def downgrade() -> None:
    bind = op.get_bind()
    Base.metadata.drop_all(bind=bind)


def _seed_admin(bind) -> None:
    """Create default admin member, builtin roles/permissions, and mark initialized."""
    now = datetime.now(timezone.utc)
    admin_id = uuid.uuid4().hex

    # 1. Default admin member
    bind.execute(text(
        "INSERT INTO members (id, name, email, phone, status, is_account, bio, avatar_url, "
        "password_hash, notification_prefs, created_at, updated_at) "
        "VALUES (:id, :name, '', '', 'active', true, '', '', '', '{}', :now, :now) "
        "ON CONFLICT DO NOTHING"
    ), {"id": admin_id, "name": "admin", "now": now})

    # 2. Builtin roles
    roles = [
        ("admin", "管理员"),
        ("manager", "部门管理者"),
        ("member", "普通成员"),
        ("guest", "访客"),
    ]
    for role_name, display in roles:
        bind.execute(text(
            "INSERT INTO roles (name, display_name, source, is_builtin, created_at) "
            "VALUES (:name, :display, 'core', true, :now) "
            "ON CONFLICT DO NOTHING"
        ), {"name": role_name, "display": display, "now": now})

    # 3. Assign admin role
    admin_role_id = bind.execute(
        text("SELECT id FROM roles WHERE name = 'admin'")
    ).scalar()
    if admin_role_id:
        bind.execute(text(
            "INSERT INTO member_roles (member_id, role_id, created_at) "
            "VALUES (:mid, :rid, :now) "
            "ON CONFLICT DO NOTHING"
        ), {"mid": admin_id, "rid": admin_role_id, "now": now})

    # 4. Mark system as initialized
    bind.execute(text(
        "INSERT INTO setup_state (key, value, updated_at) "
        "VALUES ('initialized', 'true', :now) "
        "ON CONFLICT (key) DO UPDATE SET value = 'true'"
    ), {"now": now})
    bind.execute(text(
        "INSERT INTO setup_state (key, value, updated_at) "
        "VALUES ('admin_member_id', :mid, :now) "
        "ON CONFLICT (key) DO UPDATE SET value = :mid"
    ), {"mid": admin_id, "now": now})
