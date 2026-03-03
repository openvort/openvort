"""
Alembic migration environment (synchronous).

Uses psycopg2 sync driver so it works both standalone and
when called from within an already-running asyncio event loop.
"""

import os
from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

from openvort.db.engine import Base

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

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name, disable_existing_loggers=False)

target_metadata = Base.metadata


def _get_url() -> str:
    url = os.environ.get("OPENVORT_DATABASE_URL", "")
    if not url:
        url = config.get_main_option("sqlalchemy.url", "")
    # Convert async URL to sync (psycopg2)
    return url.replace("+asyncpg", "")


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode — emit SQL to stdout."""
    url = _get_url()
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode with sync engine."""
    configuration = config.get_section(config.config_ini_section, {})
    configuration["sqlalchemy.url"] = _get_url()
    connectable = engine_from_config(
        configuration,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()
    connectable.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
