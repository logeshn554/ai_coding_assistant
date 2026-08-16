import logging
import os
from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from backend.app.config import settings

logger = logging.getLogger("devpilot.infrastructure.database.connection")

db_url = settings.DATABASE_URL
if db_url.startswith("postgresql://"):
    db_url = db_url.replace("postgresql://", "postgresql+asyncpg://", 1)
elif db_url.startswith("sqlite://") and not db_url.startswith("sqlite+aiosqlite://"):
    db_url = db_url.replace("sqlite://", "sqlite+aiosqlite://", 1)

# Connection pool configuration
POOL_SIZE = int(os.getenv("DATABASE_POOL_SIZE", "20"))
MAX_OVERFLOW = int(os.getenv("DATABASE_MAX_OVERFLOW", "10"))
POOL_TIMEOUT = float(os.getenv("DATABASE_POOL_TIMEOUT", "30.0"))
POOL_RECYCLE = float(os.getenv("DATABASE_POOL_RECYCLE", "1800.0"))

engine_kwargs = {}
if "sqlite" not in db_url.lower():
    engine_kwargs.update({
        "pool_size": POOL_SIZE,
        "max_overflow": MAX_OVERFLOW,
        "pool_timeout": POOL_TIMEOUT,
        "pool_recycle": POOL_RECYCLE,
    })
else:
    engine_kwargs.update({
        "connect_args": {"timeout": 30.0}
    })

logger.info(f"Initializing database engine with URL: {db_url}")
engine = create_async_engine(db_url, echo=False, **engine_kwargs)

from sqlalchemy import event


@event.listens_for(engine.sync_engine, "connect")
def set_sqlite_pragma(dbapi_connection, connection_record):
    if "sqlite" in db_url.lower():
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA synchronous=NORMAL")
        cursor.execute("PRAGMA busy_timeout=30000")
        cursor.close()

async_session_factory = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False
)

async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    """Yield a database session context with automatic rollback."""
    async with async_session_factory() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()

async def check_db_health() -> bool:
    """Execute a simple query to verify connection readiness."""
    try:
        from sqlalchemy import text
        async with async_session_factory() as session:
            await session.execute(text("SELECT 1"))
            return True
    except Exception as e:
        logger.error(f"Database connection check failed: {e}")
        return False
