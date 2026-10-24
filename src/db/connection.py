import unicodedata
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import aiosqlite


def remove_accents(input_str: str | None) -> str:
    """Normalize Vietnamese text to lowercase unaccented ASCII string."""
    if not input_str:
        return ""
    nfkd = unicodedata.normalize("NFKD", input_str)
    cleaned = "".join([c for c in nfkd if not unicodedata.combining(c)])
    return cleaned.replace("đ", "d").replace("Đ", "D").lower()


@asynccontextmanager
async def get_db_connection(db_path: str) -> AsyncIterator[aiosqlite.Connection]:
    """Provide async SQLite connection with WAL mode, busy timeout, foreign keys, and custom functions."""
    db = await aiosqlite.connect(db_path)
    db.row_factory = aiosqlite.Row
    await db.execute("PRAGMA journal_mode = WAL;")
    await db.execute("PRAGMA busy_timeout = 5000;")
    await db.execute("PRAGMA foreign_keys = ON;")
    await db.create_function("unaccent", 1, remove_accents)
    try:
        yield db
    finally:
        await db.close()
