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
        import openvort.plugins.knowledge.models  # noqa: F401
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

    # Enable pgvector extension for knowledge base (optional — skip if not installed on server)
    _pgvector_available = False
    try:
        async with _engine.begin() as conn:
            await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        _pgvector_available = True
    except Exception as e:
        log.warning(f"pgvector 扩展不可用，知识库向量检索功能将不可用: {e}")

    # Backward-compatible lightweight migration for VortFlow editable fields.
    async with _engine.begin() as conn:
        await conn.execute(
            text("ALTER TABLE IF EXISTS flow_stories ADD COLUMN IF NOT EXISTS tags_json TEXT DEFAULT '[]'")
        )
        await conn.execute(
            text("ALTER TABLE IF EXISTS flow_stories ADD COLUMN IF NOT EXISTS collaborators_json TEXT DEFAULT '[]'")
        )
        await conn.execute(
            text("ALTER TABLE IF EXISTS flow_stories ADD COLUMN IF NOT EXISTS parent_id VARCHAR(32) REFERENCES flow_stories(id)")
        )
        await conn.execute(
            text("CREATE INDEX IF NOT EXISTS ix_flow_stories_parent_id ON flow_stories(parent_id)")
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
                owner_id VARCHAR(32),
                start_date TIMESTAMP,
                end_date TIMESTAMP,
                status VARCHAR(32) DEFAULT 'planning',
                estimate_hours DOUBLE PRECISION,
                created_at TIMESTAMP DEFAULT now(),
                updated_at TIMESTAMP DEFAULT now()
            )
        """))
        await conn.execute(text(
            "CREATE INDEX IF NOT EXISTS ix_flow_iterations_project_id ON flow_iterations(project_id)"
        ))
        await conn.execute(text(
            "ALTER TABLE IF EXISTS flow_iterations ADD COLUMN IF NOT EXISTS owner_id VARCHAR(32)"
        ))
        await conn.execute(text(
            "ALTER TABLE IF EXISTS flow_iterations ADD COLUMN IF NOT EXISTS estimate_hours DOUBLE PRECISION"
        ))
        await conn.execute(text(
            "CREATE INDEX IF NOT EXISTS ix_flow_iterations_owner_id ON flow_iterations(owner_id)"
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
        await conn.execute(text(
            "ALTER TABLE IF EXISTS flow_versions ADD COLUMN IF NOT EXISTS owner_id VARCHAR(32)"
        ))
        await conn.execute(text(
            "ALTER TABLE IF EXISTS flow_versions ADD COLUMN IF NOT EXISTS planned_release_at TIMESTAMP"
        ))
        await conn.execute(text(
            "ALTER TABLE IF EXISTS flow_versions ADD COLUMN IF NOT EXISTS actual_release_at TIMESTAMP"
        ))
        await conn.execute(text(
            "ALTER TABLE IF EXISTS flow_versions ADD COLUMN IF NOT EXISTS progress INTEGER DEFAULT 0"
        ))
        await conn.execute(text(
            "CREATE INDEX IF NOT EXISTS ix_flow_versions_owner_id ON flow_versions(owner_id)"
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

    # Knowledge base tables (requires pgvector for kb_chunks.embedding column)
    try:
        async with _engine.begin() as conn:
            await conn.execute(text("""
                CREATE TABLE IF NOT EXISTS kb_documents (
                    id VARCHAR(32) PRIMARY KEY,
                    title VARCHAR(200) NOT NULL,
                    file_name VARCHAR(500) DEFAULT '',
                    file_type VARCHAR(20) NOT NULL,
                    file_size INTEGER DEFAULT 0,
                    content TEXT DEFAULT '',
                    status VARCHAR(20) DEFAULT 'pending',
                    error_message TEXT DEFAULT '',
                    chunk_count INTEGER DEFAULT 0,
                    owner_id VARCHAR(32) DEFAULT '',
                    created_at TIMESTAMP DEFAULT now(),
                    updated_at TIMESTAMP DEFAULT now()
                )
            """))
            await conn.execute(text(
                "CREATE INDEX IF NOT EXISTS ix_kb_documents_status ON kb_documents(status)"
            ))
            await conn.execute(text(
                "CREATE INDEX IF NOT EXISTS ix_kb_documents_file_type ON kb_documents(file_type)"
            ))

            if _pgvector_available:
                await conn.execute(text("""
                    CREATE TABLE IF NOT EXISTS kb_chunks (
                        id VARCHAR(32) PRIMARY KEY,
                        document_id VARCHAR(32) REFERENCES kb_documents(id),
                        chunk_index INTEGER DEFAULT 0,
                        content TEXT DEFAULT '',
                        embedding vector(1024),
                        token_count INTEGER DEFAULT 0,
                        metadata_json TEXT DEFAULT '{}',
                        created_at TIMESTAMP DEFAULT now()
                    )
                """))
                await conn.execute(text(
                    "CREATE INDEX IF NOT EXISTS ix_kb_chunks_document_id ON kb_chunks(document_id)"
                ))
            else:
                log.warning("跳过 kb_chunks 表创建（需要 pgvector 扩展）")
    except Exception as e:
        log.warning(f"知识库表创建失败: {e}")

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
