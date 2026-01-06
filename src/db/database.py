"""Database connection management."""

import os
from contextlib import contextmanager
from typing import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from src.db.models import Base


def get_database_url() -> str:
    """Get database URL from environment or use default SQLite."""
    return os.getenv("DATABASE_URL", "sqlite:///./shipping_agent.db")


def create_db_engine(database_url: str | None = None):
    """Create database engine with appropriate settings."""
    url = database_url or get_database_url()

    # SQLite-specific settings
    if url.startswith("sqlite"):
        return create_engine(
            url,
            connect_args={"check_same_thread": False},
            echo=os.getenv("SQL_ECHO", "").lower() == "true",
        )

    # PostgreSQL settings
    return create_engine(
        url,
        pool_size=5,
        max_overflow=10,
        pool_pre_ping=True,
        echo=os.getenv("SQL_ECHO", "").lower() == "true",
    )


# Default engine and session factory
engine = create_db_engine()
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db() -> Generator[Session, None, None]:
    """FastAPI dependency that yields a database session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@contextmanager
def get_db_session() -> Generator[Session, None, None]:
    """Context manager for database sessions outside of FastAPI."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def create_tables(db_engine=None) -> None:
    """Create all tables (for development/testing only)."""
    target_engine = db_engine or engine
    Base.metadata.create_all(bind=target_engine)


def drop_tables(db_engine=None) -> None:
    """Drop all tables (for testing only)."""
    target_engine = db_engine or engine
    Base.metadata.drop_all(bind=target_engine)


def init_db(database_url: str | None = None) -> tuple:
    """Initialize database with custom URL. Returns (engine, SessionLocal)."""
    db_engine = create_db_engine(database_url)
    session_factory = sessionmaker(autocommit=False, autoflush=False, bind=db_engine)
    return db_engine, session_factory
