---
phase: 05-role-based-access-control-telegram-admin-suite
reviewed: 2026-10-25T11:00:00Z
depth: standard
files_reviewed: 12
files_reviewed_list:
  - src/db/admin.py
  - src/db/settings.py
  - src/bot/logging_handler.py
  - src/config.py
  - src/db/schema.py
  - src/bot/security.py
  - src/services/llm_probe.py
  - src/bot/handlers/admin.py
  - src/bot/handlers/logs.py
  - src/bot/keyboards.py
  - src/bot/handlers/ingest.py
  - src/bot/app.py
findings:
  critical: 2
  warning: 5
  info: 2
  total: 9
status: issues_found
---

# Phase 05: Code Review Report

**Reviewed:** 2026-10-25T11:00:00Z
**Depth:** standard
**Files Reviewed:** 12
**Status:** issues_found

## Summary

Adversarial review of Phase 05 role-based access control, Telegram admin suite, model switcher, and whitelist persistence. The implementation covers the required UX layouts, role decorators, and in-memory log buffer, but contains two critical flaws:

1. **Complete persistence failure in production runtime**: `main.py` builds the application without passing `db`. `src/bot/handlers/admin.py` accesses `context.bot_data.get("db")` and branches on `if db:`. Because `db` is `None` in production, every database operation in `admin.py` (whitelist listing, viewing, role updating, user deleting, model persisting, dashboard order count) silently does nothing or returns empty data.
2. **Privilege escalation & Root Super Admin demotion**: In `src/bot/handlers/admin.py`, the `adm:wl:role_pick:` callback omits root Super Admin protection checks, allowing any admin to input the Super Admin's ID and demote them to `STAFF`.

Additional warnings include an unhandled Telegram HTML parser error when rendering empty logs, dropping customer orders sent after an admin prompt expires, mutating shared module-level default model lists, hardcoding model ID in search handlers, and silent exception suppression in startup sync.

## Critical Issues

### CR-01: Admin Suite Database Operations Silently Fail in Production Runtime

**File:** `src/bot/handlers/admin.py:62-64,145,176,219-220,279-281,351-352,381-385,414-415,585-592`
**Issue:** `main.py` invokes `build_application(settings)` without passing a database connection, leaving `app.bot_data["db"] = None`. Other handler modules (`orders.py`, `callbacks.py`, `ingest.py`) resolve connections via `db_ctx = nullcontext(db) if db else get_db_connection(db_path)`. In contrast, `admin.py` directly reads `db = context.bot_data.get("db")` and wraps every query in `if db:`. Consequently, when running live via `main.py`:
- `render_dashboard_card` always shows `0 đơn hàng`.
- `adm:wl:list:` always displays an empty list (`users = []`).
- Role changes, additions, and deletions are never persisted to SQLite.
- Model selections are never persisted to `system_settings`.
All unit tests passed only because test suites mocked `context.bot_data["db"]` with a dummy mock.

**Fix:**
Implement a helper to resolve connection context or acquire from `get_db_connection` whenever `db` in `bot_data` is `None`:
```python
from contextlib import nullcontext
from src.db.connection import get_db_connection

def _get_active_db_context(context: ContextTypes.DEFAULT_TYPE):
    app_context = context.application.bot_data.get("app_context")
    db = getattr(app_context, "db", None) if app_context else context.application.bot_data.get("db")
    settings = context.application.bot_data.get("settings")
    db_path = getattr(settings, "sqlite_db_path", "cassette_store.db") if settings else "cassette_store.db"
    return nullcontext(db) if db else get_db_connection(db_path)
```
Wrap all database queries in `async with _get_active_db_context(context) as db:` instead of bare `if db:` guards.

---

### CR-02: Root Super Admin Demotion Vulnerability in Whitelist Add User

**File:** `src/bot/handlers/admin.py:343-357`
**Issue:** While `adm:wl:role:` and `adm:wl:rm_cf:` guard against modifying or deleting `super_admin_id`, `adm:wl:role_pick:` contains no check against `super_admin_id`. Any admin can initiate `adm:wl:add_prompt`, enter the Root Super Admin's Telegram ID, and choose `STAFF`. The handler will overwrite the root user's role in SQLite and `bot_data["admin_roles"]`, stripping Super Admin access and violating D-15.

**Fix:**
```python
    if data.startswith("adm:wl:role_pick:"):
        parts = data.split(":")
        target_id = int(parts[3])
        chosen_role = parts[4]

        if super_admin_id is not None and target_id == super_admin_id:
            await query.answer("🛡️ Không thể chỉnh sửa hoặc hạ quyền Root Super Admin!", show_alert=True)
            return
```

## Warnings

### WR-01: Telegram HTML Parser Crash on Empty Logs

**File:** `src/bot/logging_handler.py:42`, `src/bot/handlers/logs.py:23,31`
**Issue:** `format_logs_for_telegram` returns `"<i>(Không có nhật ký nào)</i>"` when the ring buffer is empty. `_render_logs_card` interpolates this directly into `<pre><code>{formatted_logs}</code></pre>`. In Telegram Bot API HTML parsing mode, nesting inline tags like `<i>` inside `<pre>` or `<code>` blocks is invalid and raises `telegram.error.BadRequest: Can't parse entities`.

**Fix:**
Return unformatted plain text for empty messages, or place status messages outside `<pre><code>`:
```python
# In logging_handler.py
if not lines:
    return "(Không có nhật ký nào)"
```

---

### WR-02: Legitimate Customer Orders Dropped on Expired Admin Text State

**File:** `src/bot/handlers/admin.py:511-517`, `src/bot/handlers/ingest.py:173-181`
**Issue:** If an admin starts a prompt (`await_whitelist_id` or `await_model_name`) and more than 60 seconds pass, sending a normal order message triggers `handle_admin_text_input`. It pops `action_state`, sends an error message, and returns `True`. This halts processing and drops the customer order. For order action prompts (`order_actions.py`), expired states cleanly fall through to regular order ingestion.

**Fix:**
In `src/bot/handlers/admin.py`:
```python
    now = time.time()
    if now > action_state.get("expires_at", 0):
        context.user_data.pop("action_state", None)
        # Fall through so the text can be ingested as an order or search query
        return False
```

---

### WR-03: In-Place Mutation of Global Default Models List

**File:** `src/bot/handlers/admin.py:28,588-591`
**Issue:** `DEFAULT_MODELS = [...]` is a module-level list. In `handle_admin_text_input`, `models = await get_json_setting(db, "available_models", default=DEFAULT_MODELS)`. If no database record exists, `models` is a direct reference to `DEFAULT_MODELS`. `models.append(candidate_model)` mutates the global module default list in-place.

**Fix:**
Copy the list when reading defaults:
```python
models = list(await get_json_setting(db, "available_models", default=DEFAULT_MODELS) or DEFAULT_MODELS)
```

---

### WR-04: Order Search Handler Ignores Dynamic Active Model ID

**File:** `src/bot/handlers/search.py:138`
**Issue:** In `src/bot/handlers/ingest.py`, text and photo extraction use `context.application.bot_data.get("active_model_id") or settings.nine_router_model_id`. In `src/bot/handlers/search.py`, `run_order_search` is passed `model_id=settings.nine_router_model_id`. Switching models via the admin UI has no effect on natural language order queries.

**Fix:**
In `src/bot/handlers/search.py`:
```python
active_model = (
    context.application.bot_data.get("active_model_id")
    or settings.nine_router_model_id
)
result = await run_with_typing(
    chat,
    run_order_search(
        client=openai_client,
        model_id=active_model,
        db=active_db,
        query=query_text,
    ),
)
```

---

### WR-05: Silent Exception Suppression During Startup Synchronization

**File:** `src/bot/app.py:72-79`
**Issue:** In `startup_sync`, the fallback branch uses `except Exception: pass` without logging or alerting. If SQLite fails to open, tables do not exist, or data corruption occurs, the bot starts in a broken state without super admin synchronization, whitelist IDs, or active model restoration.

**Fix:**
```python
        try:
            async with get_db_connection(settings.sqlite_db_path) as conn:
                await _do_sync(app, conn, settings)
        except Exception:
            logging.getLogger(__name__).exception("Startup synchronization failed")
```

## Info

### IN-01: Whitelist Keyboard Generates Unbounded Inline Buttons Without Pagination

**File:** `src/bot/handlers/admin.py:165`, `src/bot/keyboards.py:592-652`
**Issue:** `build_whitelist_keyboard` accepts `total_pages`, but `admin.py` hardcodes `total_pages=1` and passes the entire user list. If the whitelist grows past 50 users (100 buttons), Telegram will reject the payload with `BadRequest: BUTTON_ROW_MAX_TOO_HIGH` or `TOO_MANY_BUTTONS`. Paginate `users` by slice of 8–10 users per page.

---

### IN-02: Hardcoded "Telegram ID" Timeout Message on Model Name Prompt

**File:** `src/bot/handlers/admin.py:515`
**Issue:** When an admin prompt times out in `handle_admin_text_input`, the response text is hardcoded to: `"⏳ Đã hết thời gian nhập Telegram ID (60s). Thao tác đã được huỷ."`, even when the active action was `await_model_name`. Use a prompt-specific or generic timeout message.

---

_Reviewed: 2026-10-25T11:00:00Z_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
