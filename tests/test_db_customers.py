import aiosqlite
import pytest

from src.db.connection import get_db_connection


@pytest.mark.asyncio
async def test_connection_pragmas_and_row_factory(tmp_path):
    """Test WAL mode, busy_timeout=5000, foreign_keys=ON, and row_factory."""
    db_file = str(tmp_path / "test.db")
    async with get_db_connection(db_file) as db:
        # Check row_factory
        assert db.row_factory == aiosqlite.Row

        # Check WAL pragma
        async with db.execute("PRAGMA journal_mode;") as cursor:
            row = await cursor.fetchone()
            assert row[0].upper() == "WAL"

        # Check busy_timeout pragma
        async with db.execute("PRAGMA busy_timeout;") as cursor:
            row = await cursor.fetchone()
            assert int(row[0]) == 5000

        # Check foreign_keys pragma
        async with db.execute("PRAGMA foreign_keys;") as cursor:
            row = await cursor.fetchone()
            assert int(row[0]) == 1


@pytest.mark.asyncio
async def test_connection_closes_after_context_manager(tmp_path):
    """Test connection closes properly after async context manager exits."""
    db_file = str(tmp_path / "test_close.db")
    async with get_db_connection(db_file) as db:
        conn = db
        async with conn.execute("SELECT 1;") as cursor:
            res = await cursor.fetchone()
            assert res[0] == 1

    # Attempting to execute on closed connection must fail
    with pytest.raises(Exception):
        await conn.execute("SELECT 1;")


@pytest.mark.asyncio
async def test_init_db_creates_customers_schema(test_db):
    """Test init_db creates customers table with expected columns and index."""
    # Check table existence and columns
    async with test_db.execute("PRAGMA table_info(customers);") as cursor:
        columns = {row["name"]: row["type"].upper() for row in await cursor.fetchall()}

    assert "id" in columns
    assert "name" in columns
    assert "phones" in columns
    assert "addresses" in columns
    assert "notes" in columns
    assert "created_at" in columns
    assert "updated_at" in columns

    # Check index idx_customers_name
    async with test_db.execute("PRAGMA index_list(customers);") as cursor:
        indices = [row["name"] for row in await cursor.fetchall()]
        assert "idx_customers_name" in indices
