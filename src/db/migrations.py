"""Migration utilities for programmatic migration running."""

import os
from pathlib import Path

from alembic import command
from alembic.config import Config


def get_alembic_config() -> Config:
    """Get Alembic config pointing to our migration setup."""
    # Path to alembic.ini relative to this file
    ini_path = Path(__file__).parent / "alembic.ini"
    config = Config(str(ini_path))

    # Override sqlalchemy.url with environment variable if set
    database_url = os.getenv("DATABASE_URL")
    if database_url:
        config.set_main_option("sqlalchemy.url", database_url)

    return config


def run_migrations() -> None:
    """Run all pending migrations."""
    config = get_alembic_config()
    command.upgrade(config, "head")


def downgrade_migrations(revision: str = "-1") -> None:
    """Downgrade migrations by the specified amount."""
    config = get_alembic_config()
    command.downgrade(config, revision)


def get_current_revision() -> str | None:
    """Get the current migration revision."""
    config = get_alembic_config()
    from alembic.script import ScriptDirectory
    from alembic.runtime.migration import MigrationContext
    from sqlalchemy import create_engine

    script = ScriptDirectory.from_config(config)
    url = config.get_main_option("sqlalchemy.url")

    connect_args = {}
    if url.startswith("sqlite"):
        connect_args["check_same_thread"] = False

    engine = create_engine(url, connect_args=connect_args)
    with engine.connect() as conn:
        context = MigrationContext.configure(conn)
        return context.get_current_revision()


def create_revision(message: str, autogenerate: bool = True) -> None:
    """Create a new migration revision."""
    config = get_alembic_config()
    command.revision(config, message=message, autogenerate=autogenerate)
