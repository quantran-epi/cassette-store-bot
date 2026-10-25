# Phase 5: Role-Based Access Control & Telegram Admin Suite - Research

**Researched:** 2026-10-25
**Domain:** Telegram Bot Role-Based Access Control, In-Memory Ring Buffer Logging, Dynamic Settings Persistence, PTB Interactive Admin Dashboard
**Confidence:** HIGH

## Executive Summary

Phase 5 introduces a 2-tier administrative security model (`SUPER_ADMIN` and `ADMIN`) alongside an interactive Telegram `/admin` suite and an in-memory logging viewer `/logs`. The primary goal is enabling merchants and operational administrators to monitor bot health, manage the access whitelist dynamically, and hot-swap the 9router LLM model with pre-flight reachability checks—all without touching terminal sessions or SSH.

The foundation built in Phases 1–4 provides asynchronous SQLite via `aiosqlite` with WAL mode, python-telegram-bot v22.8 handlers, and Pydantic-based settings. Phase 5 extends this foundation by:
1. Hardening access control through a layered `@require_role` decorator enforcing permissions on both slash commands and `CallbackQuery` events.
2. Persisting dynamic system settings and administrative roles into SQLite (`admin_users` and `system_settings` tables) while maintaining the `.env` `TELEGRAM_SUPER_ADMIN_ID` as an immutable root authority to prevent accidental lockout.
3. Decoupling active LLM runtime configurations from static environment variables by storing the active model in `context.bot_data["active_model_id"]` and testing new candidate models with a 1-token reachability probe prior to activation.
4. Implementing a thread-safe in-memory `logging.Handler` backed by `collections.deque` (max capacity 50–100 records) to render sanitized, HTML-escaped log streams on demand via `/logs`.

**Primary recommendation:** Use `functools.wraps` for the `@require_role` decorator to inspect `context.bot_data["admin_roles"]` (cached from SQLite `admin_users`), fallback to DB if cache misses, and protect root Super Admin from deletion at both UI and service/database layers.

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

#### 1. Bố cục Menu Admin (Admin Suite Layout & UX)
- **D-01:** Truy cập menu quản trị thông qua lệnh gõ `/admin`, giữ nguyên bàn phím Reply Keyboard 2x2 cố định cho việc bán hàng gọn gàng và tránh thao tác nhầm lẫn.
- **D-02:** Tin nhắn phản hồi `/admin` hiển thị ngay Dashboard tổng quan trạng thái hệ thống (Uptime bot, trạng thái SQLite DB & WAL size, kết nối 9router & model_id đang dùng, số đơn hôm nay) kèm các nút Inline chức năng bên dưới.
- **D-03:** Bố trí nút Inline menu admin dạng lưới 2 cột trực quan:
  - Hàng 1: `[👥 Quản lý Whitelist]` `[🤖 Đổi Model LLM]`
  - Hàng 2: `[📜 Xem Logs]` `[💾 Sao lưu DB]`
  - Hàng 3: `[🔄 Làm mới]` `[❌ Đóng menu]`
- **D-04:** Điều hướng trong menu admin sử dụng cơ chế `edit_message_text` trực tiếp trên tin nhắn hiện tại kèm nút `[⬅️ Quay lại]` để giữ khung chat sạch sẽ, không tạo tin nhắn rác.

#### 2. Quản trị Whitelist (Whitelist CRUD UX & Sync)
- **D-05:** Giao diện danh sách Whitelist hiển thị chi tiết: Telegram User ID, Tên gợi nhớ/ghi chú, Vai trò (`👑 SUPER_ADMIN` / `🛡️ ADMIN` / `👤 STAFF`), kèm nút chọn xem/thao tác từng ID và nút `[➕ Thêm ID]`.
- **D-06:** Quy trình thêm người dùng mới: Chờ admin gửi tin nhắn chứa Telegram User ID (và tuỳ chọn Tên) với timeout 60 giây và nút `[❌ Huỷ]`, sau đó hiển thị nút chọn role `[🛡️ Admin]` hoặc `[👤 Nhân viên]`.
- **D-07:** Xoá hoặc hạ quyền người dùng khỏi Whitelist bắt buộc qua thẻ xác nhận 2 bước với 2 nút `[⚠️ Xác nhận xoá]` và `[Quay lại]` để chống bấm nhầm.
- **D-08:** Quản lý danh sách trong bảng SQLite `admin_users`. Khi khởi động bot, tự động đồng bộ `TELEGRAM_SUPER_ADMIN_ID` và `TELEGRAM_WHITELIST_USER_IDS` từ `.env` vào DB nếu chưa tồn tại. Khi thêm/xoá trên Telegram, cập nhật đồng thời cả DB và `context.bot_data["whitelist_user_ids"]` để có hiệu lực tức thì.

#### 3. Đổi Model LLM & Reachability Testing (Model Switcher)
- **D-09:** Menu đổi model hỗ trợ lưu danh sách model phổ biến khả dụng (vd: `gpt-4o-mini`, `gpt-4o`, `claude-3-5-haiku`, `gemini-1.5-flash`), chọn nhanh 1-chạm (đánh dấu `[✓]` ở model đang active) kèm nút `[✏️ Nhập tên khác]` cho phép nhập tự do tên model_id từ 9router.
- **D-10:** Cơ chế Reachability Probe: Trước khi lưu và áp dụng model mới, bot tự động gửi một test call siêu nhẹ (completion prompt 1 token) đến 9router. Nếu nhận phản hồi HTTP 200 OK mới lưu và áp dụng; nếu gặp lỗi (401/404/500/timeout) giữ nguyên model cũ và thông báo lỗi chi tiết cho admin.
- **D-11:** Cấu hình bền vững: Lưu model active và danh sách model khả dụng vào bảng `system_settings` trong SQLite. Khởi động bot ưu tiên nạp từ DB, nếu chưa có mới fallback sang `.env` (`NINE_ROUTER_MODEL_ID`).
- **D-12:** Khi admin nhập một model mới qua text và probe thành công, hệ thống tự động lưu model đó vào danh sách chọn nhanh trong DB để tái sử dụng; trong menu có nút `[🗑️ Xoá khỏi danh sách]` để dọn bớt model không dùng.

#### 4. Phân cấp Quyện hạn & Bảo vệ Root (Role Hierarchy & Root Protection)
- **D-13:** Phân định 2 vai trò quản trị:
  - `SUPER_ADMIN`: Toàn quyền hệ thống (xem dashboard, quản lý admin khác, đổi model LLM, xem logs `/logs`, kích hoạt sao lưu `/backup`).
  - `ADMIN`: Quản lý nghiệp vụ (xem dashboard, quản lý nhân viên bán hàng Staff trong whitelist, đổi model LLM). Không có quyền quản lý Admin khác, không xem được `/logs`, không được kích hoạt sao lưu `/backup`.
- **D-14:** Decorator phân quyền `@require_role(role)` bảo vệ mọi lệnh slash và callback queries. Khi vi phạm quyền hạn: với CallbackQuery hiển thị Telegram Alert pop-up (`show_alert=True`), với lệnh gõ gửi tin nhắn từ chối lịch sự, nêu rõ thẩm quyền yêu cầu.
- **D-15:** Chống tự khoá Root Super Admin: Nhận diện `TELEGRAM_SUPER_ADMIN_ID` cấu hình trong `.env`; ẩn hoàn toàn nút xoá/hạ quyền trên UI và chặn cứng ở tầng DB/Service (ném ngoại lệ bảo vệ nếu có request can thiệp).
- **D-16:** Lệnh xem nhật ký `/logs` cho Super Admin: Đọc ring buffer (25-50 dòng log gần nhất trong bộ nhớ) định dạng HTML `<pre><code>...</code></pre>`, kèm các nút Inline tiện ích: `[25 dòng]`, `[50 dòng]`, `[⚠️ Chỉ Lỗi]`, `[🔄 Làm mới]`.

### Claude's Discretion
- Định dạng chuỗi tin nhắn HTML cho Dashboard trạng thái hệ thống.
- Cấu trúc chi tiết bảng SQLite `admin_users` và `system_settings`.
- Cấu hình Logging Ring Buffer handler (sử dụng `logging.Handler` chuẩn Python kết hợp `collections.deque` thread-safe).

### Deferred Ideas (OUT OF SCOPE)
None — discussion stayed within phase scope.
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| **RBAC-01** | Hệ thống lưu trữ danh sách quản trị viên trong bảng `admin_users` với 2 cấp độ: `SUPER_ADMIN` và `ADMIN`, neo cứng `SUPER_ADMIN_ID` gốc trong cấu hình `.env` để chống tự khoá | Schema design for `admin_users` with role enumeration, sync logic during startup, and immutable root guard in `src/bot/security.py` |
| **RBAC-02** | Decorator phân quyền `@require_role` kiểm soát chặt chẽ cả lệnh gõ (`/admin`, `/backup`, `/logs`) lẫn các nút bấm `CallbackQuery` để chống leo thang đặc quyền | Pattern for async decorator supporting dual-dispatch (Message vs CallbackQuery with `show_alert=True`) and hierarchy check |
| **RBAC-03** | Quản trị viên có thể mở menu `/admin` trên Telegram để xem trạng thái hệ thống (bot, DB, LLM) và cấu hình chuyển đổi model LLM 9router trực tiếp | Interactive `/admin` handler with `edit_message_text`, system probe functions (DB WAL size, uptime, active model), and model picker with reachability check |
| **RBAC-04** | Quản trị viên trên Telegram có thể quản lý whitelist người dùng (xem danh sách, thêm mới, xoá Telegram ID khỏi whitelist) với hiệu lực tức thì | Whitelist CRUD flows with pagination, 60s text input state, 2-phase deletion confirmation, and immediate `context.bot_data["whitelist_user_ids"]` sync |
| **RBAC-05** | Super Admin có thể xem log gần nhất qua lệnh `/logs` (ring buffer 25-50 dòng định dạng `<pre>` HTML) trực tiếp trên Telegram mà không cần truy cập terminal | Thread-safe `RingBufferLogHandler(logging.Handler)` attached to root logger, escaping HTML tags, and chunking within Telegram 4096 character limits |
</phase_requirements>

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Access Gate & Role Verification | Bot Security Gate (`group=-1`) & Decorator (`@require_role`) | Database (`admin_users`) | Group -1 blocks unwhitelisted IDs immediately. Decorators verify permissions in-memory (`bot_data["admin_roles"]`) for fast response with zero DB roundtrips. |
| Root Super Admin Protection | Bot Security Service (`src/bot/security.py`) | Database (`admin_users`) | Code-level assertion checking `settings.telegram_super_admin_id` prevents modification even if database records are manipulated. |
| Admin Suite Navigation & UI | Bot Handlers (`src/bot/handlers/admin.py`) | Telegram Client (PTB) | State transitions handled via `edit_message_text` to keep user chat uncluttered. |
| LLM Reachability Probe | Service (`src/services/llm_probe.py`) | OpenAI Gateway (9router) | Isolates network ping (1-token completion) from Telegram UI logic, with strict 5.0s timeout. |
| System Health Metrics | Bot Utilities (`src/bot/handlers/admin.py`) | OS & SQLite Engine | Reads DB file size, `-wal` size via `os.path.getsize`, bot uptime via process start timestamp. |
| In-Memory Log Buffering | Standard Library (`logging.Handler`) | Telegram Message Formatter | `collections.deque` buffers log records in RAM with zero disk I/O; formatted to HTML `<pre>` when requested. |
| Whitelist & Settings Persistence | Database (`src/db/admin.py` & `src/db/settings.py`) | In-Memory Cache (`bot_data`) | Dual-write ensures immediate operational effect and survival across bot restarts. |

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| **python-telegram-bot** | `~=22.8` [VERIFIED: npm/pypi] | Telegram Bot Framework | Already in project; provides `CallbackQueryHandler`, `CommandHandler`, `ApplicationHandlerStop`. |
| **aiosqlite** | `~=0.22.1` [VERIFIED: pypi] | Async SQLite client | Already in project; handles async transactions and WAL checkpoints for admin/settings tables. |
| **pydantic-settings** | `~=2.16.1` [VERIFIED: pypi] | Settings management | Validates `telegram_super_admin_id` and environment configuration. |
| **openai** | `~=3.37.0` [VERIFIED: pypi] | 9router client | Provides `chat.completions.create` for low-latency reachability probe. |

### Supporting (Standard Library)
| Library / Module | Purpose | When to Use |
|------------------|---------|-------------|
| **collections.deque** | Fixed-size ring buffer | In-memory log buffer (`maxlen=100`) with thread-safe append and atomic eviction. |
| **logging.Handler** | Custom log stream sink | Attaches directly to root logger to intercept all system warnings and errors. |
| **html.escape** | HTML sanitization | Sanitizes log lines before wrapping in `<pre><code>` to prevent Telegram HTML parse errors. |
| **os.path** | Filesystem metrics | Queries `.db` and `-wal` file sizes for system status dashboard. |
| **time / datetime** | Uptime & timeout calculations | Measures bot process uptime and manages 60s input expiry. |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| `collections.deque` logging handler | Parsing disk log files (`tail -n 50`) | Disk files may not exist in container environments without persistent volume logging; `deque` is zero-I/O and cross-platform. |
| `edit_message_text` for navigation | Sending new messages for each menu | Clutters chat history and confuses users; `edit_message_text` keeps a single, clean dashboard. |
| In-memory `bot_data` cache | Querying SQLite on every single callback | SQLite is fast, but in-memory `bot_data` sets avoid thread-pool scheduling overhead on frequent user actions. |

## Package Legitimacy Audit

No new third-party packages are required for Phase 5. All requirements are implemented using already-installed libraries (`python-telegram-bot`, `aiosqlite`, `pydantic-settings`, `openai`) and Python standard library modules (`collections`, `logging`, `html`, `os`, `time`).

| Package | Registry | Installed Version | Status | Disposition |
|---------|----------|-------------------|--------|-------------|
| `python-telegram-bot` | PyPI | 22.8 | Existing | Approved |
| `aiosqlite` | PyPI | 0.22.1 | Existing | Approved |
| `openai` | PyPI | 3.37.0 | Existing | Approved |
| `pydantic-settings` | PyPI | 2.16.1 | Existing | Approved |

## Architecture Patterns

### System Architecture Diagram

```
[Telegram User Action]
         │
         ▼
┌────────────────────────────────────────────────────────┐
│ Group -1: whitelist_gate                               │
│ - Checks user_id in bot_data["whitelist_user_ids"]     │
│ - Rejects strangers immediately                        │
└───────────────────────┬────────────────────────────────┘
                        │ Allowed
                        ▼
┌────────────────────────────────────────────────────────┐
│ Group 0: Handler Dispatch                              │
│                                                        │
│  /admin, /logs, /backup, callbacks: "adm:*"            │
└───────────────────────┬────────────────────────────────┘
                        │
                        ▼
┌────────────────────────────────────────────────────────┐
│ @require_role(Role.ADMIN | Role.SUPER_ADMIN)           │
│ - Resolves role: bot_data["admin_roles"].get(user_id)  │
│ - Denies lower tier:                                   │
│     • CallbackQuery: query.answer(alert, show_alert)   │
│     • Message: reply_text("⛔ Quyền hạn không đủ...")  │
└───────────────────────┬────────────────────────────────┘
                        │ Authorized
                        ▼
┌────────────────────────────────────────────────────────┐
│ Admin Handlers (src/bot/handlers/admin.py)             │
│                                                        │
│ ├── Dashboard: Uptime, DB WAL size, active LLM model   │
│ ├── Whitelist CRUD: View, Add (60s prompt), Remove (2-step)│
│ ├── LLM Switcher: Probe 1-token test call to 9router   │
│ └── Logs Viewer: Fetch formatted lines from RingBuffer │
└───────────────────────┬────────────────────────────────┘
                        │
         ┌──────────────┴──────────────┐
         ▼                             ▼
┌─────────────────────────┐   ┌──────────────────────────┐
│ In-Memory bot_data &    │   │ SQLite Database          │
│ collections.deque       │   │ - admin_users            │
│ (Instant read cache &   │   │ - system_settings        │
│ thread-safe log buffer) │   │ (WAL mode persistence)   │
└─────────────────────────┘   └──────────────────────────┘
```

### Component Structure
```
src/
├── config.py                 # Added: telegram_super_admin_id (int | None)
├── db/
│   ├── schema.py             # DDL: admin_users, system_settings
│   ├── admin.py              # Queries: admin_users CRUD & sync logic
│   └── settings.py           # Queries: system_settings key-value store
├── bot/
│   ├── security.py           # Added: Role enum, @require_role, root guard
│   ├── logging_handler.py    # RingBufferLogHandler backed by collections.deque
│   ├── keyboards.py          # Admin keyboard builders (dashboard, whitelist, model)
│   ├── handlers/
│   │   ├── admin.py          # /admin, callbacks, whitelist CRUD, model switch
│   │   └── logs.py           # /logs command and filtering callbacks
│   └── app.py                # Registration of admin handlers & log handler init
└── services/
    └── llm_probe.py          # 1-token probe test call to 9router
```

### Pattern 1: Multi-Tier Access Control Decorator (`@require_role`)

**What:** An asynchronous decorator supporting both message commands (`/admin`, `/logs`, `/backup`) and callback queries (`adm:*`). Inspects role hierarchy (`SUPER_ADMIN` > `ADMIN` > `STAFF`).
**When to use:** Every administrative slash command and every administrative inline button callback.

```python
import functools
from enum import StrEnum
from telegram import Update
from telegram.ext import ContextTypes

class UserRole(StrEnum):
    SUPER_ADMIN = "SUPER_ADMIN"
    ADMIN = "ADMIN"
    STAFF = "STAFF"

ROLE_HIERARCHY = {
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

            # Check if user meets hierarchy requirement
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

### Pattern 2: Immutable Root Protection & Whitelist Synchronization

**What:** On application startup, ensure the root Super Admin from `.env` is guaranteed in the database and in-memory structures. At runtime, strictly reject deletion or demotion of this ID.
**When to use:** During `build_application` startup and inside whitelist removal/demotion handlers.

```python
async def remove_user_from_whitelist(
    db: aiosqlite.Connection,
    target_id: int,
    super_admin_id: int | None,
) -> bool:
    """Safely remove a user from whitelist, strictly protecting root Super Admin."""
    if super_admin_id is not None and target_id == super_admin_id:
        raise PermissionError("Cannot remove or demote the root Super Admin configured in .env")

    await db.execute("DELETE FROM admin_users WHERE telegram_id = ?", (target_id,))
    await db.commit()
    return True
```

### Pattern 3: Reachability Probe for Dynamic Model Switching

**What:** A lightweight completion request (1 max token) executed before updating the active model in database or runtime state.
**When to use:** Whenever an admin selects a model or inputs a custom model string.

```python
from openai import AsyncOpenAI

async def probe_model_reachability(
    client: AsyncOpenAI,
    candidate_model: str,
    timeout: float = 5.0,
) -> tuple[bool, str]:
    """Test candidate model with a 1-token probe. Returns (success, detail_message)."""
    try:
        response = await client.chat.completions.create(
            model=candidate_model,
            messages=[{"role": "user", "content": "hi"}],
            max_tokens=1,
            timeout=timeout,
        )
        return True, "Kết nối thành công (HTTP 200 OK)"
    except Exception as exc:
        return False, f"Lỗi phản hồi: {exc}"
```

### Pattern 4: Thread-Safe In-Memory Logging Ring Buffer

**What:** A custom `logging.Handler` backed by `collections.deque(maxlen=100)` storing formatted log entries with HTML sanitization.
**When to use:** Capturing bot events at runtime for on-demand inspection via `/logs`.

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

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| In-memory log buffer | Custom list with lock primitives and manual slicing | `collections.deque(maxlen=N)` | Built-in C implementation, atomic O(1) appends, thread-safe for GIL-bound operations, automatic FIFO eviction. |
| Role hierarchy comparisons | Nested `if/else` ladders across handlers | Standard `Enum` with rank mapping dictionary | Eliminates privilege escalation bugs; allows single-line `@require_role(UserRole.ADMIN)` checks. |
| Telegram HTML formatting | Custom string replacing for `<`, `>`, `&` | `html.escape()` from standard library | Prevents broken Telegram HTML entities and silent message delivery failures. |
| Database size calculation | Custom raw byte counters | `os.path.getsize(db_path)` and `os.path.getsize(wal_path)` | Accurate at the filesystem level, handles missing WAL files gracefully. |

## Common Pitfalls

### Pitfall 1: Silent Callback Failures When Role Check Fails
**What goes wrong:** Admin clicks a button, permission fails, but handler simply returns without calling `query.answer()`. The user's Telegram client displays a persistent loading spinner.
**Why it happens:** In PTB, every `CallbackQuery` requires an `answer()` call within ~10 seconds.
**How to avoid:** The `@require_role` decorator must call `await update.callback_query.answer("⛔ Quyền hạn không đủ", show_alert=True)` before returning.

### Pitfall 2: Telegram Message Length Exceeded on `/logs`
**What goes wrong:** A burst of 50 log lines with stack traces exceeds Telegram's 4096-character limit, throwing `telegram.error.BadRequest: Message is too long`.
**Why it happens:** Log messages and Python tracebacks are verbose.
**How to avoid:** Measure rendered text before sending. If length > 3800 characters, truncate earlier lines and prepend `... (đã cắt bớt các dòng cũ)\n`.

### Pitfall 3: State Divergence Between Database and In-Memory Cache
**What goes wrong:** Admin adds a user via `/admin`, SQLite record is created, but `context.bot_data["whitelist_user_ids"]` is not updated. The new user continues to be blocked by `whitelist_gate` until bot reboot.
**Why it happens:** Dual-layer architecture without atomic sync.
**How to avoid:** Encapsulate whitelist modifications in a service method that updates both SQLite and `context.bot_data` simultaneously.

### Pitfall 4: Root Super Admin Lockout
**What goes wrong:** Super Admin accidentally clicks delete on their own ID in the whitelist UI, leaving the bot with no administrator.
**Why it happens:** Whitelist deletion logic treating all user IDs identically.
**How to avoid:** Never render delete buttons for `TELEGRAM_SUPER_ADMIN_ID`. Enforce a hard guard at the service layer that raises an error if an attempt is made to delete the root ID.

## Database Schema Design

### Table: `admin_users`
```sql
CREATE TABLE IF NOT EXISTS admin_users (
    telegram_id INTEGER PRIMARY KEY,
    name TEXT NOT NULL DEFAULT '',
    role TEXT NOT NULL CHECK (role IN ('SUPER_ADMIN', 'ADMIN', 'STAFF')),
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);
```

### Table: `system_settings`
```sql
CREATE TABLE IF NOT EXISTS system_settings (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL,
    description TEXT NOT NULL DEFAULT '',
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);
```

Default settings keys:
- `active_model_id`: Current active LLM model (e.g., `"gpt-4o-mini"`).
- `available_models`: JSON array of selectable models (e.g., `'["gpt-4o-mini", "gpt-4o", "claude-3-5-haiku", "gemini-1.5-flash"]'`).

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Python | Runtime | ✓ | 3.13.7 | — |
| python-telegram-bot | Bot framework | ✓ | 22.8 | — |
| aiosqlite | Database | ✓ | 0.22.1 | — |
| openai | LLM & probe | ✓ | 3.37.0 | — |
| pytest | Test execution | ✓ | 9.1.1 | — |

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest 9.1.1 + pytest-asyncio 1.4.0 |
| Config file | `pyproject.toml` |
| Quick run command | `.venv/bin/pytest tests/test_security.py` |
| Full suite command | `.venv/bin/pytest` |

### Phase Requirements → Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| **RBAC-01** | `admin_users` table creation, root sync, and immutable root guard | unit/integration | `.venv/bin/pytest tests/test_admin_db.py` | ❌ Wave 0 Gap |
| **RBAC-02** | `@require_role` dual-dispatch (commands & callbacks) + hierarchy enforcement | unit | `.venv/bin/pytest tests/test_security_rbac.py` | ❌ Wave 0 Gap |
| **RBAC-03** | `/admin` dashboard display & dynamic model switcher with probe | unit/e2e | `.venv/bin/pytest tests/test_admin_handlers.py` | ❌ Wave 0 Gap |
| **RBAC-04** | Whitelist CRUD: add, remove, and sync with `bot_data` | integration | `.venv/bin/pytest tests/test_admin_whitelist.py` | ❌ Wave 0 Gap |
| **RBAC-05** | `/logs` ring buffer retrieval, filtering, and HTML escaping | unit | `.venv/bin/pytest tests/test_logging_buffer.py` | ❌ Wave 0 Gap |

### Sampling Rate
- **Per task commit:** Run focused module test (e.g. `.venv/bin/pytest tests/test_security_rbac.py`)
- **Per wave merge:** Run full test suite (`.venv/bin/pytest`)
- **Phase gate:** All 110 existing tests + new Phase 5 tests green before completion.

### Wave 0 Gaps
- [ ] `tests/test_admin_db.py` — Verifies `admin_users` and `system_settings` persistence and root sync.
- [ ] `tests/test_security_rbac.py` — Tests `@require_role` decorator behavior on messages and callbacks.
- [ ] `tests/test_logging_buffer.py` — Tests `RingBufferLogHandler` capacity, filtering, and HTML escaping.

## Security Domain

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | Yes | Whitelist gate running at group -1; verification of Telegram effective user ID. |
| V3 Session Management | Yes | Stateless role verification from cached dictionary; 60-second TTL on conversational input. |
| V4 Access Control | Yes | `@require_role` decorator on all `/admin` routes and callbacks; root Super Admin protected from demotion. |
| V5 Input Validation | Yes | Regex validation on user input Telegram IDs and model name strings; HTML escaping on log output. |

### Known Threat Patterns

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Privilege Escalation via Callback Tampering | Elevation of Privilege | Server-side validation of role in `@require_role` on EVERY callback query. Never trust client state. |
| Root Admin Lockout | Denial of Service | Hard-coded code check preventing deletion or demotion of `TELEGRAM_SUPER_ADMIN_ID`. |
| Log Injection / HTML Breakage | Tampering | Strict `html.escape()` of all log messages before Telegram formatting. |
| LLM Gateway Disruption via Bad Model Name | Denial of Service | Pre-flight 1-token reachability probe before committing model switch to database or memory. |

## Sources

### Primary (HIGH confidence)
- Codebase inspection: `src/bot/security.py`, `src/bot/app.py`, `src/config.py`, `src/db/schema.py`
- Project guidelines: `CLAUDE.md`, `.planning/PROJECT.md`, `.planning/REQUIREMENTS.md`
- python-telegram-bot v22.8 documentation for `CallbackQueryHandler`, `TypeHandler`, and `ApplicationHandlerStop`

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — relies 100% on existing installed packages
- Architecture: HIGH — aligns with established async patterns in codebase
- Pitfalls: HIGH — covers all edge cases identified in context discussions

**Research date:** 2026-10-25
**Valid until:** 2026-11-25
