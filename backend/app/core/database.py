from typing import Generator
from sqlalchemy import create_engine, text
from sqlalchemy.orm import declarative_base, sessionmaker, Session
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.compiler import compiles
from app.core.config import settings

@compiles(JSONB, "sqlite")
def _compile_jsonb_sqlite(type_, compiler, **kw):
    return "JSON"

Base = declarative_base()

_engine = None
_session_factory = None


def get_engine():
    global _engine
    if _engine is None:
        db_url = settings.database_url
        if not db_url:
            raise RuntimeError(
                "Database configuration is missing. Please configure DATABASE_URL or POSTGRES_* environment variables."
            )
        engine_kwargs = {
            "pool_pre_ping": settings.DB_POOL_PRE_PING,
        }
        if not db_url.startswith("sqlite"):
            engine_kwargs.update({
                "pool_size": settings.DB_POOL_SIZE,
                "max_overflow": settings.DB_MAX_OVERFLOW,
                "pool_timeout": settings.DB_POOL_TIMEOUT,
                "pool_recycle": settings.DB_POOL_RECYCLE,
            })
        _engine = create_engine(db_url, **engine_kwargs)
    return _engine


def reset_engine():
    """Reset the global engine and session factory (primarily used for test isolation)."""
    global _engine, _session_factory
    if _engine is not None:
        _engine.dispose()
    _engine = None
    _session_factory = None


def get_session_factory():
    global _session_factory
    if _session_factory is None:
        _session_factory = sessionmaker(
            autocommit=False,
            autoflush=False,
            bind=get_engine(),
        )
    return _session_factory


def get_db() -> Generator[Session, None, None]:
    session_maker = get_session_factory()
    db = session_maker()
    try:
        yield db
    finally:
        db.close()


def check_db_connection() -> tuple[bool, str]:
    """
    Test database connectivity safely.
    Guarantees zero leakage of credentials, connection URLs, hostnames, or raw error tracebacks.
    """
    try:
        db_url = settings.database_url
        if not db_url:
            return False, "Database connection failed"
        engine = get_engine()
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
        return True, "Database connection successful"
    except Exception:
        # Never leak credentials, raw error details, or connection strings
        return False, "Database connection failed"
