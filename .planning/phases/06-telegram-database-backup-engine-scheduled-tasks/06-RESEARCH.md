# Phase 06: Telegram Database Backup Engine & Scheduled Tasks - Research

**Researched:** 2026-10-25
**Domain:** SQLite Hot Backup (`VACUUM INTO`), Gzip Compression, PTB JobQueue (APScheduler), Telegram Bot API Document Upload, Telegram Admin Suite Ergonomics
**Confidence:** HIGH

## Summary

Phase 06 establishes an automated and on-demand SQLite backup pipeline combined with administrative task scheduling for the Cassette Store Telegram bot. The solution leverages SQLite's atomic `VACUUM INTO` command on live WAL databases, standard library `gzip` streaming compression, retention pruning (7 most recent snapshots), and Telegram Document file transfers directly to the Super Admin chat (`TELEGRAM_SUPER_ADMIN_ID`).

By using `VACUUM INTO ?` directly on the active `aiosqlite` connection, the engine takes a consistent, crash-resilient snapshot without locking out live customer order operations or interfering with `-wal` and `-shm` temporary files. PTB's built-in `JobQueue` (backed by `APScheduler 3.11.3`) manages daily background execution at 02:00 AM UTC+7 (`Asia/Ho_Chi_Minh` via stdlib `zoneinfo`), while `/backup` and the `/admin` menu trigger instant on-demand snapshots. Safety gates enforce a 48MB threshold against Telegram Bot API's 50MB document upload limit and provide a 3-stage exponential backoff retry mechanism (2s, 5s, 10s).

Additionally, this phase finishes two ergonomics improvements for the Admin Suite: dynamic model selection (default empty list, model probe on custom addition, and deletion of unused models) and whitelist user display renaming directly via Telegram text input with a 60-second TTL.

**Primary recommendation:** Use SQLite's native `VACUUM INTO ?` followed by Python stdlib `gzip` compression with clean `try...finally` deletion of raw snapshot files. Wire PTB `JobQueue.run_daily` with `zoneinfo.ZoneInfo("Asia/Ho_Chi_Minh")` into `app.py`'s `post_init` hook and persist schedule changes in the SQLite `system_settings` table.

## User Constraints (from CONTEXT.md)

### Locked Decisions
- **D-01:** Local storage: Snapshot `VACUUM INTO` and gzip files are stored in internal directory `backups/` (peer to `data/` or project root).
- **D-02:** Naming convention: `cassette_store_backup_YYYYMMDD_HHMMSS.sqlite3.gz` (ISO timestamp, chronological ordering, collision-free).
- **D-03:** Cleanup: Raw `.sqlite3` file after `VACUUM INTO` must be deleted immediately in a `try...finally` block upon gzip compression to conserve disk space.
- **D-04:** Local retention: Keep at most 7 most recent backups in `backups/`. Auto-prune older files when running a new job.
- **D-05:** Manual backup UX: Immediate feedback message `⏳ Đang tạo snapshot và nén dữ liệu cơ sở dữ liệu...` (or message edit on callback) before sending Document and updating status.
- **D-06:** Caption format: Include snapshot time (UTC+7 `YYYY-MM-DD HH:MM:SS`), uncompressed size vs compressed size with reduction percentage, and quick DB statistics (total orders & total customers).
- **D-07:** Document message UX: Send pure Document without inline keyboard to allow 1-tap download and message forwarding.
- **D-08:** Destination: Send directly to the calling Super Admin chat for manual requests; send to `TELEGRAM_SUPER_ADMIN_ID` for scheduled runs.
- **D-09:** File size limit: Telegram Bot API document limit is 50MB. Set safe threshold at 48MB. If `>= 48MB`, do not send via Telegram, log ERROR, and send red alert text message with server file path.
- **D-10:** Network retry: 3 retries with exponential backoff (2s, 5s, 10s). If still failing, send urgent alert text and preserve `.gz` file on disk.
- **D-11:** Process isolation: Wrap backup operations in `try...except Exception`, log full stacktrace to `RingBufferLogHandler` and system log. Backup failure MUST NEVER crash bot or interrupt customer chat.
- **D-12:** Nightly alert: Any failure during the 02:00 AM job must send an alert message to Super Admin.
- **D-13:** Scheduler: Use PTB `JobQueue` (APScheduler) integrated in PTB `ApplicationBuilder`, timezone `Asia/Ho_Chi_Minh` (UTC+7).
- **D-14:** Startup behavior: Only schedule next scheduled run (default 02:00 AM). DO NOT trigger backup on boot.
- **D-15:** Dynamic schedule configuration: View and update backup time via Telegram `/admin` menu (`[⏰ Đặt giờ sao lưu]`). Persist to `system_settings` table (`backup_schedule_time`, default `"02:00"`). Reschedule immediately in `JobQueue` without restart.
- **D-16:** Permissions: Only `SUPER_ADMIN` can run `/backup`, trigger backup button, and change schedule time. `ADMIN` or `STAFF` receive access denied alert.
- **D-17:** Model Switcher refinement: Default selectable model list is empty (no hardcoded models). Added via text input with 1-token probe. Add delete button `[🗑️ Xoá model]` (cannot delete active model).
- **D-18:** Whitelist user renaming: In user detail view (`adm:wl:view:<id>`), add `[✏️ Đổi tên]` button. Prompt for text name (60s TTL, cancel button), update `admin_users.name` in DB.

### Claude's Discretion
- Caption HTML formatting details.
- Backup engine service module structure (`src/services/backup.py`).
- Gzip compression level (level 6 recommended for optimal speed vs size ratio).

### Deferred Ideas (OUT OF SCOPE)
- **RESTORE-01:** Interactive data restore wizard via Telegram document upload (deferred to v2).
- **ANALYTICS-01:** Advanced revenue chart reports via Telegram photo (deferred to v2).

## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| BKP-01 | Hot snapshot SQLite with `VACUUM INTO` under WAL mode and `gzip` compression reducing size 75-85% | Verified: SQLite native `VACUUM INTO ?` with `aiosqlite` produces clean snapshot without blocking writers; stdlib `gzip` achieves ~90%+ reduction on SQLite DBs |
| BKP-02 | Send `.sqlite3.gz` directly via Telegram Document to Super Admin with 50MB safe gate | Verified: PTB `send_document` supports streaming / file path; 48MB threshold logic blocks oversized files and alerts Super Admin |
| BKP-03 | Automated daily scheduled backup at 02:00 AM UTC+7 via PTB `JobQueue` | Verified: PTB v22.8 has built-in `JobQueue` + `APScheduler 3.11.3`; `run_daily` with `zoneinfo.ZoneInfo("Asia/Ho_Chi_Minh")` handles UTC+7 without external cron |
| BKP-04 | Super Admin instant on-demand backup via `/backup` and `/admin` menu button with immediate file response | Verified: Handlers in `admin.py` and new command `/backup` call shared backup service function and reply with status and Document |

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Snapshot Generation | Database Layer (`sqlite3` / `aiosqlite`) | File System (`backups/`) | SQLite native engine handles WAL consistency and page copying atomically via `VACUUM INTO` |
| Compression & Archiving | Application Service (`src/services/backup.py`) | File System | Python stdlib `gzip` streams uncompressed bytes to disk, removing raw DB on completion |
| Retention Management | Application Service | File System | Scans `backups/`, sorts by mtime / filename, removes entries exceeding 7 snapshots |
| Job Scheduling | PTB `JobQueue` (APScheduler) | SQLite (`system_settings`) | Event loop thread manages timer; DB stores target schedule time across reboots |
| Telegram Transmission | Telegram Bot API (`send_document`) | Telegram Client Transport | PTB bot instance sends multipart file directly to chat ID |
| Admin UI & Configuration | Telegram Bot Handlers (`src/bot/handlers/`) | Inline Keyboards / Messages | Renders admin menu, processes callback queries, and handles rename / time set text prompts |

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| `python-telegram-bot` | `~=22.8` | Bot framework & JobQueue | [VERIFIED: pip index] Built-in `JobQueue` wrapping APScheduler 3.11.3 for coroutine task scheduling |
| `aiosqlite` | `~=0.22.1` | Async SQLite driver | [VERIFIED: pip index] Already project standard; supports `VACUUM INTO ?` parameter binding |
| `gzip` | stdlib | File compression | Python standard library; zero extra dependencies, predictable memory footprint |
| `zoneinfo` | stdlib (Python 3.9+) | Timezone handling | Python standard library; supports IANA `Asia/Ho_Chi_Minh` timezone with daylight saving safety |
| `shutil` | stdlib | Streaming file copy | Python standard library; efficient chunked file copy between binary file and `gzip.GzipFile` |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| `apscheduler` | `3.11.3` | Scheduler backend for PTB `JobQueue` | [VERIFIED: pip index] Installed transitively with PTB; drives `JobQueue.run_daily` |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| `VACUUM INTO` | SQLite Backup API (`sqlite3.backup`) | `VACUUM INTO` also compacts free pages, defragments DB, and runs in a single atomic SQL command |
| `VACUUM INTO` | File copy of `.db` file | File copy of live WAL SQLite database leads to malformed/corrupted files if write transactions are in-flight |
| PTB `JobQueue` | Linux OS cron / systemd timer | Cron requires host access and cannot dynamically inspect or reschedule via Telegram in-app admin menu |
| PTB `JobQueue` | Celery / Redis | Overkill; adds external server daemon and infrastructure failure points for single-tenant bot |

## Package Legitimacy Audit

| Package | Registry | Age | Downloads | Source Repo | Verdict | Disposition |
|---------|----------|-----|-----------|-------------|---------|-------------|
| `python-telegram-bot` | PyPI | 10+ yrs | High (~2M/mo) | https://github.com/python-telegram-bot/python-telegram-bot | [OK] | Approved (existing project core dependency) |
| `aiosqlite` | PyPI | 6+ yrs | High (~8M/mo) | https://github.com/omnilib/aiosqlite | [OK] | Approved (existing project core dependency) |
| `APScheduler` | PyPI | 10+ yrs | High (~10M/mo) | https://github.com/agronholm/apscheduler | [OK] | Approved (transitive dependency of PTB) |

**Packages removed due to [SLOP] verdict:** none
**Packages flagged as suspicious [SUS]:** none

## Architecture Patterns

### System Architecture Diagram

```
[Super Admin] ──( /backup or [💾 Sao lưu DB] )──┐
                                                 ▼
[PTB JobQueue (02:00 AM UTC+7)] ───────► [Backup Service (src/services/backup.py)]
                                                 │
                   ┌─────────────────────────────┼─────────────────────────────┐
                   ▼                             ▼                             ▼
       1. Execute VACUUM INTO        2. Stream gzip to disk         3. Query Orders/Cust
       aiosqlite live connection     raw -> .sqlite3.gz            Summary statistics
       backups/snapshot_ts.sqlite3   try...finally unlink raw                  │
                   │                             │                             │
                   └─────────────────────────────┴─────────────────────────────┘
                                                 │
                                                 ▼
                                     4. Check Size Threshold
                                          (>= 48 MB?)
                                        /             \
                                    [YES]             [NO]
                                     /                   \
                   Send Red Alert Error Text       5. Retention Clean (Keep <= 7)
                   Path: backups/...gz on server         │
                                                         ▼
                                                   6. Upload Telegram Document
                                                      (3x Exponential Backoff)
                                                         │
                                                         ▼
                                                   [Super Admin Chat]
```

### Recommended Project Structure
```
src/
├── services/
│   ├── backup.py             # Backup engine (snapshot, gzip, retention, send_backup)
│   ├── llm_probe.py          # Existing 9router probe
│   └── order_extractor.py    # Existing order extractor
├── bot/
│   ├── handlers/
│   │   ├── admin.py          # Admin menu, model switcher, whitelist CRUD, schedule UI
│   │   ├── backup.py         # /backup command handler and callback triggers
│   │   └── ...
│   ├── keyboards.py          # Admin keyboards, backup time picker, rename prompt
│   └── app.py                # JobQueue initialization and startup schedule sync
└── db/
    ├── admin.py              # admin_users queries (add update_admin_user_name)
    ├── settings.py           # system_settings helpers
    └── orders.py             # Existing order queries
```

### Pattern 1: SQLite Snapshot via `VACUUM INTO` with Safe Gzip Unlink
**What:** Execute `VACUUM INTO ?` with a target path, compress using `gzip.open` and `shutil.copyfileobj`, and ensure the raw snapshot is deleted in `finally`.
**When to use:** Every backup execution (both manual and scheduled).
**Example:**
```python
import gzip
import os
import shutil
import aiosqlite

async def create_database_snapshot(db: aiosqlite.Connection, raw_path: str, gz_path: str) -> tuple[int, int]:
    """Create atomic VACUUM snapshot, compress with gzip, and remove raw file."""
    # Ensure backups directory exists
    os.makedirs(os.path.dirname(raw_path), exist_ok=True)
    
    # 1. Atomic hot snapshot
    await db.execute("VACUUM INTO ?", (raw_path,))
    raw_size = os.path.getsize(raw_path)
    
    # 2. Gzip compression with guaranteed cleanup
    try:
        with open(raw_path, "rb") as f_in, gzip.open(gz_path, "wb", compresslevel=6) as f_out:
            shutil.copyfileobj(f_in, f_out)
    finally:
        if os.path.exists(raw_path):
            os.remove(raw_path)
            
    gz_size = os.path.getsize(gz_path)
    return raw_size, gz_size
```

### Pattern 2: Exponential Backoff Telegram Document Upload
**What:** Send `.sqlite3.gz` to Telegram with retry on network error (`TimedOut`, `NetworkError`).
**When to use:** When delivering the backup document to Super Admin.
**Example:**
```python
import asyncio
import logging
from telegram import Bot
from telegram.error import NetworkError, TimedOut

logger = logging.getLogger(__name__)

async def send_document_with_retry(
    bot: Bot,
    chat_id: int,
    file_path: str,
    caption: str,
    retries: int = 3,
    delays: tuple[float, ...] = (2.0, 5.0, 10.0),
) -> bool:
    """Send document with exponential backoff on transient network failures."""
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
            return True
        except (TimedOut, NetworkError) as err:
            delay = delays[attempt] if attempt < len(delays) else delays[-1]
            logger.warning("Telegram document upload attempt %d failed: %s. Retrying in %ss...", attempt + 1, err, delay)
            if attempt < retries - 1:
                await asyncio.sleep(delay)
        except Exception as err:
            logger.exception("Fatal error uploading backup document: %s", err)
            break
    return False
```

### Pattern 3: Dynamic JobQueue Scheduling and Re-scheduling
**What:** Schedule daily job using `JobQueue.run_daily` and reschedule when setting changes without bot restart.
**When to use:** During `startup_sync` and when Super Admin updates `backup_schedule_time` in `/admin`.
**Example:**
```python
import zoneinfo
from datetime import time
from telegram.ext import Application, ContextTypes

VN_TZ = zoneinfo.ZoneInfo("Asia/Ho_Chi_Minh")
JOB_NAME = "daily_db_backup"

def schedule_daily_backup(app: Application, time_str: str) -> None:
    """Register or replace daily backup job in JobQueue."""
    hour_str, min_str = time_str.split(":")
    target_time = time(int(hour_str), int(min_str), tzinfo=VN_TZ)
    
    jq = app.job_queue
    if not jq:
        return
        
    # Remove existing jobs with this name
    existing = jq.get_jobs_by_name(JOB_NAME)
    for job in existing:
        job.schedule_removal()
        
    # Schedule new job
    jq.run_daily(
        daily_backup_job_callback,
        time=target_time,
        name=JOB_NAME,
    )
```

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Hot SQLite Copy | Python `shutil.copyfile` on live `cassette_store.db` | `VACUUM INTO ?` | File copy during active writes causes corrupted backup files or misses WAL-committed transactions |
| Task Scheduling | `while True: asyncio.sleep(...)` | PTB `JobQueue` (APScheduler) | APScheduler handles drift, daylight/timezone offsets, error isolation, and integration with PTB context |
| Compression | Custom zip wrapper or external tar process | Python stdlib `gzip` | Zero shell injection risk, predictable memory streaming with `shutil.copyfileobj` |
| Timezone calculations | Manual `+07:00` timedelta offsets | `zoneinfo.ZoneInfo("Asia/Ho_Chi_Minh")` | Standard Python library handles standard timezone database rules cleanly |

## Common Pitfalls

### Pitfall 1: Leaking Raw Uncompressed SQLite Files on Gzip Failure
**What goes wrong:** If `gzip` throws an exception (e.g. disk full), the raw snapshot file remains in `backups/`, quickly consuming disk space.
**Why it happens:** Writing `os.remove(raw_path)` after the compression call without a `finally` block.
**How to avoid:** Always enclose the compression logic in a `try...finally` block where `os.remove(raw_path)` runs unconditionally if the file exists.

### Pitfall 2: Telegram Bot 50MB Payload HTTP 413 Failure
**What goes wrong:** Uploading a file >= 50MB causes Telegram API to reject the request with `telegram.error.BadRequest: File is too big`.
**Why it happens:** Large order history and media references expand SQLite database size.
**How to avoid:** Enforce D-09: check `gz_size >= 48 * 1024 * 1024` BEFORE calling `send_document`. If exceeded, skip upload, log error, and message Super Admin with server file path.

### Pitfall 3: Blocking Event Loop During File I/O and VACUUM
**What goes wrong:** `gzip` streaming of a 20MB file blocks the Python single-threaded async event loop for 100-300ms, causing delays in message handling.
**Why it happens:** Running synchronous file compression directly in an async coroutine.
**How to avoid:** Use `asyncio.to_thread` for `gzip` compression and retention file scanning if snapshots grow large, while `aiosqlite` runs `VACUUM INTO ?` in its worker thread.

### Pitfall 4: Duplicate Jobs in PTB JobQueue on Restart/Reschedule
**What goes wrong:** Multiple backup files sent at 02:00 AM because duplicate jobs were registered.
**Why it happens:** Calling `run_daily` without calling `schedule_removal()` on existing jobs returned by `jq.get_jobs_by_name("daily_db_backup")`.
**How to avoid:** Always query and clear jobs by name before registering a replacement.

### Pitfall 5: Deleting Active Model in Model Switcher
**What goes wrong:** Super Admin deletes the model currently used by the bot, leaving `active_model_id` in an inconsistent state.
**Why it happens:** Missing safeguard in delete callback.
**How to avoid:** Per D-17, check `if model_to_delete == active_model_id`: reject with `query.answer("⚠️ Không thể xoá model đang được kích hoạt!", show_alert=True)`.

## Code Examples

### Full Backup Engine Execution Function
```python
# Source: Python stdlib & aiosqlite documentation
import asyncio
from datetime import datetime
import gzip
import logging
import os
import shutil
import zoneinfo
import aiosqlite
from telegram import Bot

logger = logging.getLogger(__name__)
VN_TZ = zoneinfo.ZoneInfo("Asia/Ho_Chi_Minh")
SAFE_SIZE_LIMIT = 48 * 1024 * 1024  # 48 MB

def prune_old_backups(backup_dir: str, keep_count: int = 7) -> list[str]:
    """Keep only the latest N backup archives in directory."""
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
        except OSError as e:
            logger.error("Failed to remove old backup %s: %e", old_file, e)
    return removed

async def execute_backup(
    db: aiosqlite.Connection,
    backup_dir: str = "backups",
) -> dict:
    """Generate snapshot, compress, prune retention, and gather statistics."""
    os.makedirs(backup_dir, exist_ok=True)
    now_vn = datetime.now(VN_TZ)
    ts = now_vn.strftime("%Y%m%d_%H%M%S")
    raw_path = os.path.join(backup_dir, f"snapshot_{ts}.sqlite3")
    gz_path = os.path.join(backup_dir, f"cassette_store_backup_{ts}.sqlite3.gz")

    # 1. Atomic hot snapshot
    await db.execute("VACUUM INTO ?", (raw_path,))
    raw_size = os.path.getsize(raw_path)

    # 2. Compression in thread pool
    def _compress():
        try:
            with open(raw_path, "rb") as f_in, gzip.open(gz_path, "wb", compresslevel=6) as f_out:
                shutil.copyfileobj(f_in, f_out)
        finally:
            if os.path.exists(raw_path):
                os.remove(raw_path)

    await asyncio.to_thread(_compress)
    gz_size = os.path.getsize(gz_path)

    # 3. Prune old backups (keep <= 7)
    await asyncio.to_thread(prune_old_backups, backup_dir, 7)

    # 4. Gather DB stats
    async with db.execute("SELECT COUNT(*) FROM orders") as cur:
        order_count = (await cur.fetchone())[0]
    async with db.execute("SELECT COUNT(*) FROM customers") as cur:
        customer_count = (await cur.fetchone())[0]

    return {
        "gz_path": gz_path,
        "timestamp_str": now_vn.strftime("%Y-%m-%d %H:%M:%S"),
        "raw_size": raw_size,
        "gz_size": gz_size,
        "order_count": order_count,
        "customer_count": customer_count,
        "is_oversized": gz_size >= SAFE_SIZE_LIMIT,
    }
```

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | `APScheduler 3.11.3` bundled with `python-telegram-bot` supports Python 3.13 without deprecation crashes | Standard Stack | Low - verified directly via pytest and live asyncio execution in repo venv |

## Open Questions

1. **Preset backup time options vs free text entry:**
   - What we know: D-15 requires Super Admin to view and change backup time on Telegram.
   - What's unclear: Best UI: Quick buttons (`01:00`, `02:00`, `03:00`, `04:00`, `Nhập giờ khác`) vs text prompt.
   - Recommendation: Provide a selection card with 4 common preset hour buttons (`01:00`, `02:00`, `03:00`, `04:00`) plus `[✏️ Nhập giờ khác]` (with HH:MM regex check and 60s TTL) for optimal ergonomics.

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Python | Runtime | ✓ | 3.13.7 | — |
| python-telegram-bot | Bot framework | ✓ | 22.8 | — |
| aiosqlite | SQLite client | ✓ | 0.22.1 | — |
| apscheduler | JobQueue | ✓ | 3.11.3 | — |
| SQLite VACUUM INTO | Snapshot engine | ✓ | 3.46.1 (bundled in Python 3.13) | — |

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest 9.1.1 + pytest-asyncio 1.4.0 |
| Config file | `pyproject.toml` |
| Quick run command | `.venv/bin/pytest tests/test_backup*.py -v` |
| Full suite command | `.venv/bin/pytest` |

### Phase Requirements → Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| BKP-01 | `VACUUM INTO` snapshot creates valid decompressed SQLite file with identical counts and cleanup of raw snapshot | unit | `.venv/bin/pytest tests/test_backup_engine.py -k test_snapshot` | ❌ Wave 0 |
| BKP-01 | Retention prunes directory keeping exactly 7 latest `.gz` files | unit | `.venv/bin/pytest tests/test_backup_engine.py -k test_retention` | ❌ Wave 0 |
| BKP-02 | Gzip file >= 48MB triggers warning message and suppresses `send_document` | unit | `.venv/bin/pytest tests/test_backup_engine.py -k test_oversized` | ❌ Wave 0 |
| BKP-02 | Network error during `send_document` retries 3 times before failing gracefully | unit | `.venv/bin/pytest tests/test_backup_engine.py -k test_retry` | ❌ Wave 0 |
| BKP-03 | PTB `JobQueue` schedules 02:00 AM job with `Asia/Ho_Chi_Minh` timezone | unit | `.venv/bin/pytest tests/test_backup_scheduler.py` | ❌ Wave 0 |
| BKP-04 | `/backup` command and `adm:bkp:trigger` require `SUPER_ADMIN` and deliver document | integration | `.venv/bin/pytest tests/test_backup_handlers.py` | ❌ Wave 0 |
| D-17, D-18 | Model deletion and whitelist user renaming in Admin Suite | integration | `.venv/bin/pytest tests/test_admin_suite_refinements.py` | ❌ Wave 0 |

### Sampling Rate
- **Per task commit:** `.venv/bin/pytest tests/test_backup*.py`
- **Per wave merge:** `.venv/bin/pytest` (Full suite: 152+ tests)
- **Phase gate:** Full suite green before `/gsd-verify-work`

### Wave 0 Gaps
- [ ] `tests/test_backup_engine.py` — unit tests for snapshot, gzip, retention, and size threshold
- [ ] `tests/test_backup_scheduler.py` — tests for JobQueue registration and dynamic reschedule
- [ ] `tests/test_backup_handlers.py` — tests for `/backup`, permission checks, and Telegram document dispatch
- [ ] `tests/test_admin_suite_refinements.py` — tests for model deletion and user renaming

## Security Domain

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V4 Access Control | yes | Decorator `@require_role(UserRole.SUPER_ADMIN)` on `/backup`, `adm:bkp:*`, and backup time configurations |
| V5 Input Validation | yes | Validate schedule time against `^([01]\d|2[0-3]):([0-5]\d)$` regex; validate model names against safe strings |
| V6 Cryptography / Data Protection | yes | Backup `.sqlite3.gz` sent via Telegram TLS API only to `TELEGRAM_SUPER_ADMIN_ID`, never public groups |

### Known Threat Patterns for SQLite & Telegram Backups

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Elevation of privilege to access backup DB | Elevation of Privilege | Strict `@require_role(UserRole.SUPER_ADMIN)` check at handler entrance; reject regular ADMIN or STAFF |
| SQL Injection via snapshot destination path | Tampering | Parameterized binding `db.execute("VACUUM INTO ?", (raw_path,))` with system-generated timestamp paths |
| Denial of Service via uncontrolled snapshot spamming | Denial of Service | In-memory flag or cooldown lock preventing multiple simultaneous backup processes |
| Information Disclosure via Telegram broadcast | Information Disclosure | Target chat ID strictly pinned to calling Super Admin ID or `settings.telegram_super_admin_id` |

## Sources

### Primary (HIGH confidence)
- Codebase inspection: `src/bot/app.py`, `src/bot/handlers/admin.py`, `src/bot/keyboards.py`, `src/db/connection.py`
- Live REPL verification: SQLite `VACUUM INTO ?` with `aiosqlite`, PTB `JobQueue` (APScheduler 3.11.3) with `ZoneInfo("Asia/Ho_Chi_Minh")`
- Official SQLite documentation: [VACUUM INTO specification](https://www.sqlite.org/lang_vacuum.html)

### Secondary (MEDIUM confidence)
- Telegram Bot API Documentation: 50MB file size limit for bot uploads via `sendDocument`

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - stdlib `gzip` and `zoneinfo`, built-in PTB `JobQueue` already verified
- Architecture: HIGH - atomic `VACUUM INTO ?` verified live on SQLite 3.46.1 WAL mode
- Pitfalls: HIGH - verified file cleanup, size limits, and job replacement semantics

**Research date:** 2026-10-25
**Valid until:** 2026-11-25
