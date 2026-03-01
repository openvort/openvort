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
    """自动迁移 chat_sessions 表：添加缺失的列 + 修复唯一约束"""
    from sqlalchemy import inspect, text

    inspector = inspect(connection)
    if "chat_sessions" not in inspector.get_table_names():
        return

    existing_cols = {col["name"] for col in inspector.get_columns("chat_sessions")}

    # 检测旧的唯一约束：(channel, user_id) 需要迁移为 (channel, user_id, session_id)
    needs_rebuild = False
    if "session_id" not in existing_cols:
        needs_rebuild = True
    else:
        for uc in inspector.get_unique_constraints("chat_sessions"):
            cols = set(uc["column_names"])
            if cols == {"channel", "user_id"}:
                needs_rebuild = True
                break

    if needs_rebuild:
        _rebuild_chat_sessions_table(connection, existing_cols)
        return

    # 仅补齐缺失列（表结构已正确的场景）
    migrations = []
    if "title" not in existing_cols:
        migrations.append("ALTER TABLE chat_sessions ADD COLUMN title VARCHAR(200) DEFAULT '新对话'")
    if "created_at" not in existing_cols:
        migrations.append("ALTER TABLE chat_sessions ADD COLUMN created_at DATETIME")

    for sql in migrations:
        connection.execute(text(sql))
        log.info(f"迁移 chat_sessions: {sql}")

    if migrations:
        connection.execute(text("UPDATE chat_sessions SET title = '新对话' WHERE title IS NULL"))
        connection.execute(text("UPDATE chat_sessions SET created_at = datetime('now') WHERE created_at IS NULL"))
        log.info("chat_sessions 表迁移完成")


def _rebuild_chat_sessions_table(connection, existing_cols: set[str]) -> None:
    """重建 chat_sessions 表以修复唯一约束（SQLite 不支持 ALTER CONSTRAINT）"""
    from sqlalchemy import text

    has_session_id = "session_id" in existing_cols
    has_title = "title" in existing_cols
    has_created_at = "created_at" in existing_cols

    connection.execute(text("""
        CREATE TABLE chat_sessions_new (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            channel VARCHAR(32),
            user_id VARCHAR(64),
            session_id VARCHAR(64) DEFAULT 'default',
            title VARCHAR(200) DEFAULT '新对话',
            messages TEXT DEFAULT '[]',
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            UNIQUE (channel, user_id, session_id)
        )
    """))

    src_session_id = "session_id" if has_session_id else "'default'"
    src_title = "title" if has_title else "'新对话'"
    src_created_at = "created_at" if has_created_at else "datetime('now')"

    connection.execute(text(f"""
        INSERT INTO chat_sessions_new
            (id, channel, user_id, session_id, title, messages, created_at, updated_at)
        SELECT
            id, channel, user_id,
            COALESCE({src_session_id}, 'default'),
            COALESCE({src_title}, '新对话'),
            messages,
            COALESCE({src_created_at}, datetime('now')),
            COALESCE(updated_at, datetime('now'))
        FROM chat_sessions
    """))

    connection.execute(text("DROP TABLE chat_sessions"))
    connection.execute(text("ALTER TABLE chat_sessions_new RENAME TO chat_sessions"))

    connection.execute(text("CREATE INDEX IF NOT EXISTS ix_chat_sessions_channel ON chat_sessions (channel)"))
    connection.execute(text("CREATE INDEX IF NOT EXISTS ix_chat_sessions_user_id ON chat_sessions (user_id)"))
    connection.execute(text("CREATE INDEX IF NOT EXISTS ix_chat_sessions_session_id ON chat_sessions (session_id)"))

    log.info("chat_sessions 表已重建：唯一约束更新为 (channel, user_id, session_id)")
