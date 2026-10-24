# Phase 02: LLM Ingestion & Interactive Confirmation - Research

**Researched:** 2026-10-24
**Domain:** Natural Language Order Ingestion, 9router LLM Gateway (OpenAI-compatible), Structured Outputs, Telegram Inline UX & SQLite Persistence
**Confidence:** HIGH

## Summary

Phase 02 implements the core value proposition of the Cassette Store Telegram Chatbot: allowing non-technical or elderly store owners to forward arbitrary, unstructured Vietnamese order messages (from Zalo, Facebook, SMS) or photos with captions into Telegram. The bot contacts the 9router LLM gateway to extract structured order fields (customer name, phone, shipping address, tape titles, order total, COD amount, payment method), validates and cross-references customer history against SQLite, and presents an interactive two-phase Preview Card with one-tap inline buttons (`[✅ Xác nhận lưu]` and `[❌ Huỷ bỏ]`) before committing any data.

The technical architecture centers on three robust decoupled layers:
1. **Extraction Service (`src/services/extractor.py`):** An asynchronous client wrapping `openai.AsyncOpenAI` configured for 9router. It implements a 2-tier fallback strategy (`beta.chat.completions.parse` with Pydantic schema first; graceful fallback to `response_format={"type": "json_object"}` with `model_validate_json` for router backends lacking strict `json_schema` support) combined with deterministic phone regex normalization and Vietnamese currency parsing rules ("250k", "1tr2", "cọc 50k thu 200k").
2. **Customer Intelligence & History Layer (`src/db/orders.py`, `src/db/customers.py`):** Fast indexed queries against SQLite (`idx_orders_customer_id`, `idx_customers_name`) that instantly summarize previous order count, lifetime spend, BOM_HANG alert flags, and auto-populate existing shipping addresses for returning buyers.
3. **Interactive Telegram Ingestion Handler (`src/bot/handlers/ingest.py`, `src/bot/handlers/callbacks.py`):** Message handlers capturing text and photos with captions, generating short unique draft IDs stored in `context.user_data["pending_orders"]`, rendering high-clarity HTML cards, and handling stateless inline callbacks without blocking the event loop or exceeding Telegram's 64-byte `callback_data` limit.

**Primary recommendation:** Use `openai.AsyncOpenAI` with a 2-tier structured fallback, store temporary order drafts in `context.user_data["pending_orders"]` using compact 8-character hex IDs (`ord:cf:<id>`, `ord:ca:<id>`), query customer stats in a single aggregated SQLite query, and render preview cards using Telegram HTML formatting with `html.escape`.

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
- **D-01:** Số điện thoại (SĐT) là khoá nhận diện duy nhất và bắt buộc (`sđt là key`). Chỉ cần có SĐT hợp lệ là bot tiến hành tạo đơn nháp và hiển thị thẻ xem trước. Các trường thông tin khác (tên khách, địa chỉ, danh sách băng cassette, giá tiền) nếu thiếu trong tin nhắn thì hiển thị dạng placeholder `[Chưa có]` và vẫn cho phép lưu đơn.
- **D-02:** Tin nhắn không phải đơn hàng (không tìm thấy SĐT hợp lệ hoặc tin nhắn chat thông thường): Bot nhắc nhẹ nhàng, lịch sự: *"Em không nhận diện được đơn hàng từ tin nhắn này. Bác vui lòng gửi lại tin nhắn có số điện thoại khách nhé!"* để hướng dẫn người lớn tuổi cách thao tác.
- **D-03:** Hiển thị tài chính phân tách rõ ràng 2 dòng: `Tổng tiền: ... đ` và `Tiền COD thu khách: ... đ` (kèm thông tin tiền đã cọc nếu có) để người lớn tuổi nhìn một cái hiểu ngay, tránh nhầm lẫn giữa tiền hàng và tiền thu hộ COD.
- **D-04:** Bộ nút bấm Inline Keyboard dưới thẻ xem trước gồm 2 nút to trên cùng 1 hàng: `[✅ Xác nhận lưu]` và `[❌ Huỷ bỏ]`. Khi bấm `❌ Huỷ bỏ`, tin nhắn thẻ được cập nhật thông báo huỷ, không ghi gì vào DB. Khi bấm `✅ Xác nhận lưu`, ghi dữ liệu vào DB và cập nhật tin nhắn thẻ thành thông báo thành công.
- **D-05:** Khi trích xuất được SĐT, bot tự động truy vấn DB để kiểm tra khách cũ:
  - Nếu là khách quen: Hiển thị ngay phần tóm tắt lịch sử mua hàng trong thẻ xem trước: Số lượng đơn đã đặt, tổng tiền đã mua, và đặc biệt là **Cảnh báo bom hàng** (nếu khách có đơn ở trạng thái `BOM_HANG`).
- **D-06:** Tự động điền địa chỉ cho khách quen:
  - Nếu khách quen KHÔNG nhắn lại địa chỉ trong tin nhắn mới:
    - Nếu khách chỉ có **1 địa chỉ** trong DB: Tự động điền địa chỉ đó vào đơn và ghi chú rõ trong preview card `📍 Địa chỉ (tự lấy từ đơn trước): ...`.
    - Nếu khách có **từ 2 địa chỉ trở lên** đã lưu: Bot hiển thị các nút Inline bấm nhanh cho từng địa chỉ để người dùng chạm chọn 1 trong các địa chỉ cũ, hoặc chọn nhập địa chỉ mới.
  - Nếu khách quen nhắn **địa chỉ mới** khác các địa chỉ cũ đã lưu: Tự động bổ sung địa chỉ mới vào danh sách `addresses` của khách hàng trong DB và snapshot vào đơn hàng hiện tại.
- **D-07:** Cơ chế lưu tạm sử dụng in-memory `context.user_data["pending_orders"][draft_id]`. Mỗi thẻ preview gắn 1 `draft_id` ngẫu nhiên (UUID hoặc chuỗi ngắn), nút bấm Inline mang `callback_data` có cấu trúc: `ord:confirm:<draft_id>` và `ord:cancel:<draft_id>`. Nếu bot bị restart khiến mất dữ liệu tạm trong memory, khi bấm nút bot phản hồi thông báo: *"Thao tác hết hạn, bác vui lòng gửi lại tin nhắn nhé!"*.
- **D-08:** Hỗ trợ gửi dồn nhiều tin nhắn cùng lúc (đa đơn độc lập): Mỗi tin nhắn gửi đến sinh một thẻ xem trước với `draft_id` độc lập. Người dùng có thể paste liên tục 2-3 tin nhắn đơn và bấm xác nhận từng thẻ riêng biệt mà không bị ghi đè.
- **D-09:** Khi người dùng gửi 1 bức ảnh kèm caption (chú thích ảnh): Bot lấy caption gửi cho LLM bóc tách như tin nhắn text thông thường, đồng thời trích xuất `photo.file_id` (lấy độ phân giải cao nhất) đưa vào danh sách `photo_file_ids` của đơn nháp để lưu vào DB khi xác nhận.
- **D-10:** Xử lý lỗi kết nối hoặc phản hồi từ 9router LLM (timeout, hết quota, format lỗi): Báo nhẹ nhàng: *"⚠️ Hệ thống bóc tách đang bận hoặc gián đoạn kết nối. Bác vui lòng thử gửi lại tin nhắn sau giây lát nhé!"* và ghi log chi tiết lỗi cho kỹ thuật viên.

### Claude's Discretion
- Định dạng prompt gửi cho LLM (bao gồm hướng dẫn tiếng Việt, ví dụ tiếng lóng "250k", "1tr2", "cọc 50k thu 200k").
- Cơ chế 2-tier fallback khi gọi LLM: thử dùng `beta.chat.completions.parse()` với Pydantic schema, nếu gateway 9router không hỗ trợ `json_schema` thì fallback sang `response_format={"type": "json_object"}` kết hợp `Pydantic.model_validate_json()`.
- Cấu trúc layout chi tiết và emoji trong Preview Card sao cho thoáng mắt, dễ đọc nhất trên màn hình điện thoại.

### Deferred Ideas (OUT OF SCOPE)
- Đổi trạng thái đơn hàng (sang `Đang làm`, `Đã đóng gói`, ...) và các nút bấm sao chép 1 chạm thông tin giao hàng: thuộc Phase 3 (Ergonomic Order Management & Low-Tech Actions).
- Tìm kiếm đơn hàng bằng chat tự nhiên: thuộc Phase 4 (Natural Language Order Search).
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| INGEST-01 | Nhận tin nhắn free-text bất kỳ từ Zalo/Facebook chuyển sang; LLM (qua 9router gateway) tự động bóc tách: Tên khách, SĐT, Địa chỉ, Danh sách băng cassette, Tiền thu khách, Tiền COD, Hình thức thanh toán. | `openai.AsyncOpenAI` with system prompt tuned for Vietnamese order parsing; Pydantic model `ExtractedOrder`; multi-tier API fallback for 9router. |
| INGEST-02 | Tự động chuẩn hoá đơn vị tiền tệ tiếng Việt ("250k", "1tr2", "50 ngàn", "cọc 50k thu 200k") thành số nguyên VNĐ chuẩn xác. | LLM prompt few-shot currency normalization rules + deterministic regex post-processor ensuring `total_amount`, `cod_amount`, `deposit_amount` are non-negative integer VNĐ values. |
| INGEST-03 | Hiển thị thẻ thông tin đơn xem trước (preview card) kèm 2 nút bấm Inline: `✅ Xác nhận lưu` và `❌ Huỷ bỏ`. | PTB `InlineKeyboardMarkup` with compact 8-char hex callback tokens (`ord:cf:<id>`, `ord:ca:<id>`); formatted preview card with customer history & BOM_HANG alert. |
| INGEST-04 | Đơn hàng chỉ được ghi vào DB và gửi thông báo hoàn tất sau khi người dùng bấm nút xác nhận. | Two-phase commit: in-memory draft stored in `context.user_data["pending_orders"]`; database write only triggered in callback handler on `ord:cf:<id>`. Cancel callback discards draft without DB mutation. |
</phase_requirements>

## Project Constraints (from CLAUDE.md)

1. **Python & Async Framework:** Python 3.12+ (tested on Python 3.13.7) with `python-telegram-bot` v22.8 using native `async`/`await`.
2. **Database:** SQLite with `aiosqlite` v0.22.1 using WAL mode, `busy_timeout=5000ms`, foreign keys enabled. No synchronous `sqlite3` inside async bot handlers.
3. **LLM Gateway:** 9router (OpenAI-compatible protocol) using `openai` v3.37.0 `AsyncOpenAI`. Configurable `base_url`, `api_key` (`SecretStr`), and `model_id`.
4. **LLM Structured Output Resilience:** Strict 2-tier extractor: try `beta.chat.completions.parse()` first; catch failures and fallback to `response_format={"type": "json_object"}` + `model_validate_json()`.
5. **Access Control:** Whitelist gate verified at Handler Group -1. Only configured Telegram user IDs can trigger LLM or DB operations.
6. **No Heavy Infrastructure:** No FastAPI/Flask webhooks, no Redis, no Celery, no full-blown ORM (SQLAlchemy/Tortoise). Rely on `aiosqlite` and `context.user_data`.
7. **Elderly Low-Tech UX:** Maximum 1-tap inline buttons, no long slash commands, clear Vietnamese messages, no cryptic error traces shown to the user.

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Ingestion & Text/Photo Routing | Telegram Bot Handlers (`src/bot/handlers/ingest.py`) | Application router | Intercepts incoming messages, extracts text/caption and photo file IDs, enforces access control gate. |
| Natural Language Extraction | LLM Service (`src/services/extractor.py`) | 9router Gateway | Constructs OpenAI-compatible chat completion payload with system prompt, schema, and fallback tiers. |
| Phone & Currency Normalization | Domain Validation / Post-processor | Pydantic Schema | Normalizes Vietnamese colloquial units ("250k" -> 250000, "0912.345.678" -> "0912345678") into strict integers/canonical strings. |
| Customer Matching & History Lookup | Persistence Layer (`src/db/customers.py`, `src/db/orders.py`) | SQLite Index | Matches customer by phone, computes order count, total revenue, and BOM_HANG flags via indexed query. |
| Interactive Confirmation (Two-Phase Commit) | Callback Handler (`src/bot/handlers/callbacks.py`) | Bot Context Memory (`context.user_data`) | Holds unconfirmed draft in memory; executes transactional insert to `customers` and `orders` only upon explicit callback confirmation. |

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| `openai` | `~=3.37.0` [VERIFIED: PyPI] | LLM Client for 9router | Official client supporting custom `base_url`, async streaming, and `beta.chat.completions.parse`. |
| `pydantic` | `~=2.14.1` [VERIFIED: PyPI] | Schema validation & parsing | Rust-backed fast validation for LLM extraction models (`ExtractedOrder`) and domain models. |
| `python-telegram-bot` | `~=22.8` [VERIFIED: PyPI] | Bot framework & Inline keyboards | Async Bot API 7.x+ framework; handles message routing, inline buttons, and photo attachments. |
| `aiosqlite` | `~=0.22.1` [VERIFIED: PyPI] | Async SQLite client | Non-blocking thread-pool driver for local SQLite with WAL mode and row factory dictionaries. |
| `pydantic-settings` | `~=2.16.1` [VERIFIED: PyPI] | Configuration management | Loads `.env` secrets (`SecretStr`) and gateway settings without polluting logs. |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| `httpx` | `~=0.28.1` [VERIFIED: PyPI] | HTTP transport | Underlying client for `openai` and PTB; handles timeouts and proxy connections. |
| `pytest` | `~=9.1.1` [VERIFIED: PyPI] | Test runner | Runs unit and integration test suites. |
| `pytest-asyncio` | `~=1.4.0` [VERIFIED: PyPI] | Async test fixtures | Drives async test execution for DB and handler logic. |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| `openai.AsyncOpenAI` | Raw `httpx.AsyncClient` | Raw `httpx` requires hand-rolling retry logic, connection pooling, and JSON schema parsing. `openai` provides these out of the box. |
| In-memory `context.user_data` | SQLite temporary draft table | SQLite draft table requires schema migrations and periodic TTL cleanup tasks. For human-in-the-loop confirmation lasting <2 minutes, in-memory dict with expiry message is simpler and cleaner. |
| HTML Parse Mode | MarkdownV2 | MarkdownV2 requires escaping 18 reserved characters (including `.`, `-`, `_`, `!`), causing frequent runtime parsing crashes on customer addresses. HTML only requires escaping `&`, `<`, `>`. |

## Package Legitimacy Audit

All packages are already installed in `.venv` and verified in Phase 01.

| Package | Registry | Age | Downloads | Source Repo | Verdict | Disposition |
|---------|----------|-----|-----------|-------------|---------|-------------|
| `openai` | PyPI | 4+ yrs | High (>10M/wk) | github.com/openai/openai-python | [OK] | Approved |
| `pydantic` | PyPI | 7+ yrs | High (>80M/wk) | github.com/pydantic/pydantic | [OK] | Approved |
| `pydantic-settings` | PyPI | 2+ yrs | High (>15M/wk) | github.com/pydantic/pydantic-settings | [OK] | Approved |
| `python-telegram-bot` | PyPI | 9+ yrs | High (>1M/wk) | python-telegram-bot.org | [OK] | Approved |
| `aiosqlite` | PyPI | 6+ yrs | High (>2M/wk) | github.com/omnilib/aiosqlite | [OK] | Approved |

**Packages removed due to [SLOP] verdict:** None
**Packages flagged as suspicious [SUS]:** None

## Architecture Patterns

### System Architecture Diagram

```
User (Telegram)
      │
      ▼
Group -1: Whitelist Gate (src/bot/security.py)
      │
      ├─ [Blocked: Unrecognized User ID] ──> Reject silently / log warning
      │
      ▼
Group 0: Message Ingestion (src/bot/handlers/ingest.py)
      │
      ├─ Text Message OR Photo with Caption
      │   Extract raw_text & photo_file_id (highest resolution)
      │
      ▼
LLM Extraction Service (src/services/extractor.py)
      │
      ├─ Tier 1: client.beta.chat.completions.parse(model=..., response_format=ExtractedOrder)
      │   └─ [On 400/Unsupported json_schema] ──>
      │
      ├─ Tier 2: client.chat.completions.create(response_format={"type": "json_object"})
      │          + ExtractedOrder.model_validate_json(...)
      │   └─ [On LLM Timeout/Down] ──> Polite user message (D-10)
      │
      ▼
Phone Validation & Customer Lookup (src/db/customers.py & src/db/orders.py)
      │
      ├─ Phone missing/invalid? ──> Send polite guidance message (D-02)
      │
      ├─ Phone exists in DB?
      │   ├─ Compute stats: total orders, total revenue, BOM_HANG count
      │   └─ Address resolution (D-06):
      │       ├─ Missing in text + 1 existing addr: Auto-populate
      │       ├─ Missing in text + >=2 existing addrs: Show address selection buttons
      │       └─ New addr in text: Append to customer record on save
      │
      ▼
Draft Generation & Preview Card Rendering
      │
      ├─ Generate draft_id = uuid.uuid4().hex[:8]
      ├─ Store in context.user_data["pending_orders"][draft_id]
      ├─ Build Inline Keyboard: [✅ Xác nhận lưu: ord:cf:<id>] [❌ Huỷ bỏ: ord:ca:<id>]
      └─ Send Preview Message (HTML format, high readability)
      │
      ▼
Interactive Callback (src/bot/handlers/callbacks.py)
      │
      ├─ ord:ca:<id> (Cancel) ──> Discard draft, update card to "Đã huỷ", 0 DB writes
      │
      └─ ord:cf:<id> (Confirm)
          ├─ Expired/missing draft? ──> "Thao tác hết hạn, bác vui lòng gửi lại tin nhắn nhé!"
          ├─ Insert/Update customer in DB
          ├─ Insert order record in DB (status=CHO_LAM)
          └─ Update card to "✅ Đã lưu đơn thành công #<order_id>"
```

### Component Responsibilities Table

| Component | File Path | Key Functions |
|-----------|-----------|---------------|
| Extractor Schema | `src/models/extractor.py` | `ExtractedOrder` Pydantic model with fields, currency & phone validators |
| LLM Extractor | `src/services/extractor.py` | `extract_order_from_text()`, 2-tier fallback, Vietnamese system prompt |
| Customer Aggregates | `src/db/orders.py` | `get_customer_order_stats(db, customer_id)` returning count, total spent, bom_count |
| Ingest Handlers | `src/bot/handlers/ingest.py` | `handle_text_order()`, `handle_photo_order()`, preview card renderer |
| Callback Handlers | `src/bot/handlers/callbacks.py` | `handle_order_callback()` processing `ord:cf:`, `ord:ca:`, `ord:ad:` |
| Application Wiring | `src/bot/app.py` | Registers `MessageHandler` and `CallbackQueryHandler` in Group 0 |

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| JSON parsing from LLM | Custom regex string search | `openai` structured outputs + `Pydantic` `model_validate_json` | LLM outputs can include markdown backticks (````json...````), trailing commas, or nested objects that break naive string splitting. |
| Telegram Callback Answering | Delayed async logic before answering | Immediate `await query.answer()` at handler entry | Telegram displays a 30-second spinning loader on the user's screen if `answer()` is not called within ~3 seconds. |
| Telegram Message Escaping | MarkdownV2 backslash escaping | HTML formatting (`parse_mode="HTML"`) with `html.escape()` | Vietnamese diacritics and address punctuation (`-`, `.`, `,`, `(`, `)`) trigger entity syntax errors in MarkdownV2. |
| Currency Parsing | Pure hardcoded math | Hybrid: LLM prompt examples + safe integer fallback | Vietnamese slang ("1tr2", "250k", "50 ngàn", "cọc 50k thu 200k") has contextual nuances best resolved by LLM, with type-safety enforced by Pydantic integers. |

## Common Pitfalls

### Pitfall 1: Telegram Callback Data 64-Byte Overflow
**What goes wrong:** `telegram.error.BadRequest: Button_data_invalid` crashes the bot when rendering inline buttons.
**Why it happens:** Telegram API enforces a strict maximum length of 64 bytes on `InlineKeyboardButton.callback_data`. Using `ord:confirm:c5b8e967-4d7a-4c22-b9e7-4b71e16f3d8a` is 48 bytes, but longer names or nested parameters like `ord:select_customer_address:c5b8e967-4d7a-4c22-b9e7-4b71e16f3d8a:address_index_1` easily exceeds 64 bytes.
**How to avoid:** Use ultra-short prefixes and 8-character hex IDs: `ord:cf:<hex8>` (15 bytes), `ord:ca:<hex8>` (15 bytes), `ord:ad:<hex8>:<idx>` (17 bytes).
**Warning signs:** Exception `Button_data_invalid` in logs when user sends order.

### Pitfall 2: 9router / OpenAI-Compatible Gateway `json_schema` Incompatibility
**What goes wrong:** `beta.chat.completions.parse()` crashes with HTTP 400 `BadRequestError: Unrecognized request parameter: response_format.json_schema`.
**Why it happens:** 9router routes to diverse backend models (OpenAI, Anthropic, DeepSeek, Google, local models). Not all underlying endpoints support strict OpenAI structured output schemas.
**How to avoid:** Always wrap `parse()` in a try/except block. On `BadRequestError` or validation failure, immediately retry with standard `response_format={"type": "json_object"}` and parse using `ExtractedOrder.model_validate_json()`.
**Warning signs:** Bot sends error message *"⚠️ Hệ thống bóc tách đang bận..."* even though the model is online.

### Pitfall 3: Blocking Event Loop on LLM Calls
**What goes wrong:** Other users experience lag or frozen bot responses while one user's order is being parsed.
**Why it happens:** Calling synchronous OpenAI client `openai.OpenAI()` instead of `openai.AsyncOpenAI()` inside async handlers blocks the single-threaded asyncio event loop.
**How to avoid:** Strictly instantiate and call `AsyncOpenAI(base_url=..., api_key=...)` with `await client.chat.completions...`.
**Warning signs:** `/ping` command takes 5+ seconds to respond when an order is processing.

### Pitfall 4: Race Conditions & Overwrites in In-Memory Draft State
**What goes wrong:** A store owner pastes 2 orders in rapid succession; the second preview card overwrites the first, and confirming card 1 saves card 2.
**Why it happens:** Storing a single draft in `context.user_data["pending_order"]` instead of a dictionary keyed by unique `draft_id`.
**How to avoid:** Use `context.user_data.setdefault("pending_orders", {})[draft_id] = draft_data`. Each message generates its own `draft_id`.
**Warning signs:** Confirmation button on earlier card modifies the wrong customer.

## Code Examples

### 1. Pydantic Extraction Schema (`src/models/extractor.py`)
```python
# [VERIFIED: Pydantic v2 documentation]
from pydantic import BaseModel, Field


class ExtractedOrder(BaseModel):
    """Pydantic model for structured LLM order extraction."""

    customer_name: str | None = Field(default=None, description="Tên khách hàng nếu có trong tin nhắn")
    customer_phone: str | None = Field(default=None, description="Số điện thoại khách hàng (10 chữ số)")
    shipping_address: str | None = Field(default=None, description="Địa chỉ giao hàng chi tiết")
    items_text: str | None = Field(default=None, description="Danh sách các cuốn băng cassette kèm số lượng")
    total_amount: int = Field(default=0, description="Tổng giá trị đơn hàng tính theo VNĐ")
    cod_amount: int = Field(default=0, description="Số tiền COD cần thu khách khi giao tính theo VNĐ")
    deposit_amount: int = Field(default=0, description="Số tiền khách đã chuyển khoản đặt cọc trước (nếu có)")
    payment_method: str = Field(default="COD", description="Hình thức thanh toán: COD hoặc CHUYEN_KHOAN")
    notes: str = Field(default="", description="Ghi chú thêm về đơn hàng hoặc yêu cầu của khách")
```

### 2. Dual-Mode 9router LLM Extractor with Fallback (`src/services/extractor.py`)
```python
# [VERIFIED: OpenAI Python SDK v1.50+ / v3.37]
import json
import logging
from openai import AsyncOpenAI, BadRequestError
from src.models.extractor import ExtractedOrder

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """
Bạn là trợ lý AI chuyên bóc tách đơn hàng cho shop bán băng cassette tại Việt Nam.
Nhiệm vụ: Trích xuất thông tin đơn hàng từ tin nhắn chat tự do của khách.

Quy tắc tài chính & đơn vị tiền tệ:
- Chuẩn hoá mọi tiếng lóng tiền tệ thành số nguyên VNĐ:
  + "250k" -> 250000
  + "1tr2", "1.2tr", "1,2 triệu" -> 1200000
  + "50 ngàn", "50k" -> 50000
- Phân biệt giữa Tổng tiền và Tiền COD:
  + Nếu có đặt cọc (VD: "cọc 50k thu 200k", "tổng 250k đã ck 50k"): total_amount = 250000, deposit_amount = 50000, cod_amount = 200000
  + Nếu khách chuyển khoản hết (VD: "đã ck đủ 300k"): total_amount = 300000, cod_amount = 0, payment_method = "CHUYEN_KHOAN"
  + Nếu giao hàng thu tiền bình thường: cod_amount = total_amount, payment_method = "COD"

Quy tắc số điện thoại:
- Tìm số điện thoại di động Việt Nam (thường gồm 10 số, bắt đầu bằng 03, 05, 07, 08, 09 hoặc +84).
- Chuẩn hoá về định dạng 10 số bắt đầu bằng 0 (VD: "0912345678").
- Nếu không tìm thấy bất kỳ số điện thoại nào, để customer_phone = null.
"""

async def extract_order_from_text(
    client: AsyncOpenAI,
    model_id: str,
    text: str,
) -> ExtractedOrder | None:
    """Extract order info using 2-tier fallback strategy."""
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": f"<message>{text}</message>"},
    ]

    # Tier 1: Try strict structured output parsing
    try:
        response = await client.beta.chat.completions.parse(
            model=model_id,
            messages=messages,
            response_format=ExtractedOrder,
            timeout=15.0,
        )
        parsed = response.choices[0].message.parsed
        if parsed:
            return parsed
    except (BadRequestError, Exception) as e:
        logger.warning("Tier 1 structured output failed, falling back to JSON mode: %s", e)

    # Tier 2: Fallback to standard json_object response format
    try:
        response = await client.chat.completions.create(
            model=model_id,
            messages=messages,
            response_format={"type": "json_object"},
            timeout=15.0,
        )
        content = response.choices[0].message.content
        if content:
            return ExtractedOrder.model_validate_json(content)
    except Exception as e:
        logger.error("Tier 2 LLM extraction failed: %s", e)
        return None

    return None
```

### 3. Customer History & BOM_HANG Query (`src/db/orders.py`)
```python
# [VERIFIED: aiosqlite query pattern]
import aiosqlite

async def get_customer_order_stats(
    db: aiosqlite.Connection, customer_id: int
) -> dict[str, int]:
    """Retrieve customer lifetime order count, total spend, and BOM_HANG count."""
    query = """
        SELECT 
            COUNT(*) AS total_orders,
            COALESCE(SUM(CASE WHEN status != 'HUY_DON' THEN total_amount ELSE 0 END), 0) AS total_spent,
            COUNT(CASE WHEN status = 'BOM_HANG' THEN 1 END) AS bom_count
        FROM orders 
        WHERE customer_id = ?
    """
    async with db.execute(query, (customer_id,)) as cursor:
        row = await cursor.fetchone()
        if not row:
            return {"total_orders": 0, "total_spent": 0, "bom_count": 0}
        return {
            "total_orders": row["total_orders"],
            "total_spent": row["total_spent"],
            "bom_count": row["bom_count"],
        }
```

### 4. Preview Card Layout & Inline Buttons (`src/bot/handlers/ingest.py`)
```python
# [VERIFIED: python-telegram-bot InlineKeyboardMarkup]
import html
from telegram import InlineKeyboardButton, InlineKeyboardMarkup

def render_preview_card(draft: dict, stats: dict | None) -> tuple[str, InlineKeyboardMarkup]:
    """Format elderly-friendly HTML preview card and 1-tap inline buttons."""
    name = html.escape(draft.get("customer_name") or "[Chưa có]")
    phone = html.escape(draft.get("customer_phone") or "[Chưa có]")
    address = html.escape(draft.get("shipping_address") or "[Chưa có]")
    items = html.escape(draft.get("items_text") or "[Chưa có]")
    total = f"{draft.get('total_amount', 0):,} đ".replace(",", ".")
    cod = f"{draft.get('cod_amount', 0):,} đ".replace(",", ".")
    deposit = draft.get("deposit_amount", 0)

    # Customer history tag
    history_tag = ""
    warning_tag = ""
    if stats and stats["total_orders"] > 0:
        spent = f"{stats['total_spent']:,} đ".replace(",", ".")
        history_tag = f" <i>[Khách quen: {stats['total_orders']} đơn - {spent}]</i>"
        if stats["bom_count"] > 0:
            warning_tag = f"\n⚠️ <b>CẢNH BÁO: Khách từng có {stats['bom_count']} đơn BOM HÀNG!</b>"

    deposit_info = f" (đã cọc {deposit:,} đ)".replace(",", ".") if deposit > 0 else ""

    text = (
        f"📦 <b>ĐƠN HÀNG MỚI (Xem trước)</b>\n"
        f"👤 <b>Khách:</b> {name}{history_tag}\n"
        f"📞 <b>SĐT:</b> <code>{phone}</code>\n"
        f"📍 <b>Địa chỉ:</b> {address}\n"
        f"📼 <b>Băng cassette:</b> {items}\n"
        f"💰 <b>Tổng tiền:</b> {total}\n"
        f"💵 <b>Tiền COD thu:</b> {cod}{deposit_info}"
        f"{warning_tag}\n"
        f"────────────────────\n"
        f"Bác bấm nút bên dưới để xác nhận nhé:"
    )

    draft_id = draft["draft_id"]
    keyboard = [
        [
            InlineKeyboardButton("✅ Xác nhận lưu", callback_data=f"ord:cf:{draft_id}"),
            InlineKeyboardButton("❌ Huỷ bỏ", callback_data=f"ord:ca:{draft_id}"),
        ]
    ]
    return text, InlineKeyboardMarkup(keyboard)
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Unstructured regex parsing of order chats | LLM gateway (9router) with Pydantic structured output | 2024 / GPT-4o era | Accurately extracts messy conversational Vietnamese, nicknames, and flexible payment arrangements. |
| Strict JSON Schema only | 2-Tier Fallback (`parse` -> `json_object` + `model_validate_json`) | 2024-2025 | Prevents 400 crashes on heterogeneous router backends that lack strict schema support. |
| Long ConversationHandler for text inputs | Stateless Inline Keyboard with short callback tokens | PTB v20+ async | Immune to conversation state locks; elderly users can tap anytime without command order friction. |
| MarkdownV2 formatting | HTML parse mode with `html.escape` | Current standard | Eliminates unescaped character crashes on Vietnamese addresses and phone punctuation. |

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | 9router gateway endpoint reliably supports `gpt-4o-mini` or equivalent OpenAI-compatible model with JSON mode [ASSUMED] | Standard Stack / Extractor | If 9router is down or model ID is invalid, fallback notification (D-10) informs the user gracefully without crash. |

## Open Questions

1. **How should multi-address selection behave if user clicks Confirm without picking an address?**
   - What we know: D-06 states if customer has >=2 addresses and text lacks address, inline buttons allow picking.
   - What's unclear: Should the preview default to the most recent address if no button is tapped?
   - Recommendation: Default to the most recent address (with an inline note `📍 Địa chỉ (gần nhất): ...`), and provide inline buttons `[📍 Đổi sang địa chỉ khác]` so the user can save with 1 tap without mandatory extra clicks.

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Python | Runtime | ✓ | 3.13.7 | — |
| python-telegram-bot | Bot framework | ✓ | 22.8 | — |
| openai | LLM client | ✓ | 3.37.0 | — |
| aiosqlite | SQLite persistence | ✓ | 0.22.1 | — |
| pydantic | Data validation | ✓ | 2.14.1 | — |
| pydantic-settings | Settings | ✓ | 2.16.1 | — |
| pytest / pytest-asyncio | Test suite | ✓ | 9.1.1 / 1.4.0 | — |

**Missing dependencies:** None. All tools and runtimes are pre-installed in `.venv`.

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest 9.1.1 with pytest-asyncio 1.4.0 |
| Config file | `pyproject.toml` |
| Quick run command | `./.venv/bin/pytest tests/test_extractor.py tests/test_ingest.py -x` |
| Full suite command | `./.venv/bin/pytest` |

### Phase Requirements → Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| INGEST-01 | LLM order extraction from free-text | unit | `./.venv/bin/pytest tests/test_extractor.py -k test_extraction` | ❌ Wave 0 |
| INGEST-02 | Vietnamese currency normalization ("250k", "1tr2", deposit) | unit | `./.venv/bin/pytest tests/test_extractor.py -k test_currency` | ❌ Wave 0 |
| INGEST-03 | Preview card layout, customer history, BOM_HANG alert | unit | `./.venv/bin/pytest tests/test_ingest.py -k test_preview` | ❌ Wave 0 |
| INGEST-04 | 2-phase confirmation callback: save to DB on confirm, discard on cancel | integration | `./.venv/bin/pytest tests/test_ingest.py -k test_callback` | ❌ Wave 0 |
| INGEST-04b | Photo with caption ingestion | unit/mock | `./.venv/bin/pytest tests/test_ingest.py -k test_photo` | ❌ Wave 0 |

### Sampling Rate
- **Per task commit:** `./.venv/bin/pytest tests/test_extractor.py tests/test_ingest.py -x`
- **Per wave merge:** `./.venv/bin/pytest`
- **Phase gate:** Full suite green (all Phase 1 + Phase 2 tests pass) before verification.

### Wave 0 Gaps
- [ ] `tests/test_extractor.py` — unit tests for `ExtractedOrder`, currency normalization, and mocked `AsyncOpenAI` 2-tier fallback.
- [ ] `tests/test_ingest.py` — unit & integration tests for message handlers, preview card generation, customer history lookup, and inline callback handling.

## Security Domain

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | yes | Whitelist gate (Handler Group -1, `src/bot/security.py`) checks Telegram user ID before any ingestion handler runs. |
| V4 Access Control | yes | Callbacks and text messages from non-whitelisted user IDs are dropped immediately. |
| V5 Input Validation | yes | Vietnamese phone regex validation (`^(0|\+?84)[3|5|7|8|9][0-9]{8}$`); Pydantic schema validation for numeric fields (`total_amount >= 0`, `cod_amount >= 0`); HTML escaping for message rendering. |
| V6 Cryptography | yes | `nine_router_api_key` wrapped in `SecretStr`, never printed in logs or sent to Telegram. |

### Known Threat Patterns for LLM Chat Ingestion

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Prompt Injection / Jailbreak in order text | Tampering | Wrap raw user text in clear boundary tags (`<message>...</message>`) and explicitly instruct system prompt that text inside boundary tags is data only, never instructions. |
| Telegram Callback Tampering | Tampering | Restrict callback pattern to regex `^ord:(cf|ca|ad):[a-f0-9]{8}(:\d+)?$`; verify `draft_id` exists in `context.user_data["pending_orders"]`. |
| Memory Exhaustion via Concurrent Orders | Denial of Service | Store max 20 pending drafts per user; expire drafts older than 1 hour or prune oldest on overflow. |

## Sources

### Primary (HIGH confidence)
- Official PyPI & Codebase: `CLAUDE.md`, `src/config.py`, `src/db/connection.py`, `src/db/schema.py`, `src/bot/security.py`.
- Telegram Bot API Documentation: `core.telegram.org/bots/api#inlinekeyboardmarkup` & `callback_data` 64-byte specification.
- OpenAI Python SDK documentation: `github.com/openai/openai-python` structured outputs & `AsyncOpenAI` specifications.

### Secondary (MEDIUM confidence)
- Context & Requirements: `.planning/phases/02-llm-ingestion-interactive-confirmation/02-CONTEXT.md`, `.planning/REQUIREMENTS.md`.

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - All core libraries already pinned, installed, and verified in `.venv`.
- Architecture: HIGH - 2-tier fallback, in-memory drafts, and callback mechanics align with existing codebase conventions.
- Pitfalls: HIGH - Documented Telegram 64-byte callback limit, MarkdownV2 escape crashes, and router schema incompatibilities.

**Research date:** 2026-10-24
**Valid until:** 2026-11-24 (stable 30-day window)
