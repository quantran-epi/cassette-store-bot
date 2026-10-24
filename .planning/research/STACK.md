# Stack Research: Cassette Store Telegram Chatbot

**Domain:** Telegram Order Management Chatbot (Low-Tech Merchant / Local SQLite / OpenAI-Compatible LLM)  
**Researched:** 2026-10-24  
**Confidence:** HIGH  

---

## Recommended Stack

### Core Technologies

| Technology | Version | Purpose | Why Recommended |
|------------|---------|---------|-----------------|
| **Python** | `3.12+` or `3.13+` | Runtime environment | Standard modern async support (`asyncio.TaskGroup`, `to_thread`), native performance improvements, long-term support. |
| **python-telegram-bot** | `~=22.8` (`>=21.10,<23.0`) | Telegram Bot framework | Industry-standard async framework for Telegram Bot API 7.x+. Built-in `ApplicationBuilder`, non-blocking polling, type hints, and full support for `CopyTextButton` (crucial 1-tap copy UX for elderly users). |
| **aiosqlite** | `~=0.22.1` (`>=0.20.0`) | Async SQLite client | Zero-infrastructure, zero-network database running as local single file (`.db`). Wraps standard library `sqlite3` in worker threads to prevent event loop stalls. Supports WAL mode and row factory dictionaries. |
| **openai** | `~=3.37.0` (`>=1.50.0`) | LLM client for 9router | Official client with native `AsyncOpenAI`, configurable `base_url`, custom headers, timeout controls, and `beta.chat.completions.parse` for structured output extraction. |
| **pydantic** | `~=2.14.1` (`>=2.8.0`) | Schema validation & parsing | High-performance Rust-backed data modeling. Powers LLM output parsing, strict schema validation, currency/phone normalization, and customer/order domain objects. |
| **pydantic-settings** | `~=2.16.1` (`>=2.4.0`) | Environment & configuration | Reads `.env` files with fail-fast type validation. Automatically parses comma-separated strings into `list[int]` (whitelist IDs) and hides sensitive tokens via `SecretStr`. |

---

### Supporting Libraries

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| **httpx** | `~=0.28.1` | Underlying HTTP transport for OpenAI | Installed automatically as dependency of `openai` and `python-telegram-bot`. Use directly for custom gateway diagnostics or health check probes if needed. |
| **typing-extensions** | `>=4.12.0` | Advanced type annotations | Transitive dependency enabling modern type features across Python versions. |

---

### Development Tools

| Tool | Purpose | Notes |
|------|---------|-------|
| **ruff** | Linter & formatter | Replaces flake8, isort, black. Ultra-fast, keeps code tidy with minimal config. |
| **pytest** & **pytest-asyncio** | Async unit and integration tests | Essential for testing DB queries, parsing logic, and LLM extraction schemas without running live Telegram polling. |

---

## Installation

```bash
# Core dependencies
pip install "python-telegram-bot[rate-limiter]~=22.8" "aiosqlite~=0.22.1" "openai~=3.37.0" "pydantic~=2.14.1" "pydantic-settings~=2.16.1"

# Development dependencies
pip install -D pytest pytest-asyncio ruff
```

Or `requirements.txt`:
```text
python-telegram-bot[rate-limiter]>=21.10,<23.0
aiosqlite>=0.20.0,<1.0.0
openai>=1.50.0,<4.0.0
pydantic>=2.8.0,<3.0.0
pydantic-settings>=2.4.0,<3.0.0
```

---

## Technical Implementations & Architectural Patterns

### 1. Telegram Bot (python-telegram-bot v20+ Async)

#### Access Control Whitelist (Security Gate)
Use a custom `TypeHandler` or `BaseFilter` to restrict the bot exclusively to whitelist Telegram IDs. Rejecting unauthorized updates early prevents data leaks.

```python
from telegram import Update
from telegram.ext import ApplicationHandlerStop, ContextTypes, TypeHandler

class WhitelistMiddleware:
    def __init__(self, allowed_ids: set[int]):
        self.allowed_ids = allowed_ids

    async def __call__(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user = update.effective_user
        if not user or user.id not in self.allowed_ids:
            if update.effective_message:
                await update.effective_message.reply_text("⛔ Bạn không có quyền truy cập bot này.")
            raise ApplicationHandlerStop()  # Stop further handler execution
```

#### ConversationHandler vs Stateless Callback Handlers
- **Free-text ingestion & confirmation:** Use stateless `CallbackQueryHandler` with structured `callback_data` (e.g., `ord:confirm:<draft_id>` or `ord:cancel:<draft_id>`). Store temporary drafts in `context.user_data["pending_order"]`.
- **Text input prompts (e.g. entering tracking code or notes):** Use `ConversationHandler` with explicit timeout and cancel fallback:

```python
from telegram.ext import ConversationHandler, CommandHandler, MessageHandler, CallbackQueryHandler, filters

WAIT_TRACKING_CODE = 1

tracking_conv = ConversationHandler(
    entry_points=[CallbackQueryHandler(prompt_tracking_input, pattern=r"^prompt_track:\d+$")],
    states={
        WAIT_TRACKING_CODE: [
            MessageHandler(filters.TEXT & ~filters.COMMAND, save_tracking_input)
        ]
    },
    fallbacks=[
        CommandHandler("cancel", cancel_conversation),
        CallbackQueryHandler(cancel_conversation, pattern=r"^cancel$")
    ],
    conversation_timeout=120,  # Auto-reset if user abandons input
    per_user=True,
    per_chat=True
)
```

#### Elderly Low-Tech UX Patterns
1. **1-Tap Clipboard Copy:** Use Telegram Bot API 7.3+ `CopyTextButton` so elderly users tap once to copy phone numbers, addresses, or tracking codes without holding and highlighting small text on mobile:
   ```python
   from telegram import InlineKeyboardButton, InlineKeyboardMarkup, CopyTextButton

   keyboard = InlineKeyboardMarkup([
       [InlineKeyboardButton("📋 Chép SĐT", copy_text=CopyTextButton(text=phone))],
       [InlineKeyboardButton("📋 Chép Địa Chỉ", copy_text=CopyTextButton(text=address))],
       [InlineKeyboardButton("📋 Chép Mã Vận Đơn", copy_text=CopyTextButton(text=tracking_code))]
   ])
   ```
2. **Visual Status Badges:** Use self-explanatory Vietnamese words and distinct emoji (`⏳ Chờ làm`, `🔨 Đang làm`, `📦 Đã đóng gói`, `📱 Đã lên app`, `🚚 Shipper lấy`, `✅ Đã giao`, `💣 Bom hàng`, `❌ Huỷ`).
3. **Single Confirmation Actions:** Never perform state mutation or deletion on a single click without confirmation; use an inline confirmation card (`Xác nhận đổi sang: Đã giao? [Đồng ý] [Quay lại]`).

---

### 2. SQLite Database & Schema Design

#### Database Configuration (aiosqlite)
Always configure WAL mode and enforce foreign keys on initialization:
```python
import aiosqlite

async def init_db(db_path: str):
    async with aiosqlite.connect(db_path) as db:
        await db.execute("PRAGMA journal_mode = WAL;")
        await db.execute("PRAGMA foreign_keys = ON;")
        await db.execute("PRAGMA busy_timeout = 5000;")
        await db.executescript(SCHEMA_SQL)
        await db.commit()
```

#### Relational Schema (Multi-phone, Multi-address, Snapshot Orders)
```sql
-- Customers table
CREATE TABLE IF NOT EXISTS customers (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    notes TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now', 'localtime')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now', 'localtime'))
);

-- Multiple phones per customer
CREATE TABLE IF NOT EXISTS customer_phones (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    customer_id INTEGER NOT NULL REFERENCES customers(id) ON DELETE CASCADE,
    phone TEXT NOT NULL,
    is_primary INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL DEFAULT (datetime('now', 'localtime')),
    UNIQUE(customer_id, phone)
);
CREATE INDEX IF NOT EXISTS idx_customer_phones_lookup ON customer_phones(phone);

-- Multiple addresses per customer
CREATE TABLE IF NOT EXISTS customer_addresses (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    customer_id INTEGER NOT NULL REFERENCES customers(id) ON DELETE CASCADE,
    address TEXT NOT NULL,
    is_primary INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL DEFAULT (datetime('now', 'localtime'))
);

-- Orders table
CREATE TABLE IF NOT EXISTS orders (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    customer_id INTEGER REFERENCES customers(id) ON DELETE SET NULL,
    
    -- Historical snapshots (essential: customer profile edits must not alter past orders)
    customer_name_snapshot TEXT NOT NULL,
    customer_phone_snapshot TEXT NOT NULL,
    customer_address_snapshot TEXT NOT NULL,
    
    -- Order details
    items_text TEXT NOT NULL,                  -- Free-text list of cassettes and quantities
    total_amount INTEGER NOT NULL DEFAULT 0,   -- Total order amount in VND
    cod_amount INTEGER NOT NULL DEFAULT 0,     -- Amount to collect via COD in VND (0 if prepaid)
    payment_method TEXT NOT NULL CHECK(payment_method IN ('COD', 'BANKING')),
    
    -- Lifecycle state
    status TEXT NOT NULL DEFAULT 'CHO_LAM' CHECK(
        status IN ('CHO_LAM', 'DANG_LAM', 'DA_DONG_GOI', 'DA_TAO_APP', 'SHIPPER_DA_LAY', 'DA_GIAO', 'BOM_HANG', 'DA_HUY')
    ),
    
    tracking_code TEXT,                        -- Shipping tracking number
    raw_text TEXT,                             -- Original customer raw message parsed by LLM
    
    created_at TEXT NOT NULL DEFAULT (datetime('now', 'localtime')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now', 'localtime'))
);

CREATE INDEX IF NOT EXISTS idx_orders_status ON orders(status);
CREATE INDEX IF NOT EXISTS idx_orders_created_at ON orders(created_at);
CREATE INDEX IF NOT EXISTS idx_orders_tracking_code ON orders(tracking_code);
```

---

### 3. OpenAI Client, 9router Gateway & Structured Outputs

#### Pydantic Extraction Schema
```python
from typing import Literal, Optional
from pydantic import BaseModel, Field

class OrderExtractionResult(BaseModel):
    customer_name: str = Field(description="Tên người nhận hàng")
    phone: str = Field(description="Số điện thoại người nhận (chuẩn hóa số)")
    address: str = Field(description="Địa chỉ nhận hàng đầy đủ (số nhà, đường, phường/xã, quận/huyện, tỉnh/thành)")
    items_text: str = Field(description="Danh sách các cuốn băng cassette kèm số lượng/chi tiết")
    total_amount: int = Field(default=0, description="Tổng tiền đơn hàng tính bằng VNĐ (đổi 'k', 'nghìn' thành số nguyên)")
    cod_amount: int = Field(default=0, description="Số tiền cần thu COD tính bằng VNĐ (nếu khách chuyển khoản trước thì cod=0)")
    payment_method: Literal["COD", "BANKING"] = Field(
        default="COD", 
        description="Phương thức thanh toán: 'BANKING' nếu đã chuyển khoản, 'COD' nếu thu tiền khi nhận"
    )
    notes: Optional[str] = Field(default=None, description="Ghi chú thêm về đơn hàng hoặc yêu cầu khách")
```

#### Dual-Mode LLM Client with Fallback
9router routes between different upstream models (OpenAI, Gemini, Anthropic, DeepSeek). Some upstream models do not support OpenAI's strict `response_format={"type": "json_schema"}`. The robust production pattern attempts `beta.chat.completions.parse()` first, then falls back to `json_object` + manual Pydantic validation:

```python
import json
import logging
from openai import AsyncOpenAI, APIConnectionError, RateLimitError, APIStatusError

logger = logging.getLogger(__name__)

class OrderExtractor:
    def __init__(self, client: AsyncOpenAI, primary_model: str, fallback_model: str):
        self.client = client
        self.primary_model = primary_model
        self.fallback_model = fallback_model

    async def extract_order(self, raw_text: str) -> OrderExtractionResult:
        system_prompt = (
            "Bạn là trợ lý trích xuất đơn hàng cho shop bán băng cassette. "
            "Nhiệm vụ: Trích xuất thông tin khách hàng, số điện thoại, địa chỉ, hàng hoá, "
            "tiền COD và phương thức thanh toán từ tin nhắn chat tự nhiên. "
            "Trả về đúng định dạng JSON yêu cầu. Tự động quy đổi tiền: 100k -> 100000."
        )

        models_to_try = [self.primary_model, self.fallback_model]
        last_error = None

        for model in models_to_try:
            try:
                # 1. Attempt strict schema parsing (OpenAI models)
                try:
                    response = await self.client.beta.chat.completions.parse(
                        model=model,
                        messages=[
                            {"role": "system", "content": system_prompt},
                            {"role": "user", "content": raw_text}
                        ],
                        response_format=OrderExtractionResult,
                        temperature=0.1
                    )
                    parsed = response.choices[0].message.parsed
                    if parsed:
                        return parsed
                except Exception as parse_err:
                    logger.warning(f"Strict parse unsupported on {model}, falling back to json_object: {parse_err}")
                
                # 2. Fallback to generic json_object mode (Compatible with any model on 9router)
                response = await self.client.chat.completions.create(
                    model=model,
                    messages=[
                        {"role": "system", "content": f"{system_prompt}\nĐịnh dạng JSON theo schema: {OrderExtractionResult.model_json_schema()}"},
                        {"role": "user", "content": raw_text}
                    ],
                    response_format={"type": "json_object"},
                    temperature=0.1
                )
                content = response.choices[0].message.content
                return OrderExtractionResult.model_validate_json(content)

            except (APIConnectionError, RateLimitError, APIStatusError) as e:
                logger.error(f"Model {model} failed: {e}. Trying fallback...")
                last_error = e

        raise RuntimeError(f"All LLM extraction attempts failed. Last error: {last_error}")
```

---

### 4. Settings Management (Pydantic-Settings v2)

```python
from pathlib import Path
from pydantic import SecretStr, Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

class AppSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )

    # Telegram configuration
    telegram_bot_token: SecretStr
    allowed_telegram_user_ids: list[int] = Field(
        default_factory=list,
        description="Comma-separated Telegram user IDs allowed to interact with the bot"
    )

    # LLM & 9router Gateway configuration
    llm_base_url: str = "https://api.9router.com/v1"
    llm_api_key: SecretStr
    llm_primary_model: str = "gpt-4o-mini"
    llm_fallback_model: str = "gemini-2.0-flash"
    llm_timeout_seconds: float = 30.0

    # Storage
    database_path: Path = Path("data/cassette_store.db")
    debug: bool = False

    @field_validator("allowed_telegram_user_ids", mode="before")
    @classmethod
    def parse_user_ids(cls, v):
        if isinstance(v, str):
            if not v.strip():
                return []
            return [int(x.strip()) for x in v.split(",") if x.strip()]
        return v
```

Sample `.env` file:
```env
TELEGRAM_BOT_TOKEN="1234567890:ABCdefGHIjklMNOpqrSTUvwxYZ"
ALLOWED_TELEGRAM_USER_IDS="102938475,987654321"

LLM_BASE_URL="https://api.9router.com/v1"
LLM_API_KEY="sk-9router-secret-key"
LLM_PRIMARY_MODEL="gpt-4o-mini"
LLM_FALLBACK_MODEL="gemini-2.0-flash"

DATABASE_PATH="data/cassette_store.db"
```

---

## Alternatives Considered

| Recommended | Alternative | When to Use Alternative |
|-------------|-------------|-------------------------|
| **aiosqlite** | **SQLAlchemy Async / Tortoise ORM** | Only if domain has 20+ tables with complex relation graphs and multi-database migrations. For a 3-table store bot, ORMs add 300+ lines of async session lifecycle ceremony without value. |
| **aiosqlite** | **Standard sqlite3 + asyncio.to_thread** | Acceptable for quick prototypes, but `aiosqlite` encapsulates context managers and thread pools cleanly with fewer bugs. |
| **pydantic-settings** | **python-dotenv** | Use `python-dotenv` only if zero additional dependencies are permitted. `python-dotenv` lacks type validation and fails silently if env vars are malformed or missing. |
| **openai (AsyncOpenAI)** | **httpx raw calls** | When zero external client dependencies are desired. However, `openai` already provides connection pooling, retry logic, error hierarchies, and type definitions out of the box. |
| **python-telegram-bot** | **aiogram (v3)** | Both are excellent modern async frameworks. PTB is chosen here because of simpler high-level conversation handling, stability, and direct standard library alignment without extra FSM boilerplate. |

---

## What NOT to Use

| Avoid | Why | Use Instead |
|-------|-----|-------------|
| **Synchronous `sqlite3` in async handlers** | Blocks Python's single-threaded event loop during disk writes; freezes bot responses for all users. | `aiosqlite` with WAL mode. |
| **FastAPI / Flask / Webhook servers** | Requires public static IP, HTTPS certificates, reverse proxy (Nginx), or tunnel (ngrok) for local running. Unnecessary operational friction for a private internal bot. | PTB's built-in `Application.run_polling()`. |
| **Redis / Celery** | Overkill complexity for low-throughput retail bot (<100 orders/day). Adds external service failure modes. | SQLite for persistence and Python `asyncio` for background operations. |
| **Strict JSON schema only (without fallback)** | 9router routes to heterogeneous models; models from some providers crash with HTTP 400 when sent OpenAI `json_schema` parameters. | 2-tier extractor: try `beta.chat.completions.parse()`, fallback to `response_format={"type": "json_object"}` + `Pydantic.model_validate_json()`. |
| **Hardcoded Vietnamese strings in queries** | Fails on diacritic accents and informal address queries. | Use SQL parameters and SQLite `LIKE` queries with normalized strings. |

---

## Version Compatibility

| Package A | Compatible With | Notes |
|-----------|-----------------|-------|
| `python-telegram-bot==22.8` | `httpx~=0.28.1`, `Python >= 3.9` | Fully async; supports Bot API 7.3+ `CopyTextButton`. |
| `openai==3.37.0` | `pydantic>=2.8.0`, `httpx>=0.28.0` | Supports structured output parsing (`parse`) and custom `base_url`. |
| `pydantic-settings==2.16.1` | `pydantic>=2.14.0` | Provides unified environment and secret management. |
| `aiosqlite==0.22.1` | `Python >= 3.8` | Stable thread-pool async bridge to SQLite. |

---

## Sources

- [PyPI - python-telegram-bot](https://pypi.org/project/python-telegram-bot/) — verified v22.8 release and Bot API 7.3+ CopyTextButton support.
- [PyPI - openai](https://pypi.org/project/openai/) — verified v3.37.0 release, `AsyncOpenAI`, and structured output support.
- [PyPI - pydantic-settings](https://pypi.org/project/pydantic-settings/) — verified v2.16.1 release and type coercion capabilities.
- [PyPI - aiosqlite](https://pypi.org/project/aiosqlite/) — verified v0.22.1 release.
- [Telegram Bot API Documentation](https://core.telegram.org/bots/api#copytextbutton) — verified `CopyTextButton` specification.
