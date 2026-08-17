"""
Global pytest configuration and session-level fixtures.

Runs a safe schema migration against the test database before any test
so that newly added columns (workspace_root, profile_name, etc.) are
always present, even if the on-disk SQLite file predates the model change.
"""
from __future__ import annotations

import asyncio
import logging

import pytest

logger = logging.getLogger("loopix.tests.conftest")


def _run_schema_migration():
    """
    Apply safe ALTER TABLE migrations against the SQLite test DB.
    Idempotent — skips columns that already exist.
    """
    import os
    from backend.app.config import settings

    db_url = settings.DATABASE_URL
    if not db_url.startswith("sqlite"):
        # Only needed for SQLite; PostgreSQL uses proper Alembic
        return

    # Extract path from sqlite:///path or sqlite+aiosqlite:///path
    db_path = db_url.split("///", 1)[-1]
    if not os.path.isfile(db_path):
        return  # Fresh DB — models.create_all will handle it

    try:
        import sqlite3
        con = sqlite3.connect(db_path)
        cur = con.cursor()
        cur.execute("PRAGMA table_info(agent_runs)")
        existing_cols = {row[1] for row in cur.fetchall()}

        new_cols = [
            ("workspace_root", "VARCHAR(1024)"),
            ("profile_name", "VARCHAR(255)"),
        ]
        for col_name, col_type in new_cols:
            if col_name not in existing_cols:
                cur.execute(f"ALTER TABLE agent_runs ADD COLUMN {col_name} {col_type}")
                logger.info(f"conftest: added column agent_runs.{col_name}")

        con.commit()
        con.close()
    except Exception as exc:
        logger.warning(f"conftest schema migration warning: {exc}")


# Run once at import time — before any test collection
_run_schema_migration()
def pytest_sessionstart(session):
    import os
    import asyncio
    from backend.app.infrastructure.database.models import Base
    from backend.app.infrastructure.database.connection import engine
    
    for db_f in ("loopix.db", "loopix.db"):
        if os.path.exists(db_f):
            try:
                os.remove(db_f)
            except Exception:
                pass
        
    async def init_tables():
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
            
    asyncio.run(init_tables())
