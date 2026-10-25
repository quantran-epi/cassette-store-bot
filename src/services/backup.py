import asyncio
import gzip
import logging
import os
import shutil
import zoneinfo
from datetime import datetime

import aiosqlite

logger = logging.getLogger(__name__)

VN_TZ = zoneinfo.ZoneInfo("Asia/Ho_Chi_Minh")
SAFE_SIZE_LIMIT = 48 * 1024 * 1024  # 48 MB per D-09
DEFAULT_RETENTION_COUNT = 7  # 7 archives per D-04


def prune_old_backups(backup_dir: str = "backups", keep_count: int = DEFAULT_RETENTION_COUNT) -> list[str]:
    """Scan backup directory, sort archives descending by mtime, unlink older than keep_count."""
    if not os.path.exists(backup_dir):
        return []

    files = [
        os.path.join(backup_dir, f)
        for f in os.listdir(backup_dir)
        if f.startswith("cassette_store_backup_") and f.endswith(".sqlite3.gz")
    ]
    files.sort(key=os.path.getmtime, reverse=True)

    removed = []
    for old_file in files[keep_count:]:
        try:
            os.remove(old_file)
            removed.append(old_file)
            logger.info("Pruned old backup: %s", old_file)
        except OSError as e:
            logger.error("Failed to remove old backup archive %s: %s", old_file, e)

    return removed


async def execute_backup(
    db: aiosqlite.Connection,
    backup_dir: str = "backups",
) -> dict:
    """Generate atomic VACUUM INTO snapshot, stream gzip compress, delete raw file in finally, prune retention."""
    os.makedirs(backup_dir, exist_ok=True)
    now_vn = datetime.now(VN_TZ)
    ts = now_vn.strftime("%Y%m%d_%H%M%S")
    raw_path = os.path.join(backup_dir, f"snapshot_{ts}.sqlite3")
    gz_path = os.path.join(backup_dir, f"cassette_store_backup_{ts}.sqlite3.gz")

    # 1. Atomic hot snapshot on live WAL SQLite connection
    await db.execute("VACUUM INTO ?", (raw_path,))
    raw_size = os.path.getsize(raw_path)

    # 2. Gzip compression with guaranteed raw file cleanup in try...finally
    def _compress_and_cleanup() -> None:
        try:
            with open(raw_path, "rb") as f_in, gzip.open(gz_path, "wb", compresslevel=6) as f_out:
                shutil.copyfileobj(f_in, f_out)
        finally:
            if os.path.exists(raw_path):
                try:
                    os.remove(raw_path)
                except OSError as e:
                    logger.warning("Could not delete temporary raw snapshot %s: %s", raw_path, e)

    await asyncio.to_thread(_compress_and_cleanup)
    gz_size = os.path.getsize(gz_path)

    # 3. Retention pruning (retain at most 7 newest archives)
    await asyncio.to_thread(prune_old_backups, backup_dir, DEFAULT_RETENTION_COUNT)

    # 4. Gather DB statistics for caption
    async with db.execute("SELECT COUNT(*) FROM orders") as cur:
        order_count = (await cur.fetchone())[0]
    async with db.execute("SELECT COUNT(*) FROM customers") as cur:
        customer_count = (await cur.fetchone())[0]

    return {
        "gz_path": gz_path,
        "raw_path": raw_path,
        "timestamp_str": now_vn.strftime("%Y-%m-%d %H:%M:%S"),
        "raw_size": raw_size,
        "gz_size": gz_size,
        "order_count": order_count,
        "customer_count": customer_count,
        "is_oversized": gz_size >= SAFE_SIZE_LIMIT,
    }
