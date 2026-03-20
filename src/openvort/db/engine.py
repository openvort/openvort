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

    async with _engine.begin() as conn:
        tables = Base.metadata.sorted_tables
        if not _pgvector_available:
            tables = [t for t in tables if t.name != "kb_chunks"]
        await conn.run_sync(Base.metadata.create_all, tables=tables)

    # Remote work nodes (renamed from openclaw_nodes)
    async with _engine.begin() as conn:
        # Migrate: rename openclaw_nodes -> remote_nodes if old table exists
        await conn.execute(text("""
            DO $$
            BEGIN
                IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'openclaw_nodes')
                   AND NOT EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'remote_nodes')
                THEN
                    ALTER TABLE openclaw_nodes RENAME TO remote_nodes;
                    ALTER INDEX IF EXISTS ix_openclaw_nodes_name RENAME TO ix_remote_nodes_name;
                END IF;
            END $$
        """))

        await conn.execute(text("""
            CREATE TABLE IF NOT EXISTS remote_nodes (
                id VARCHAR(32) PRIMARY KEY,
                name VARCHAR(64) NOT NULL,
                node_type VARCHAR(32) DEFAULT 'openclaw',
                description TEXT DEFAULT '',
                gateway_url VARCHAR(512) NOT NULL,
                gateway_token TEXT DEFAULT '',
                config TEXT DEFAULT '{}',
                status VARCHAR(16) DEFAULT 'unknown',
                machine_info TEXT DEFAULT '{}',
                last_heartbeat_at TIMESTAMP,
                created_at TIMESTAMP DEFAULT now(),
                updated_at TIMESTAMP DEFAULT now()
            )
        """))
        await conn.execute(text(
            "CREATE INDEX IF NOT EXISTS ix_remote_nodes_name ON remote_nodes(name)"
        ))

        # Migrate: add node_type / config columns for existing tables
        await conn.execute(text(
            "ALTER TABLE IF EXISTS remote_nodes ADD COLUMN IF NOT EXISTS node_type VARCHAR(32) DEFAULT 'openclaw'"
        ))
        await conn.execute(text(
            "ALTER TABLE IF EXISTS remote_nodes ADD COLUMN IF NOT EXISTS config TEXT DEFAULT '{}'"
        ))

        # Legacy migration: rename hook_token -> gateway_token
        await conn.execute(text("""
            DO $$
            BEGIN
                IF EXISTS (
                    SELECT 1 FROM information_schema.columns
                    WHERE table_name = 'remote_nodes' AND column_name = 'hook_token'
                ) THEN
                    ALTER TABLE remote_nodes RENAME COLUMN hook_token TO gateway_token;
                END IF;
            END $$
        """))

        # Migrate: rename members.openclaw_node_id -> remote_node_id
        await conn.execute(
            text("ALTER TABLE IF EXISTS members ADD COLUMN IF NOT EXISTS remote_node_id VARCHAR(32) DEFAULT ''")
        )
        await conn.execute(text("""
            DO $$
            BEGIN
                IF EXISTS (
                    SELECT 1 FROM information_schema.columns
                    WHERE table_name = 'members' AND column_name = 'openclaw_node_id'
                ) THEN
                    UPDATE members SET remote_node_id = openclaw_node_id
                        WHERE openclaw_node_id IS NOT NULL AND openclaw_node_id != ''
                              AND (remote_node_id IS NULL OR remote_node_id = '');
                    ALTER TABLE members DROP COLUMN openclaw_node_id;
                END IF;
            END $$
        """))

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
        await conn.execute(text("""
            DO $$ BEGIN
                IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'flow_stories') THEN
                    CREATE INDEX IF NOT EXISTS ix_flow_stories_parent_id ON flow_stories(parent_id);
                END IF;
            END $$
        """))
        await conn.execute(
            text("ALTER TABLE IF EXISTS flow_tasks ADD COLUMN IF NOT EXISTS tags_json TEXT DEFAULT '[]'")
        )
        await conn.execute(
            text("ALTER TABLE IF EXISTS flow_tasks ADD COLUMN IF NOT EXISTS collaborators_json TEXT DEFAULT '[]'")
        )
        await conn.execute(
            text("ALTER TABLE IF EXISTS flow_tasks ADD COLUMN IF NOT EXISTS parent_id VARCHAR(32) REFERENCES flow_tasks(id)")
        )
        await conn.execute(text("""
            DO $$ BEGIN
                IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'flow_tasks') THEN
                    CREATE INDEX IF NOT EXISTS ix_flow_tasks_parent_id ON flow_tasks(parent_id);
                END IF;
            END $$
        """))
        await conn.execute(
            text("ALTER TABLE IF EXISTS flow_tasks ADD COLUMN IF NOT EXISTS creator_id VARCHAR(32)")
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

        # VortFlow custom views & column settings
        await conn.execute(text("""
            CREATE TABLE IF NOT EXISTS flow_views (
                id VARCHAR(32) PRIMARY KEY,
                name VARCHAR(100) NOT NULL,
                work_item_type VARCHAR(16) NOT NULL,
                scope VARCHAR(16) DEFAULT 'personal',
                owner_id VARCHAR(32),
                filters_json TEXT DEFAULT '{}',
                columns_json TEXT DEFAULT '[]',
                view_order INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT now(),
                updated_at TIMESTAMP DEFAULT now()
            )
        """))
        await conn.execute(text(
            "CREATE INDEX IF NOT EXISTS ix_flow_views_owner_id ON flow_views(owner_id)"
        ))
        await conn.execute(text(
            "CREATE INDEX IF NOT EXISTS ix_flow_views_work_item_type ON flow_views(work_item_type)"
        ))

        await conn.execute(text("""
            CREATE TABLE IF NOT EXISTS flow_column_settings (
                id VARCHAR(32) PRIMARY KEY,
                member_id VARCHAR(32) NOT NULL,
                work_item_type VARCHAR(16) NOT NULL,
                columns_json TEXT DEFAULT '[]',
                updated_at TIMESTAMP DEFAULT now(),
                CONSTRAINT uq_column_setting UNIQUE (member_id, work_item_type)
            )
        """))
        await conn.execute(text(
            "CREATE INDEX IF NOT EXISTS ix_flow_column_settings_member_id ON flow_column_settings(member_id)"
        ))

    # VortFlow: new columns for stories/tasks/bugs + comments table
    async with _engine.begin() as conn:
        for tbl in ("flow_stories", "flow_tasks", "flow_bugs"):
            await conn.execute(text(f"ALTER TABLE IF EXISTS {tbl} ADD COLUMN IF NOT EXISTS start_at TIMESTAMP"))
            await conn.execute(text(f"ALTER TABLE IF EXISTS {tbl} ADD COLUMN IF NOT EXISTS end_at TIMESTAMP"))
            await conn.execute(text(f"ALTER TABLE IF EXISTS {tbl} ADD COLUMN IF NOT EXISTS repo_id VARCHAR(32)"))
            await conn.execute(text(f"ALTER TABLE IF EXISTS {tbl} ADD COLUMN IF NOT EXISTS branch VARCHAR(200) DEFAULT ''"))
        await conn.execute(text(
            "ALTER TABLE IF EXISTS flow_bugs ADD COLUMN IF NOT EXISTS estimate_hours FLOAT"
        ))
        await conn.execute(text(
            "ALTER TABLE IF EXISTS flow_bugs ADD COLUMN IF NOT EXISTS actual_hours FLOAT"
        ))
        await conn.execute(text(
            "ALTER TABLE IF EXISTS flow_bugs ADD COLUMN IF NOT EXISTS deadline TIMESTAMP"
        ))

        await conn.execute(text("""
            CREATE TABLE IF NOT EXISTS flow_comments (
                id BIGSERIAL PRIMARY KEY,
                entity_type VARCHAR(32) NOT NULL,
                entity_id VARCHAR(32) NOT NULL,
                author_id VARCHAR(32) NOT NULL,
                content TEXT DEFAULT '',
                mentions_json TEXT DEFAULT '[]',
                created_at TIMESTAMP DEFAULT now(),
                updated_at TIMESTAMP DEFAULT now()
            )
        """))
        await conn.execute(text(
            "CREATE INDEX IF NOT EXISTS ix_flow_comments_entity ON flow_comments(entity_type, entity_id)"
        ))
        await conn.execute(text(
            "CREATE INDEX IF NOT EXISTS ix_flow_comments_author ON flow_comments(author_id)"
        ))

    # VortFlow: tag definitions table
    async with _engine.begin() as conn:
        await conn.execute(text("""
            CREATE TABLE IF NOT EXISTS flow_tags (
                id VARCHAR(32) PRIMARY KEY,
                name VARCHAR(100) NOT NULL UNIQUE,
                color VARCHAR(20) DEFAULT '#3b82f6',
                sort_order INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT now(),
                updated_at TIMESTAMP DEFAULT now()
            )
        """))

    # VortFlow: work item links table (generic many-to-many between story/task/bug)
    async with _engine.begin() as conn:
        await conn.execute(text("""
            CREATE TABLE IF NOT EXISTS flow_work_item_links (
                id VARCHAR(32) PRIMARY KEY,
                source_type VARCHAR(16) NOT NULL,
                source_id VARCHAR(32) NOT NULL,
                target_type VARCHAR(16) NOT NULL,
                target_id VARCHAR(32) NOT NULL,
                created_by VARCHAR(32),
                created_at TIMESTAMP DEFAULT now(),
                CONSTRAINT uq_work_item_link UNIQUE (source_type, source_id, target_type, target_id)
            )
        """))
        await conn.execute(text(
            "CREATE INDEX IF NOT EXISTS ix_flow_wil_source ON flow_work_item_links(source_type, source_id)"
        ))
        await conn.execute(text(
            "CREATE INDEX IF NOT EXISTS ix_flow_wil_target ON flow_work_item_links(target_type, target_id)"
        ))

    # VortFlow: status definitions table
    async with _engine.begin() as conn:
        await conn.execute(text("""
            CREATE TABLE IF NOT EXISTS flow_statuses (
                id VARCHAR(32) PRIMARY KEY,
                name VARCHAR(100) NOT NULL UNIQUE,
                icon VARCHAR(10) DEFAULT '○',
                icon_color VARCHAR(20) DEFAULT '#3b82f6',
                command VARCHAR(200) DEFAULT '',
                work_item_types_json TEXT DEFAULT '[]',
                sort_order INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT now(),
                updated_at TIMESTAMP DEFAULT now()
            )
        """))

    # VortFlow: test case module / test case / test case - work item link
    async with _engine.begin() as conn:
        await conn.execute(text("""
            CREATE TABLE IF NOT EXISTS flow_test_modules (
                id VARCHAR(32) PRIMARY KEY,
                project_id VARCHAR(32) REFERENCES flow_projects(id),
                parent_id VARCHAR(32) REFERENCES flow_test_modules(id),
                name VARCHAR(200) NOT NULL,
                sort_order INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT now(),
                updated_at TIMESTAMP DEFAULT now()
            )
        """))
        await conn.execute(text(
            "CREATE INDEX IF NOT EXISTS ix_flow_test_modules_project_id ON flow_test_modules(project_id)"
        ))
        await conn.execute(text(
            "CREATE INDEX IF NOT EXISTS ix_flow_test_modules_parent_id ON flow_test_modules(parent_id)"
        ))

        await conn.execute(text("""
            CREATE TABLE IF NOT EXISTS flow_test_cases (
                id VARCHAR(32) PRIMARY KEY,
                project_id VARCHAR(32) REFERENCES flow_projects(id),
                module_id VARCHAR(32) REFERENCES flow_test_modules(id),
                title VARCHAR(500) NOT NULL,
                precondition TEXT DEFAULT '',
                notes TEXT DEFAULT '',
                case_type VARCHAR(32) DEFAULT 'functional',
                priority INTEGER DEFAULT 2,
                maintainer_id VARCHAR(32),
                review_result VARCHAR(32) DEFAULT 'pending',
                steps_json TEXT DEFAULT '[]',
                created_at TIMESTAMP DEFAULT now(),
                updated_at TIMESTAMP DEFAULT now()
            )
        """))
        await conn.execute(text(
            "CREATE INDEX IF NOT EXISTS ix_flow_test_cases_project_id ON flow_test_cases(project_id)"
        ))
        await conn.execute(text(
            "CREATE INDEX IF NOT EXISTS ix_flow_test_cases_module_id ON flow_test_cases(module_id)"
        ))

        await conn.execute(text("""
            CREATE TABLE IF NOT EXISTS flow_test_case_work_items (
                id VARCHAR(32) PRIMARY KEY,
                test_case_id VARCHAR(32) REFERENCES flow_test_cases(id),
                entity_type VARCHAR(16) NOT NULL,
                entity_id VARCHAR(32) NOT NULL,
                created_by VARCHAR(32),
                created_at TIMESTAMP DEFAULT now(),
                CONSTRAINT uq_testcase_workitem UNIQUE (test_case_id, entity_type, entity_id)
            )
        """))
        await conn.execute(text(
            "CREATE INDEX IF NOT EXISTS ix_flow_tcwi_test_case_id ON flow_test_case_work_items(test_case_id)"
        ))
        await conn.execute(text(
            "CREATE INDEX IF NOT EXISTS ix_flow_tcwi_entity ON flow_test_case_work_items(entity_type, entity_id)"
        ))

    # Group chat table (group-project binding)
    async with _engine.begin() as conn:
        await conn.execute(text("""
            CREATE TABLE IF NOT EXISTS group_chats (
                id VARCHAR(32) PRIMARY KEY,
                chat_id VARCHAR(128) NOT NULL UNIQUE,
                platform VARCHAR(16) NOT NULL,
                name VARCHAR(200) DEFAULT '',
                project_id VARCHAR(32),
                bound_by VARCHAR(32),
                bound_at TIMESTAMP,
                created_at TIMESTAMP DEFAULT now(),
                updated_at TIMESTAMP DEFAULT now()
            )
        """))
        await conn.execute(text(
            "CREATE INDEX IF NOT EXISTS ix_group_chats_chat_id ON group_chats(chat_id)"
        ))
        await conn.execute(text(
            "CREATE INDEX IF NOT EXISTS ix_group_chats_platform ON group_chats(platform)"
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

    # IM inbox dedup + consume cursors
    async with _engine.begin() as conn:
        await conn.execute(text("""
            CREATE TABLE IF NOT EXISTS im_inbox (
                id SERIAL PRIMARY KEY,
                channel VARCHAR(32) NOT NULL,
                msg_id VARCHAR(256) NOT NULL,
                status VARCHAR(16) NOT NULL DEFAULT 'claimed',
                error TEXT NOT NULL DEFAULT '',
                created_at TIMESTAMP NOT NULL DEFAULT NOW(),
                CONSTRAINT uq_im_inbox_channel_msg_id UNIQUE (channel, msg_id)
            )
        """))
        await conn.execute(text(
            "CREATE INDEX IF NOT EXISTS ix_im_inbox_created_at ON im_inbox(created_at)"
        ))
        await conn.execute(text("""
            CREATE TABLE IF NOT EXISTS im_cursors (
                key VARCHAR(64) PRIMARY KEY,
                value BIGINT NOT NULL DEFAULT 0,
                updated_at TIMESTAMP NOT NULL DEFAULT NOW()
            )
        """))

    # Member plugin settings (per-user plugin config like API keys)
    async with _engine.begin() as conn:
        await conn.execute(text("""
            CREATE TABLE IF NOT EXISTS member_plugin_settings (
                id SERIAL PRIMARY KEY,
                member_id VARCHAR(32) NOT NULL REFERENCES members(id),
                plugin_name VARCHAR(64) NOT NULL,
                settings_data TEXT DEFAULT '{}',
                created_at TIMESTAMP DEFAULT now(),
                updated_at TIMESTAMP DEFAULT now(),
                CONSTRAINT uq_member_plugin_setting UNIQUE (member_id, plugin_name)
            )
        """))
        await conn.execute(text(
            "CREATE INDEX IF NOT EXISTS ix_member_plugin_settings_member_id ON member_plugin_settings(member_id)"
        ))
        await conn.execute(text(
            "CREATE INDEX IF NOT EXISTS ix_member_plugin_settings_plugin_name ON member_plugin_settings(plugin_name)"
        ))

    # Marketplace display name for installed skills
    async with _engine.begin() as conn:
        await conn.execute(text(
            "ALTER TABLE IF EXISTS skills ADD COLUMN IF NOT EXISTS marketplace_display_name VARCHAR(200) DEFAULT ''"
        ))

    # Migrate schedule_jobs: add creator_id + fix owner semantics
    async with _engine.begin() as conn:
        await conn.execute(text(
            "ALTER TABLE IF EXISTS schedule_jobs ADD COLUMN IF NOT EXISTS creator_id VARCHAR(32) DEFAULT ''"
        ))
        await conn.execute(text(
            "CREATE INDEX IF NOT EXISTS ix_schedule_jobs_creator_id ON schedule_jobs(creator_id)"
        ))
        # One-time data migration: for rows where target_member_id is set (AI employee),
        # move owner_id -> creator_id, target_member_id -> owner_id, reset visible
        await conn.execute(text("""
            UPDATE schedule_jobs
            SET creator_id = owner_id,
                owner_id = target_member_id,
                visible = true
            WHERE target_member_id IS NOT NULL
              AND target_member_id != ''
              AND (creator_id IS NULL OR creator_id = '')
        """))

    # --- Messaging & notification system tables ---
    async with _engine.begin() as conn:
        # chat_messages: persistent message records for UI, unread tracking, search
        await conn.execute(text("""
            CREATE TABLE IF NOT EXISTS chat_messages (
                id BIGSERIAL PRIMARY KEY,
                session_id VARCHAR(64) NOT NULL,
                owner_id VARCHAR(32) NOT NULL,
                sender_type VARCHAR(16) NOT NULL,
                sender_id VARCHAR(32) DEFAULT '',
                content TEXT DEFAULT '',
                metadata_json TEXT DEFAULT '{}',
                source VARCHAR(16) DEFAULT 'chat',
                is_read BOOLEAN DEFAULT FALSE,
                created_at TIMESTAMP DEFAULT now()
            )
        """))
        await conn.execute(text(
            "CREATE INDEX IF NOT EXISTS ix_chat_messages_session ON chat_messages(session_id, created_at)"
        ))
        await conn.execute(text(
            "CREATE INDEX IF NOT EXISTS ix_chat_messages_owner_unread ON chat_messages(owner_id, is_read) WHERE NOT is_read"
        ))

        # notifications: delayed IM delivery tracking
        await conn.execute(text("""
            CREATE TABLE IF NOT EXISTS notifications (
                id BIGSERIAL PRIMARY KEY,
                recipient_id VARCHAR(32) NOT NULL,
                source VARCHAR(32) NOT NULL,
                source_id VARCHAR(64) DEFAULT '',
                session_id VARCHAR(64) DEFAULT '',
                title VARCHAR(200) NOT NULL,
                summary TEXT DEFAULT '',
                status VARCHAR(16) DEFAULT 'pending',
                im_sent_at TIMESTAMP,
                im_channel VARCHAR(32) DEFAULT '',
                read_at TIMESTAMP,
                created_at TIMESTAMP DEFAULT now()
            )
        """))
        await conn.execute(text(
            "CREATE INDEX IF NOT EXISTS ix_notifications_recipient ON notifications(recipient_id, status)"
        ))

        # agent_tasks: async task execution tracking
        await conn.execute(text("""
            CREATE TABLE IF NOT EXISTS agent_tasks (
                id VARCHAR(64) PRIMARY KEY,
                session_id VARCHAR(64) NOT NULL,
                owner_id VARCHAR(32) NOT NULL,
                executor_id VARCHAR(32) DEFAULT '',
                source VARCHAR(16) DEFAULT 'chat',
                source_id VARCHAR(64) DEFAULT '',
                status VARCHAR(16) DEFAULT 'pending',
                description TEXT DEFAULT '',
                progress TEXT DEFAULT '',
                result_summary TEXT DEFAULT '',
                cancel_requested BOOLEAN DEFAULT FALSE,
                created_at TIMESTAMP DEFAULT now(),
                started_at TIMESTAMP,
                completed_at TIMESTAMP
            )
        """))
        await conn.execute(text(
            "CREATE INDEX IF NOT EXISTS ix_agent_tasks_owner ON agent_tasks(owner_id, status)"
        ))
        await conn.execute(text(
            "CREATE INDEX IF NOT EXISTS ix_agent_tasks_executor ON agent_tasks(executor_id, status)"
        ))

        # chat_sessions: add unread_count column
        await conn.execute(text(
            "ALTER TABLE IF EXISTS chat_sessions ADD COLUMN IF NOT EXISTS unread_count INTEGER DEFAULT 0"
        ))

        # chat_sessions: context reset support (archived_messages + context_reset_at)
        await conn.execute(text(
            "ALTER TABLE IF EXISTS chat_sessions ADD COLUMN IF NOT EXISTS archived_messages TEXT"
        ))
        await conn.execute(text(
            "ALTER TABLE IF EXISTS chat_sessions ADD COLUMN IF NOT EXISTS context_reset_at TIMESTAMP"
        ))

    # VortFlow: add project_id to flow_tasks & flow_bugs (direct project association)
    async with _engine.begin() as conn:
        for tbl in ("flow_tasks", "flow_bugs"):
            await conn.execute(text(
                f"ALTER TABLE IF EXISTS {tbl} ADD COLUMN IF NOT EXISTS project_id VARCHAR(32) REFERENCES flow_projects(id)"
            ))
            await conn.execute(text(
                f"CREATE INDEX IF NOT EXISTS ix_{tbl}_project_id ON {tbl}(project_id)"
            ))
        await conn.execute(text("""
            UPDATE flow_tasks
            SET project_id = s.project_id
            FROM flow_stories s
            WHERE flow_tasks.story_id = s.id
              AND flow_tasks.project_id IS NULL
              AND s.project_id IS NOT NULL
        """))
        await conn.execute(text("""
            UPDATE flow_bugs
            SET project_id = s.project_id
            FROM flow_stories s
            WHERE flow_bugs.story_id = s.id
              AND flow_bugs.project_id IS NULL
              AND s.project_id IS NOT NULL
        """))

    # Report module: template description + rule workdays_only
    async with _engine.begin() as conn:
        await conn.execute(text(
            "ALTER TABLE IF EXISTS report_templates ADD COLUMN IF NOT EXISTS description VARCHAR(512) DEFAULT ''"
        ))
        await conn.execute(text(
            "ALTER TABLE IF EXISTS report_rules ADD COLUMN IF NOT EXISTS workdays_only BOOLEAN DEFAULT TRUE"
        ))

    # Notifications: add data_json for structured notification payload
    async with _engine.begin() as conn:
        await conn.execute(text(
            "ALTER TABLE IF EXISTS notifications ADD COLUMN IF NOT EXISTS data_json TEXT DEFAULT '{}'"
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
