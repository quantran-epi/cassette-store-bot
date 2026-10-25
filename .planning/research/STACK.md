# Stack Research: Milestone v1.1

**Domain:** Telegram Chatbot Management, Natural Language Mutation, Server Console CLI, RBAC & Automated Cloud Backup  
**Researched:** 2026-10-25  
**Confidence:** HIGH  

## Recommended Stack

Stack additions for Milestone v1.1 build directly upon Milestone v1.0 baseline (`python-telegram-bot~=22.8`, `aiosqlite~=0.22.1`, `openai~=3.37.0`, `pydantic~=2.14.1`, `pydantic-settings~=2.16.1`, `httpx~=0.28.1`). Additions prioritize stdlib and existing dependencies first.

### Core Technologies

| Technology | Version | Purpose | Why Recommended |
|------------|---------|---------|-----------------|
| **python-telegram-bot[job-queue]** | `~=22.8` | Scheduled recurring tasks (SQLite backup) | Official PTB extension bundling `APScheduler~=3.10.4`. Integrates directly into PTB `Application` lifespan; provides `run_daily` with timezone awareness (`ZoneInfo("Asia/Ho_Chi_Minh")`) for daily automated backups and dynamic control via `context.job_queue`. |
| **prompt_toolkit** | `~=3.0.53` | Interactive server terminal console | Async-native terminal interface (`prompt_async()`) running concurrently in the same asyncio event loop as PTB. Built-in `patch_stdout` context manager isolates console input from background Telegram polling and LLM HTTP log streams. |
| **SQLite3 VACUUM INTO** | Stdlib (`sqlite3 3.27+`) | Safe online database snapshot | Atomic point-in-time database snapshot executed via `aiosqlite`. Safely exports single consolidated `.db` file from active WAL mode without locking concurrent readers or writers; zero external packages. |
| **httpx (GitHub REST API)** | `~=0.28.1` (Existing) | Cloud backup transport | Reuses already-installed async HTTP client to upload snapshots directly to GitHub repository via GitHub REST Contents API (`PUT /repos/{owner}/{repo}/contents/{path}`) or GitHub Releases API. Zero new dependencies, no Git CLI or SSH setup required. |

### Supporting Libraries

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| **zoneinfo** | Stdlib (`Python >= 3.9`) | Timezone math | Accurate scheduling of daily 02:00 AM VN time backup with PTB `run_daily`. |
| **base64** | Stdlib | File payload encoding | Encoding SQLite snapshot bytes for GitHub REST API JSON payloads. |
| **enum.StrEnum** | Stdlib (`Python >= 3.11`) | RBAC role definitions | Defining `UserRole.SUPER_ADMIN` and `UserRole.ADMIN` with type safety and SQLite string mapping. |

### Development Tools

| Tool | Purpose | Notes |
|------|---------|-------|
| **pytest** & **pytest-asyncio** | Async unit and integration tests | Already installed; test RBAC filters, backup triggers, and mutation schemas. |
| **ruff** | Linter & formatter | Already configured in `pyproject.toml`. |

---

## Installation

```bash
# Core additions for v1.1
pip install "python-telegram-bot[job-queue]~=22.8" "prompt_toolkit~=3.0.53"

# Existing core dependencies (unchanged)
pip install "aiosqlite~=0.22.1" "openai~=3.37.0" "pydantic~=2.14.1" "pydantic-settings~=2.16.1"
```

Updated `pyproject.toml` dependencies:
```toml
dependencies = [
    "python-telegram-bot[job-queue]~=22.8",
    "prompt-toolkit~=3.0.53",
    "aiosqlite~=0.22.1",
    "pydantic~=2.14.1",
    "pydantic-settings~=2.16.1",
    "openai~=3.37.0",
]
```

---

## Technical Implementations & Architectural Decisions

### 1. Interactive Server Console alongside PTB

#### Challenge
Running PTB polling and an interactive terminal CLI in the same process causes two issues:
1. `app.run_polling()` blocks the main thread.
2. Background logs (Telegram updates, HTTP traffic) interleave and corrupt standard `input()` / `sys.stdin` lines.

#### Solution
Run custom async lifecycle using `prompt_toolkit` with `patch_stdout`:

```python
import asyncio
from prompt_toolkit import PromptSession
from prompt_toolkit.patch_stdout import patch_stdout
from telegram.ext import Application

async def console_loop(app: Application) -> None:
    session = PromptSession()
    with patch_stdout():
        while True:
            try:
                cmd = await session.prompt_async("cassette-admin> ")
                cmd = cmd.strip()
                if not cmd:
                    continue
                if cmd == "exit":
                    break
                elif cmd == "backup":
                    await trigger_manual_backup(app)
                elif cmd == "status":
                    await print_bot_status(app)
            except (EOFError, KeyboardInterrupt):
                break

async def run_bot_and_console(app: Application) -> None:
    await app.initialize()
    await app.start()
    await app.updater.start_polling()

    try:
        await console_loop(app)
    finally:
        await app.updater.stop()
        await app.stop()
        await app.shutdown()
```

### 2. Safe Online SQLite Backup & GitHub Push

#### Challenge
Directly copying `cassette_store.db` under WAL mode misses uncommitted WAL frames or causes database corruption. Pushing via `git` CLI bloats git tree history with binary delta diffs.

#### Solution
1. Use `VACUUM INTO` via `aiosqlite` to create an atomic, compacted single-file snapshot.
2. Push snapshot via `httpx` (already in env) to GitHub REST API.

```python
import base64
import datetime
from pathlib import Path
import httpx
import aiosqlite

async def create_backup_snapshot(db: aiosqlite.Connection, temp_path: Path) -> Path:
    if temp_path.exists():
        temp_path.unlink()
    # VACUUM INTO produces standalone DB with zero WAL dependencies
    await db.execute("VACUUM INTO ?", (str(temp_path),))
    return temp_path

async def upload_backup_to_github(
    file_path: Path,
    github_token: str,
    repo: str,
    target_branch: str = "db-backup"
) -> str:
    content_bytes = file_path.read_bytes()
    b64_content = base64.b64encode(content_bytes).decode("ascii")
    
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    github_file_path = f"backups/cassette_store_{timestamp}.db"
    
    url = f"https://api.github.com/repos/{repo}/contents/{github_file_path}"
    headers = {
        "Authorization": f"Bearer {github_token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    payload = {
        "message": f"automated backup {timestamp}",
        "content": b64_content,
        "branch": target_branch,
    }
    
    async with httpx.AsyncClient(timeout=60.0) as client:
        resp = await client.put(url, headers=headers, json=payload)
        resp.raise_for_status()
        return github_file_path
```

### 3. Periodic Background Backup (PTB JobQueue)

Configure daily scheduled job at 02:00 AM VN time (`Asia/Ho_Chi_Minh`):

```python
import datetime
from zoneinfo import ZoneInfo
from telegram.ext import ApplicationBuilder, ContextTypes

async def scheduled_backup_job(context: ContextTypes.DEFAULT_TYPE) -> None:
    # Trigger backup logic and notify super admin on failure
    pass

def setup_scheduler(app) -> None:
    vn_tz = ZoneInfo("Asia/Ho_Chi_Minh")
    target_time = datetime.time(hour=2, minute=0, tzinfo=vn_tz)
    app.job_queue.run_daily(
        scheduled_backup_job,
        time=target_time,
        name="daily_github_backup"
    )
```

### 4. RBAC Data Modeling & Access Control

#### Schema & Roles
Define roles using stdlib `enum.StrEnum`. Store bootstrap super admins in `.env` (`pydantic-settings`) and operators in SQLite table `admins`:

```sql
CREATE TABLE IF NOT EXISTS admins (
    user_id INTEGER PRIMARY KEY,
    username TEXT,
    full_name TEXT,
    role TEXT NOT NULL CHECK(role IN ('super_admin', 'admin')),
    added_by INTEGER,
    created_at TEXT NOT NULL DEFAULT (datetime('now', 'localtime')),
    FOREIGN KEY (added_by) REFERENCES admins(user_id)
);
```

#### Authorization Decorator
```python
from functools import wraps
from enum import StrEnum
from telegram import Update
from telegram.ext import ContextTypes

class UserRole(StrEnum):
    SUPER_ADMIN = "super_admin"
    ADMIN = "admin"

def require_role(min_role: UserRole):
    def decorator(func):
        @wraps(func)
        async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE, *args, **kwargs):
            user_id = update.effective_user.id
            role = await get_user_role(user_id, context.bot_data)
            if not role:
                await update.effective_message.reply_text("⛔ Quyền truy cập bị từ chối.")
                return
            if min_role == UserRole.SUPER_ADMIN and role != UserRole.SUPER_ADMIN:
                await update.effective_message.reply_text("⛔ Thao tác này chỉ dành riêng cho Super Admin.")
                return
            return await func(update, context, *args, **kwargs)
        return wrapper
    return decorator
```

---

## Alternatives Considered

| Recommended | Alternative | When to Use Alternative |
|-------------|-------------|-------------------------|
| **prompt_toolkit** (`~=3.0.53`) | **asyncio.to_thread(input)** | When server console is simple read-only prompt and ALL logging is routed to file (`logging.FileHandler`), leaving stdout strictly empty. If logging touches stdout, prompt line breaks. |
| **prompt_toolkit** | **aioconsole** | Never. `aioconsole` is unmaintained, buggy on Python 3.12+, and lacks stdout patching. |
| **httpx GitHub API** | **Git CLI subprocess** (`asyncio.create_subprocess_exec`) | When server already has cloned git repo with SSH deploy keys configured and team insists on git commit history rather than REST API token. |
| **httpx GitHub API** | **PyGithub** | Only if managing complex GitHub orgs/teams/repos. For uploading one backup file, PyGithub adds 20MB of transitive crypto dependencies for zero gain. |
| **PTB[job-queue]** (`APScheduler`) | **asyncio.create_task loop** (`asyncio.sleep`) | When zero new dependencies are allowed. A 15-line custom `asyncio` sleep loop works for a single static timer, but lacks wall-clock DST alignment, pause/resume, and PTB context integration. |
| **SQLite admins table + .env bootstrap** | **Casbin / Authlib** | Only if RBAC requires hierarchical attribute-based policies (ABAC) across hundreds of users. For 2 roles (Super Admin vs Admin), simple SQLite column + filter is cleanest. |

---

## What NOT to Use

| Avoid | Why | Use Instead |
|-------|-----|-------------|
| **PyGithub** | Heavyweight synchronous package pulling `PyNaCl`, `cryptography`, `requests`. Blocks event loop. | Existing `httpx` async client + GitHub REST API. |
| **aioconsole** | Deprecated, unmaintained, breaks terminal line on concurrent background logs. | `prompt_toolkit` with `patch_stdout`. |
| **Celery / Redis / RQ** | Massive infrastructure overhead requiring Redis server and broker management for 1 daily task. | `python-telegram-bot[job-queue]` or native asyncio task. |
| **cron daemon (OS-level crontab)** | Decouples backup logic from bot process, requires separate credentials configuration and manual Telegram error reporting pipes. | In-process PTB JobQueue / asyncio runner. |
| **Direct SQLite file copy (`shutil.copy2`)** | In WAL mode, copying `.db` file while writes occur results in corrupt backups or missing transactions left in `.db-wal`. | SQLite `VACUUM INTO` via `aiosqlite`. |
| **SQLAlchemy / Tortoise ORM** | Heavy abstraction layer for adding 1 single `admins` table. | Parameterized raw SQL via `aiosqlite`. |

---

## Stack Patterns by Variant

**If console runs in background server (systemd daemon / Docker without TTY):**
- Run PTB with standard `app.run_polling()`.
- Disable interactive `prompt_toolkit` console if `sys.stdin.isatty()` is False.
- Rely on Telegram Admin commands for remote management.

**If GitHub repository restricts large files (>100MB):**
- Use GitHub Releases API via `httpx` instead of Contents API (`POST /repos/{owner}/{repo}/releases` followed by binary asset upload).
- Or compress snapshot using stdlib `gzip` before uploading (`cassette_store_backup.db.gz`).

---

## Version Compatibility

| Package A | Compatible With | Notes |
|-----------|-----------------|-------|
| `python-telegram-bot[job-queue]==22.8` | `APScheduler~=3.10.4`, `pytz`, `httpx~=0.28.1` | Native extension for PTB v22.8. |
| `prompt_toolkit==3.0.53` | `wcwidth`, `Python >= 3.8` | Stable async terminal support. |
| `httpx==0.28.1` | `Python >= 3.8` | Official HTTP/2 & REST transport, compatible with GitHub API v2022-11-28. |

---

## Sources

- [PyPI - prompt_toolkit](https://pypi.org/project/prompt_toolkit/) — verified v3.0.53 release, `prompt_async` and `patch_stdout` support.
- [PyPI - python-telegram-bot](https://pypi.org/project/python-telegram-bot/) — verified v22.8 optional `[job-queue]` extra and APScheduler integration.
- [SQLite Official Documentation - VACUUM INTO](https://www.sqlite.org/lang_vacuum.html#vacuuminto) — verified atomic online backup behavior in WAL mode without locking readers/writers.
- [GitHub REST API Documentation - Repositories Contents](https://docs.github.com/en/rest/repos/contents#create-or-update-file-contents) — verified Base64 PUT endpoint and 100MB file limit.
