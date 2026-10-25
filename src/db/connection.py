import re
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


def sqlite_word_match(haystack: str | None, needle: str | None) -> int:
    """Check if unaccented needle matches as whole words within unaccented haystack.

    Returns 1 if matched, 0 otherwise. Safe against regex injection via re.escape.
    """
    if not haystack or not needle:
        return 0
    h_clean = remove_accents(haystack).strip()
    n_clean = remove_accents(needle).strip()
    if not h_clean or not n_clean:
        return 0
    # Match as full word boundaries (\bneedle\b)
    pattern = rf"\b{re.escape(n_clean)}\b"
    return 1 if re.search(pattern, h_clean) else 0


@asynccontextmanager
async def get_db_connection(db_path: str) -> AsyncIterator[aiosqlite.Connection]:
    """Provide async SQLite connection with WAL mode, busy timeout, foreign keys, and custom functions."""
    db = await aiosqlite.connect(db_path)
    db.row_factory = aiosqlite.Row
    await db.execute("PRAGMA journal_mode = WAL;")
    await db.execute("PRAGMA busy_timeout = 5000;")
    await db.execute("PRAGMA foreign_keys = ON;")
    await db.create_function("unaccent", 1, remove_accents)
    await db.create_function("word_match", 2, sqlite_word_match)
    try:
        yield db
    finally:
        await db.close()
