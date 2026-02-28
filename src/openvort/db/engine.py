"""
数据库引擎

SQLAlchemy 2.0 异步引擎，支持 SQLite（开发）和 PostgreSQL（生产）。
"""

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from openvort.utils.logging import get_logger

log = get_logger("db")


class Base(DeclarativeBase):
    """ORM 基类"""
    pass


# 全局引擎和 session 工厂（延迟初始化）
_engine = None
_session_factory = None


async def init_db(database_url: str) -> None:
    """初始化数据库连接并创建表"""
    global _engine, _session_factory

    # 延迟导入所有 ORM 模型，确保 Base.metadata 包含所有表
    import openvort.auth.models  # noqa: F401
    import openvort.contacts.models  # noqa: F401
    import openvort.core.setup  # noqa: F401
    import openvort.db.models  # noqa: F401

    _engine = create_async_engine(database_url, echo=False)
    _session_factory = async_sessionmaker(_engine, class_=AsyncSession, expire_on_commit=False)

    async with _engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

        # 自动迁移：给已有表添加缺失的列（create_all 不会修改已有表）
        await conn.run_sync(_migrate_chat_sessions)

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


def _migrate_chat_sessions(connection) -> None:
    """自动迁移 chat_sessions 表：添加缺失的列"""
    from sqlalchemy import inspect, text

    inspector = inspect(connection)
    if "chat_sessions" not in inspector.get_table_names():
        return

    existing_cols = {col["name"] for col in inspector.get_columns("chat_sessions")}
    migrations = []

    if "session_id" not in existing_cols:
        migrations.append("ALTER TABLE chat_sessions ADD COLUMN session_id VARCHAR(64) DEFAULT 'default'")
    if "title" not in existing_cols:
        migrations.append("ALTER TABLE chat_sessions ADD COLUMN title VARCHAR(200) DEFAULT '新对话'")
    if "created_at" not in existing_cols:
        migrations.append("ALTER TABLE chat_sessions ADD COLUMN created_at DATETIME")

    for sql in migrations:
        connection.execute(text(sql))
        log.info(f"迁移 chat_sessions: {sql}")

    # 把已有行的 NULL 值填充为默认值
    if migrations:
        connection.execute(text("UPDATE chat_sessions SET session_id = 'default' WHERE session_id IS NULL"))
        connection.execute(text("UPDATE chat_sessions SET title = '新对话' WHERE title IS NULL"))
        connection.execute(text("UPDATE chat_sessions SET created_at = datetime('now') WHERE created_at IS NULL"))
        log.info("chat_sessions 表迁移完成")
