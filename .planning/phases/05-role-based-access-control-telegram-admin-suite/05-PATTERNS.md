# Phase 5: Role-Based Access Control & Telegram Admin Suite - Pattern Map

**Mapped:** 2026-10-25  
**Files analyzed:** 12 (7 existing/modified, 5 new implementations + 5 test suites)  
**Analogs found:** 11 / 12  

---

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|---|---|---|---|---|
| `src/config.py` | config | static / request-response | `src/config.py` | exact |
| `src/db/schema.py` | migration / schema | DDL | `src/db/schema.py` | exact |
| `src/db/admin.py` | model / service | CRUD | `src/db/customers.py` | role-match |
| `src/db/settings.py` | model / service | CRUD | `src/db/customers.py` | role-match |
| `src/bot/security.py` | middleware / guard | request-response | `src/bot/security.py` | exact |
| `src/bot/logging_handler.py` | utility / service | streaming / event-driven | N/A (Standard Library `logging.Handler`) | novel / research |
| `src/bot/keyboards.py` | component / view | transform | `src/bot/keyboards.py` | exact |
| `src/bot/handlers/admin.py` | controller | request-response | `src/bot/handlers/order_actions.py` | exact |
| `src/bot/handlers/logs.py` | controller | request-response | `src/bot/handlers/base.py` | role-match |
| `src/services/llm_probe.py` | service | request-response | `src/services/extractor.py` | exact |
| `src/bot/app.py` | config / entrypoint | setup | `src/bot/app.py` | exact |
| `tests/test_security_rbac.py` | test | assert / mock | `tests/test_security.py` | exact |
| `tests/test_admin_db.py` | test | CRUD / integration | `tests/test_db_orders.py` | exact |
| `tests/test_admin_handlers.py` | test | mock / e2e | `tests/test_orders_ui.py` | exact |
| `tests/test_logging_buffer.py` | test | unit | `tests/test_config.py` | role-match |

---

## Pattern Assignments

### 1. `src/config.py` (config, static)
**Analog:** `src/config.py` (lines 45-56)

Add `telegram_super_admin_id: int | None = None` to `Settings`.

```python
# src/config.py:44-55
    # Telegram bot configuration
    telegram_bot_token: SecretStr
    telegram_whitelist_user_ids: list[int] = []
    telegram_super_admin_id: int | None = None

    # LLM Gateway configuration (9router / OpenAI-compatible)
    nine_router_api_key: SecretStr = SecretStr("")
    nine_router_base_url: str = "https://api.9router.com/v1"
    nine_router_model_id: str = "gpt-4o-mini"

    # SQLite Database configuration
    sqlite_db_path: str = "cassette_store.db"
```

---

### 2. `src/db/schema.py` (migration/schema, DDL)
**Analog:** `src/db/schema.py` (lines 4-24, 72)

Async table and index creation pattern with `IF NOT EXISTS`.

```python
# src/db/schema.py:4-24
async def init_db(db: aiosqlite.Connection) -> None:
    """Initialize database tables and indices."""
    await db.execute(
        """
        CREATE TABLE IF NOT EXISTS admin_users (
            telegram_id INTEGER PRIMARY KEY,
            name TEXT NOT NULL DEFAULT '',
            role TEXT NOT NULL CHECK (role IN ('SUPER_ADMIN', 'ADMIN', 'STAFF')),
            created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
        );
        """
    )
    await db.execute(
        """
        CREATE TABLE IF NOT EXISTS system_settings (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL,
            description TEXT NOT NULL DEFAULT '',
            updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
        );
        """
    )
    await db.commit()
```

---

### 3. `src/db/admin.py` (service/model, CRUD)
**Analog:** `src/db/customers.py` (lines 24-49, 93-101)

Async database queries using row mapping, parameter substitution, and commit.

```python
# src/db/customers.py:24-49
async def create_or_update_admin_user(
    db: aiosqlite.Connection, telegram_id: int, name: str, role: str
) -> bool:
    cursor = await db.execute(
        """
        INSERT INTO admin_users (telegram_id, name, role, updated_at)
        VALUES (?, ?, ?, CURRENT_TIMESTAMP)
        ON CONFLICT(telegram_id) DO UPDATE SET
            name = excluded.name,
            role = excluded.role,
            updated_at = CURRENT_TIMESTAMP
        """,
        (telegram_id, name, role),
    )
    await db.commit()
    return cursor.rowcount > 0

async def get_admin_user(db: aiosqlite.Connection, telegram_id: int) -> dict | None:
    async with db.execute("SELECT * FROM admin_users WHERE telegram_id = ?", (telegram_id,)) as cursor:
        row = await cursor.fetchone()
        if not row:
            return None
        return dict(row)
```

**Root Protection Pattern inside removal service:**
```python
async def delete_admin_user(
    db: aiosqlite.Connection,
    target_id: int,
    super_admin_id: int | None,
) -> bool:
    """Strictly protect root super admin configured in .env from deletion."""
    if super_admin_id is not None and target_id == super_admin_id:
        raise PermissionError("Cannot delete or demote root Super Admin configured in .env")
    cursor = await db.execute("DELETE FROM admin_users WHERE telegram_id = ?", (target_id,))
    await db.commit()
    return cursor.rowcount > 0
```

---

### 4. `src/db/settings.py` (service/model, CRUD)
**Analog:** `src/db/customers.py` (lines 66-91)

Simple key-value operations on `system_settings` table.

```python
async def get_setting(db: aiosqlite.Connection, key: str, default: str | None = None) -> str | None:
    async with db.execute("SELECT value FROM system_settings WHERE key = ?", (key,)) as cursor:
        row = await cursor.fetchone()
        return row["value"] if row else default

async def set_setting(db: aiosqlite.Connection, key: str, value: str, description: str = "") -> None:
    await db.execute(
        """
        INSERT INTO system_settings (key, value, description, updated_at)
        VALUES (?, ?, ?, CURRENT_TIMESTAMP)
        ON CONFLICT(key) DO UPDATE SET
            value = excluded.value,
            description = excluded.description,
            updated_at = CURRENT_TIMESTAMP
        """,
        (key, value, description),
    )
    await db.commit()
```

---

### 5. `src/bot/security.py` (middleware/guard, request-response)
**Analog:** `src/bot/security.py` (lines 5-33)

Add `UserRole` StrEnum and `@require_role` decorator wrapping message and callback events.

```python
# src/bot/security.py:5-32
import functools
from enum import StrEnum
from telegram import Update
from telegram.ext import ContextTypes

class UserRole(StrEnum):
    SUPER_ADMIN = "SUPER_ADMIN"
    ADMIN = "ADMIN"
    STAFF = "STAFF"

ROLE_HIERARCHY: dict[UserRole, int] = {
    UserRole.SUPER_ADMIN: 3,
    UserRole.ADMIN: 2,
    UserRole.STAFF: 1,
}

def require_role(min_role: UserRole):
    """Enforce minimum role requirement on Commands and CallbackQueries."""
    def decorator(func):
        @functools.wraps(func)
        async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE, *args, **kwargs):
            user = update.effective_user
            if not user:
                return

            roles_map: dict[int, UserRole] = context.bot_data.get("admin_roles", {})
            user_role = roles_map.get(user.id, UserRole.STAFF)

            if ROLE_HIERARCHY.get(user_role, 0) < ROLE_HIERARCHY[min_role]:
                denial_text = f"⛔ Bạn không có quyền thực hiện thao tác này (Yêu cầu: {min_role.value})."
                if update.callback_query:
                    await update.callback_query.answer(denial_text, show_alert=True)
                elif update.effective_message:
                    await update.effective_message.reply_text(denial_text)
                return

            return await func(update, context, *args, **kwargs)
        return wrapper
    return decorator
```

---

### 6. `src/bot/keyboards.py` (component/view, transform)
**Analog:** `src/bot/keyboards.py` (lines 60-76, 124-206)

InlineKeyboardMarkup grid constructors with 2-column buttons, confirmation modals, and back buttons.

```python
# src/bot/keyboards.py:124-142
def build_admin_main_keyboard() -> InlineKeyboardMarkup:
    """Build 2-column admin suite navigation grid per D-03."""
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("👥 Quản lý Whitelist", callback_data="adm:wl:list:1"),
                InlineKeyboardButton("🤖 Đổi Model LLM", callback_data="adm:mdl:menu"),
            ],
            [
                InlineKeyboardButton("📜 Xem Logs", callback_data="adm:log:view:25:all"),
                InlineKeyboardButton("💾 Sao lưu DB", callback_data="adm:bkp:trigger"),
            ],
            [
                InlineKeyboardButton("🔄 Làm mới", callback_data="adm:dash:refresh"),
                InlineKeyboardButton("❌ Đóng menu", callback_data="adm:dash:close"),
            ],
        ]
    )

def build_whitelist_confirm_delete_keyboard(target_id: int) -> InlineKeyboardMarkup:
    """Build 2-step confirmation modal for whitelist removal per D-07."""
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("⚠️ Xác nhận xoá", callback_data=f"adm:wl:rm_cf:{target_id}"),
            ],
            [
                InlineKeyboardButton("Quay lại", callback_data=f"adm:wl:v:{target_id}"),
            ],
        ]
    )
```

---

### 7. `src/bot/handlers/admin.py` (controller, request-response)
**Analog:** `src/bot/handlers/order_actions.py` (lines 44-110, 196-270)

State machine with `query.edit_message_text`, `query.answer()`, regex callback matching, and TTL input prompts.

```python
# src/bot/handlers/order_actions.py:44-82
async def handle_admin_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Route admin inline button actions with in-place message editing."""
    query = update.callback_query
    if not query or not query.data:
        return

    data = query.data
    # Dismiss / close
    if data == "adm:dash:close":
        await query.answer()
        try:
            await query.edit_message_text("❌ Đã đóng menu quản trị.")
        except BadRequest as e:
            if "Message is not modified" not in str(e):
                raise
        return

    # Whitelist view, model switch, etc.
```

---

### 8. `src/services/llm_probe.py` (service, request-response)
**Analog:** `src/services/extractor.py` (lines 145-175)

Async completion request using AsyncOpenAI with custom timeout and exception handling.

```python
# src/services/extractor.py:158-175
from openai import AsyncOpenAI

async def probe_model_reachability(
    client: AsyncOpenAI,
    candidate_model: str,
    timeout: float = 5.0,
) -> tuple[bool, str]:
    """Test candidate model with a 1-token probe. Returns (success, detail_message)."""
    try:
        await client.chat.completions.create(
            model=candidate_model,
            messages=[{"role": "user", "content": "hi"}],
            max_tokens=1,
            timeout=timeout,
        )
        return True, "Kết nối thành công (HTTP 200 OK)"
    except Exception as exc:
        return False, f"Lỗi phản hồi: {exc}"
```

---

### 9. `src/bot/app.py` (config/entrypoint, setup)
**Analog:** `src/bot/app.py` (lines 38-75, 77-120)

Store runtime state in `bot_data`, register handlers with regex patterns.

```python
# src/bot/app.py:53-85
    # Store dynamic roles and active model in bot_data
    app.bot_data["admin_roles"] = {}  # dict[int, UserRole] loaded from DB
    app.bot_data["active_model_id"] = settings.nine_router_model_id

    # Register admin commands
    app.add_handler(CommandHandler("admin", admin_command), group=0)
    app.add_handler(CommandHandler("logs", logs_command), group=0)

    # Register admin callback query handlers
    app.add_handler(CallbackQueryHandler(handle_admin_callback, pattern=r"^adm:"), group=0)
```

---

## Shared Patterns

### Callback Query Answer Handling
**Source:** `src/bot/handlers/order_actions.py:46-54`  
**Apply to:** All `adm:*` callback handlers  
Always call `await query.answer()` early or `await query.answer(text, show_alert=True)` to prevent Telegram client spinner freeze. Catch `telegram.error.BadRequest` on `edit_message_text` when content is identical:
```python
try:
    await query.edit_message_text(text=card_text, reply_markup=keyboard, parse_mode="HTML")
except BadRequest as e:
    if "Message is not modified" not in str(e):
        raise
```

### Temporary Action State in `context.user_data`
**Source:** `src/bot/handlers/order_actions.py:231-236`  
**Apply to:** Admin whitelist input and custom model text prompts  
```python
context.user_data["action_state"] = {
    "action": "await_whitelist_id",
    "expires_at": time.time() + 60,
}
```

### Test Update Construction
**Source:** `tests/test_security.py:14-43`  
**Apply to:** `tests/test_security_rbac.py` and `tests/test_admin_handlers.py`  
```python
def make_mock_update(user_id: int | None = 123456, is_callback: bool = False):
    ...
```

---

## Novel Pattern (No Codebase Analog)

### `src/bot/logging_handler.py` (utility/service, streaming/event-driven)
**Reason:** No in-memory logging buffer currently exists in codebase.  
**Reference:** Python standard library `logging.Handler` + `collections.deque(maxlen=100)`.

```python
import collections
import html
import logging

class RingBufferLogHandler(logging.Handler):
    """In-memory ring buffer log handler with fixed capacity."""

    def __init__(self, capacity: int = 100):
        super().__init__()
        self.buffer = collections.deque(maxlen=capacity)

    def emit(self, record: logging.LogRecord) -> None:
        try:
            msg = self.format(record)
            self.buffer.append({
                "level": record.levelname,
                "msg": msg,
                "created": record.created,
            })
        except Exception:
            self.handleError(record)

    def get_logs(self, limit: int = 25, errors_only: bool = False) -> list[str]:
        records = list(self.buffer)
        if errors_only:
            records = [r for r in records if r["level"] in ("WARNING", "ERROR", "CRITICAL")]
        selected = records[-limit:]
        return [html.escape(r["msg"]) for r in selected]
```

---

## Metadata

**Analog search scope:** `src/`, `tests/`  
**Files scanned:** 18  
**Pattern extraction date:** 2026-10-25  
