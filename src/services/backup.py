import asyncio
import gzip
import logging
import os
import shutil
import sqlite3
import zoneinfo
from datetime import datetime

import aiosqlite
from telegram import Bot
from telegram.error import NetworkError, TimedOut

logger = logging.getLogger(__name__)

VN_TZ = zoneinfo.ZoneInfo("Asia/Ho_Chi_Minh")
SAFE_SIZE_LIMIT = 48 * 1024 * 1024  # 48 MB per D-09
DEFAULT_RETENTION_COUNT = 7  # 7 archives per D-04
MAX_RESTORE_UNCOMPRESSED = 256 * 1024 * 1024  # 256 MB gzip-bomb guard
SQLITE_MAGIC = b"SQLite format 3\x00"
REQUIRED_TABLES: dict[str, tuple[str, ...]] = {
    "customers": ("id", "name", "phones", "addresses"),
    "orders": (
        "id",
        "customer_name",
        "customer_phone",
        "shipping_address",
        "items_text",
        "total_amount",
        "cod_amount",
        "payment_method",
        "status",
    ),
}


class RestoreValidationError(ValueError):
    """Raised when an uploaded backup archive is unsafe or malformed."""


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


def _readonly_uri(path: str) -> str:
    """Build a SQLite read-only URI for an absolute path (Windows-safe)."""
    return f"file:{os.path.abspath(path).replace(os.sep, '/')}?mode=ro"


def _safe_remove(path: str) -> None:
    try:
        os.remove(path)
    except OSError:
        pass


def _decompress_archive(gz_path: str, staged_path: str) -> None:
    """Stream gzip -> staged file, enforcing the uncompressed size ceiling."""
    total = 0
    try:
        with gzip.open(gz_path, "rb") as src, open(staged_path, "wb") as out:
            while True:
                chunk = src.read(1024 * 1024)
                if not chunk:
                    break
                total += len(chunk)
                if total > MAX_RESTORE_UNCOMPRESSED:
                    raise RestoreValidationError(
                        "File giải nén vượt quá giới hạn 256 MB"
                    )
                out.write(chunk)
    except RestoreValidationError:
        raise
    except Exception as exc:  # BadGzipFile/EOFError/zlib.error/OSError
        raise RestoreValidationError("File không phải định dạng gzip hợp lệ") from exc


def _validate_staged_db(staged_path: str) -> tuple[int, int]:
    """Validate magic bytes, integrity and required schema; return row counts."""
    with open(staged_path, "rb") as f:
        if f.read(len(SQLITE_MAGIC)) != SQLITE_MAGIC:
            raise RestoreValidationError(
                "Nội dung file không phải cơ sở dữ liệu SQLite hợp lệ"
            )

    try:
        conn = sqlite3.connect(_readonly_uri(staged_path), uri=True)
        try:
            row = conn.execute("PRAGMA integrity_check").fetchone()
            if not row or row[0] != "ok":
                raise RestoreValidationError(
                    "Cơ sở dữ liệu trong file bị hỏng (integrity_check thất bại)"
                )

            missing: list[str] = []
            for table, required_columns in REQUIRED_TABLES.items():
                kind = conn.execute(
                    "SELECT type FROM sqlite_master WHERE name = ?", (table,)
                ).fetchone()
                info = conn.execute(f"PRAGMA table_info({table})").fetchall()
                if not kind or kind[0] != "table" or not info:
                    missing.append(table)
                    continue
                existing = {r[1] for r in info}
                for col in required_columns:
                    if col not in existing:
                        missing.append(f"{table}.{col}")

            if missing:
                raise RestoreValidationError(
                    "Cơ sở dữ liệu thiếu bảng/cột bắt buộc: " + ", ".join(missing)
                )

            order_count = conn.execute("SELECT COUNT(*) FROM orders").fetchone()[0]
            customer_count = conn.execute("SELECT COUNT(*) FROM customers").fetchone()[0]
        finally:
            conn.close()
    except RestoreValidationError:
        raise
    except sqlite3.Error as exc:
        raise RestoreValidationError(
            f"Không đọc được cơ sở dữ liệu trong file: {exc}"
        ) from exc

    return order_count, customer_count


def stage_restore_archive(gz_path: str, staging_dir: str) -> dict:
    """Decompress an untrusted archive, validate it and leave a staged DB behind.

    Synchronous by design: callers must run it via ``asyncio.to_thread``.
    On any failure the staged file is removed and ``RestoreValidationError`` raised.
    """
    os.makedirs(staging_dir, exist_ok=True)
    staged_path = os.path.join(staging_dir, "restore.sqlite3")

    try:
        _decompress_archive(gz_path, staged_path)
        raw_size = os.path.getsize(staged_path)
        order_count, customer_count = _validate_staged_db(staged_path)
    except BaseException:
        _safe_remove(staged_path)
        raise

    return {
        "staged_path": staged_path,
        "raw_size": raw_size,
        "order_count": order_count,
        "customer_count": customer_count,
    }


class RestoreApplyError(RuntimeError):
    """Raised when applying a staged restore fails; reports rollback outcome."""

    def __init__(self, message: str, *, current_data_safe: bool, safety_path: str) -> None:
        super().__init__(message)
        self.current_data_safe = current_data_safe
        self.safety_path = safety_path


def _restore_from_snapshot(snapshot_path: str, db_path: str) -> bool:
    """Best-effort rollback of the live DB from the pre-restore snapshot."""
    dest = source = None
    try:
        dest = sqlite3.connect(db_path)
        dest.execute("PRAGMA busy_timeout = 5000")
        source = sqlite3.connect(_readonly_uri(snapshot_path), uri=True)
        source.backup(dest)
        dest.execute("PRAGMA wal_checkpoint(TRUNCATE)")
        dest.commit()
        return True
    except Exception as exc:
        logger.error("Rollback from %s failed: %s", snapshot_path, exc)
        return False
    finally:
        for conn in (source, dest):
            if conn is not None:
                try:
                    conn.close()
                except Exception:
                    pass


def apply_staged_restore(
    staged_path: str, db_path: str, backup_dir: str = "backups"
) -> dict:
    """Snapshot the live DB, then replace it with the staged database.

    Synchronous by design: callers must run it via ``asyncio.to_thread``.
    # ponytail: restore runs while the bot polls; separate connections keep it
    # atomic enough for a small shop (busy_timeout + backup API). Add a global
    # lock / stop polling if zero-downtime restores are ever required.
    """
    now_vn = datetime.now(VN_TZ)
    safety_path = os.path.join(
        backup_dir, f"pre_restore_{now_vn.strftime('%Y%m%d_%H%M%S')}.sqlite3"
    )
    suffix = 1
    while os.path.exists(safety_path):
        safety_path = os.path.join(
            backup_dir,
            f"pre_restore_{now_vn.strftime('%Y%m%d_%H%M%S')}_{suffix}.sqlite3",
        )
        suffix += 1

    dest = None
    modified = False
    try:
        os.makedirs(backup_dir, exist_ok=True)
        dest = sqlite3.connect(db_path)
        dest.execute("PRAGMA busy_timeout = 5000")
        dest.execute("VACUUM INTO ?", (safety_path,))
        dest.execute("PRAGMA wal_checkpoint(TRUNCATE)")

        source = sqlite3.connect(_readonly_uri(staged_path), uri=True)
        try:
            modified = True  # destination pages are about to be replaced
            source.backup(dest)
        finally:
            source.close()

        dest.execute("PRAGMA wal_checkpoint(TRUNCATE)")
        dest.commit()
    except Exception as exc:
        if dest is not None:
            try:
                dest.close()
            except Exception:
                pass
            dest = None

        if not modified:
            raise RestoreApplyError(
                f"Khôi phục thất bại trước khi ghi dữ liệu: {exc}. "
                "Dữ liệu hiện tại không bị thay đổi.",
                current_data_safe=True,
                safety_path=safety_path if os.path.exists(safety_path) else "",
            ) from exc

        restored = _restore_from_snapshot(safety_path, db_path)
        if restored:
            raise RestoreApplyError(
                f"Khôi phục thất bại: {exc}. "
                "Dữ liệu cũ đã được phục hồi từ snapshot an toàn.",
                current_data_safe=True,
                safety_path=safety_path,
            ) from exc
        raise RestoreApplyError(
            f"Khôi phục thất bại: {exc}. Không thể xác nhận dữ liệu cũ còn nguyên vẹn.",
            current_data_safe=False,
            safety_path=safety_path,
        ) from exc
    finally:
        if dest is not None:
            dest.close()

    logger.info("Restored %s into %s (safety snapshot: %s)", staged_path, db_path, safety_path)
    return {"safety_path": safety_path}


async def send_backup_document(
    bot: Bot,
    chat_id: int,
    file_path: str,
    caption: str,
    retries: int = 3,
    delays: tuple[float, ...] = (2.0, 5.0, 10.0),
) -> bool:
    """Send backup document with exponential backoff on transient network failures."""
    for attempt in range(retries):
        try:
            with open(file_path, "rb") as doc:
                await bot.send_document(
                    chat_id=chat_id,
                    document=doc,
                    filename=os.path.basename(file_path),
                    caption=caption,
                    parse_mode="HTML",
                    read_timeout=60.0,
                    write_timeout=60.0,
                    connect_timeout=30.0,
                )
            logger.info("Backup document %s successfully delivered to chat %s", file_path, chat_id)
            return True
        except (TimedOut, NetworkError) as err:
            delay = delays[attempt] if attempt < len(delays) else delays[-1]
            logger.warning(
                "Telegram document upload attempt %d/%d failed: %s. Retrying in %ss...",
                attempt + 1,
                retries,
                err,
                delay,
            )
            if attempt < retries - 1:
                await asyncio.sleep(delay)
        except Exception as err:
            logger.exception("Unexpected error uploading backup document: %s", err)
            break

    return False

