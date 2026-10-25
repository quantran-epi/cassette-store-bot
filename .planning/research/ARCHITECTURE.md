# Architecture Research: Milestone v1.1 Integration

**Domain:** Telegram Retail Order Management Chatbot (Small Low-Tech Merchant)  
**Milestone:** v1.1 NL Order Mutation, Console Admin, RBAC & GitHub Backup  
**Researched:** 2026-10-25  
**Confidence:** HIGH  

---

## Standard Architecture

### System Overview

```
┌─────────────────────────────────────────────────────────────────────────────────────────────────┐
│                                   Presentation & Interface Layer                                │
├───────────────────────────────────────────────┬─────────────────────────────────────────────────┤
│  Telegram Bot (python-telegram-bot v20+)       │  Interactive Server Console (Terminal TTY)       │
│  ├─ Security Gate (Group -1: RBAC Middleware) │  ├─ Non-blocking stdin reader (asyncio.to_thread)│
│  ├─ Free-Text & Photo Message Handlers        │  ├─ System Status & Metrics Monitor             │
│  ├─ Natural Language Router (3-Way Dispatch)  │  ├─ Dynamic Admin & Whitelist Manager           │
│  ├─ 2-Phase Confirmation Callback Handlers    │  ├─ Manual GitHub Backup Trigger                │
│  └─ Ergonomic Keyboards & CopyTextButtons     │  └─ Headless auto-detection (isatty check)      │
├───────────────────────────────────────────────┴─────────────────────────────────────────────────┤
│                                  Core Application Services Layer                                │
├────────────────────────────────┬───────────────────────────────┬────────────────────────────────┤
│  Intent Router & Extraction    │  RBAC & Security Service      │  GitHub Backup Service         │
│  ├─ Intent Classifier (3-Way)  │  ├─ Roles (SUPER_ADMIN/ADMIN) │  ├─ VACUUM INTO atomic snapshot│
│  ├─ Order Target Resolver      │  ├─ Super Admin Bootstrap     │  ├─ Gzip compression pipeline  │
│  ├─ LLM Mutation Extractor     │  ├─ RBAC Enforcement (Decor.) │  ├─ httpx Async GitHub REST API│
│  └─ Visual Diff Card Formatter │  └─ In-Memory Role Cache      │  └─ Background Async Scheduler │
├────────────────────────────────┴───────────────────────────────┴────────────────────────────────┤
│                                   Persistence & Storage Layer                                   │
├─────────────────────────────────────────────────────────────────────────────────────────────────┤
│  aiosqlite Connection Pool (WAL Mode, PRAGMA busy_timeout=5000, unaccent function)              │
│  ├─ orders table (Order lifecycle, tracking, snapshots, customer FK)                            │
│  ├─ customers table (Multi-phone, multi-address, notes, history)                                │
│  └─ admin_users table (Telegram ID, Role: SUPER_ADMIN | ADMIN, name, audit log)                 │
└─────────────────────────────────────────────────────────────────────────────────────────────────┘
```

---

### Component Responsibilities

| Component | Responsibility | Status | Implementation Details |
|-----------|----------------|--------|------------------------|
| **Interactive Console App** | Provides direct server-side operator control without Telegram dependency. Runs concurrently with bot polling. | **NEW** | Async lifecycle in `main.py`, reading `sys.stdin` via `asyncio.to_thread`. Auto-detects headless mode via `sys.stdin.isatty()`. |
| **3-Way Intent Router** | Classifies incoming chat into Mutation, Search, or New Ingestion. Prevents mutation collisions with order creation. | **NEW** | Pattern & keyword heuristic classifier in `src/services/router.py`, routing to search, mutation, or ingest handlers. |
| **NL Order Mutation Service** | Resolves target orders, extracts field changes via LLM structured output, and coordinates 2-phase visual diff confirmation. | **NEW** | `src/services/order_mutation.py` using `OrderMutationDelta` Pydantic model + 9router LLM gateway. |
| **RBAC Manager** | Enforces two-tier authority (`SUPER_ADMIN` vs `ADMIN`). Persists admin roles, manages bootstrap from `.env`, exposes decorators. | **NEW** | `src/bot/rbac.py` + `admin_users` table in SQLite + `@require_role` decorators for handlers. |
| **GitHub Backup Service** | Takes safe, consistent snapshots of SQLite WAL database and uploads gzipped backups to GitHub repository. | **NEW** | `src/services/backup.py` using `VACUUM INTO`, gzip, and `httpx.AsyncClient` against GitHub REST API. |
| **Background Scheduler** | Drives periodic backup tasks without requiring heavy external cron or APScheduler dependencies. | **NEW** | Native `asyncio.create_task` loop with cancellation handling tied to application lifecycle. |
| **Telegram Ingest & Search** | Existing v1.0 handlers for order creation, photo batching, and text-to-SQL search. | **MODIFIED** | Updated to delegate routing decisions to 3-Way Intent Router instead of assuming all non-search text is a new order. |
| **Security Gate (`whitelist_gate`)** | Group -1 filter intercepting every Telegram update. | **MODIFIED** | Upgraded from static `.env` list to dynamic `admin_users` database table with memory caching. |
| **Database Schema & Factory** | Manages SQLite connection lifecycle, WAL settings, custom functions, and schema migrations. | **MODIFIED** | Added `admin_users` table and migration helpers in `src/db/schema.py`. |

---

## Recommended Project Structure

```
src/
├── __init__.py
├── config.py                     # Pydantic Settings (GitHub token, Super Admin ID, 9router, DB path)
│
├── bot/                          # Telegram Presentation Layer
│   ├── __init__.py
│   ├── app.py                   # ApplicationBuilder, lifecycle hooks, handler registration
│   ├── keyboards.py             # Markup builders (Visual diff confirmation, Admin menu, 1-tap copy)
│   ├── formatters.py            # HTML card formatters (Order cards, Mutation diffs, Backup alerts)
│   ├── rbac.py                  # [NEW] RBAC decorators (@require_role), permission checks, role enum
│   └── handlers/
│       ├── __init__.py
│       ├── base.py              # /start, /ping, /help
│       ├── callbacks.py         # Order creation callbacks (ord:cf, ord:ca, ord:ad)
│       ├── ingest.py            # Free-text & photo ingestion handler
│       ├── order_actions.py     # Status transitions, tracking code prompt
│       ├── orders.py            # Menu reply buttons, navigation callbacks
│       ├── search.py            # Natural language order search & Text-to-SQL
│       ├── mutation.py          # [NEW] NL order mutation callback handlers & diff confirmation
│       └── admin.py             # [NEW] /admin commands (list, add, remove, backup) for Super Admin
│
├── console/                      # [NEW] Interactive Server Console CLI
│   ├── __init__.py
│   ├── cli.py                   # Terminal interactive loop, non-blocking input, menu dispatch
│   └── commands.py              # CLI commands: status, admin management, manual backup, order inspect
│
├── services/                     # Business Logic & External Integrations
│   ├── __init__.py
│   ├── extractor.py             # LLM order extraction (9router gateway)
│   ├── order_search.py          # NL text-to-SQL order search
│   ├── router.py                # [NEW] 3-Way Intent Classifier (MUTATION | SEARCH | CREATE)
│   ├── order_mutation.py        # [NEW] NL mutation pipeline, target resolver, LLM delta extractor
│   ├── backup.py                # [NEW] SQLite VACUUM INTO + gzip + GitHub REST API client
│   └── scheduler.py             # [NEW] Async background periodic scheduler for automated backups
│
├── models/                       # Pydantic Schemas & Domain Enums
│   ├── __init__.py
│   ├── customer.py              # Customer domain model
│   ├── order.py                 # Order domain model, OrderStatus enum
│   ├── extractor.py             # ExtractedOrder, ExtractedSearch schemas
│   ├── mutation.py              # [NEW] OrderMutationDelta, MutationAction schemas
│   └── rbac.py                  # [NEW] Role enum (SUPER_ADMIN, ADMIN), AdminUser schema
│
└── db/                           # Persistence Layer
    ├── __init__.py
    ├── connection.py            # aiosqlite connection factory (WAL, busy_timeout, unaccent)
    ├── schema.py                # DDL schema (customers, orders, admin_users)
    ├── customers.py             # Customer queries
    ├── orders.py                # Order queries & status updates
    ├── admin_users.py           # [NEW] Admin user CRUD, role updates, whitelist synchronization
    └── backup_ops.py            # [NEW] VACUUM INTO execution wrapper
```

### Structure Rationale

- **`src/console/` decoupled from Telegram:** Server terminal management logic runs independently. It accesses `src/db/` and `src/services/` directly, meaning the console operates even if Telegram connectivity is impaired.
- **`src/services/router.py` centralizes intent dispatch:** Prevents scattered regex rules across `ingest.py` and `search.py`. Router decides intent before passing text to specific pipelines.
- **`src/services/backup.py` isolated from bot runtime:** The backup engine (SQLite VACUUM + GitHub REST API) is callable from both the automated async scheduler, the Telegram `/backup` handler, and the Console CLI.
- **`src/bot/rbac.py` single source of authority:** Unifies role checking for Telegram handlers, callback queries, and command dispatch.

---

## Architectural Patterns

### Pattern 1: Non-Blocking Console Loop within Asyncio Lifecycle

**What:** Run an interactive server terminal menu concurrently with python-telegram-bot's long-polling loop inside the same asyncio event loop without freezing update processing or crashing on headless environments.  
**When to use:** Server-side administration for operators who want local control without sending Telegram messages.  
**Trade-offs:** Reading `sys.stdin` via `input()` blocks the Python thread. Using `asyncio.to_thread` moves blocking I/O off the main event loop thread. Requires handling environments without a TTY (`sys.stdin.isatty() == False`).

**Implementation:**

```python
# main.py
import asyncio
import logging
import sys
from src.bot.app import build_application
from src.config import Settings
from src.console.cli import run_console
from src.db.connection import get_db_connection
from src.db.schema import init_db
from src.services.scheduler import start_backup_scheduler

logger = logging.getLogger(__name__)

async def main_async() -> None:
    settings = Settings()
    
    # 1. Initialize DB schema
    async with get_db_connection(settings.sqlite_db_path) as db:
        await init_db(db)
        
    # 2. Build PTB Application
    app = build_application(settings)
    
    # 3. Explicit Async Application Lifecycle (Replaces app.run_polling())
    async with app:
        await app.initialize()
        await app.start()
        await app.updater.start_polling(drop_pending_updates=True)
        logger.info("Telegram Bot polling started.")

        # 4. Start background backup scheduler
        stop_event = asyncio.Event()
        scheduler_task = asyncio.create_task(
            start_backup_scheduler(settings, stop_event)
        )

        # 5. Run Console if interactive TTY is available; else wait on stop_event
        if sys.stdin.isatty():
            logger.info("Interactive TTY detected. Launching Console CLI...")
            try:
                await run_console(app, settings, stop_event)
            except Exception:
                logger.exception("Console CLI terminated unexpectedly")
        else:
            logger.info("Non-interactive / daemon environment. Running headless...")
            await stop_event.wait()

        # 6. Graceful Shutdown
        stop_event.set()
        await scheduler_task
        await app.updater.stop()
        await app.stop()
        await app.shutdown()

def main() -> None:
    asyncio.run(main_async())
```

```python
# src/console/cli.py
import asyncio
import sys

async def read_input(prompt: str) -> str:
    """Read line from stdin in a background thread to prevent blocking event loop."""
    sys.stdout.write(prompt)
    sys.stdout.flush()
    return await asyncio.to_thread(sys.stdin.readline)

async def run_console(app, settings, stop_event: asyncio.Event) -> None:
    while not stop_event.is_set():
        print("\n=== CASSETTE STORE BOT - SERVER CONSOLE ===")
        print("1. Trạng thái hệ thống & DB")
        print("2. Quản lý Admin / Whitelist")
        print("3. Sao lưu DB lên GitHub ngay")
        print("4. Danh sách đơn hàng gần đây")
        print("0. Dừng bot & Thoát")
        
        choice = (await read_input("Chọn chức năng: ")).strip()
        if choice == "1":
            await handle_status(app, settings)
        elif choice == "2":
            await handle_admin_management(settings)
        elif choice == "3":
            await handle_manual_backup(settings)
        elif choice == "0":
            print("Đang dừng bot an toàn...")
            stop_event.set()
            break
```

---

### Pattern 2: 3-Way Intent Routing Pipeline (Collision Avoidance)

**What:** In incoming text processing, classify intent into **MUTATION**, **SEARCH**, or **CREATE** *before* triggering LLM extraction. This prevents mutation commands (e.g. "Đổi địa chỉ đơn anh Minh") from triggering the new order creation workflow or being misparsed by search.  
**When to use:** Every incoming free-text message in `handle_text_order`.  
**Trade-offs:** Adds a deterministic heuristic classification step. Guarantees 0-token cost for obvious intents and eliminates draft creation collisions.

```
Incoming Free-Text Message
           │
           ▼
┌──────────────────────────────────────┐
│ Active State Check in user_data?     │
│ (action_state, pending_mutation)     │
└──────────────────┬───────────────────┘
                   │ No
                   ▼
┌────────────────────────────────────────────────────────┐
│ Heuristic Intent Router (src/services/router.py)        │
│ 1. Mutation Pattern Match? (verbs + order cue/fields)  │
│ 2. Search Pattern Match? (is_search_intent)           │
│ 3. Fallback: New Order Creation                        │
└──────┬──────────────────────┬────────────────────┬─────┘
       │ MUTATION             │ SEARCH             │ CREATE
       ▼                      ▼                    ▼
┌──────────────────┐   ┌──────────────────┐  ┌──────────────────┐
│ Order Mutation   │   │ Text-to-SQL      │  │ Order Extractor  │
│ Pipeline         │   │ Search Handler   │  │ Preview Card     │
└──────────────────┘   └──────────────────┘  └──────────────────┘
```

#### Mutation Verbs & Keywords Heuristic

- **Action Verbs:** `sửa`, `đổi`, `chuyển`, `cập nhật`, `huỷ`, `bỏ`, `gán mã`, `thêm mã`, `hoàn`, `bom`, `đổi giá`, `sửa cod`, `đổi địa chỉ`, `đổi sđt`.
- **Target Identifiers:** `#\d+`, `đơn \d+`, `đơn vừa tạo`, `đơn mới nhất`, `đơn của <tên>`, or 10-digit phone number.
- **Target Fields:** `trạng thái`, `địa chỉ`, `sđt`, `ghi chú`, `mã vận đơn`, `cod`, `tiền`.

---

### Pattern 3: Five-Stage NL Order Mutation Pipeline

**What:** Complete flow from natural language command to verified database mutation with elderly-friendly visual diff confirmation.  
**Pipeline:** `Intent Classifier` → `Order Target Resolution` → `LLM Mutation Extractor` → `Confirmation Callback (2-Phase)` → `Atomic DB Update`.

```
Step 1: Intent Classifier (MUTATION detected)
   │
   ▼
Step 2: Order Target Resolution (Order Search)
   ├─ Extract target cue: ID (#105), phone (0901...), customer name, or recency ("đơn vừa tạo")
   ├─ Query SQLite DB for candidate orders:
   │    ├─ 0 candidates: Reply "Không tìm thấy đơn hàng cần sửa. Bác kiểm tra lại nhé."
   │    ├─ >1 candidates: Show interactive list of buttons: [Đơn #101] [Đơn #104]
   │    └─ 1 candidate: Lock target order record.
   │
   ▼
Step 3: LLM Mutation Extractor (Structured Delta)
   ├─ Send: Target Order JSON Snapshot + User Text to 9router
   ├─ Receive: Pydantic OrderMutationDelta
   │    {
   │      "order_id": 105,
   │      "status": "SHIPPER_DA_LAY",
   │      "tracking_code": "VN88291039",
   │      "shipping_address": null,
   │      "cod_amount": null
   │    }
   │
   ▼
Step 4: Interactive Confirmation Callback (Visual Diff Card)
   ├─ Generate Before/After HTML Diff
   ├─ Render Inline Keyboard: [✅ Xác nhận sửa | ❌ Huỷ]
   ├─ Cache pending delta in context.user_data[f"mut:{token}"] (TTL: 120s)
   │
   ▼
Step 5: Database Update & Audit
   ├─ User taps [✅ Xác nhận sửa]
   ├─ Execute atomic UPDATE on orders table
   ├─ If address/phone modified: sync customer record in customers table
   └─ Update message: "✅ Đã cập nhật thành công đơn hàng #105!"
```

#### Visual Diff Card Format

```html
✏️ <b>XÁC NHẬN SỬA ĐƠN HÀNG #105</b>
👤 <b>Khách hàng:</b> Nguyễn Văn An (<code>0901234567</code>)
────────────────────
🔄 <b>Nội dung thay đổi:</b>
• <b>Trạng thái:</b> ⏳ Chờ làm ➡️ 🚚 <b>Shipper đã lấy</b>
• <b>Mã vận đơn:</b> [Chưa có] ➡️ <code>VN88291039</code>
• <b>Địa chỉ:</b> <i>(Giữ nguyên)</i>
• <b>Tiền COD:</b> <i>(Giữ nguyên: 280.000 đ)</i>
────────────────────
Bác kiểm tra kỹ rồi bấm nút bên dưới nhé:
```

---

### Pattern 4: RBAC Hierarchy with In-Memory Cache & Super Admin Bootstrap

**What:** Two-tier permission model (`SUPER_ADMIN` vs `ADMIN`). Super Admin is bootstrapped from configuration and can manage other admins via Telegram or Console.  
**When to use:** Multi-user operations where shop staff can manage orders but must not add/remove admins or alter security whitelist.  
**Trade-offs:** Requires an `admin_users` table in SQLite. Keeping an in-memory `dict[int, str]` in `bot_data` guarantees zero database query latency on every Telegram request.

```sql
CREATE TABLE IF NOT EXISTS admin_users (
    telegram_id INTEGER PRIMARY KEY,
    role TEXT NOT NULL CHECK(role IN ('SUPER_ADMIN', 'ADMIN')),
    full_name TEXT NOT NULL DEFAULT '',
    added_by INTEGER,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);
```

#### Authority Matrix

| Capability | SUPER_ADMIN | ADMIN | Strangers |
|------------|:-----------:|:-----:|:---------:|
| Pass Security Gate (Group -1) | ✅ | ✅ | ❌ (Rejected) |
| Create / Ingest Orders | ✅ | ✅ | ❌ |
| Search & View Orders | ✅ | ✅ | ❌ |
| NL Order Mutation & Status Update | ✅ | ✅ | ❌ |
| Trigger Manual Backup (/backup) | ✅ | ✅ | ❌ |
| Add / Remove Admins (/admin add/rm) | ✅ | ❌ | ❌ |
| Promote / Demote Roles | ✅ | ❌ | ❌ |
| Access Server Console CLI | ✅ | N/A (Server access) | ❌ |

#### Handler Decorator Example

```python
# src/bot/rbac.py
from functools import wraps
from telegram import Update
from telegram.ext import ContextTypes
from src.models.rbac import Role

def require_role(min_role: Role):
    def decorator(func):
        @wraps(func)
        async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE, *args, **kwargs):
            user_id = update.effective_user.id
            roles: dict[int, str] = context.bot_data.get("user_roles", {})
            user_role = roles.get(user_id)
            
            if not user_role:
                return  # Blocked by gatekeeper
            
            if min_role == Role.SUPER_ADMIN and user_role != Role.SUPER_ADMIN.value:
                if update.callback_query:
                    await update.callback_query.answer("⛔ Chỉ Super Admin mới có quyền này!", show_alert=True)
                elif update.effective_message:
                    await update.effective_message.reply_text("⛔ Bác không có quyền thực hiện chức năng này (Yêu cầu Super Admin).")
                return
            
            return await func(update, context, *args, **kwargs)
        return wrapper
    return decorator
```

---

### Pattern 5: Safe SQLite WAL Backup via Atomic VACUUM INTO & GitHub REST API

**What:** Snapshot the live SQLite database without blocking concurrent transactions or corrupting uncheckpointed WAL pages, compress it, and commit it to GitHub.  
**Why standard file copy fails in WAL mode:** SQLite WAL writes active pages into `<db>-wal`. Copying `<db>` alone captures stale state or torn pages.  
**Solution:** `VACUUM INTO` creates an atomic, consistent, compacted standalone database file containing all transactions committed up to that exact instant, with zero WAL or SHM dependencies.

```
┌────────────────────────────────────────────────────────┐
│  Live SQLite DB (WAL Mode)                             │
│  cassette_store.db + cassette_store.db-wal             │
└──────────────────────────┬─────────────────────────────┘
                           │ 1. db.execute("VACUUM INTO ?")
                           ▼
┌────────────────────────────────────────────────────────┐
│  Temp Standalone DB (Zero WAL dependencies)             │
│  /tmp/backup_20261025_120000.db                        │
└──────────────────────────┬─────────────────────────────┘
                           │ 2. gzip.compress()
                           ▼
┌────────────────────────────────────────────────────────┐
│  Compressed Archive (70-85% smaller)                   │
│  /tmp/backup_20261025_120000.db.gz                     │
└──────────────────────────┬─────────────────────────────┘
                           │ 3. httpx.AsyncClient (GitHub REST API)
                           │ PUT /repos/{owner}/{repo}/contents/backups/{file}
                           ▼
┌────────────────────────────────────────────────────────┐
│  Private GitHub Repository (Safe Cloud Storage)         │
│  backups/2026-10/backup_20261025_120000.db.gz          │
└────────────────────────────────────────────────────────┘
```

#### GitHub REST API Integration Pattern

Instead of invoking shell `git` CLI (which requires SSH keys, local repo config, and risks git lock collisions), use `httpx.AsyncClient` to upload directly via the GitHub Contents API:

```python
# src/services/backup.py
import base64
import gzip
import os
import httpx
from datetime import datetime

async def push_backup_to_github(
    backup_file_path: str,
    github_token: str,
    repo: str,
    branch: str = "main",
) -> str:
    """Read DB, gzip compress, encode base64, and upload via GitHub REST API."""
    gz_path = f"{backup_file_path}.gz"
    with open(backup_file_path, "rb") as f_in, gzip.open(gz_path, "wb") as f_out:
        f_out.writelines(f_in)

    with open(gz_path, "rb") as f:
        content_b64 = base64.b64encode(f.read()).decode("utf-8")

    filename = os.path.basename(gz_path)
    date_path = datetime.now().strftime("%Y-%m")
    api_url = f"https://api.github.com/repos/{repo}/contents/backups/{date_path}/{filename}"
    
    headers = {
        "Authorization": f"Bearer {github_token}",
        "Accept": "application/vnd.github.v3+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    payload = {
        "message": f"chore(backup): automated sqlite backup {filename}",
        "content": content_b64,
        "branch": branch,
    }

    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.put(api_url, json=payload, headers=headers)
        resp.raise_for_status()

    # Clean up local temporary files
    os.remove(backup_file_path)
    os.remove(gz_path)
    return filename
```

---

## Data Flow

### Request Flow: NL Order Mutation

```
[User sends: "Đổi địa chỉ đơn anh Minh sang 45 Lê Lợi"]
    ↓
[Group -1: Whitelist & RBAC Gate] ──(Valid ADMIN)──► [Group 0: Text Handler]
    ↓
[3-Way Intent Router]
    ↓ (Matches Mutation Heuristic: verb "Đổi", field "địa chỉ", name "Minh")
[Order Target Resolver] ──► SQLite Query (unaccent customer_name LIKE '%minh%')
    ↓ (Found 1 candidate: Order #42)
[LLM Mutation Extractor (9router)]
    ↓ (Returns OrderMutationDelta: order_id=42, shipping_address="45 Lê Lợi")
[Formatters: render_mutation_preview_card]
    ↓
[Bot replies with Visual Diff & Confirmation Inline Buttons]
    ↓
[User clicks "✅ Xác nhận sửa"]
    ↓
[Mutation Callback Handler] ──► aiosqlite UPDATE orders SET shipping_address=?
    ↓
[Bot edits message to Success Card with timestamp & updated badge]
```

### State Management

- **Ephemeral Drafts:** Unconfirmed mutations stored in `context.user_data["pending_mutation:<token>"]` with 120s TTL. Avoids database pollution if cancelled or abandoned.
- **RBAC Role Cache:** Cached in `context.bot_data["user_roles"]` dictionary (`telegram_id -> role`). Cache refreshed on every admin mutation command.
- **Application Lifecycle State:** Shared `asyncio.Event` (`stop_event`) coordinating shutdown across PTB polling, Console CLI, and Backup Scheduler.

---

## Scaling Considerations

| Scale | Architecture Status | Actions Needed |
|-------|---------------------|----------------|
| **Single Shop (< 100 orders/day)** | **Current Architecture** | SQLite WAL mode + local in-memory caching easily handles 100-500 transactions/second. Zero external services needed. |
| **Growing Shop (100 - 1,000 orders/day)** | **Well within limits** | GitHub backup size ~5-10MB/month gzipped. Weekly VACUUM keeps SQLite lean. In-memory role dict takes <100KB. |
| **Enterprise / Multi-Branch (10K+ orders/day)** | **Out of Scope** | Migrating to Postgres/RDS and separating bot polling from worker queues. Not applicable for cassette shop domain. |

### Scaling & Safety Priorities

1. **Backup file growth:** Use `gzip` compression and folder partitioning (`backups/YYYY-MM/`) to prevent GitHub repository file-count limits.
2. **Terminal state guards:** Ensure orders in `COMPLETED`, `HUY_DON`, or `BOM_HANG` require explicit override confirmation before allowing mutations.
3. **LLM Gateway rate limits:** The 2-tier fallback (structured parse → json_object) already proven in v1.0 handles 9router provider instability.

---

## Anti-Patterns

### Anti-Pattern 1: Direct File Copy of SQLite DB in WAL Mode

**What:** Using `shutil.copyfile("cassette_store.db", "backup.db")` while the bot is running.  
**Why it's wrong:** In WAL mode, transactions are written to `cassette_store.db-wal`. Copying only `.db` produces an incomplete, corrupt, or inconsistent snapshot missing the latest orders.  
**Do this instead:** Run `VACUUM INTO 'backup.db'` on the open `aiosqlite` connection. It guarantees an atomic, consistent, clean single-file snapshot.

### Anti-Pattern 2: Running Blocking `input()` on the Asyncio Event Loop

**What:** Calling standard Python `input()` inside an async console function.  
**Why it's wrong:** `input()` halts the OS thread waiting for user keystrokes. In Python asyncio, this freezes the single-threaded event loop, blocking all Telegram bot polling and background tasks until the user hits Enter.  
**Do this instead:** Offload input reading to worker thread: `await asyncio.to_thread(sys.stdin.readline)`.

### Anti-Pattern 3: Greedy Fallback to Order Creation on Free-Text

**What:** Assuming any text message that isn't a search query must be a new order.  
**Why it's wrong:** Users typing "Huỷ đơn #12" or "Đổi sđt khách Nam" get prompted with "ĐƠN HÀNG MỚI (Xem trước)" because LLM tries to hallucinate a new order from mutation text.  
**Do this instead:** Implement a 3-way intent router before LLM ingestion. Route mutation commands to the mutation pipeline.

### Anti-Pattern 4: Hardcoding Admin IDs Exclusively in `.env`

**What:** Storing all admin Telegram IDs only in a `.env` comma-separated string.  
**Why it's wrong:** Adding or removing an admin requires SSH access, editing files, and restarting the bot container, causing downtime.  
**Do this instead:** Use `.env` only for the bootstrap `SUPER_ADMIN_ID`. Store all active admins in SQLite `admin_users` table with in-memory caching. Allow Super Admin to add/remove admins dynamically via Telegram `/admin` and Console CLI.

---

## Integration Points

### External Services

| Service | Protocol | Integration Pattern | Error Handling / Gotchas |
|---------|----------|---------------------|--------------------------|
| **9router (OpenAI Gateway)** | HTTPS REST / JSON | `AsyncOpenAI` client with structured outputs (`parse` + fallback `json_object`). | 15s timeout, polite error message to user, fallback to manual button action. |
| **Telegram Bot API** | HTTPS Long-Polling | `python-telegram-bot` v20+ async `Application`. | Automated reconnect on network drop. Non-blocking callback query answering. |
| **GitHub REST API** | HTTPS REST / JSON | `httpx.AsyncClient` PUT `/repos/{owner}/{repo}/contents/{path}`. | Requires Personal Access Token with `contents:write`. Gzip files to minimize transfer payload. |

### Internal Boundaries

| Boundary | Communication Pattern | Notes |
|----------|----------------------|-------|
| **Console CLI ↔ Telegram Bot App** | Shared `Application` instance & `stop_event` | Console inspects `app.bot_data` and controls shutdown gracefully. |
| **Intent Router ↔ Mutation / Ingest / Search** | Direct function call dispatch | Pure routing decision based on message characteristics. |
| **RBAC Security Gate ↔ Handlers** | Group -1 filter + `@require_role` decorator | Halts execution before Group 0 if unauthorized; attaches role to `user_data`. |
| **Backup Scheduler ↔ SQLite DB** | Background `asyncio.Task` calling `VACUUM INTO` | Zero lock contention with concurrent order writes due to SQLite WAL isolation. |

---

## Suggested Build Order & Dependencies

```
Wave 1: Foundation (RBAC & Database Schema)
├── 1. Add admin_users table in src/db/schema.py & queries in src/db/admin_users.py
├── 2. Implement Super Admin bootstrap from config.py in app initialization
└── 3. Implement src/bot/rbac.py with @require_role decorators & update whitelist_gate

Wave 2: Concurrency & Infrastructure (Console & Backup)
├── 4. Refactor main.py to explicit async lifecycle (app.initialize/start/polling)
├── 5. Implement non-blocking Console CLI (src/console/) with TTY auto-detection
├── 6. Implement SQLite VACUUM INTO + GitHub REST API client (src/services/backup.py)
└── 7. Implement background periodic backup scheduler (src/services/scheduler.py)

Wave 3: NL Order Mutation Pipeline
├── 8. Build 3-Way Intent Router (src/services/router.py) to prevent ingest collisions
├── 9. Implement Order Target Resolver & Pydantic OrderMutationDelta schema
├── 10. Implement 2-phase Visual Diff card & confirmation callbacks (src/bot/handlers/mutation.py)
└── 11. Add Telegram Admin management commands (/admin, /backup) in src/bot/handlers/admin.py
```

---

## Sources

- [SQLite Official Documentation - VACUUM INTO](https://www.sqlite.org/lang_vacuum.html#vacuuminto) — verified atomic backup snapshot behavior in WAL mode.
- [python-telegram-bot Documentation - Application Lifecycle](https://docs.python-telegram-bot.org/en/v22.8/telegram.ext.application.html) — verified manual async lifecycle (`initialize`, `start`, `updater.start_polling`, `stop`).
- [GitHub REST API Documentation - Create or update file contents](https://docs.github.com/en/rest/repos/contents#create-or-update-file-contents) — verified Base64 PUT endpoint.
- [Python asyncio Documentation - Running in Threads](https://docs.python.org/3/library/asyncio-task.html#asyncio.to_thread) — verified non-blocking standard input reading.

---
*Architecture research for: Cassette Store Telegram Chatbot (Milestone v1.1)*  
*Researched: 2026-10-25*
