from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import aiosqlite


@asynccontextmanager
async def get_db_connection(db_path: str) -> AsyncIterator[aiosqlite.Connection]:
    """Provide async SQLite connection with WAL mode, busy timeout, and foreign keys."""
    db = await aiosqlite.connect(db_path)
    db.row_factory = aiosqlite.Row
    await db.execute("PRAGMA journal_mode = WAL;")
    await db.execute("PRAGMA busy_timeout = 5000;")
    await db.execute("PRAGMA foreign_keys = ON;")
    try:
        yield db
    finally:
        await db.close()
