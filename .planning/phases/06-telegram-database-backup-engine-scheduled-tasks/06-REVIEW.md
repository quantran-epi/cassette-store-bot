---
phase: 06-telegram-database-backup-engine-scheduled-tasks
reviewed: 2026-10-25T00:00:00Z
depth: standard
files_reviewed: 12
files_reviewed_list:
  - src/bot/app.py
  - src/bot/handlers/admin.py
  - src/bot/handlers/backup.py
  - src/bot/handlers/ingest.py
  - src/bot/keyboards.py
  - src/db/admin.py
  - src/services/backup.py
  - tests/test_admin_handlers.py
  - tests/test_admin_suite_refinements.py
  - tests/test_backup_engine.py
  - tests/test_backup_handlers.py
  - tests/test_backup_scheduler.py
findings:
  critical: 3
  warning: 6
  info: 4
  total: 13
status: issues_found
---

# Phase 06: Code Review Report

**Reviewed:** 2026-10-25T00:00:00Z
**Depth:** standard
**Files Reviewed:** 12
**Status:** issues_found

## Summary

Phase 06 implementation adds an automated SQLite backup engine (`VACUUM INTO` + gzip compression), Telegram uploader with backoff, JobQueue daily scheduler, `/backup` command, and admin suite refinements (model switcher pruning and whitelist user renaming).

The adversarial review identified 3 Critical/Blocker defects, 6 Warnings, and 4 Info-level maintainability issues:
1. Dangling `action_state` when clicking inline "Huỷ" on backup scheduling and user renaming intercepts regular user chat messages.
2. Long LLM model names (>52 chars) exceed Telegram's 64-byte `callback_data` limit, permanently bricking the model switcher with `BadRequest: Button_data_invalid`.
3. Customer database backups containing full PII in `backups/` are omitted from `.gitignore`.
4. Concurrency race condition on simultaneous manual/scheduled backups without a mutex lock.
5. Incomplete gzip archives left in retention pool upon compression failure.
6. Unescaped HTML in scheduled backup exception alerts causing Telegram entity parse errors and silent failure.

---

## Narrative Findings (AI reviewer)

## Critical Issues

### CR-01: Dangling `action_state` on cancel traps user input and mutates user names

**File:** `src/bot/handlers/admin.py:224-239, 329-362, 473`
**Issue:**
When a user opens the custom backup time prompt (`adm:bkp:custom_prompt`) or user rename prompt (`adm:wl:rename_prompt:{target_id}`), `context.user_data["action_state"]` is set.
The inline "❌ Huỷ" buttons point to `adm:bkp:menu` and `adm:wl:view:{target_id}` respectively. Neither of these callback handlers calls `context.user_data.pop("action_state", None)`.
When the user cancels and proceeds to type a normal message in chat (e.g. customer order or search query), `handle_admin_text_input` intercepts it:
- For `await_backup_time`: the bot rejects the text as an invalid time format.
- For `await_user_rename`: the bot silently saves the user's chat message as the new display name of the target account in SQLite!

**Fix:**
Clear `action_state` when navigating to `adm:bkp:menu` and `adm:wl:view:`:
```python
# In handle_admin_callback under adm:bkp:menu:
if data == "adm:bkp:menu":
    await query.answer()
    context.user_data.pop("action_state", None)
    ...

# In handle_admin_callback under adm:wl:view:
if data.startswith("adm:wl:view:"):
    await query.answer()
    context.user_data.pop("action_state", None)
    ...
```

### CR-02: Telegram 64-byte `callback_data` overflow permanently crashes Model Switcher on long model IDs

**File:** `src/bot/handlers/admin.py:815-840` and `src/bot/keyboards.py:757-761, 795-797`
**Issue:**
Telegram Bot API imposes a strict 64-byte limit on inline keyboard `callback_data`.
In `build_model_switcher_keyboard` and `build_model_delete_keyboard`, callbacks use `adm:mdl:sel:{m}` (12 bytes) and `adm:mdl:del:{m}` (12 bytes).
Any 9router model ID longer than 52 characters (e.g. `meta-llama/llama-3.1-405b-instruct:bf16-preview`, `microsoft/phi-3.5-mini-128k-instruct:free`, or custom slugs) results in `callback_data` > 64 bytes.
Calling `edit_message_text(..., reply_markup=keyboard)` immediately raises `telegram.error.BadRequest: Button_data_invalid`. Because the invalid model ID is persisted in SQLite `available_models`, every subsequent attempt to open the model switcher menu (`adm:mdl:menu`) crashes with `Button_data_invalid`, permanently bricking the model switcher UI.

**Fix:**
Validate model ID length before probing and persisting in `handle_admin_text_input`:
```python
if action == "await_model_name":
    candidate_model = raw_text
    if len(candidate_model) > 50:
        await update.effective_message.reply_text(
            "⚠️ <b>Tên model quá dài</b> (tối đa 50 ký tự để phù hợp giới hạn nút bấm Telegram).",
            parse_mode="HTML",
        )
        return True
```

### CR-03: Backup archives and `.sqlite3` / `.gz` files omitted from `.gitignore`

**File:** `.gitignore:5-8` and `src/services/backup.py:49-53`
**Issue:**
`execute_backup` writes hot backups containing unencrypted customer PII (full names, phone numbers, addresses, COD amounts, and order histories) to `backups/cassette_store_backup_*.sqlite3.gz`.
`.gitignore` only specifies `*.db`, `*.db-wal`, `*.db-shm`. It does not ignore `backups/`, `*.sqlite3`, or `*.sqlite3.gz`.
Running `git status` or `git add .` exposes raw customer database archives as untracked files, risking accidental commit into source control.

**Fix:**
Add `backups/`, `*.sqlite3`, and `*.gz` to `.gitignore`:
```gitignore
# SQLite databases & backups
*.db
*.db-wal
*.db-shm
*.sqlite3
*.sqlite3.gz
backups/
```

---

## Warnings

### WR-01: Concurrent backup execution race condition and missing backup lock

**File:** `src/bot/handlers/backup.py:25-30`, `src/bot/handlers/admin.py:183-185`, `src/bot/app.py:57-61`
**Issue:**
There is no concurrency lock or guard across `/backup`, `adm:bkp:trigger`, and `daily_backup_job_callback`.
If two backups run within the same second, both produce the same timestamp string `ts`, causing `VACUUM INTO ?` to crash with `sqlite3.OperationalError: output file already exists`. If overlapping during compression, both write to the same `.gz` file concurrently, corrupting the archive.

**Fix:**
Introduce an `asyncio.Lock` in `src/services/backup.py`:
```python
_backup_lock = asyncio.Lock()

async def execute_backup(db: aiosqlite.Connection, backup_dir: str = "backups") -> dict:
    if _backup_lock.locked():
        raise RuntimeError("Another backup is currently in progress")
    async with _backup_lock:
        ...
```

### WR-02: Partial corrupt `.gz` archive retained upon compression error

**File:** `src/services/backup.py:60-75`
**Issue:**
In `_compress_and_cleanup()`, `finally` removes `raw_path`, but does not clean up `gz_path` if an exception occurs during `shutil.copyfileobj`. A truncated, corrupt `.gz` file remains on disk.
When `prune_old_backups` runs next, it counts this corrupt file among the 7 newest archives, pushing out a valid historical backup.

**Fix:**
Delete `gz_path` if compression fails:
```python
def _compress_and_cleanup() -> None:
    try:
        with open(raw_path, "rb") as f_in, gzip.open(gz_path, "wb", compresslevel=6) as f_out:
            shutil.copyfileobj(f_in, f_out)
    except Exception:
        if os.path.exists(gz_path):
            try:
                os.remove(gz_path)
            except OSError:
                pass
        raise
    finally:
        if os.path.exists(raw_path):
            try:
                os.remove(raw_path)
            except OSError as e:
                logger.warning("Could not delete temporary raw snapshot %s: %s", raw_path, e)
```

### WR-03: Unescaped HTML exception in `daily_backup_job_callback` causes silent alert failure

**File:** `src/bot/app.py:101-108`
**Issue:**
`daily_backup_job_callback` attempts to alert Super Admin using:
`text=f"❌ <b>[Sao lưu tự động] Gặp lỗi nghiêm trọng:</b> {e}", parse_mode="HTML"`.
If `e` contains `<`, `>`, or `&` (e.g. SQLite syntax error, HTTP error response, or XML entity), Telegram rejects the message with `BadRequest: Can't parse entities`.
The surrounding `except Exception: pass` swallows the failure, leaving the Super Admin unaware that the scheduled backup failed.

**Fix:**
Escape `e` using `html.escape(str(e))` before formatting HTML.

### WR-04: Model switcher default model list inconsistency

**File:** `src/bot/handlers/admin.py:665`
**Issue:**
Phase 06-02 refined `available_models` to start empty (`default=[]`) across `adm:mdl:menu` (line 566), `adm:mdl:del_menu` (line 591), and `adm:mdl:input_cancel` (line 730).
However, line 665 in `adm:mdl:sel:` still has `default=DEFAULT_MODELS`.
Selecting a model when `available_models` is unset in SQLite causes all 4 default models to suddenly appear, but navigating away and reopening the menu causes them to disappear again.

**Fix:**
Change line 665 `default=DEFAULT_MODELS` to `default=[]`.

### WR-05: Missing optional dependency `python-telegram-bot[job-queue]` and silent JobQueue failure

**File:** `pyproject.toml:12` and `src/bot/app.py:113-116`
**Issue:**
`pyproject.toml` specifies `python-telegram-bot~=22.8` rather than `python-telegram-bot[job-queue]~=22.8`.
If dependencies are installed in a clean environment without `APScheduler`, `app.job_queue` is `None`.
In `schedule_daily_backup`, `jq = getattr(app, "job_queue", None); if not jq: return` silently returns without logging. Scheduled daily backups will never run.

**Fix:**
Change dependency in `pyproject.toml` to `"python-telegram-bot[job-queue]~=22.8"`, and log an error in `schedule_daily_backup` if `jq` is None.

### WR-06: Double clicking whitelist role button wipes user name

**File:** `src/bot/handlers/admin.py:532-536`
**Issue:**
`pending = context.user_data.pop("pending_add_user", {})`.
If an admin double-taps the role button, the second callback executes with `pending == {}`, setting `name = ""`.
`create_or_update_admin_user` performs `ON CONFLICT(telegram_id) DO UPDATE SET name = excluded.name`, overwriting the newly created name with an empty string.

**Fix:**
Only update `name` if `name` is truthy, or keep existing name if user already exists:
```python
pending = context.user_data.pop("pending_add_user", {})
name = pending.get("name", "") if pending.get("telegram_id") == target_id else ""
existing = await get_admin_user(db, target_id) if db else None
final_name = name or (existing.get("name", "") if existing else "")
if db:
    await create_or_update_admin_user(db, target_id, final_name, chosen_role)
```

---

## Info

### IN-01: Code duplication in backup caption formatting across three modules

**File:** `src/bot/app.py:74-82`, `src/bot/handlers/admin.py:194-202`, `src/bot/handlers/backup.py:41-49`
**Issue:**
The exact same 9-line caption formatting block is copy-pasted across `app.py`, `admin.py`, and `backup.py`.
**Fix:**
Extract a shared helper `format_backup_caption(stats: dict, is_auto: bool = False) -> str` in `src/services/backup.py`.

### IN-02: Private helper `_get_active_db_context` cross-module import coupling

**File:** `src/bot/handlers/admin.py:42-56`, `src/bot/app.py:54`, `src/bot/handlers/backup.py:7`
**Issue:**
`app.py` and `backup.py` import private function `_get_active_db_context` from `admin.py`, while `admin.py` imports `schedule_daily_backup` from `app.py`, requiring lazy inline imports to avoid circular dependencies.
**Fix:**
Move `_get_active_db_context` into `src/db/connection.py`.

### IN-03: Retention pruning sorts by mutable filesystem `mtime` instead of immutable filename timestamp

**File:** `src/services/backup.py:30`
**Issue:**
`files.sort(key=os.path.getmtime, reverse=True)` depends on filesystem modification timestamps. If files are restored, copied, or touched, `mtime` changes, causing older archives to be kept and newer archives to be deleted.
**Fix:**
Sort by filename `os.path.basename(f)` which embeds the ISO timestamp `YYYYMMDD_HHMMSS`.

### IN-04: `update_admin_user_name` creates phantom in-memory user card when user not found in SQLite

**File:** `src/bot/handlers/admin.py:908-914`
**Issue:**
If `update_admin_user_name` updates 0 rows, the handler constructs a mock `target_user` dictionary with `role="STAFF"` and displays a success card, even though nothing was updated in SQLite.
**Fix:**
Check return value of `update_admin_user_name` and display an error card if `target_id` was not found.

---

_Reviewed: 2026-10-25T00:00:00Z_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
