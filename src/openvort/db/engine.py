"""
数据库引擎

SQLAlchemy 2.0 异步引擎（PostgreSQL）。
"""

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from openvort.utils.logging import get_logger

log = get_logger("db")


class Base(DeclarativeBase):
    """ORM 基类"""
    pass


_engine = None
_session_factory = None


async def init_db(database_url: str) -> None:
    """Initialize database connection."""
    global _engine, _session_factory

    import openvort.auth.models  # noqa: F401
    import openvort.contacts.models  # noqa: F401
    import openvort.core.setup  # noqa: F401
    import openvort.db.models  # noqa: F401
    try:
        import openvort.services.asr.asr_service  # noqa: F401
    except ImportError:
        pass

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

    _engine = create_async_engine(database_url, echo=False)
    _session_factory = async_sessionmaker(_engine, class_=AsyncSession, expire_on_commit=False)

    # Backward-compatible lightweight migration for VortFlow editable fields.
    async with _engine.begin() as conn:
        await conn.execute(
            text("ALTER TABLE IF EXISTS flow_stories ADD COLUMN IF NOT EXISTS tags_json TEXT DEFAULT '[]'")
        )
        await conn.execute(
            text("ALTER TABLE IF EXISTS flow_stories ADD COLUMN IF NOT EXISTS collaborators_json TEXT DEFAULT '[]'")
        )
        await conn.execute(
            text("ALTER TABLE IF EXISTS flow_tasks ADD COLUMN IF NOT EXISTS tags_json TEXT DEFAULT '[]'")
        )
        await conn.execute(
            text("ALTER TABLE IF EXISTS flow_tasks ADD COLUMN IF NOT EXISTS collaborators_json TEXT DEFAULT '[]'")
        )
        await conn.execute(
            text("ALTER TABLE IF EXISTS flow_bugs ADD COLUMN IF NOT EXISTS tags_json TEXT DEFAULT '[]'")
        )
        await conn.execute(
            text("ALTER TABLE IF EXISTS flow_bugs ADD COLUMN IF NOT EXISTS collaborators_json TEXT DEFAULT '[]'")
        )

        # VortFlow iterations & versions tables
        await conn.execute(text("""
            CREATE TABLE IF NOT EXISTS flow_iterations (
                id VARCHAR(32) PRIMARY KEY,
                project_id VARCHAR(32) REFERENCES flow_projects(id),
                name VARCHAR(200) NOT NULL,
                goal TEXT DEFAULT '',
                start_date TIMESTAMP,
                end_date TIMESTAMP,
                status VARCHAR(32) DEFAULT 'planning',
                created_at TIMESTAMP DEFAULT now(),
                updated_at TIMESTAMP DEFAULT now()
            )
        """))
        await conn.execute(text(
            "CREATE INDEX IF NOT EXISTS ix_flow_iterations_project_id ON flow_iterations(project_id)"
        ))

        await conn.execute(text("""
            CREATE TABLE IF NOT EXISTS flow_versions (
                id VARCHAR(32) PRIMARY KEY,
                project_id VARCHAR(32) REFERENCES flow_projects(id),
                name VARCHAR(64) NOT NULL,
                description TEXT DEFAULT '',
                release_date TIMESTAMP,
                status VARCHAR(32) DEFAULT 'planning',
                created_at TIMESTAMP DEFAULT now(),
                updated_at TIMESTAMP DEFAULT now()
            )
        """))
        await conn.execute(text(
            "CREATE INDEX IF NOT EXISTS ix_flow_versions_project_id ON flow_versions(project_id)"
        ))

        await conn.execute(text("""
            CREATE TABLE IF NOT EXISTS flow_version_stories (
                id VARCHAR(32) PRIMARY KEY,
                version_id VARCHAR(32) REFERENCES flow_versions(id),
                story_id VARCHAR(32) REFERENCES flow_stories(id),
                added_reason TEXT DEFAULT '',
                story_order INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT now(),
                CONSTRAINT uq_version_story UNIQUE (version_id, story_id)
            )
        """))
        await conn.execute(text(
            "CREATE INDEX IF NOT EXISTS ix_flow_version_stories_version_id ON flow_version_stories(version_id)"
        ))
        await conn.execute(text(
            "CREATE INDEX IF NOT EXISTS ix_flow_version_stories_story_id ON flow_version_stories(story_id)"
        ))

        await conn.execute(text("""
            CREATE TABLE IF NOT EXISTS flow_iteration_stories (
                id VARCHAR(32) PRIMARY KEY,
                iteration_id VARCHAR(32) REFERENCES flow_iterations(id),
                story_id VARCHAR(32) REFERENCES flow_stories(id),
                story_order INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT now(),
                CONSTRAINT uq_iteration_story UNIQUE (iteration_id, story_id)
            )
        """))
        await conn.execute(text(
            "CREATE INDEX IF NOT EXISTS ix_flow_iteration_stories_iteration_id ON flow_iteration_stories(iteration_id)"
        ))
        await conn.execute(text(
            "CREATE INDEX IF NOT EXISTS ix_flow_iteration_stories_story_id ON flow_iteration_stories(story_id)"
        ))

        await conn.execute(text("""
            CREATE TABLE IF NOT EXISTS flow_iteration_tasks (
                id VARCHAR(32) PRIMARY KEY,
                iteration_id VARCHAR(32) REFERENCES flow_iterations(id),
                task_id VARCHAR(32) REFERENCES flow_tasks(id),
                task_order INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT now(),
                CONSTRAINT uq_iteration_task UNIQUE (iteration_id, task_id)
            )
        """))
        await conn.execute(text(
            "CREATE INDEX IF NOT EXISTS ix_flow_iteration_tasks_iteration_id ON flow_iteration_tasks(iteration_id)"
        ))
        await conn.execute(text(
            "CREATE INDEX IF NOT EXISTS ix_flow_iteration_tasks_task_id ON flow_iteration_tasks(task_id)"
        ))

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
