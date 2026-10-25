# Architecture Research: Milestone v1.1 Integration

**Domain:** Telegram Retail Order Management Chatbot (Low-Tech Cassette Merchant)  
**Milestone:** v1.1 NL Order Mutation, Telegram Admin Suite, Telegram DB Backup & Container Deployment  
**Researched:** 2026-10-25  
**Confidence:** HIGH  

---

## Standard Architecture

### System Overview

```
┌──────────────────────────────────────────────────────────────────────────────────────────────────┐
│                                   Presentation & Interface Layer                                 │
├──────────────────────────────────────────────────────────────────────────────────────────────────┤
│  Telegram Bot (python-telegram-bot v20+ Async Polling)                                           │
│  ├─ Security Gate (Group -1: Dynamic RBAC Filter via bot_data["user_roles"])                     │
│  ├─ Free-Text Message Router (3-Way Dispatch: Ingest vs Search vs Mutate)                        │
│  ├─ Media Group Ingestion (Debounced Photo Album + Text Batching)                                │
│  ├─ Interactive Admin Suite Handlers (/admin, /logs, /backup, Inline Menus)                      │
│  ├─ 2-Phase Confirmation Handlers (Preview Cards: Ingest ord:*, Mutation mut:*)                  │
│  └─ Ergonomic Order Views (1-Tap CopyTextButtons, 2x2 Reply Keyboard)                            │
├──────────────────────────────────────────────────────────────────────────────────────────────────┤
│                                  Core Application Services Layer                                 │
├───────────────────────────────┬────────────────────────────────┬─────────────────────────────────┤
│  3-Way Intent Router          │  NL Order Mutation Service     │  Telegram DB Backup Engine      │
│  ├─ Active State Guard        │  ├─ Target Order Resolver      │  ├─ aiosqlite VACUUM INTO       │
│  ├─ Regex/Keyword Heuristic   │  ├─ LLM Mutation Extractor     │  ├─ Python stdlib gzip stream   │
│  ├─ LLM Intent Classifier     │  ├─ Visual Diff Card Formatter │  ├─ bot.send_document to Admin  │
│  └─ Route Dispatcher          │  └─ 120s TTL Draft Manager     │  └─ PTB JobQueue Daily Task     │
├───────────────────────────────┴────────────────────────────────┴─────────────────────────────────┤
│  Admin & RBAC Service                                                                            │
│  ├─ Super Admin Root-of-Trust (TELEGRAM_SUPER_ADMIN_ID from .env)                                │
│  ├─ Dynamic Admin Whitelist CRUD & In-Memory Sync (bot_data["user_roles"])                       │
│  ├─ Runtime LLM Model Switcher (bot_data["settings"].nine_router_model_id)                       │
│  ├─ In-Memory Ring Buffer Log Handler (collections.deque for /logs)                             │
│  └─ Role Enforcement Decorators (@require_role(Role.SUPER_ADMIN | Role.ADMIN))                   │
├──────────────────────────────────────────────────────────────────────────────────────────────────┤
│                                   Persistence & Storage Layer                                    │
├──────────────────────────────────────────────────────────────────────────────────────────────────┤
│  aiosqlite Connection Manager (WAL Mode, PRAGMA busy_timeout=5000, unaccent function)            │
│  ├─ orders table (Snapshot items, status enum, tracking, JSON photo file_ids)                    │
│  ├─ customers table (Multi-phone, multi-address JSON arrays, notes)                              │
│  └─ admin_users table (Telegram user_id PK, role ENUM, full_name, timestamps)                   │
├──────────────────────────────────────────────────────────────────────────────────────────────────┤
│                                 Runtime & Infrastructure Layer                                   │
├──────────────────────────────────────────────────────────────────────────────────────────────────┤
│  Containerized Execution (Single Pod / Single Container)                                        │
│  ├─ Multi-Stage Dockerfile (python:3.12-slim runtime, non-root appuser UID 10001)                │
│  ├─ Persistent Volume Mount: /app/data (holds *.db, *.db-wal, *.db-shm safely)                  │
│  ├─ K8s Deployment Strategy: Recreate (Single-replica lock, zero multi-writer risk)              │
│  └─ Graceful Shutdown Engine (SIGTERM handler -> stop polling -> WAL checkpoint -> DB close)    │
└──────────────────────────────────────────────────────────────────────────────────────────────────┘
```

---

### Component Responsibilities

| Component | Responsibility | Status | Implementation Details |
|-----------|----------------|--------|------------------------|
| **3-Way Intent Router** | Classifies incoming free-text into INGEST (new order), SEARCH (read-only query), or MUTATE (order update). Prevents race conditions and false order creation. | **NEW** | `src/services/router.py`: 3-tier cascade (active context state -> keyword/regex heuristic -> LLM structured classification fallback). |
| **NL Order Mutation Service** | Resolves target orders from chat reference, extracts field changes via LLM, formats high-contrast Before/After visual diff card, and handles atomic update. | **NEW** | `src/services/order_mutation.py`: `OrderMutationDelta` Pydantic model + 9router gateway + `src/db/orders.py:apply_order_mutation`. |
| **RBAC & Security Service** | Enforces two-tier permissions (`SUPER_ADMIN` vs `ADMIN`). Anchors root admin in `.env`, synchronizes database `admin_users` table with in-memory `bot_data` cache. | **NEW** | `src/bot/rbac.py`: `@require_role` decorator, `Role` enum, root-of-trust check against `settings.telegram_super_admin_id`. |
| **Telegram Admin Suite** | Mobile-first admin management directly inside Telegram: inline keyboard whitelist CRUD, 1-tap LLM model switcher, and in-memory log viewer (`/logs`). | **NEW** | `src/bot/handlers/admin.py`: `/admin` interactive keyboard menu, model selector, log buffer extractor. |
| **Telegram Backup Engine** | Zero-third-party SQLite backup: takes non-blocking snapshot using `VACUUM INTO`, compresses with `gzip`, and sends `.sqlite3.gz` directly to Super Admin chat. | **NEW** | `src/services/backup.py` & `src/bot/handlers/backup.py`: Manual `/backup` handler + PTB `JobQueue` scheduled daily backup at 02:00 AM UTC+7. |
| **In-Memory Log Buffer** | Captures application log records into fixed-size ring buffer for on-demand inspection via `/logs` without server shell access. | **NEW** | `src/utils/logging.py`: Custom `logging.Handler` backed by `collections.deque(maxlen=1000)`. |
| **Container & K8s Packaging** | Multi-stage Docker image, Docker Compose service, and Kubernetes manifests ensuring single-pod SQLite persistence with WAL file preservation. | **NEW** | `Dockerfile`, `docker-compose.yml`, `k8s/` (`deployment.yaml` with `Recreate` strategy, `pvc.yaml`, `configmap.yaml`, `secret.yaml`). |
| **Security Gate (`whitelist_gate`)** | Intercepts updates at Group -1. Rejects unauthenticated users before executing any group 0 handler. | **MODIFIED** | `src/bot/security.py`: Updated from static `.env` list to check dynamic `bot_data["user_roles"]` cache populated from `admin_users` table and root ID. |
| **Text Ingestion Handler (`handle_text_order`)** | Entry point for free-text chat messages from operators. | **MODIFIED** | `src/bot/handlers/ingest.py`: Replaces inline `is_search_intent` check with delegation to 3-Way Intent Router. |
| **Database Schema (`init_db`)** | Creates tables, triggers, and indices at startup. | **MODIFIED** | `src/db/schema.py`: Adds `admin_users` table and migrates initial whitelist from settings if empty. |
| **Application Builder (`build_application`)** | Configures PTB Application, registers handlers, initializes dependencies. | **MODIFIED** | `src/bot/app.py`: Registers `/admin`, `/backup`, `/logs`, mutation callbacks (`mut:*`), and initializes backup `JobQueue`. |
| **Process Entrypoint (`main.py`)** | Orchestrates startup, schema migrations, and shutdown signals. | **MODIFIED** | `main.py`: Attaches `SIGTERM`/`SIGINT` handlers to ensure `PRAGMA wal_checkpoint(TRUNCATE)` and clean DB closure on container termination. |

---

## Recommended Project Structure

```
cassette-store-bot/
├── .planning/                          # GSD planning & research artifacts
├── k8s/                                # Kubernetes production manifests
│   ├── configmap.yaml                  # Non-sensitive runtime configuration
│   ├── deployment.yaml                 # Single-replica Deployment (strategy: Recreate)
│   ├── pvc.yaml                        # PersistentVolumeClaim for SQLite /app/data
│   └── secret.yaml                     # Encrypted/Base64 secrets (Bot token, 9router key)
├── src/
│   ├── __init__.py
│   ├── config.py                       # Pydantic Settings (adds super_admin_id, backup_chat_id)
│   ├── bot/
│   │   ├── __init__.py
│   │   ├── app.py                      # ApplicationBuilder, handler registration, JobQueue setup
│   │   ├── keyboards.py                # Inline keyboards (order actions, admin menus, diff cards)
│   │   ├── rbac.py                     # RBAC Role enum, @require_role decorator, permission checks
│   │   ├── security.py                 # Group -1 security gate checking dynamic user_roles
│   │   └── handlers/
│   │       ├── __init__.py
│   │       ├── admin.py                # NEW: /admin menu, whitelist CRUD, model switch, /logs
│   │       ├── backup.py               # NEW: /backup manual trigger & JobQueue daily callback
│   │       ├── base.py                 # /start, /ping, /help
│   │       ├── callbacks.py            # Order creation confirmation callbacks (ord:*)
│   │       ├── ingest.py               # MODIFIED: Dispatches free-text via 3-Way Intent Router
│   │       ├── mutation.py             # NEW: Mutation confirmation callbacks (mut:cf, mut:ca, mut:pick)
│   │       ├── order_actions.py        # 1-tap status change, tracking update, photo attachment
│   │       ├── orders.py               # Date browsing, order detail view, CopyTextButtons
│   │       └── search.py               # Natural language text-to-SQL search & unaccent queries
│   ├── db/
│   │   ├── __init__.py
│   │   ├── connection.py               # aiosqlite connection manager, WAL mode, unaccent
│   │   ├── customers.py                # Customer repository
│   │   ├── orders.py                   # MODIFIED: Added apply_order_mutation atomic transaction
│   │   ├── rbac.py                     # NEW: admin_users CRUD and role sync queries
│   │   └── schema.py                   # MODIFIED: Added admin_users table definition
│   ├── models/
│   │   ├── __init__.py
│   │   ├── customer.py                 # Customer domain model
│   │   ├── extractor.py                # ExtractedOrder Pydantic schema
│   │   ├── mutation.py                 # NEW: OrderMutationDelta & IntentClassification schemas
│   │   ├── order.py                    # Order and OrderStatus models
│   │   └── rbac.py                     # NEW: AdminUser and Role domain models
│   ├── services/
│   │   ├── __init__.py
│   │   ├── backup.py                   # NEW: VACUUM INTO + gzip + send_document service
│   │   ├── extractor.py                # LLM order extraction
│   │   ├── order_mutation.py           # NEW: Target resolution, delta extraction, diff formatter
│   │   ├── order_search.py             # NL search SQL generation & execution
│   │   └── router.py                   # NEW: 3-Way Intent Router (INGEST vs SEARCH vs MUTATE)
│   └── utils/
│       ├── __init__.py
│       └── logging.py                  # NEW: RingBufferLogHandler for in-memory log inspection
├── tests/                              # Automated test suite (pytest + pytest-asyncio)
├── Dockerfile                          # Multi-stage production container build
├── docker-compose.yml                  # Docker Compose deployment with local named volume
├── main.py                             # Process entrypoint & SIGTERM graceful shutdown hook
├── pyproject.toml                      # Project metadata & dependencies
└── requirements.txt                    # Pinned production dependencies
```

### Structure Rationale

- **`src/services/router.py` decoupled from `handlers/ingest.py`:** Keeps intent classification testable in isolation without mocking Telegram `Update` and `Context` objects.
- **`src/services/order_mutation.py` and `src/bot/handlers/mutation.py`:** Follows established Phase 02/04 architecture separating LLM extraction & business logic from Telegram message rendering and callback routing.
- **`src/bot/rbac.py` and `src/db/rbac.py`:** Separates presentation-layer access control decorators from persistence-layer SQLite `admin_users` queries.
- **`src/services/backup.py`:** Zero Telegram dependency in the snapshot engine; snapshot generation accepts a destination path and returns bytes or file path, allowing clean unit testing without network calls.
- **`k8s/` and `docker-compose.yml`:** Container manifests live in root directory following standard 12-factor cloud-native practices.

---

## Architectural Patterns

### Pattern 1: 3-Way Intent Router & Disambiguation Cascade

**What:** Multi-tier intent resolver routing incoming operator chat messages to either Ingestion (new order), Search (lookup/stats), or Mutation (updating existing order).  
**When to use:** Every time a whitelisted operator sends a free-text message without command prefix (`/`).  
**Trade-offs:** Fast regex prevents unnecessary LLM token cost and latency for obvious queries; LLM fallback handles colloquial ambiguities at the cost of one extra inference call.

```python
# src/services/router.py
from enum import Enum
import re

class IntentType(str, Enum):
    INGEST = "INGEST"
    SEARCH = "SEARCH"
    MUTATE = "MUTATE"

MUTATION_PREFIXES = ("đổi", "sửa", "cập nhật", "gán", "huỷ", "bỏ", "chuyển", "thay")
SEARCH_PREFIXES = ("tìm", "tra cứu", "kiểm tra", "xem lại đơn", "hỏi đơn")

def fast_classify_intent(text: str) -> IntentType | None:
    """Heuristic classifier running in sub-millisecond time."""
    trimmed = text.strip().lower()
    
    # Explicit mutation keywords
    if any(trimmed.startswith(verb) for verb in MUTATION_PREFIXES):
        return IntentType.MUTATE
        
    # Explicit search keywords
    if any(trimmed.startswith(verb) for verb in SEARCH_PREFIXES):
        return IntentType.SEARCH
        
    # Phone number presence with no action verb indicates new order note
    if re.search(r"(?:(?:\+84|84|0)[35789])\d{8}\b", text):
        return IntentType.INGEST
        
    return None  # Inconclusive -> pass to LLM structured classifier
```

---

### Pattern 2: Two-Phase Visual Diff Confirmation Pipeline

**What:** Destructive mutations (status, address, phone, price, tracking) are never executed immediately. The system resolves candidate orders, parses changes, renders a high-contrast Before ➡️ After HTML diff card, and holds an in-memory draft with a 120-second TTL awaiting 1-tap confirmation.  
**When to use:** Any natural language order mutation request.  
**Trade-offs:** Requires an extra tap from the user, but completely eliminates accidental customer data loss or unintended status jumps for elderly merchants.

```
[Operator: "Sửa đơn anh Tuấn đổi sđt sang 0988777666 và chuyển sang Đã đóng gói"]
                                ↓
                [Order Mutation Resolver]
   Finds Order #42 (Anh Tuấn, 0912345678, CHO_LAM, 2 Băng Chế Linh)
                                ↓
                 [Visual Diff Generator]
   Only modified fields rendered with change arrows:
   📞 SĐT: 0912345678 ➡️ 0988777666
   📦 Trạng thái: ⏳ CHỜ LÀM ➡️ 📦 ĐÃ ĐÓNG GÓI
                                ↓
             [Telegram Preview Message + Inline Keyboard]
   Draft stored in context.user_data["pending_mutations"][draft_id]
   [✅ Xác nhận sửa (120s)]    [❌ Huỷ giữ nguyên]
                                ↓
                   [mut:cf:<draft_id> Clicked]
        Atomic SQLite UPDATE executed -> Success notice sent
```

---

### Pattern 3: Two-Tier RBAC & Dynamic Whitelist Sync

**What:** Distinguishes `SUPER_ADMIN` (owner: whitelist management, backup triggers, model switching, logs) from `ADMIN` (staff: daily operations, orders, search, mutations). Root Super Admin is hardcoded in `.env` as the immutable root of trust; secondary admins are persisted in the `admin_users` SQLite table and cached in PTB's `bot_data["user_roles"]`.  
**When to use:** In Group -1 security gate and admin command decorators (`@require_role`).  
**Trade-offs:** Database read occurs only once at startup and during admin modifications; runtime checks are zero-cost dictionary lookups in memory.

```python
# src/bot/rbac.py
from functools import wraps
from enum import Enum
from telegram import Update
from telegram.ext import ContextTypes

class Role(str, Enum):
    SUPER_ADMIN = "SUPER_ADMIN"
    ADMIN = "ADMIN"

def require_role(min_role: Role):
    """Decorator guarding handler execution by user role."""
    def decorator(handler_fn):
        @wraps(handler_fn)
        async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE, *args, **kwargs):
            user = update.effective_user
            if not user:
                return
            roles: dict[int, Role] = context.bot_data.get("user_roles", {})
            user_role = roles.get(user.id)
            
            # Root Super Admin override from settings
            settings = context.bot_data.get("settings")
            if settings and user.id == getattr(settings, "telegram_super_admin_id", None):
                user_role = Role.SUPER_ADMIN

            if user_role == Role.SUPER_ADMIN or (min_role == Role.ADMIN and user_role == Role.ADMIN):
                return await handler_fn(update, context, *args, **kwargs)
                
            msg = "⛔ Bạn không có quyền thực hiện thao tác quản trị này."
            if update.callback_query:
                await update.callback_query.answer(msg, show_alert=True)
            elif update.effective_message:
                await update.effective_message.reply_text(msg)
        return wrapper
    return decorator
```

---

### Pattern 4: Atomic VACUUM INTO Telegram Backup Engine

**What:** Non-blocking SQLite point-in-time snapshot directly exported to compressed archive and transmitted via Telegram Bot API `send_document` to the Super Admin's private chat.  
**When to use:** Manual `/backup` command or automated daily PTB `JobQueue` run at 02:00 AM UTC+7.  
**Trade-offs:** Replaces fragile external cloud storage or GitHub Personal Access Tokens with Telegram's native, free, encrypted file storage infrastructure.

```python
# src/services/backup.py
import aiosqlite
import gzip
import os
import tempfile
from datetime import datetime
from zoneinfo import ZoneInfo

async def create_backup_archive(db_path: str) -> tuple[str, int]:
    """Create atomic SQLite snapshot using VACUUM INTO and compress with gzip."""
    now_vn = datetime.now(ZoneInfo("Asia/Ho_Chi_Minh"))
    timestamp = now_vn.strftime("%Y%m%d_%H%M%S")
    
    with tempfile.TemporaryDirectory() as tmpdir:
        snapshot_db = os.path.join(tmpdir, "snapshot.db")
        gz_out_path = os.path.join(tempfile.gettempdir(), f"cassette_store_{timestamp}.sqlite3.gz")
        
        # 1. Atomic live SQLite snapshot (works seamlessly during WAL writes)
        async with aiosqlite.connect(db_path) as db:
            await db.execute(f"VACUUM INTO '{snapshot_db}'")
            
        # 2. Compress snapshot with stdlib gzip
        with open(snapshot_db, "rb") as f_in, gzip.open(gz_out_path, "wb", compresslevel=9) as f_out:
            while chunk := f_in.read(64 * 1024):
                f_out.write(chunk)
                
        file_size = os.path.getsize(gz_out_path)
        return gz_out_path, file_size
```

---

### Pattern 5: Single-Replica Container Lifecycle & WAL Flush

**What:** Containerized deployment architecture enforcing strict single-pod lifecycle (`replicas: 1`, `strategy.type: Recreate`) with volume directory mounts and `SIGTERM` trap ensuring zero WAL corruption on restarts or updates.  
**When to use:** Production deployments on Kubernetes, Docker Compose, or standalone Docker.  
**Trade-offs:** Zero-downtime rolling updates are not possible with single-file SQLite; brief ~5-second pod recreate downtime guarantees 100% data integrity without database split-brain locks.

```python
# Graceful shutdown pattern in main.py
import signal
import asyncio

async def shutdown_handler(app, db_path):
    """Flush SQLite WAL to main database file before container exits."""
    logger.info("Received termination signal. Shutting down gracefully...")
    # 1. Stop Telegram polling
    await app.stop()
    # 2. Force WAL checkpoint flush
    async with get_db_connection(db_path) as db:
        await db.execute("PRAGMA wal_checkpoint(TRUNCATE);")
    logger.info("SQLite WAL flushed. Ready to exit.")
```

---

## Data Flow

### Request Flow: 3-Way Intent & Mutation Execution

```
[Operator sends text: "Đổi đơn 10 sang Đã giao và thêm ghi chú khách khen băng đẹp"]
                                ↓
               [Security Gate: Group -1 (whitelist_gate)]
         Passes if user_id in bot_data["user_roles"] (SUPER_ADMIN or ADMIN)
                                ↓
               [Group 0: handle_text_order (ingest.py)]
                                ↓
               [3-Way Intent Router (router.py)]
         Classifies intent as: IntentType.MUTATE
                                ↓
             [Order Mutation Service (order_mutation.py)]
         1. Parse target order: id=10
         2. Fetch current record from SQLite: Order #10 (Status: DA_DONG_GOI, Notes: "")
         3. Extract delta via 9router LLM:
            - status: DA_GIAO
            - notes: "Khách khen băng đẹp"
         4. Generate Visual Diff:
            📦 Trạng thái: 📦 ĐÃ ĐÓNG GÓI ➡️ ✅ ĐÃ GIAO
            📝 Ghi chú: [Trống] ➡️ Khách khen băng đẹp
         5. Create in-memory draft in context.user_data["pending_mutations"][draft_id]
                                ↓
                [Telegram Preview Message Sent]
         "Bác kiểm tra lại thay đổi đơn #10 nhé:"
         [✅ Xác nhận sửa (120s)]    [❌ Huỷ giữ nguyên]
                                ↓
               [Operator taps: mut:cf:<draft_id>]
                                ↓
              [Mutation Callback Handler (mutation.py)]
         1. Validate draft TTL (time.time() <= expires_at)
         2. Call src/db/orders.py:apply_order_mutation(db, 10, delta)
         3. Execute atomic UPDATE orders SET ... WHERE id = 10;
         4. Edit preview message: "✅ Đã cập nhật đơn #10 thành công!"
```

---

### Data Flow: Super Admin Backup & Delivery

```
[Trigger: Manual /backup OR JobQueue Daily at 02:00 AM UTC+7]
                                ↓
                    [Security Verification]
         Assert user_id == SUPER_ADMIN (ignored for automated job)
                                ↓
                 [Telegram Typing / Status Notice]
         "⏳ Đang tạo bản sao lưu dữ liệu an toàn..."
                                ↓
                   [Backup Engine (backup.py)]
         1. Execute: VACUUM INTO '/tmp/.../snapshot.db' (lock-free)
         2. Read orders count & customer count for backup caption
         3. Compress: gzip into 'cassette_store_YYYYMMDD_HHMMSS.sqlite3.gz'
                                ↓
                    [Telegram Document Delivery]
         bot.send_document(
             chat_id=settings.telegram_super_admin_id,
             document=open(gz_file, "rb"),
             filename="cassette_store_20261025_020000.sqlite3.gz",
             caption="💾 Bản sao lưu cơ sở dữ liệu định kỳ\n📦 Tổng đơn: 142 | 👤 Khách hàng: 88\n📊 Dung lượng: 45.2 KB"
         )
                                ↓
                   [Temporary File Cleanup]
         Unlink snapshot and compressed .gz files from temporary storage
```

---

### Data Flow: Telegram Admin Suite Management

```
[Super Admin sends: /admin]
           ↓
[Render Master Admin Menu]
├── 👥 [Quản lý Admin & Whitelist]
│      ├── List active users (ID, Name, Role badge)
│      ├── [➕ Thêm Admin mới] -> Sets user_data["admin_action"] = "await_add_id"
│      └── [❌ Thu hồi quyền] -> Lists admins with revocation buttons
├── 🤖 [Chuyển đổi Model LLM]
│      ├── [✅ gpt-4o-mini (Hiện tại)]
│      ├── [⚡ gemini-2.5-flash]
│      └── [🧠 deepseek-chat]
│      (Tapping immediately updates bot_data["settings"].nine_router_model_id)
├── 📋 [Xem Logs gần đây] -> Calls /logs 30 -> Reads ring buffer deque
└── 💾 [Sao lưu cơ sở dữ liệu] -> Invokes /backup immediately
```

---

## Scaling & Concurrency Considerations

| Area | Production Strategy | Rationale |
|------|---------------------|-----------|
| **SQLite Writer Concurrency** | Single-connection transaction queue with `PRAGMA busy_timeout = 5000` | SQLite WAL allows unlimited concurrent readers but exactly one concurrent writer. Short transactions (<10ms) easily handle low-tech shop scale (<100 orders/day) with zero locking conflicts. |
| **Kubernetes Pod Lifecycle** | `replicas: 1` with `strategy.type: Recreate` | Multi-pod scaling is an anti-pattern for single-file SQLite databases. `Recreate` ensures old pod fully unmounts and terminates before new pod starts, preventing shared volume lock corruption. |
| **Persistent Volume Strategy** | Mount directory `/app/data`, NOT file `/app/data/cassette_store.db` | SQLite WAL mode creates sibling files (`cassette_store.db-wal` and `cassette_store.db-shm`). Single-file bind mounts break Linux filesystem inode updates during WAL truncation, leading to silent data loss. |
| **In-Memory Draft Expiration** | 120-second TTL stored in `context.user_data` | Temporary mutation and order drafts are held in memory with Unix timestamps. If operator walks away without tapping confirm, the draft expires cleanly without cluttering database tables with unconfirmed garbage. |
| **Log Storage Overhead** | In-memory `collections.deque(maxlen=1000)` | Prevents VPS disk filling up while enabling mobile inspection via `/logs` without configuring ELK, Promtail, or Loki stacks. |

---

## Anti-Patterns to Avoid

### Anti-Pattern 1: Interactive Terminal Console Application
**What people do:** Building an interactive CLI loop (`while True: input()`) inside `main.py` so the developer can manage admins from the server terminal.  
**Why it's wrong:** The operator is an elderly merchant with zero Linux or SSH knowledge. A server CLI requires terminal TTY allocation, interferes with background Docker daemon logs, complicates container process management (`PID 1`), and duplicates administrative functions.  
**Do this instead:** Build a 100% mobile-friendly Telegram Admin Suite (`/admin`) using inline keyboard buttons and RBAC.

### Anti-Pattern 2: Backup via GitHub Contents API
**What people do:** Using personal GitHub tokens to commit SQLite `.db` or `.gz` files into a private GitHub repository.  
**Why it's wrong:** GitHub Personal Access Tokens expire every 90 days; Git repositories bloat exponentially with binary blobs; commits can fail on merge conflicts or rate limits; and it exposes sensitive customer PII to external git history.  
**Do this instead:** Stream atomic `VACUUM INTO` gzipped snapshots directly into the Super Admin's private Telegram chat using `bot.send_document`. It is fast, free, private, and has zero external dependencies.

### Anti-Pattern 3: In-Place Customer Record Overwrite During Order Mutation
**What people do:** When an operator mutates the shipping address or phone number on an order, automatically updating the master `customers` profile table.  
**Why it's wrong:** Customers frequently ship orders as gifts to relatives, friends, or alternate temporary locations. Overwriting the master customer record corrupts their primary home address for future orders.  
**Do this instead:** Mutate only the order's snapshot fields (`customer_phone`, `shipping_address`). Keep the master `customers` table immutable during order edits, or prompt an explicit optional checkbox: `[Lưu làm địa chỉ chính]`.

### Anti-Pattern 4: Direct Unconfirmed NL Order Mutations
**What people do:** Executing SQL updates immediately upon receiving a natural language command ("Sửa đơn 5 thành đã giao" -> `UPDATE orders SET status='DA_GIAO' WHERE id=5`).  
**Why it's wrong:** LLMs can misinterpret ambiguous references ("đơn hôm qua", "đơn Tuấn" when there are 3 Tuấns), or speech-to-text typos can accidentally cancel an order or wipe out COD values.  
**Do this instead:** Strict 2-phase visual diff confirmation card with explicit old vs new comparison and 120-second timeout.

---

## Integration Points

### External Services

| Service | Protocol / Transport | Purpose | Integration Details |
|---------|----------------------|---------|---------------------|
| **Telegram Bot API** | HTTPS Long-Polling (`python-telegram-bot` v20+) | Operator interface, notifications, document delivery | Polling mode eliminates public IP/HTTPS webhook requirements. Outgoing document transfer streams gzipped SQLite backups. |
| **9router LLM Gateway** | HTTPS Async REST (OpenAI-compatible) | Intent classification, order extraction, mutation deltas | Configured via `Settings` (`nine_router_base_url`, `nine_router_api_key`, `nine_router_model_id`). Runtime model switching updates `bot_data` instantly. |

### Internal Boundaries

| Boundary | Communication Mechanism | Notes |
|----------|--------------------------|-------|
| `handle_text_order` ↔ `3-Way Intent Router` | Direct async call `classify_text_intent(text, active_state)` | Returns `IntentType.INGEST`, `IntentType.SEARCH`, or `IntentType.MUTATE`. |
| `Intent Router` ↔ `Mutation Service` | Async invocation `process_order_mutation(update, context, text)` | Resolves target order, extracts delta, sends preview card. |
| `Mutation Handlers` ↔ `SQLite Database` | `src/db/orders.py:apply_order_mutation(db, order_id, delta)` | Executes atomic single-transaction SQL UPDATE with parameter binding. |
| `Security Gate` ↔ `RBAC Database` | In-memory cache `bot_data["user_roles"]` synchronized via `src/db/rbac.py` | Eliminates SQLite query on every inbound Telegram message; zero latency overhead. |
| `Backup Engine` ↔ `aiosqlite` | `VACUUM INTO 'snapshot.db'` | Standard SQLite command creating a clean point-in-time snapshot file without locking readers or writers. |

---

## Suggested Build Order

To avoid circular dependencies and ensure verified milestones, build components in this exact order:

```
┌────────────────────────────────────────────────────────────┐
│ Phase 1: Foundation, RBAC & Telegram Admin Suite           │
│ - Create admin_users table & migration                     │
│ - Build src/bot/rbac.py (@require_role, Role enum)         │
│ - Upgrade Group -1 security gate to check user_roles cache │
│ - Implement /admin menu: Whitelist CRUD & Model Switcher   │
│ - Implement In-Memory Ring Buffer & /logs handler          │
└─────────────────────────────┬──────────────────────────────┘
                              │
┌─────────────────────────────▼──────────────────────────────┐
│ Phase 2: Telegram DB Backup Engine                         │
│ - Implement src/services/backup.py (VACUUM INTO + gzip)    │
│ - Implement manual /backup command (Super Admin only)      │
│ - Configure PTB JobQueue daily scheduled backup (02:00 VN) │
│ - Connect backup action into /admin menu                   │
└─────────────────────────────┬──────────────────────────────┘
                              │
┌─────────────────────────────▼──────────────────────────────┐
│ Phase 3: 3-Way Intent Router & NL Order Mutation           │
│ - Define OrderMutationDelta & Intent schemas in Pydantic   │
│ - Implement src/services/router.py (3-Way classifier)      │
│ - Implement order target resolution & disambiguation picker│
│ - Build visual Before ➡️ After diff formatter             │
│ - Implement mutation confirmation callbacks (mut:cf, mut:ca│
│ - Implement src/db/orders.py:apply_order_mutation          │
│ - Wire router into src/bot/handlers/ingest.py              │
└─────────────────────────────┬──────────────────────────────┘
                              │
┌─────────────────────────────▼──────────────────────────────┐
│ Phase 4: Containerization & Deployment                     │
│ - Multi-stage Dockerfile with non-root appuser             │
│ - Docker Compose file with persistent /app/data volume     │
│ - Kubernetes manifests (Deployment Recreate, PVC, Secrets) │
│ - Implement SIGTERM graceful shutdown & WAL checkpoint trap│
└────────────────────────────────────────────────────────────┘
```

---

## Sources

- [python-telegram-bot Documentation](https://docs.python-telegram-bot.org/) — JobQueue scheduling, CallbackQuery handling, TypeHandler Group -1.
- [SQLite Official Documentation: VACUUM INTO](https://www.sqlite.org/lang_vacuum.html) — Transactionally safe point-in-time database snapshot generation while in WAL mode.
- [Kubernetes Persistent Volumes for SQLite](https://kubernetes.io/docs/concepts/storage/persistent-volumes/) — Volume locking, ReadWriteOnce constraints, and `Recreate` deployment strategy.
- [Python AsyncOpenAI Client](https://github.com/openai/openai-python) — Structured outputs and custom base URL routing for 9router.

---
*Architecture research for: Milestone v1.1 NL Order Mutation, Telegram Admin Suite, Telegram DB Backup & Container Deployment*  
*Researched: 2026-10-25*
