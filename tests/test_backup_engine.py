import gzip
import os
import shutil
import sqlite3

import aiosqlite
import pytest

from src.services.backup import (
    DEFAULT_RETENTION_COUNT,
    SAFE_SIZE_LIMIT,
    execute_backup,
    prune_old_backups,
)


@pytest.fixture
async def sample_db(tmp_path):
    """Fixture providing an initialized SQLite database with sample data."""
    db_file = tmp_path / "test_store.db"
    async with aiosqlite.connect(str(db_file)) as db:
        await db.execute("PRAGMA journal_mode = WAL;")
        await db.execute(
            """
            CREATE TABLE customers (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL
            );
            """
        )
        await db.execute(
            """
            CREATE TABLE orders (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                customer_id INTEGER,
                total_amount INTEGER
            );
            """
        )
        await db.execute("INSERT INTO customers (name) VALUES ('Nguyen Van A'), ('Tran Thi B');")
        await db.execute("INSERT INTO orders (customer_id, total_amount) VALUES (1, 150000), (2, 300000);")
        await db.commit()
    return str(db_file)


@pytest.mark.asyncio
async def test_snapshot_creation_and_integrity(sample_db, tmp_path):
    """Verify execute_backup creates valid gzip archive, deletes raw snapshot, and preserves data."""
    backup_dir = tmp_path / "backups"
    async with aiosqlite.connect(sample_db) as db:
        result = await execute_backup(db, backup_dir=str(backup_dir))

    # Assert return structure
    assert "gz_path" in result
    assert "raw_path" in result
    assert result["order_count"] == 2
    assert result["customer_count"] == 2
    assert result["is_oversized"] is False
    assert result["gz_size"] > 0
    assert result["raw_size"] > 0

    gz_path = result["gz_path"]
    raw_path = result["raw_path"]

    # Raw file must be deleted per D-03
    assert not os.path.exists(raw_path)
    # Compressed file must exist per D-02
    assert os.path.exists(gz_path)
    assert gz_path.endswith(".sqlite3.gz")

    # Decompress and verify SQLite database integrity
    decompressed_db_path = tmp_path / "decompressed.sqlite3"
    with gzip.open(gz_path, "rb") as f_in, open(decompressed_db_path, "wb") as f_out:
        shutil.copyfileobj(f_in, f_out)

    assert os.path.exists(decompressed_db_path)

    # Check data in decompressed DB
    conn = sqlite3.connect(str(decompressed_db_path))
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM customers")
    assert cursor.fetchone()[0] == 2
    cursor.execute("SELECT COUNT(*) FROM orders")
    assert cursor.fetchone()[0] == 2
    conn.close()


def test_retention_pruning(tmp_path):
    """Verify prune_old_backups retains only the 7 newest archives."""
    backup_dir = tmp_path / "backups"
    backup_dir.mkdir(parents=True, exist_ok=True)

    created_files = []
    # Create 10 dummy backup files with staggered timestamps
    for i in range(10):
        file_path = backup_dir / f"cassette_store_backup_2026102{i}_120000.sqlite3.gz"
        file_path.write_text(f"dummy content {i}")
        # Set mtime explicitly
        mtime = 1700000000 + i * 100
        os.utime(file_path, (mtime, mtime))
        created_files.append(str(file_path))

    # Prune keeping 7
    removed = prune_old_backups(str(backup_dir), keep_count=DEFAULT_RETENTION_COUNT)

    assert len(removed) == 3
    # The 3 oldest should be removed
    for f in created_files[:3]:
        assert f in removed
        assert not os.path.exists(f)

    # The 7 newest should remain
    remaining = [
        os.path.join(str(backup_dir), f)
        for f in os.listdir(str(backup_dir))
        if f.startswith("cassette_store_backup_") and f.endswith(".sqlite3.gz")
    ]
    assert len(remaining) == 7
    for f in created_files[3:]:
        assert f in remaining
        assert os.path.exists(f)


@pytest.mark.asyncio
async def test_oversized_backup_detection(sample_db, tmp_path, monkeypatch):
    """Verify execute_backup flags is_oversized=True when file size >= SAFE_SIZE_LIMIT."""
    backup_dir = tmp_path / "backups"

    # Monkeypatch os.path.getsize to return >= SAFE_SIZE_LIMIT for the .gz file
    orig_getsize = os.path.getsize

    def fake_getsize(path):
        if str(path).endswith(".gz"):
            return SAFE_SIZE_LIMIT + 1024
        return orig_getsize(path)

    monkeypatch.setattr(os.path, "getsize", fake_getsize)

    async with aiosqlite.connect(sample_db) as db:
        result = await execute_backup(db, backup_dir=str(backup_dir))

    assert result["is_oversized"] is True
    assert result["gz_size"] >= SAFE_SIZE_LIMIT
