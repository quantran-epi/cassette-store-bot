# Architecture Research: Cassette Store Telegram Chatbot

**Domain:** Telegram Retail Order Management Chatbot (Small Low-Tech Merchant)  
**Researched:** 2026-10-24  
**Confidence:** HIGH  

---

## Standard Architecture

### System Overview

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                       1. Configuration & Security Layer                      │
├─────────────────────────────────────────────────────────────────────────────┤
│  ┌───────────────────────────────┐     ┌─────────────────────────────────┐  │
│  │  pydantic-settings (.env)     │     │  Telegram User ID Whitelist     │  │
│  │  (Tokens, 9router URL, Paths) │     │  Auth Middleware (Gatekeeper)   │  │
│  └───────────────┬───────────────┘     └────────────────┬────────────────┘  │
│                  │                                      │                   │
├──────────────────┴──────────────────────────────────────┴───────────────────┤
│                       2. Telegram Bot Presentation Layer                     │
├─────────────────────────────────────────────────────────────────────────────┤
│  ┌───────────────────────────┐  ┌────────────────────────────────────────┐  │
│  │ Message Handlers          │  │ Callback Router (Inline Queries)       │  │
│  │ - Free-text Ingest Handler│  │ - Order Draft Confirmation             │  │
│  │ - Query / Search Handler  │  │ - Order Status Transitions             │  │
│  │ - Admin / Daily List      │  │ - Tracking Code Prompt                 │  │
│  └─────────────┬─────────────┘  └───────────────────┬────────────────────┘  │
│                │                                    │                       │
│  ┌─────────────┴─────────────┐  ┌───────────────────┴────────────────────┐  │
│  │ Message Formatters        │  │ Inline & Reply Keyboards               │  │
│  │ - Order Receipt Card      │  │ - Persistent Menu (Tạo đơn, Hôm nay)   │  │
│  │ - Compact Daily List      │  │ - 1-Tap Copy Text Buttons              │  │
│  │ - Status Badges & Emojis  │  │ - Two-Phase Confirm/Cancel Buttons     │  │
│  └─────────────┬─────────────┘  └───────────────────┬────────────────────┘  │
│                │                                    │                       │
├────────────────┼────────────────────────────────────┼───────────────────────┤
│                ▼                                    ▼                       │
│        3. LLM Extraction & NLP Query Service (9router Gateway)               │
├─────────────────────────────────────────────────────────────────────────────┤
│  ┌───────────────────────────────────────────────────────────────────────┐  │
│  │ AsyncOpenAI Client (9router OpenAI-compatible Endpoint)               │  │
│  │ ├─ Prompt Templates (Vietnamese cassette slang, addresses, phones)    │  │
│  │ ├─ Pydantic Structured Output Schemas (OrderDraft, SearchFilter)      │  │
│  │ └─ Response Validation & Normalization Service                        │  │
│  └──────────────────────────────────┬────────────────────────────────────┘  │
│                                     │                                       │
├─────────────────────────────────────┼───────────────────────────────────────┤
│                                     ▼                                       │
│                        4. Domain & State Management                          │
├─────────────────────────────────────────────────────────────────────────────┤
│  ┌──────────────────────────────────────┐  ┌─────────────────────────────┐  │
│  │ Ephemeral Flow State Manager         │  │ Order Lifecycle FSM         │  │
│  │ - In-memory Draft Cache (UUID key)   │  │ - Valid transition rules    │  │
│  │ - TTL cleanup (PTB user_data / dict) │  │ - Terminal state guards     │  │
│  └──────────────────┬───────────────────┘  └──────────────┬──────────────┘  │
│                     │                                     │                 │
├─────────────────────┴─────────────────────────────────────┴─────────────────┤
│                       5. Data & Persistence Layer (SQLite)                   │
├─────────────────────────────────────────────────────────────────────────────┤
│  ┌───────────────────────────────────────────────────────────────────────┐  │
│  │ SQLite Repositories (WAL Mode, Foreign Keys = ON, Parameterized SQL)  │  │
│  │ ├─ CustomerRepository (Find/Upsert by phone, multi-address, notes)    │  │
│  │ ├─ OrderRepository (CRUD, status update, tracking code, date query)   │  │
│  │ └─ OrderSearchRepository (Fuzzy text match, phone lookup, date range) │  │
│  └──────────────────────────────────┬────────────────────────────────────┘  │
│                                     │                                       │
│                                     ▼                                       │
│                   [Local SQLite Storage: store.db]                          │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

### Component Responsibilities

| Component | Responsibility | Typical Implementation |
|-----------|----------------|------------------------|
| **Security Whitelist Middleware** | Intercepts incoming `Update` objects. Discards or rejects users whose Telegram User ID is not in `ALLOWED_USER_IDS`. Protects PII and shop data. | Custom PTB `BaseHandler` wrapper or outer update filter checking `update.effective_user.id`. |
| **Telegram Handlers & Routers** | Maps incoming user actions (text messages, command buttons, inline callbacks) to appropriate service logic. Dispatches actions without holding database connections open. | `python-telegram-bot` (v20+ async) `MessageHandler`, `CallbackQueryHandler`. |
| **Keyboards & Formatters** | Generates elder-friendly UI: large emoji labels, high-contrast status tags, 1-tap copy buttons (`CopyTextButton` / monospace text), and persistent bottom reply menus. | Pure presentation functions returning `InlineKeyboardMarkup`, `ReplyKeyboardMarkup`, and MarkdownV2/HTML formatted strings. |
| **LLM Gateway Service (9router)** | Wraps OpenAI-compatible API on 9router. Sends raw Vietnamese chat text with few-shot system prompts, returning validated JSON matching Pydantic models. | `openai.AsyncOpenAI(base_url=..., api_key=...)` using structured outputs (`client.beta.chat.completions.parse` or `response_format={"type": "json_object"}`). |
| **Ephemeral Flow Cache** | Temporarily retains unconfirmed order drafts and pending search selections between user typing and button clicking. Keeps callback payloads under 64 bytes. | Key-value store inside PTB `context.user_data` or short-lived in-memory dict with UUID keys and timestamp expiration. |
| **Domain State Machine** | Enforces cassette production order lifecycle (`Chờ làm` -> `Đang làm` -> `Đã đóng gói` -> `Đã tạo đơn app` -> `Shipper đã lấy` -> `Đã giao` / `Bom` / `Huỷ`). Blocks illegal jumps. | Python `Enum` + transition dictionary check before updating DB status. |
| **SQLite Repositories** | Handles all CRUD operations, database constraints, customer deduplication, and transactions. Ensures ACID durability locally. | Python standard library `sqlite3` (or `aiosqlite`) with WAL mode, parameterized queries, and dedicated repository classes. |

---

## Recommended Project Structure

```
cassette-store/
├── .env.example                 # Example environment variables
├── pyproject.toml               # Python dependencies and project metadata
├── README.md                    # Setup and execution guide
├── store.db                     # Local SQLite database (git-ignored)
└── src/
    ├── __init__.py
    ├── main.py                  # Application entry point: initializes bot & DB
    ├── config.py                # Pydantic BaseSettings: tokens, 9router URL, whitelist
    │
    ├── bot/                     # Telegram Presentation Layer
    │   ├── __init__.py
    │   ├── app.py               # Bot builder, handlers registration, error handling
    │   ├── middleware.py        # Whitelist authentication filter
    │   ├── keyboards.py         # Inline & Reply markup builders
    │   ├── formatters.py        # Telegram Markdown card formatters
    │   └── handlers/
    │       ├── __init__.py
    │       ├── admin.py         # /start, /help, stats, persistent menu init
    │       ├── ingest.py        # Free-text order ingestion & preview confirmation
    │       ├── orders.py        # Order details, 1-tap copy card, tracking code entry
    │       ├── lifecycle.py     # Status transitions (Đang làm -> Đóng gói -> ...)
    │       └── search.py        # Date-filtered queries (Hôm nay, Hôm qua) & NL search
    │
    ├── llm/                     # LLM Extraction & NLP Query Service
    │   ├── __init__.py
    │   ├── client.py            # 9router AsyncOpenAI client wrapper
    │   ├── schemas.py           # Pydantic schemas (ExtractedOrder, ExtractedSearch)
    │   └── prompts.py           # Few-shot prompts for Vietnamese cassette ordering
    │
    ├── domain/                  # Domain Models & Rules
    │   ├── __init__.py
    │   ├── models.py            # Dataclasses: Customer, Order, OrderItem, Address, Phone
    │   └── lifecycle.py         # OrderStatus Enum and valid state transition matrix
    │
    └── db/                      # Persistence Layer (SQLite)
        ├── __init__.py
        ├── connection.py        # SQLite connection factory (WAL, foreign keys, row_factory)
        ├── schema.sql           # DDL schema definitions and indexes
        ├── migrations.py        # Automated schema migration on startup
        └── repositories/
            ├── __init__.py
            ├── customer_repo.py # Customer, phones, addresses lookup & upsert
            └── order_repo.py    # Order persistence, state update, search queries
```

### Structure Rationale

- **`src/bot/handlers/` segregated by domain flow:** Separates ingest, lifecycle, and query logic. Prevents monolithic 2000-line bot files.
- **`src/llm/` isolated from Telegram:** LLM prompts and Pydantic schemas can be tested independently with mock inputs or unit tests without firing up a Telegram polling loop.
- **`src/domain/` zero external dependencies:** Holds pure Python definitions of order states, transition validation, and core data contracts.
- **`src/db/repositories/` data access boundary:** Keeps SQL queries isolated. Handlers never write raw SQL. Changing schema or queries touches only the repository layer.
- **`src/bot/keyboards.py` & `formatters.py`:** Centralizes all text templates and button layouts. Guarantees visual consistency across the entire UI for the low-tech user.

---

## Architectural Patterns

### Pattern 1: Two-Phase Ephemeral State Confirmation

**What:** Never write to the database immediately upon LLM parsing or text extraction. Instead, store the parsed `OrderDraft` into an ephemeral cache with a UUID token, display a confirmation card with buttons (`[Xác nhận tạo đơn]`, `[Huỷ]`), and commit to SQLite only when the user taps confirmation.  
**When to use:** Crucial for all AI-assisted ingestion and sensitive mutations (cancelling orders, marking orders as "Bom").  
**Trade-offs:** Requires ephemeral storage in memory; draft expires if user abandons the chat. Eliminates accidental database corruption caused by LLM hallucination or typos.

```python
# src/bot/handlers/ingest.py
import uuid
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

async def handle_freetext_order(update: Update, context: ContextTypes.DEFAULT_TYPE):
    raw_text = update.message.text
    # 1. Parse via LLM
    draft = await context.bot_data["llm_service"].extract_order(raw_text)
    
    # 2. Store in ephemeral context using short UUID
    draft_id = str(uuid.uuid4())[:8]
    context.user_data[f"draft:{draft_id}"] = draft
    
    # 3. Present confirmation card
    receipt_preview = formatters.format_order_preview(draft)
    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("✅ Xác nhận tạo đơn", callback_data=f"confirm_order:{draft_id}"),
            InlineKeyboardButton("❌ Huỷ bỏ", callback_data=f"cancel_order:{draft_id}")
        ]
    ])
    await update.message.reply_text(receipt_preview, reply_markup=keyboard, parse_mode="HTML")
```

### Pattern 2: Schema-Enforced Extraction via Pydantic & 9router

**What:** Direct 9router API to respond with structured JSON adhering strictly to a JSON Schema derived from a Pydantic model.  
**When to use:** All free-text parsing (order placement text, search queries).  
**Trade-offs:** Strict schema ensures zero regex parsing bugs on downstream layers. Requires model that respects structured outputs / JSON mode.

```python
# src/llm/schemas.py
from pydantic import BaseModel, Field
from typing import List, Optional

class ExtractedItem(BaseModel):
    title: str = Field(description="Tên cuốn băng hoặc mặt hàng cassette")
    quantity: int = Field(default=1, description="Số lượng")
    unit_price: Optional[int] = Field(default=None, description="Đơn giá nếu có")

class ExtractedOrder(BaseModel):
    customer_name: str = Field(description="Tên người nhận hàng")
    phones: List[str] = Field(description="Danh sách số điện thoại tìm thấy")
    address: str = Field(description="Địa chỉ giao hàng chi tiết")
    items: List[ExtractedItem] = Field(description="Danh sách băng cassette khách đặt")
    total_amount: int = Field(description="Tổng tiền thanh toán (VNĐ)")
    cod_amount: int = Field(default=0, description="Tiền cần thu hộ khi giao hàng (0 nếu đã CK)")
    payment_method: str = Field(description="'BANKING' nếu khách chuyển khoản trước, 'COD' nếu thu tiền mặt")
    notes: Optional[str] = Field(default=None, description="Ghi chú đặc biệt về bài hát, phôi băng hoặc giao hàng")
```

### Pattern 3: SQLite Repository with Write-Ahead Logging (WAL)

**What:** Configure SQLite with `PRAGMA journal_mode = WAL` and `PRAGMA foreign_keys = ON`. Encapsulate all database interaction inside explicit repository classes.  
**When to use:** Multi-handler async environment where reads (listing orders, searching) occur concurrently with writes (updating status, inserting orders).  
**Trade-offs:** WAL mode allows concurrent readers and a writer without `database is locked` errors. Single-file database remains trivial to back up and inspect.

```python
# src/db/connection.py
import sqlite3
from pathlib import Path

def get_connection(db_path: str = "store.db") -> sqlite3.Connection:
    conn = sqlite3.connect(db_path, timeout=10.0)
    conn.execute("PRAGMA journal_mode = WAL;")
    conn.execute("PRAGMA foreign_keys = ON;")
    conn.execute("PRAGMA synchronous = NORMAL;")
    conn.row_factory = sqlite3.Row
    return conn
```

### Pattern 4: 1-Tap Ergonomic Clipboard Copy Actions

**What:** Eliminate mobile text selection friction for elderly shop owners. Format order details with Telegram Bot API `CopyTextButton` on modern clients and backtick monospaced text on fallback clients.  
**When to use:** Order detail cards containing carrier tracking codes, recipient phone numbers, and full delivery addresses.  
**Trade-offs:** Minimal development cost; dramatically speeds up manual entry into shipping apps (GHTK, ViettelPost, GHN).

```python
# src/bot/keyboards.py
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, CopyTextButton

def build_order_copy_keyboard(order_id: int, phone: str, address: str, tracking_code: str | None) -> InlineKeyboardMarkup:
    buttons = []
    if phone:
        buttons.append([InlineKeyboardButton("📞 Sao chép SĐT", copy_text=CopyTextButton(text=phone))])
    if address:
        buttons.append([InlineKeyboardButton("🏠 Sao chép Địa chỉ", copy_text=CopyTextButton(text=address))])
    if tracking_code:
        buttons.append([InlineKeyboardButton("📦 Sao chép Mã vận đơn", copy_text=CopyTextButton(text=tracking_code))])
    
    # State update actions
    buttons.append([InlineKeyboardButton("🔄 Đổi trạng thái", callback_data=f"status_menu:{order_id}")])
    return InlineKeyboardMarkup(buttons)
```

---

## State Management for Conversational Flows

Telegram bot interactions fall into two categories: **linear wizards** (brittle) vs **stateless message dispatch with ephemeral action tokens** (resilient). For elderly non-tech users, rigid multi-step conversation wizards (`ConversationHandler`) fail because users send out-of-order messages, type greetings, or make mistakes without knowing how to cancel.

### Architectural Decision: Stateless Action Tokens over ConversationHandler

1. **Order Confirmation Flow:**
   - User pastes raw order chat.
   - Bot calls LLM parser -> Generates `draft_id = uuid.uuid4()[:8]`.
   - Bot writes `draft` to `context.user_data[f"draft:{draft_id}"]`.
   - Bot renders preview card with inline buttons: `confirm_order:{draft_id}` and `cancel_order:{draft_id}`.
   - If user taps Confirm: Read draft from `user_data`, write to SQLite in atomic transaction, edit message into confirmed receipt, delete draft from `user_data`.
   - If user ignores or pastes another order: Old draft silently expires with TTL or is overwritten. Bot remains responsive to every message.

2. **Tracking Code Update Flow:**
   - User taps `[✏️ Thêm mã vận đơn]` on order card.
   - Bot writes `context.user_data["awaiting_tracking_order_id"] = order_id`.
   - Bot prompts: *"Bác hãy dán mã vận đơn từ app giao hàng vào đây:"* with an inline button `[❌ Huỷ]`.
   - Next text message from user is checked: if key exists in `user_data`, update order in SQLite, clear state key, return updated order card.

3. **Natural Language Search Confirmation Flow:**
   - User types: *"Tìm đơn anh Tuấn mua băng Chế Linh"*
   - LLM extracts query parameters: `customer_name="Tuấn"`, `tape_title="Chế Linh"`.
   - Search repository queries DB for candidates.
   - If multiple candidates: Bot displays a list with preview buttons: `[Đơn #12 - 0912*** - 280k]`, `[Đơn #15 - 0988*** - 150k]`.
   - If single candidate: Bot asks: *"Có phải đơn của bác **Nguyễn Văn Tuấn** (SĐT ...89) không?"* with `[✅ Đúng đơn này]` / `[❌ Không phải]`.
   - User confirms -> Bot renders full order inspection card with copy buttons.

---

## Data Flow

### 1. Primary Ingestion Flow (Raw Chat to Confirmed DB Order)

```
[Merchant Telegram Chat]
         │ (Pastes raw customer chat text)
         ▼
[Whitelist Middleware] ───(Unauthorized)───► [Silent Drop / Access Denied]
         │ (Authorized)
         ▼
[Ingest Message Handler]
         │
         ▼
[9router LLM Service] ───(HTTP POST /chat/completions with Pydantic JSON Schema)
         │
         ▼ (Returns ExtractedOrder JSON)
[Ephemeral Cache] ───(Save draft: context.user_data[draft_id])
         │
         ▼
[Message Formatter] ───(Generates HTML Preview Card + Inline Keyboard)
         │
         ▼
[Merchant Telegram Chat] ◄─── (Displays: "Bác kiểm tra lại thông tin đơn hàng...")
         │
         │ (Merchant taps [✅ Xác nhận tạo đơn])
         ▼
[Callback Query Handler]
         │ (Fetches draft by draft_id from user_data)
         ▼
[CustomerRepository] ───(Find or create Customer, insert Phone & Address)
         │
         ▼
[OrderRepository] ───(Insert Order & OrderItems in SQLite transaction)
         │
         ▼
[Message Formatter] ───(Edit original message into Formal Order Receipt + Copy Buttons)
```

### 2. Natural Language Search & Order Inspection Flow

```
[Merchant Telegram Chat]
         │ (Types: "tìm đơn anh Hùng ship về Hải Phòng")
         ▼
[Search Handler]
         │
         ▼
[LLM Query Extractor] ───(Extracts: name="Hùng", city="Hải Phòng")
         │
         ▼
[OrderSearchRepository] ───(SQL: SELECT orders JOIN customers WHERE name LIKE %Hùng%...)
         │
         ├────────────────────────────────────────┬─────────────────────────────────────┐
         ▼ (Found 0)                              ▼ (Found 1)                           ▼ (Found > 1)
[Reply: Không tìm thấy]       [Preview Confirmation Card]                 [Candidate List Buttons]
                              "Có phải đơn của bác Hùng...?"               [Đơn 101 - 320k] [Đơn 104 - 150k]
                                         │ (Taps [✅ Xem chi tiết])                 │ (Taps candidate)
                                         └──────────────────┬───────────────────────┘
                                                            ▼
                                               [Full Order Inspection Card]
                                               - Line items, COD amount, Status badge
                                               - [📞 Copy Phone] [🏠 Copy Address]
                                               - [🔄 Cập nhật trạng thái]
```

### 3. Order Lifecycle Transition Flow

```
[Merchant taps [🔄 Đổi trạng thái] on Order Card]
         │
         ▼
[Lifecycle Handler]
         │ (Reads current_status from DB)
         ▼
[Lifecycle State Machine] ───(Calculates allowed next transitions)
         │ (e.g. "Đang làm" -> ["Đã đóng gói", "Huỷ đơn"])
         ▼
[Inline Keyboard Builder] ───(Displays allowed action buttons)
         │
         ▼
[Merchant taps: [📦 Đã đóng gói]]
         │
         ▼
[OrderRepository] ───(UPDATE orders SET status = 'Đã đóng gói', updated_at = CURRENT_TIMESTAMP)
         │
         ▼
[Message Formatter] ───(Edit message: Updates badge to "📦 ĐÃ ĐÓNG GÓI", refreshes next buttons)
```

---

## Scaling Considerations

| Scale | Architecture Adjustments |
|-------|--------------------------|
| **1 - 100 orders/day** *(Current baseline)* | Single-process Python bot running `sqlite3` in WAL mode on local VPS/mini PC. Local SQLite handles all queries in < 2ms. Bot polling mode is fully sufficient. |
| **100 - 1,000 orders/day** | Keep single-node SQLite. Ensure composite indexes on `(created_at, status)` and `customer_id`. Retain daily database backup file to Google Drive or S3 using simple cron script. |
| **1,000+ orders/day** *(Far beyond single shop)* | Migrate from SQLite to PostgreSQL. Switch bot from Long Polling to Telegram Webhook behind Nginx. Offload LLM parsing jobs to Redis-backed task queue (Celery/ARQ). |

### Scaling & Failure Priorities

1. **First bottleneck: 9router / LLM Gateway Latency & Rate Limits.** LLM completion takes 1.5s - 4.0s. Handlers must run async (`AsyncOpenAI`) to ensure the Telegram bot event loop never blocks during extraction. Display a transient typing indicator (`send_chat_action("typing")`) so the user knows processing is active.
2. **Second bottleneck: SQLite File Lock on Concurrent Writes.** If multiple handlers write simultaneously, standard SQLite can raise `OperationalError: database is locked`. **Solution:** Enable WAL mode (`PRAGMA journal_mode = WAL;`) and set a connection busy timeout (`timeout=10.0`).

---

## Anti-Patterns to Avoid

### Anti-Pattern 1: Direct Database Commit Without User Confirmation
- **What people do:** Write directly to `orders` and `customers` as soon as the LLM returns JSON.
- **Why it's wrong:** LLMs make mistakes on ambiguous Vietnamese texts (e.g., confusing sender address with receiver address, splitting composite numbers, or mistaking tape titles for customer notes). Once committed, correcting bad data on Telegram mobile UI is frustrating for non-tech users.
- **Do this instead:** Strictly adhere to the Two-Phase Ephemeral State Confirmation pattern. Every LLM output is presented as a draft card with explicit `[Xác nhận]` and `[Huỷ]` buttons.

### Anti-Pattern 2: Multi-Step Conversational Wizards (`ConversationHandler`)
- **What people do:** Build a rigid step-by-step form: Step 1 (Ask name) -> Step 2 (Ask phone) -> Step 3 (Ask address) -> Step 4 (Ask cassettes)...
- **Why it's wrong:** High cognitive burden on elderly operators. If they make a mistake in step 2, they get stuck, can't navigate back, and abandon the bot.
- **Do this instead:** One single free-text paste -> LLM extracts all entities at once -> 1-tap confirmation.

### Anti-Pattern 3: Bloated Callback Data Exceeding Telegram 64-Byte Limit
- **What people do:** Serialize raw JSON or long strings into inline button `callback_data` (e.g. `callback_data="confirm_order:name=Tuan&phone=0912345678&total=300000"`).
- **Why it's wrong:** Telegram Bot API limits `callback_data` strictly to 1-64 bytes. Long strings trigger silent failures or API exceptions.
- **Do this instead:** Store the payload in `context.user_data` or cache keyed by an 8-character UUID or integer ID. Button `callback_data` carries only the action prefix and ID (e.g., `cf_ord:a1b2c3d4`).

### Anti-Pattern 4: Coupling Database Connection with Telegram Handlers
- **What people do:** Create a single global `sqlite3.connect` object shared across all async handlers or open/close connections inside handler functions without context managers.
- **Why it's wrong:** Multi-threaded async event loops sharing raw SQLite connection objects cause thread affinity errors (`sqlite3.ProgrammingError: SQLite objects created in a thread can only be used in that same thread`).
- **Do this instead:** Use a connection factory or repository methods that manage short-lived connection lifetimes per operation, or utilize an async wrapper (`aiosqlite`).

---

## Integration Points

### External Services

| Service | Integration Pattern | Notes |
|---------|---------------------|-------|
| **Telegram Bot API** | `python-telegram-bot` (v20+ async) via HTTPS Long Polling (`ApplicationBuilder().token(...).build()`). | No public domain or reverse proxy required; runs behind standard home or VPS NAT. |
| **9router LLM Gateway** | `openai.AsyncOpenAI(base_url="https://9router.example/v1", api_key=...)`. | Model ID configurable via `.env` (`LLM_MODEL_NAME`). Must support Vietnamese comprehension and JSON mode. |

### Internal Boundaries

| Boundary | Communication Pattern | Notes |
|----------|-----------------------|-------|
| **Bot Handler ↔ Security Middleware** | Pre-handler inspection of `update.effective_user.id`. | Rejects unauthorized users before triggering any LLM or DB work. |
| **Bot Handler ↔ LLM Service** | Async method invocation passing raw text string, returning Pydantic model (`ExtractedOrder`). | Handler catches `LLMParseError` and displays a gentle *"Không thể đọc tin nhắn, bác hãy kiểm tra lại"* message. |
| **Bot Handler ↔ Domain Repositories** | Function calls passing domain models / primitives, receiving validated objects. | Handlers do not execute SQL directly. |
| **Handler ↔ Ephemeral Cache** | Read/write to `context.user_data` with prefix keys and auto-cleanup. | Isolates user draft state per Telegram chat. |

---

## Suggested Build Order & Dependencies

To ensure zero blocked development cycles, components must be constructed in strict topological dependency order:

```
[Phase 1: Foundation]
  ├── Settings & Configuration (.env, Pydantic settings)
  └── SQLite Schema & Connection (DDL tables, WAL mode, migrations)
       │
       ▼
[Phase 2: Repositories & Domain Engine]
  ├── CustomerRepository & OrderRepository (CRUD tests)
  └── Lifecycle State Machine (Transition logic & validation)
       │
       ▼
[Phase 3: LLM Extraction Engine]
  ├── 9router Client configuration
  ├── Pydantic extraction schemas
  └── Vietnamese few-shot prompts & parser verification
       │
       ▼
[Phase 4: Telegram Presentation Core]
  ├── Whitelist security middleware
  ├── Persistent Reply Keyboard & command router
  └── Formatters (Order preview card, copy buttons, badges)
       │
       ▼
[Phase 5: Ingestion & Confirmation Workflow]
  ├── Free-text message handler -> LLM parser
  ├── Ephemeral draft cache
  └── Confirmation callback router -> DB commit
       │
       ▼
[Phase 6: Order Lifecycle & Tracking Updates]
  ├── Order detail view with 1-tap copy buttons
  ├── Inline status transition buttons
  └── Tracking code prompt & update handler
       │
       ▼
[Phase 7: Query & Natural Language Search]
  ├── Date-filtered listings (Hôm nay, Hôm qua, Ngày cụ thể)
  └── Natural language search with match confirmation
```

### Build Order Rationale

1. **Database & Repositories first:** Handlers and LLM outputs have nowhere to persist without a rock-solid data model. Building and testing SQLite repositories with pytest guarantees data integrity before any UI exists.
2. **LLM Extraction second:** Allows benchmarking prompt extraction accuracy on real Vietnamese cassette chat samples before writing Telegram handler code.
3. **Bot Shell & Security third:** Guarantees that unauthorized Telegram users cannot access the bot while development and testing are ongoing.
4. **Ingestion & Lifecycle fourth and fifth:** Implements the core business value (paste chat -> confirm -> advance state).
5. **Search & Analytics last:** Natural language search is an enhancement built on top of an already populated database and proven LLM infrastructure.

---

## Sources

- [Telegram Bot API Official Documentation (v7.8+)](https://core.telegram.org/bots/api) — CopyTextButton & Inline Keyboards.
- [python-telegram-bot Documentation](https://docs.python-telegram-bot.org/) — ApplicationBuilder, Handler architecture, user_data context.
- [SQLite Write-Ahead Logging (WAL) Documentation](https://www.sqlite.org/wal.html) — Concurrency and reliability guidelines.
- [OpenAI Structured Outputs Guide](https://platform.openai.com/docs/guides/structured-outputs) — Schema validation via Pydantic.
- [FEATURES.md](./FEATURES.md) — Cassette Store feature requirements and table stakes.

---
*Architecture research for: Cassette Store Telegram Chatbot*  
*Researched: 2026-10-24*
