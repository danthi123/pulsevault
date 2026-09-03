"""Database engine, session factory, and declarative base."""
from __future__ import annotations

from collections.abc import Iterator

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from .config import settings

engine = create_engine(settings.database_url, pool_pre_ping=True, future=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


def get_session() -> Iterator[Session]:
    """FastAPI dependency yielding a scoped DB session."""
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


def init_db() -> None:
    """Create tables if they do not exist.

    v1 uses create_all for a zero-friction single-user deploy. When the schema
    starts evolving in production, introduce Alembic (models already live in
    app.models, so autogenerate will work) and replace this call.
    """
    from . import models  # noqa: F401  (register mappers)

    Base.metadata.create_all(bind=engine)
