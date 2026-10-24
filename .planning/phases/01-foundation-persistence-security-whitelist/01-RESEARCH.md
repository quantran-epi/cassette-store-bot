# Phase 1: Foundation, Persistence & Security Whitelist - Research

**Researched:** 2026-10-24
**Domain:** Python Async Architecture, Telegram Bot Security, SQLite Persistence (aiosqlite), Pydantic Settings
**Confidence:** HIGH

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

#### Whitelist & Security
- **D-01:** Khi người lạ (User ID ngoài whitelist) nhắn tin đến bot, bot phản hồi từ chối lịch sự và hiển thị Telegram User ID của họ (để admin/chủ shop dễ sao chép thêm vào cấu hình whitelist khi cần).
- **D-02:** Whitelist hỗ trợ nạp từ biến môi trường `TELEGRAM_WHITELIST_USER_IDS` dưới dạng chuỗi phân tách bởi dấu phẩy, tự động chuyển đổi thành `list[int]` qua Pydantic-Settings.

#### Database & Persistence
- **D-03:** Bảng `customers` sử dụng cột JSON array để lưu danh sách nhiều số điện thoại (`phones`) và nhiều địa chỉ (`addresses`), kèm `notes` và `name`. Giữ thiết kế tinh gọn, tránh phải JOIN 3 bảng.
- **D-04:** Bảng `orders` lưu snapshot thông tin khách tại thời điểm đặt (tên, SĐT, địa chỉ nhận hàng), chi tiết hàng hoá text tự do, tổng tiền, COD, hình thức thanh toán, mã vận đơn và cột `photo_file_ids` (mảng JSON lưu danh sách file_id Telegram).
- **D-05:** Cấu hình SQLite kích hoạt `PRAGMA journal_mode=WAL` và `PRAGMA busy_timeout=5000` thông qua `aiosqlite` để đảm bảo tương thích async không gây lock database.
- **D-06:** Vòng đời đơn hàng quản lý qua enum 7 trạng thái: `CHO_LAM` (Chờ làm), `DANG_LAM` (Đang làm), `DA_DONG_GOI` (Đã đóng gói), `DA_TAO_DON` (Đã tạo đơn trên app vận chuyển), `SHIPPER_DA_LAY` (Shipper đã lấy hàng), `DA_GIAO` (Đã giao thành công), `BOM_HANG` (Bom hàng), `HUY_DON` (Huỷ đơn).

#### Code Organization & Settings
- **D-07:** Tổ chức mã nguồn trong thư mục `src/` phân tách rõ ràng:
  - `src/config.py`: Quản lý cấu hình `Settings` với Pydantic-Settings v2.
  - `src/db/`: Quản lý kết nối SQLite `aiosqlite`, tạo schema và các hàm CRUD cơ sở.
  - `src/models/`: Định nghĩa các Pydantic models và domain schemas.
  - `src/bot/`: Khởi tạo Application `python-telegram-bot`, security middleware / filter chặn whitelist, và lệnh cơ bản `/start`, `/ping`.
  - `main.py` ở root: Điểm khởi chạy chính ứng dụng.

### Claude's Discretion
- Định dạng tin nhắn phản hồi `/start` và `/ping` cho admin kiểm tra trạng thái bot khởi động.
- Chi tiết câu lệnh SQL CREATE TABLE và index trên các cột tìm kiếm (`customer_id`, `created_at`, `status`).

### Deferred Ideas (OUT OF SCOPE)
None — discussion stayed within phase scope.
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| **CFG-01** | Cấu hình hệ thống local (`.env` / file settings): quản lý Bot Token, danh sách Whitelist User IDs, URL 9router, API Key và Model ID. | `pydantic-settings` v2 `BaseSettings` với `field_validator(mode="before")` tách chuỗi SĐT/User ID, `SecretStr` bảo vệ Token/API Key. |
| **SEC-01** | Whitelist Telegram User ID bảo mật — chỉ các Telegram User ID được cấu hình mới có quyền sử dụng bot; chặn và từ chối toàn bộ tương tác từ người lạ. | `TypeHandler(Update, whitelist_gate)` đặt tại `group=-1` kết hợp `raise ApplicationHandlerStop()`, gửi thông báo từ chối lịch sự kèm User ID của người gửi. |
| **DATA-01** | Khách hàng được lưu trữ với tên, hỗ trợ nhiều số điện thoại, nhiều địa chỉ nhận hàng, và ghi chú đi kèm. | Bảng `customers` với cột JSON array `phones` (`TEXT DEFAULT '[]'`) và `addresses` (`TEXT DEFAULT '[]'`), model `Customer` xác thực danh sách. |
| **DATA-02** | Đơn hàng lưu chi tiết hàng hoá dạng text tự do (tên băng cassette, số lượng, giá), tổng tiền thu khách, tiền COD, hình thức (chuyển khoản trước hay COD), và mã vận đơn đối tác ship. | Bảng `orders` với snapshot tên, SĐT, địa chỉ nhận hàng, cột `items_text`, `total_amount`, `cod_amount`, `payment_method`, `tracking_code`. |
| **DATA-03** | Quản lý vòng đời đơn hàng qua 7 trạng thái rõ ràng: `Chờ làm` -> `Đang làm` -> `Đã đóng gói` -> `Đã tạo đơn trên app vận chuyển` -> `Shipper đã lấy hàng` -> `Đã giao thành công` / `Bom hàng` / `Huỷ đơn`. | Python `Enum` `OrderStatus` (8 giá trị: 6 bước tuần tự + 2 trạng thái huỷ/bom), ràng buộc `CHECK (status IN (...))` trong SQLite schema. |
| **DATA-04** | Đơn hàng hỗ trợ đính kèm 1 hoặc nhiều ảnh (lưu trữ mã `file_id` Telegram vào DB, hỗ trợ gửi kèm lúc tạo đơn hoặc thêm ảnh bổ sung sau khi có đơn). | Cột `photo_file_ids TEXT NOT NULL DEFAULT '[]'` trong bảng `orders`, lưu trữ mảng chuỗi Telegram `file_id` dạng JSON, kèm helper query/update. |
</phase_requirements>

## Project Constraints (from CLAUDE.md)

- **Tech stack**: Python 3.12+ (hệ thống hiện tại: Python 3.13.7) + SQLite (sqlite3) + python-telegram-bot (v20+ async).
- **LLM Gateway**: 9router (OpenAI-compatible protocol), cho phép cấu hình URL, API Key và Model ID trong local settings (chuẩn bị sẵn cấu hình trong Phase 1 cho Phase 2 dùng).
- **Bảo mật**: Whitelist Telegram User IDs — từ chối tương tác từ người lạ.
- **UX**: Tối đa nút bấm Inline, tối thiểu việc gõ phím cấu trúc/lệnh dài dòng; mọi hành động nhạy cảm đều phải có bước hỏi lại để confirm.
- **Async Pattern**: Tuyệt đối không dùng thư viện đồng bộ `sqlite3` trực tiếp trong async handler; phải dùng `aiosqlite` ở chế độ WAL.
- **Deployment**: Local polling với `Application.run_polling()`, không dùng FastAPI/Webhook.

## Summary

Phase 1 xây dựng nền tảng cốt lõi cho bot quản lý shop cassette: nạp cấu hình bảo mật từ `.env`, cơ chế kiểm soát truy cập whitelist tuyệt đối tại tầng cập nhật Telegram, và hạ tầng lưu trữ cơ sở dữ liệu SQLite async hỗ trợ snapshot thông tin khách hàng, đơn hàng, ảnh đính kèm.

Điểm mấu chốt trong kiến trúc bảo mật Telegram của bot là cơ chế chặn tại Handler Group `-1`: Mọi update (tin nhắn, nút bấm, lệnh) đều đi qua `TypeHandler(Update, whitelist_gate)` trước tiên. Nếu người gửi không nằm trong whitelist, bot lập tức phản hồi thông báo lịch sự nêu rõ Telegram User ID của họ và ném ngoại lệ `ApplicationHandlerStop()`, ngăn chặn triệt để tất cả các handler khác tại group `0` trở đi được thực thi.

Về phía dữ liệu, việc sử dụng `aiosqlite` kết hợp `PRAGMA journal_mode=WAL` và `PRAGMA busy_timeout=5000` triệt tiêu nguy cơ database locked khi chạy async. Thiết kế schema lưu trữ mảng JSON trực tiếp cho số điện thoại/địa chỉ khách hàng và Telegram `file_id` cho ảnh đơn hàng giúp đơn giản hoá tối đa mô hình dữ liệu, loại bỏ overhead quản lý bảng phụ mà vẫn đảm bảo tính toàn vẹn và khả năng truy vấn cao.

**Primary recommendation:** Sử dụng `TypeHandler(Update, whitelist_gate)` tại `group=-1` với `ApplicationHandlerStop()` làm chốt bảo mật tập trung; dùng `aiosqlite` với WAL mode và row factory dict-like; cấu hình `pydantic-settings` v2 với `field_validator(mode="before")` để parse linh hoạt mảng ID whitelist từ chuỗi phân tách bởi dấu phẩy.

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Settings & Env Management (`CFG-01`) | Backend / Config (`src/config.py`) | OS Environment (`.env`) | Pydantic-Settings v2 xác thực kiểu dữ liệu, ẩn SecretStr, fail-fast ngay khi khởi động. |
| Telegram Access Control (`SEC-01`) | Telegram Bot Layer (`src/bot/security.py`) | Application Engine (`group=-1`) | Chặn ở tầng lọc sự kiện cao nhất bằng `ApplicationHandlerStop`, không để lọt update vào business logic. |
| Telegram App Lifecycle (`src/bot/`) | Telegram Bot Layer (`src/bot/app.py`) | Process Runtime (`main.py`) | Khởi tạo PTB ApplicationBuilder, đăng ký handlers và khởi chạy polling. |
| Customer Persistence (`DATA-01`) | Persistence Tier (`src/db/customers.py`) | Domain Models (`src/models/customer.py`) | SQLite lưu trữ dữ liệu bền vững; Pydantic mô hình hóa và serialize JSON arrays. |
| Order Persistence & Snapshot (`DATA-02`, `DATA-04`) | Persistence Tier (`src/db/orders.py`) | Domain Models (`src/models/order.py`) | Lưu trữ snapshot không phụ thuộc biến động của bảng khách; lưu trữ danh sách photo file_ids. |
| Order Status Lifecycle (`DATA-03`) | Domain Models (`src/models/order.py`) | Database Constraint (`CHECK status IN`) | Python Enum đảm bảo type safety trong code; SQLite CHECK constraint đảm bảo tính nhất quán tầng DB. |

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| **Python** | `3.13.7` (3.12+) | Runtime async | Hỗ trợ cú pháp typing hiện đại, `asyncio` chuẩn hoá, hiệu năng cao. [VERIFIED: local runtime] |
| **python-telegram-bot** | `22.8` (`~=22.8`) | Telegram bot framework | Chuẩn công nghiệp cho Telegram Bot API 7.x+, hỗ trợ đầy đủ `TypeHandler`, `ApplicationHandlerStop`, `CopyTextButton`. [VERIFIED: pypi] |
| **aiosqlite** | `0.22.1` (`~=0.22.1`) | Async SQLite bridge | Chạy SQLite worker threads ngầm, không block event loop, hỗ trợ WAL mode và `Row` factory. [VERIFIED: pypi] |
| **pydantic** | `2.14.1` (`~=2.14.1`) | Schema & data validation | Xác thực dữ liệu tốc độ cao (Rust core), hỗ trợ custom validators và JSON serialization. [VERIFIED: pypi] |
| **pydantic-settings** | `2.16.1` (`~=2.16.1`) | Configuration management | Nạp biến môi trường `.env`, ẩn `SecretStr`, nạp kiểu dữ liệu an toàn. [VERIFIED: pypi] |
| **openai** | `3.37.0` (`~=3.37.0`) | Client giao tiếp 9router | Client chính thức kết nối 9router OpenAI-compatible; khai báo sẵn trong settings & dependencies cho Phase 2. [VERIFIED: pypi] |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| **pytest** | `>=8.3.0` | Test runner | Chạy kiểm thử tự động toàn bộ module config, db, và bot gates. [VERIFIED: pypi] |
| **pytest-asyncio** | `1.4.0` (`>=0.24.0`) | Async test fixtures | Hỗ trợ test các hàm async DB và async Telegram handler không cần live bot. [VERIFIED: pypi] |
| **ruff** | `>=0.9.0` | Linter & formatter | Kiểm tra cú pháp, format code và dọn dẹp import tự động. [VERIFIED: pypi] |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| `aiosqlite` | `SQLAlchemy Async` | SQLAlchemy thêm 300+ dòng boilerplate session/metadata, quá cồng kềnh cho schema 2 bảng nhỏ. `aiosqlite` trực quan, nhẹ, đúng triết lý YAGNI. |
| `pydantic-settings` | `python-dotenv` | `python-dotenv` không kiểm tra kiểu dữ liệu, không fail-fast khi thiếu biến bắt buộc, không parse tự động sang `list[int]`. |
| `TypeHandler(Update, gate)` | `filters.User` trên từng Handler | `filters.User` gây im lặng (không báo lỗi ID cho người lạ), dễ quên gán ở các handler mới phát sinh ở Phase 2, 3, 4. |

**Installation:**
```bash
python3 -m pip install "python-telegram-bot~=22.8" "aiosqlite~=0.22.1" "pydantic~=2.14.1" "pydantic-settings~=2.16.1" "openai~=3.37.0"
python3 -m pip install "pytest>=8.3.0" "pytest-asyncio>=0.24.0" "ruff>=0.9.0"
```

**Version verification:**
- `python-telegram-bot`: `22.8` (Verified on PyPI 2026-10-24)
- `aiosqlite`: `0.22.1` (Verified on PyPI 2026-10-24)
- `pydantic-settings`: `2.16.1` (Verified on PyPI 2026-10-24)
- `pydantic`: `2.14.1` (Verified on PyPI 2026-10-24)
- `openai`: `3.37.0` (Verified on PyPI 2026-10-24)
- `pytest-asyncio`: `1.4.0` (Verified on PyPI 2026-10-24)

## Package Legitimacy Audit

| Package | Registry | Age | Downloads | Source Repo | Verdict | Disposition |
|---------|----------|-----|-----------|-------------|---------|-------------|
| `python-telegram-bot` | PyPI | >8 yrs | ~500K/wk | [python-telegram-bot.org](https://python-telegram-bot.org) | [OK] [CITED: pypi.org/project/python-telegram-bot] | Approved |
| `aiosqlite` | PyPI | >6 yrs | ~2M/wk | [github.com/omnilib/aiosqlite](https://github.com/omnilib/aiosqlite) | [OK] [CITED: pypi.org/project/aiosqlite] | Approved |
| `pydantic` | PyPI | >6 yrs | ~50M/wk | [github.com/pydantic/pydantic](https://github.com/pydantic/pydantic) | [OK] [CITED: pypi.org/project/pydantic] | Approved |
| `pydantic-settings` | PyPI | >2 yrs | ~15M/wk | [github.com/pydantic/pydantic-settings](https://github.com/pydantic/pydantic-settings) | [OK] [CITED: pypi.org/project/pydantic-settings] | Approved |
| `openai` | PyPI | >4 yrs | ~30M/wk | [github.com/openai/openai-python](https://github.com/openai/openai-python) | [OK] [CITED: pypi.org/project/openai] | Approved |
| `pytest-asyncio` | PyPI | >5 yrs | ~15M/wk | [github.com/pytest-dev/pytest-asyncio](https://github.com/pytest-dev/pytest-asyncio) | [OK] [CITED: pypi.org/project/pytest-asyncio] | Approved |
| `ruff` | PyPI | >2 yrs | ~20M/wk | [docs.astral.sh/ruff](https://docs.astral.sh/ruff) | [OK] [CITED: pypi.org/project/ruff] | Approved |

*Tất cả các package đều là thư viện chuẩn của hệ sinh thái Python, được cộng đồng kiểm chứng và bảo trì thường xuyên.*

## Architecture Patterns

### System Architecture Diagram

```
                 +---------------------------------------------+
                 |       Incoming Telegram Update Event        |
                 |      (Message, CallbackQuery, Command)      |
                 +---------------------------------------------+
                                        |
                                        v
                    +---------------------------------------+
                    |  Group -1: Whitelist Gate Middleware  |
                    |   telegram.ext.TypeHandler(Update)    |
                    +---------------------------------------+
                                        |
                        [user.id in whitelist?]
                               /        \
                            NO /          \ YES
                              /            \
                             v              v
      +-----------------------------+   +-----------------------------+
      |  Send polite denial with ID |   |  Pass through to Group 0    |
      |  raise ApplicationHandlerStop|   |  (/start, /ping, orders...) |
      +-----------------------------+   +-----------------------------+
                     |                                 |
                     x [Halt execution]                v
                                        +-----------------------------+
                                        |  Application Handlers       |
                                        |  Interact with DB Layer     |
                                        +-----------------------------+
                                                       |
                                                       v
                                        +-----------------------------+
                                        |  aiosqlite Connection Pool  |
                                        |  (WAL mode, busy_timeout)   |
                                        +-----------------------------+
                                                       |
                                                       v
                                        +-----------------------------+
                                        |   SQLite: cassette_store.db |
                                        |   - customers (JSON phones) |
                                        |   - orders (snapshot, files)|
                                        +-----------------------------+
```

### Recommended Project Structure
```
cassette-store/
├── .env.example              # Mẫu biến môi trường cấu hình bot
├── .gitignore                # Bỏ qua venv, .env, *.db, *.db-wal, *.db-shm
├── pyproject.toml            # Khai báo metadata dự án, dependencies & ruff/pytest config
├── main.py                   # Điểm khởi chạy polling bot
├── src/
│   ├── __init__.py
│   ├── config.py             # Pydantic-Settings v2 Settings class
│   ├── bot/
│   │   ├── __init__.py
│   │   ├── app.py            # Hàm build_application() khởi tạo PTB App
│   │   ├── security.py       # TypeHandler gate kiểm tra whitelist + ApplicationHandlerStop
│   │   └── handlers/
│   │       ├── __init__.py
│   │       └── base.py       # Handlers cho lệnh /start, /ping
│   ├── db/
│   │   ├── __init__.py
│   │   ├── connection.py     # Quản lý connection aiosqlite, WAL pragma, row_factory
│   │   ├── schema.py         # Script khởi tạo DDL CREATE TABLE & INDEX
│   │   ├── customers.py      # CRUD customers (hỗ trợ JSON phones, addresses)
│   │   └── orders.py         # CRUD orders (hỗ trợ snapshot, photo_file_ids, status enum)
│   └── models/
│       ├── __init__.py
│       ├── customer.py       # Pydantic Customer domain model
│       └── order.py          # Pydantic Order domain model & OrderStatus enum
└── tests/
    ├── __init__.py
    ├── conftest.py           # Fixtures SQLite in-memory, mock settings, mock bot context
    ├── test_config.py        # Test parsing .env, whitelist comma string, SecretStr
    ├── test_security.py      # Test whitelist gate (chấp nhận/từ chối, reply ID, stop exception)
    └── test_db.py            # Test CRUD customer & order, JSON array fields, status lifecycle
```

### Pattern 1: Pydantic-Settings v2 Configuration
**What:** Đọc `.env` tự động, xác thực kiểu dữ liệu, giải mã chuỗi phân tách bởi dấu phẩy thành `list[int]`, và bảo vệ token nhạy cảm bằng `SecretStr`.
**When to use:** Ngay khi ứng dụng khởi động (`CFG-01`, `D-02`).
**Example:**
```python
# [CITED: pydantic.dev/docs/validation/latest/concepts/pydantic_settings/]
from typing import Any
from pydantic import SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    telegram_bot_token: SecretStr
    telegram_whitelist_user_ids: list[int]
    nine_router_api_key: SecretStr = SecretStr("mock-key-phase1")
    nine_router_base_url: str = "https://api.9router.com/v1"
    nine_router_model_id: str = "gpt-4o-mini"
    sqlite_db_path: str = "cassette_store.db"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @field_validator("telegram_whitelist_user_ids", mode="before")
    @classmethod
    def parse_whitelist(cls, v: Any) -> list[int]:
        if isinstance(v, str):
            v = v.strip()
            if not v:
                return []
            if v.startswith("[") and v.endswith("]"):
                import json
                return [int(x) for x in json.loads(v)]
            return [int(item.strip()) for item in v.split(",") if item.strip()]
        if isinstance(v, (list, set, tuple)):
            return [int(x) for x in v]
        raise ValueError(f"Invalid format for whitelist IDs: {v}")
```

### Pattern 2: PTB v20+ TypeHandler Security Whitelist Gate
**What:** Một callback handler gắn trên `TypeHandler(Update, ...)` tại handler `group=-1` kiểm tra User ID. Nếu không có trong whitelist, gửi tin nhắn từ chối lịch sự chứa ID người gửi và ném `ApplicationHandlerStop()`.
**When to use:** Bảo vệ toàn bộ bot trước bất kỳ thao tác từ người lạ (`SEC-01`, `D-01`).
**Example:**
```python
# [CITED: docs.python-telegram-bot.org/en/v22.8/telegram.ext.applicationhandlerstop.html]
from telegram import Update
from telegram.ext import ApplicationHandlerStop, ContextTypes, TypeHandler


async def whitelist_gate(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    if user is None:
        # Update không gắn user cụ thể (channel post, poll update)
        raise ApplicationHandlerStop()

    whitelist: set[int] = context.bot_data.get("whitelist_user_ids", set())
    if user.id not in whitelist:
        # Nếu là callback query (bấm nút inline)
        if update.callback_query:
            await update.callback_query.answer(
                f"⛔ Bạn không có quyền truy cập bot này (ID: {user.id})",
                show_alert=True,
            )

        # Nếu có tin nhắn text / command gửi đến
        if update.effective_message:
            await update.effective_message.reply_text(
                f"⛔ Bạn không có quyền truy cập bot này.\n"
                f"Telegram User ID của bạn: `{user.id}`\n"
                f"Vui lòng liên hệ quản trị viên.",
                parse_mode="Markdown",
            )

        # Chặn toàn bộ handlers ở tất cả các group tiếp theo
        raise ApplicationHandlerStop()
```

### Pattern 3: aiosqlite WAL Mode, Foreign Keys & Row Factory
**What:** Khởi tạo kết nối SQLite với cấu hình chống lock, hỗ trợ truy vấn dạng dict.
**When to use:** Mọi thao tác đọc/ghi cơ sở dữ liệu (`D-05`, `DATA-01`, `DATA-02`).
**Example:**
```python
# [CITED: aiosqlite.omnilib.dev]
import aiosqlite
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager


@asynccontextmanager
async def get_db_connection(db_path: str) -> AsyncIterator[aiosqlite.Connection]:
    db = await aiosqlite.connect(db_path)
    db.row_factory = aiosqlite.Row
    await db.execute("PRAGMA journal_mode = WAL;")
    await db.execute("PRAGMA busy_timeout = 5000;")
    await db.execute("PRAGMA foreign_keys = ON;")
    try:
        yield db
    finally:
        await db.close()
```

### Pattern 4: SQLite Schema với JSON Array & Snapshot
**What:** Lưu danh sách SĐT, địa chỉ và photo_file_ids dưới dạng JSON array chuỗi; snapshot tên, SĐT, địa chỉ trên đơn hàng.
**When to use:** Thiết kế bảng `customers` và `orders` (`D-03`, `D-04`, `DATA-01` .. `DATA-04`).
**Example:**
```sql
CREATE TABLE IF NOT EXISTS customers (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    phones TEXT NOT NULL DEFAULT '[]',       -- JSON array: ["0912345678", "0987654321"]
    addresses TEXT NOT NULL DEFAULT '[]',    -- JSON array: ["123 Le Loi, Q1, HCM"]
    notes TEXT NOT NULL DEFAULT '',
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS orders (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    customer_id INTEGER,
    customer_name TEXT NOT NULL,             -- Snapshot at order time
    customer_phone TEXT NOT NULL,            -- Snapshot at order time
    shipping_address TEXT NOT NULL,          -- Snapshot at order time
    items_text TEXT NOT NULL,                -- Free-text cassettes & prices
    total_amount INTEGER NOT NULL DEFAULT 0, -- In VNĐ
    cod_amount INTEGER NOT NULL DEFAULT 0,   -- In VNĐ
    payment_method TEXT NOT NULL DEFAULT 'COD', -- 'COD', 'CHUYEN_KHOAN', 'TIEN_MAT'
    status TEXT NOT NULL DEFAULT 'CHO_LAM'
        CHECK (status IN (
            'CHO_LAM', 'DANG_LAM', 'DA_DONG_GOI', 'DA_TAO_DON',
            'SHIPPER_DA_LAY', 'DA_GIAO', 'BOM_HANG', 'HUY_DON'
        )),
    tracking_code TEXT NOT NULL DEFAULT '',
    photo_file_ids TEXT NOT NULL DEFAULT '[]', -- JSON array of Telegram file_id strings
    raw_text TEXT NOT NULL DEFAULT '',
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (customer_id) REFERENCES customers(id) ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS idx_orders_customer_id ON orders(customer_id);
CREATE INDEX IF NOT EXISTS idx_orders_status ON orders(status);
CREATE INDEX IF NOT EXISTS idx_orders_created_at ON orders(created_at);
CREATE INDEX IF NOT EXISTS idx_customers_name ON customers(name);
```

### Anti-Patterns to Avoid
- **Dùng thư viện đồng bộ `sqlite3` trong handler PTB:** Chặn event loop chính của bot khi ghi đĩa, làm đơ toàn bộ tương tác của bot cho các user khác. Phải dùng `aiosqlite`.
- **Dùng `filters.User` rải rác ở từng handler:** Dễ bỏ sót handler mới tạo ở Phase 2, 3, 4; đồng thời làm bot im lặng không thông báo ID cho người dùng mới để họ báo admin. Phải dùng `TypeHandler(Update, whitelist_gate)` ở `group=-1`.
- **Dùng `json.loads` trực tiếp từ chuỗi `.env` không kiểm tra:** Pydantic-Settings v2 mặc định đòi hỏi chuỗi JSON array có ngoặc vuông `[1, 2]`; người dùng nhập `123, 456` sẽ khiến bot crash lúc boot. Phải dùng `@field_validator(..., mode="before")`.
- **Foreign key xoá cascading làm mất đơn hàng:** Nếu khách bị xoá, đơn hàng không được mất. Phải dùng `ON DELETE SET NULL` và dựa trên snapshot thông tin khách đã lưu sẵn trên bảng `orders`.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Environment parsing & validation | Tự viết script đọc `.env` bằng `open()` và `split()` | `pydantic-settings` v2 | Dễ bỏ lọt case khoảng trắng, quotes, kiểu boolean/int, và làm lộ bí mật khi in log. |
| Telegram update routing & polling | Tự viết vòng lặp `requests.get("https://api.telegram.org/...")` | `python-telegram-bot` v20+ `Application` | Xử lý backoff network, timeout, concurrency worker pool, và Telegram API rate limits chuẩn xác. |
| Async database threading | Tự tạo `threading.Thread` hoặc `loop.run_in_executor` wrap `sqlite3` | `aiosqlite` | `aiosqlite` quản lý luồng chuyên dụng trên mỗi kết nối, giải phóng tài nguyên an toàn và hỗ trợ async context manager. |

## Common Pitfalls

### Pitfall 1: SQLite `database is locked` trong môi trường Async
**What goes wrong:** Khi nhiều tác vụ async cùng ghi vào SQLite (hoặc vừa đọc vừa ghi), SQLite ném lỗi `OperationalError: database is locked`.
**Why it happens:** Chế độ mặc định của SQLite là Rollback Journal, khoá toàn bộ file DB khi có transaction ghi.
**How to avoid:**
1. Kích hoạt `PRAGMA journal_mode = WAL;` khi khởi tạo DB (cho phép đọc đồng thời trong khi đang ghi).
2. Kích hoạt `PRAGMA busy_timeout = 5000;` trên mọi kết nối mở để SQLite tự chờ tối đa 5 giây trước khi báo lỗi lock.
**Warning signs:** Kiểm tra file DB không thấy xuất hiện file `-wal` hoặc gặp exception `busy` khi chạy test đồng thời.

### Pitfall 2: Pydantic-Settings JSONDecodeError với Whitelist IDs
**What goes wrong:** Khởi động bot báo lỗi `pydantic_settings.exceptions.SettingsError: error parsing value for field ... JSONDecodeError`.
**Why it happens:** Pydantic v2 mặc định dùng `json.loads` để nạp các trường kiểu `list[...]`. Chuỗi `123456, 789101` không có dấu ngoặc vuông `[...]` nên bị coi là JSON không hợp lệ.
**How to avoid:** Viết `@field_validator("telegram_whitelist_user_ids", mode="before")` để parse cả 2 trường hợp: chuỗi phân tách bởi dấu phẩy và chuỗi JSON array.

### Pitfall 3: Lọt lệnh bot do đặt sai Handler Group trong PTB
**What goes wrong:** Người ngoài whitelist vẫn kích hoạt được một số lệnh hoặc bot không chặn được callback query nút bấm.
**Why it happens:** Đặt gate ở `group=0` cùng cấp với `CommandHandler` hoặc đặt sau các handler khác.
**How to avoid:** Luôn đăng ký `TypeHandler(Update, whitelist_gate)` ở `group=-1`. Các handler thông thường đặt ở `group=0`. Khi từ chối, bắt buộc gọi `raise ApplicationHandlerStop()`.

### Pitfall 4: Lỗi PRAGMA foreign_keys trong SQLite
**What goes wrong:** Khách hàng bị xoá hoặc cập nhật nhưng ràng buộc khoá ngoại không hoạt động.
**Why it happens:** SQLite tắt `foreign_keys` theo mặc định trên từng kết nối mới tạo (per-connection).
**How to avoid:** Chạy `PRAGMA foreign_keys = ON;` ngay sau khi mở bất kỳ kết nối `aiosqlite.connect()` nào.

## Code Examples

### 1. Model Domain Pydantic & Enum Trạng Thái Đơn Hàng
```python
# [CITED: pydantic.dev]
from datetime import datetime
from enum import Enum
from pydantic import BaseModel, Field


class OrderStatus(str, Enum):
    CHO_LAM = "CHO_LAM"                 # Chờ làm
    DANG_LAM = "DANG_LAM"               # Đang làm
    DA_DONG_GOI = "DA_DONG_GOI"         # Đã đóng gói
    DA_TAO_DON = "DA_TAO_DON"           # Đã tạo đơn trên app vận chuyển
    SHIPPER_DA_LAY = "SHIPPER_DA_LAY"   # Shipper đã lấy hàng
    DA_GIAO = "DA_GIAO"                 # Đã giao thành công
    BOM_HANG = "BOM_HANG"               # Bom hàng
    HUY_DON = "HUY_DON"                 # Huỷ đơn


class Customer(BaseModel):
    id: int | None = None
    name: str
    phones: list[str] = Field(default_factory=list)
    addresses: list[str] = Field(default_factory=list)
    notes: str = ""
    created_at: datetime | None = None
    updated_at: datetime | None = None


class Order(BaseModel):
    id: int | None = None
    customer_id: int | None = None
    customer_name: str
    customer_phone: str
    shipping_address: str
    items_text: str
    total_amount: int = 0
    cod_amount: int = 0
    payment_method: str = "COD"
    status: OrderStatus = OrderStatus.CHO_LAM
    tracking_code: str = ""
    photo_file_ids: list[str] = Field(default_factory=list)
    raw_text: str = ""
    created_at: datetime | None = None
    updated_at: datetime | None = None
```

### 2. CRUD Cơ Sở Khách Hàng & Đơn Hàng (src/db/)
```python
# [CITED: aiosqlite.omnilib.dev]
import json
import aiosqlite
from src.models.customer import Customer
from src.models.order import Order, OrderStatus


async def create_customer(db: aiosqlite.Connection, customer: Customer) -> int:
    cursor = await db.execute(
        """
        INSERT INTO customers (name, phones, addresses, notes)
        VALUES (?, ?, ?, ?)
        """,
        (
            customer.name,
            json.dumps(customer.phones, ensure_ascii=False),
            json.dumps(customer.addresses, ensure_ascii=False),
            customer.notes,
        ),
    )
    await db.commit()
    return cursor.lastrowid  # type: ignore[return-value]


async def get_customer_by_id(db: aiosqlite.Connection, customer_id: int) -> Customer | None:
    async with db.execute("SELECT * FROM customers WHERE id = ?", (customer_id,)) as cursor:
        row = await cursor.fetchone()
        if not row:
            return None
        return Customer(
            id=row["id"],
            name=row["name"],
            phones=json.loads(row["phones"]),
            addresses=json.loads(row["addresses"]),
            notes=row["notes"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )


async def create_order(db: aiosqlite.Connection, order: Order) -> int:
    cursor = await db.execute(
        """
        INSERT INTO orders (
            customer_id, customer_name, customer_phone, shipping_address,
            items_text, total_amount, cod_amount, payment_method,
            status, tracking_code, photo_file_ids, raw_text
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            order.customer_id,
            order.customer_name,
            order.customer_phone,
            order.shipping_address,
            order.items_text,
            order.total_amount,
            order.cod_amount,
            order.payment_method,
            order.status.value,
            order.tracking_code,
            json.dumps(order.photo_file_ids, ensure_ascii=False),
            order.raw_text,
        ),
    )
    await db.commit()
    return cursor.lastrowid  # type: ignore[return-value]
```

### 3. Khởi Tạo Application & Đăng Ký Whitelist Gate (src/bot/app.py)
```python
# [CITED: docs.python-telegram-bot.org/en/v22.8/telegram.ext.applicationbuilder.html]
from telegram import Update
from telegram.ext import Application, ApplicationBuilder, CommandHandler, TypeHandler
from src.config import Settings
from src.bot.security import whitelist_gate
from src.bot.handlers.base import start_command, ping_command


def build_application(settings: Settings) -> Application:
    app = (
        ApplicationBuilder()
        .token(settings.telegram_bot_token.get_secret_value())
        .build()
    )

    # Lưu tập whitelist vào bot_data để gate truy cập O(1)
    app.bot_data["whitelist_user_ids"] = set(settings.telegram_whitelist_user_ids)
    app.bot_data["settings"] = settings

    # Group -1: Chốt chặn bảo mật whitelist (bắt buộc chạy trước tất cả handlers khác)
    app.add_handler(TypeHandler(Update, whitelist_gate), group=-1)

    # Group 0: Các lệnh cơ bản
    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CommandHandler("ping", ping_command))

    return app
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| `python-telegram-bot` v13 (Sync handlers) | `python-telegram-bot` v20+ / v22+ (Asyncio native) | 2023 / PTB v20 | Toàn bộ handlers phải là `async def`; sử dụng `ApplicationBuilder` thay cho `Updater`. |
| Sync `sqlite3` trong async loop | `aiosqlite` với WAL mode | Hiện đại | Ngăn chặn hiện tượng nghẽn I/O làm đơ bot; cho phép đọc và ghi song song. |
| `pydantic` v1 (`BaseSettings` trong pydantic) | `pydantic-settings` v2 (Package riêng biệt) | Pydantic v2 (2023) | Phải cài `pydantic-settings`, dùng `SettingsConfigDict` thay cho `class Config`. |
| Hardcode token / plaintext token trong log | `SecretStr` của Pydantic | Hiện đại | Token không bị lộ khi `print(settings)` hoặc khi dump cấu hình ra log audit. |

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | Người dùng bot là nội bộ (chủ shop/nhân viên), danh sách whitelist tương đối nhỏ (<50 user ID) nên lưu trực tiếp trong biến môi trường và nạp vào bộ nhớ `set[int]`. | Whitelist & Security | Thấp — nếu sau này mở rộng hàng nghìn user thì chuyển sang bảng `whitelist_users` trong SQLite mà không ảnh hưởng logic gate. |
| A2 | Đơn vị tiền tệ lưu trữ trong database là số nguyên VNĐ (`INTEGER`), không dùng số thực để tránh sai số dấu phẩy động. | Database Schema | Rất thấp — chuẩn tiền tệ VNĐ không có hào/xu, luôn là số nguyên. |

## Open Questions

1. **Format chi tiết tin nhắn `/start` và `/ping` cho admin:**
   - Đã chốt theo Claude's Discretion:
     - `/start`: Hiển thị lời chào thân thiện, thông báo bot quản lý đơn Cassette Store đang hoạt động, hiển thị ID admin đã được xác thực, và tóm tắt các tính năng sẵn sàng.
     - `/ping`: Phản hồi `pong! 🏓`, kèm thông tin uptime bot và trạng thái kết nối SQLite (`OK`).

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Python | Runtime | ✓ | 3.13.7 | — |
| SQLite3 | Database Engine | ✓ | 3.51.0 | — |
| pip3 | Package Installer | ✓ | 25.2 | — |
| Git | Version Control | ✓ | 2.39+ | — |

**Missing dependencies with no fallback:** None.
**Missing dependencies with fallback:** None.

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | `pytest` + `pytest-asyncio` |
| Config file | `pyproject.toml` (Wave 0) |
| Quick run command | `pytest tests/ -q` |
| Full suite command | `pytest tests/ -v` |

### Phase Requirements → Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| **CFG-01** | Nạp settings từ `.env`, parse `telegram_whitelist_user_ids` từ chuỗi phẩy, bảo vệ `SecretStr` | Unit | `pytest tests/test_config.py -v` | ❌ Wave 0 |
| **SEC-01** | `whitelist_gate` cho phép user trong whitelist đi qua; chặn user ngoài whitelist, reply thông báo chứa ID và raise `ApplicationHandlerStop` | Unit / Mock | `pytest tests/test_security.py -v` | ❌ Wave 0 |
| **DATA-01** | CRUD khách hàng: thêm, đọc theo ID, lưu và đọc lại `phones` và `addresses` dạng JSON array | Integration (SQLite in-memory) | `pytest tests/test_db.py::test_customer_crud -v` | ❌ Wave 0 |
| **DATA-02** | CRUD đơn hàng: lưu snapshot tên, SĐT, địa chỉ, items text, tiền tổng, tiền COD, mã vận đơn | Integration (SQLite in-memory) | `pytest tests/test_db.py::test_order_crud -v` | ❌ Wave 0 |
| **DATA-03** | Enum `OrderStatus` quản lý 8 trạng thái, ràng buộc CHECK constraint SQLite ngăn trạng thái sai | Unit & DB | `pytest tests/test_db.py::test_order_status_lifecycle -v` | ❌ Wave 0 |
| **DATA-04** | Đơn hàng lưu và truy vấn danh sách `photo_file_ids` mảng JSON, hỗ trợ thêm ảnh bổ sung | Integration (SQLite in-memory) | `pytest tests/test_db.py::test_order_photos -v` | ❌ Wave 0 |

### Sampling Rate
- **Per task commit:** `pytest tests/ -q`
- **Per wave merge:** `pytest tests/ -v && ruff check .`
- **Phase gate:** Toàn bộ test suite pass 100%, không cần kết nối mạng hay Telegram token thật.

### Wave 0 Gaps
- [ ] `pyproject.toml` — Khai báo dependencies, cấu hình pytest (`asyncio_mode = "auto"`) và ruff
- [ ] `tests/conftest.py` — Fixtures cho test settings, in-memory SQLite database, và mock Telegram objects (`Update`, `User`, `Message`, `CallbackQuery`, `Context`)
- [ ] `tests/test_config.py` — Test coverage cho CFG-01
- [ ] `tests/test_security.py` — Test coverage cho SEC-01
- [ ] `tests/test_db.py` — Test coverage cho DATA-01, DATA-02, DATA-03, DATA-04

## Security Domain

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| **V2 Authentication** | Yes | Whitelist Telegram User ID bắt buộc trước mọi tương tác (`SEC-01`). |
| **V3 Session Management** | No | Ứng dụng bot chạy stateless polling; phiên làm việc định danh qua Telegram User ID duy nhất. |
| **V4 Access Control** | Yes | `TypeHandler(Update, whitelist_gate)` đặt tại `group=-1` ngăn chặn triệt để mọi truy cập trái phép. |
| **V5 Input Validation** | Yes | Pydantic v2 xác thực kiểu dữ liệu cấu hình; câu lệnh SQL dùng tham số bind `?` 100% để loại trừ SQL Injection. |
| **V6 Cryptography** | Yes | `SecretStr` bảo vệ Bot Token và API Key trong bộ nhớ, không in ra logs. |

### Known Threat Patterns for Python + Telegram + SQLite Stack

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Mạo danh người dùng hợp lệ | Spoofing | Telegram Bot API cung cấp `update.effective_user.id` từ máy chủ Telegram được mã hoá, client không thể giả mạo ID này. |
| Thao túng câu lệnh SQL qua text đơn hàng | Tampering | Sử dụng parameterized queries (`?`) của `aiosqlite` cho tất cả câu lệnh SQL; tuyệt đối không dùng format string f-string. |
| Lộ lọt Telegram Bot Token hoặc 9router API Key | Information Disclosure | Lưu trong file `.env` được đưa vào `.gitignore`; mô hình hoá bằng `SecretStr` của Pydantic để che giấu khi print/log. |
| Tấn công Denial of Service làm treo DB | Denial of Service | SQLite kích hoạt WAL mode (`PRAGMA journal_mode=WAL`) và timeout (`PRAGMA busy_timeout=5000`) ngăn chặn database locking. |
| Người lạ nhắn tin quấy rối bot | Elevation of Privilege | Chặn ngay tại `group=-1` với `ApplicationHandlerStop()`; không tiêu tốn tài nguyên xử lý hay gọi LLM cho người lạ. |

## Sources

### Primary (HIGH confidence)
- [PyPI python-telegram-bot](https://pypi.org/project/python-telegram-bot/) — Xác minh phiên bản `22.8`, hỗ trợ async ApplicationBuilder và Telegram API 7.x.
- [Telegram Bot API Doc - ApplicationHandlerStop](https://docs.python-telegram-bot.org/en/v22.8/telegram.ext.applicationhandlerstop.html) — Xác minh cơ chế ngắt pipeline handler khi từ chối truy cập.
- [Telegram Bot API Doc - TypeHandler](https://docs.python-telegram-bot.org/en/v22.8/telegram.ext.typehandler.html) — Xác minh khả năng bắt toàn bộ `Update` tại `group=-1`.
- [Pydantic Settings Documentation](https://pydantic.dev/docs/validation/latest/concepts/pydantic_settings/) — Xác minh cơ chế `field_validator(mode="before")` để parse chuỗi phân tách bởi dấu phẩy và sử dụng `SecretStr`.
- [aiosqlite Documentation](https://aiosqlite.omnilib.dev/) — Xác minh API async context manager, row_factory, và cơ chế thread worker cho SQLite.

### Secondary (MEDIUM confidence)
- [CLAUDE.md Architecture Guidelines](./CLAUDE.md) — Ràng buộc công nghệ, kiến trúc SQLite WAL, JSON array phones/addresses, và triết lý UX người lớn tuổi.
- [.planning/REQUIREMENTS.md](./.planning/REQUIREMENTS.md) — Chi tiết yêu cầu CFG-01, SEC-01, DATA-01, DATA-02, DATA-03, DATA-04.

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — Tất cả package được kiểm chứng tồn tại và tương thích trên môi trường Python 3.13.7.
- Architecture: HIGH — Pattern security gate `group=-1` và `ApplicationHandlerStop` là chuẩn chính thức của PTB v20+.
- Pitfalls: HIGH — Các vấn đề Pydantic-settings JSONDecodeError và SQLite locked trong async đã được kiểm chứng và có giải pháp dứt điểm.

**Research date:** 2026-10-24
**Valid until:** 2026-11-24 (30 days)
