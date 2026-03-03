"""
数据库引擎

SQLAlchemy 2.0 异步引擎 + create_all 自动建表（PostgreSQL）。
"""

import uuid
from datetime import datetime, timezone

from sqlalchemy import create_engine, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from openvort.utils.logging import get_logger

log = get_logger("db")


class Base(DeclarativeBase):
    """ORM 基类"""
    pass


_engine = None
_session_factory = None


def _make_sync_url(database_url: str) -> str:
    """Convert async URL to sync psycopg2 URL."""
    return database_url.replace("+asyncpg", "")


def _sync_create_all(database_url: str) -> None:
    """Create all tables and seed initial data using a synchronous engine."""
    sync_url = _make_sync_url(database_url)
    sync_engine = create_engine(sync_url, echo=False)

    Base.metadata.create_all(bind=sync_engine)

    with sync_engine.connect() as conn:
        _seed_initial_data(conn)
        conn.commit()

    sync_engine.dispose()


def _seed_initial_data(conn) -> None:
    """Create default admin, builtin roles/permissions, and mark initialized.

    All statements use ON CONFLICT DO NOTHING so this is safe to run repeatedly.
    """
    now = datetime.now(timezone.utc)
    admin_id = uuid.uuid4().hex

    conn.execute(text(
        "INSERT INTO members (id, name, email, phone, status, is_account, bio, avatar_url, "
        "password_hash, notification_prefs, created_at, updated_at) "
        "VALUES (:id, :name, '', '', 'active', true, '', '', '', '{}', :now, :now) "
        "ON CONFLICT DO NOTHING"
    ), {"id": admin_id, "name": "admin", "now": now})

    roles = [
        ("admin", "管理员"),
        ("manager", "部门管理者"),
        ("member", "普通成员"),
        ("guest", "访客"),
    ]
    for role_name, display in roles:
        conn.execute(text(
            "INSERT INTO roles (name, display_name, source, is_builtin, created_at) "
            "VALUES (:name, :display, 'core', true, :now) "
            "ON CONFLICT DO NOTHING"
        ), {"name": role_name, "display": display, "now": now})

    admin_role_id = conn.execute(
        text("SELECT id FROM roles WHERE name = 'admin'")
    ).scalar()
    existing_admin = conn.execute(
        text("SELECT id FROM members WHERE name = 'admin' LIMIT 1")
    ).scalar()
    if admin_role_id and existing_admin:
        conn.execute(text(
            "INSERT INTO member_roles (member_id, role_id, created_at) "
            "VALUES (:mid, :rid, :now) "
            "ON CONFLICT DO NOTHING"
        ), {"mid": existing_admin, "rid": admin_role_id, "now": now})

    conn.execute(text(
        "INSERT INTO setup_state (key, value, updated_at) "
        "VALUES ('initialized', 'true', :now) "
        "ON CONFLICT (key) DO UPDATE SET value = 'true'"
    ), {"now": now})
    conn.execute(text(
        "INSERT INTO setup_state (key, value, updated_at) "
        "VALUES ('admin_member_id', :mid, :now) "
        "ON CONFLICT (key) DO UPDATE SET value = :mid"
    ), {"mid": existing_admin or admin_id, "now": now})


async def init_db(database_url: str) -> None:
    """Initialize database connection and create tables."""
    global _engine, _session_factory

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
        import openvort.plugins.jenkins.models  # noqa: F401
    except ImportError:
        pass

    try:
        import openvort.plugins.report.models  # noqa: F401
    except ImportError:
        pass

    _sync_create_all(database_url)

    _engine = create_async_engine(database_url, echo=False)
    _session_factory = async_sessionmaker(_engine, class_=AsyncSession, expire_on_commit=False)

    log.info(f"数据库已初始化: {database_url.split('://')[0]}")


async def close_db() -> None:
    """关闭数据库连接"""
    global _engine, _session_factory
    if _engine:
        await _engine.dispose()
        _engine = None
        _session_factory = None
        log.info("数据库连接已关闭")


def get_session() -> AsyncSession:
    """获取数据库 session"""
    if _session_factory is None:
        raise RuntimeError("数据库未初始化，请先调用 init_db()")
    return _session_factory()


def get_session_factory() -> async_sessionmaker[AsyncSession]:
    """获取 session 工厂（用于需要 context manager 的场景）"""
    if _session_factory is None:
        raise RuntimeError("数据库未初始化，请先调用 init_db()")
    return _session_factory
