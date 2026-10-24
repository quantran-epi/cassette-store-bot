# Phase 03: Ergonomic Order Management & Low-Tech Actions - Pattern Map

**Mapped:** 2026-10-24
**Files analyzed:** 9 (4 new, 5 modified)
**Analogs found:** 9 / 9

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|-------------------|------|-----------|----------------|---------------|
| `src/bot/keyboards.py` | component / utility | transform / UI | `src/bot/handlers/ingest.py` | exact |
| `src/bot/handlers/orders.py` | controller / handler | request-response / CRUD | `src/bot/handlers/callbacks.py` | exact |
| `src/bot/handlers/order_actions.py` | controller / handler | request-response / state | `src/bot/handlers/callbacks.py` | exact |
| `src/db/orders.py` | service / repository | CRUD / query | `src/db/orders.py` | exact |
| `src/bot/app.py` | config / router | request-response / middleware | `src/bot/app.py` | exact |
| `src/bot/handlers/base.py` | controller / handler | request-response | `src/bot/handlers/base.py` | exact |
| `src/bot/handlers/ingest.py` | controller / handler | request-response / bypass | `src/bot/handlers/ingest.py` | exact |
| `tests/test_orders_ui.py` | test | request-response / UI | `tests/test_ingest.py` | exact |
| `tests/test_db_orders.py` | test | CRUD / DB | `tests/test_db_orders.py` | exact |

## Pattern Assignments

### `src/bot/keyboards.py` (component / utility, transform / UI)

**Analog:** `src/bot/handlers/ingest.py` (lines 1-8, 19-82)

**Imports pattern:**
```python
import html
from telegram import (
    CopyTextButton,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardMarkup,
)
from src.models.order import Order, OrderStatus
```

**Card format & HTML escaping pattern** (analog: `src/bot/handlers/ingest.py:19-61`):
```python
# Format card with Vietnamese currency and html.escape on user strings
def render_order_detail_card(order: Order) -> str:
    status_label = STATUS_NAMES.get(order.status, order.status.value)
    total_fmt = f"{order.total_amount:,} đ".replace(",", ".")
    cod_fmt = f"{order.cod_amount:,} đ".replace(",", ".")
    tracking_str = f"<code>{html.escape(order.tracking_code)}</code>" if order.tracking_code else "<i>(Chưa có)</i>"
    photo_str = f"{len(order.photo_file_ids)} ảnh" if order.photo_file_ids else "Không có"

    return (
        f"📦 <b>CHI TIẾT ĐƠN HÀNG #{order.id}</b>\n"
        f"Trạng thái: <b>{status_label}</b>\n"
        f"────────────────────\n"
        f"👤 <b>Khách:</b> {html.escape(order.customer_name)}\n"
        f"📞 <b>SĐT:</b> <code>{order.customer_phone}</code> <i>(chạm để copy)</i>\n"
        f"📍 <b>Địa chỉ:</b> <code>{html.escape(order.shipping_address)}</code>\n"
        f"📼 <b>Băng:</b> {html.escape(order.items_text)}\n"
        f"💰 <b>Tổng tiền:</b> {total_fmt}\n"
        f"💵 <b>Tiền COD thu:</b> {cod_fmt}\n"
        f"🚚 <b>Mã vận đơn:</b> {tracking_str}\n"
        f"📷 <b>Ảnh đính kèm:</b> {photo_str}\n"
        f"────────────────────"
    )
```

**Keyboard building & CopyTextButton pattern** (analog: `src/bot/handlers/ingest.py:64-82`):
```python
# Multi-row inline keyboard with Telegram Bot API 7.3+ CopyTextButton
def build_order_detail_keyboard(order: Order, date_str: str, page: int) -> InlineKeyboardMarkup:
    buttons: list[list[InlineKeyboardButton]] = []
    # Copy buttons row
    buttons.append([
        InlineKeyboardButton("📋 Copy SĐT", copy_text=CopyTextButton(text=order.customer_phone)),
        InlineKeyboardButton("📍 Copy Địa chỉ", copy_text=CopyTextButton(text=order.shipping_address)),
    ])
    # Action callbacks (compact <= 64 bytes)
    buttons.append([
        InlineKeyboardButton("🔄 Đổi trạng thái", callback_data=f"ord_st_menu:{order.id}"),
        InlineKeyboardButton("⬅️ Quay lại", callback_data=f"ord_bk:{date_str}:{page}"),
    ])
    return InlineKeyboardMarkup(buttons)
```

---

### `src/bot/handlers/orders.py` (controller / handler, request-response / CRUD)

**Analog:** `src/bot/handlers/callbacks.py` (lines 1-33, 76-94)

**Imports pattern:**
```python
import html
import logging
import re
from contextlib import nullcontext
from datetime import datetime, timedelta, timezone

from telegram import Update
from telegram.error import BadRequest
from telegram.ext import ContextTypes

from src.bot.keyboards import (
    build_date_picker_keyboard,
    build_order_detail_keyboard,
    build_order_list_keyboard,
    render_order_detail_card,
    render_order_list_card,
)
from src.db.connection import get_db_connection
from src.db.orders import count_orders_by_date, get_order_by_id, list_orders_by_date
```

**Database connection resolution pattern** (analog: `src/bot/handlers/callbacks.py:76-94`):
```python
app_context = context.application.bot_data.get("app_context")
db = getattr(app_context, "db", None) if app_context else context.application.bot_data.get("db")
settings = context.application.bot_data.get("settings")
db_path = getattr(settings, "sqlite_db_path", "cassette_store.db") if settings else "cassette_store.db"

db_ctx = nullcontext(db) if db else get_db_connection(db_path)
async with db_ctx as active_db:
    if not active_db:
        logger.error("Database connection could not be established")
        return
```

**Callback answering & Message edit with BadRequest guard** (analog: `src/bot/handlers/callbacks.py:27-29`):
```python
await query.answer()

try:
    await query.edit_message_text(
        text=card_text,
        reply_markup=keyboard,
        parse_mode="HTML",
    )
except BadRequest as e:
    if "Message is not modified" not in str(e):
        raise
```

---

### `src/bot/handlers/order_actions.py` (controller / handler, request-response / state)

**Analog:** `src/bot/handlers/callbacks.py` (lines 18-42, 63-75) and `src/bot/handlers/ingest.py` (lines 203-220)

**Imports pattern:**
```python
import logging
import time
from contextlib import nullcontext

from telegram import InputMediaPhoto, Update
from telegram.error import BadRequest
from telegram.ext import ContextTypes

from src.db.connection import get_db_connection
from src.db.orders import (
    append_order_photos,
    get_order_by_id,
    update_order_status,
    update_order_tracking,
)
from src.models.order import OrderStatus
```

**Toast alert + State update pattern** (analog: `src/bot/handlers/callbacks.py:28`):
```python
# Instant toast alert without spinner
await query.answer(text=f"✅ Đã chuyển sang: {status_label}", show_alert=False)
```

**Sensitive status confirmation pattern:**
```python
SENSITIVE_STATUSES = {OrderStatus.BOM_HANG, OrderStatus.HUY_DON}

if target_status in SENSITIVE_STATUSES and not is_confirmed:
    confirm_kb = InlineKeyboardMarkup([
        [
            InlineKeyboardButton(f"⚠️ Xác nhận {label}", callback_data=f"ord_st_cf:{order_id}:{target_status.value}"),
            InlineKeyboardButton("Quay lại", callback_data=f"ord_v:{order_id}:{date_str}:{page}"),
        ]
    ])
    await query.edit_message_text(
        f"⚠️ <b>XÁC NHẬN CHUYỂN TRẠNG THÁI</b>\n\n"
        f"Bác có chắc muốn chuyển đơn <b>#{order_id}</b> sang <b>{label}</b> không?",
        reply_markup=confirm_kb,
        parse_mode="HTML",
    )
    return
```

**TTL-based action state pattern (120s timeout):**
```python
# Set prompt state
context.user_data["action_state"] = {
    "action": "await_tracking",
    "order_id": order_id,
    "expires_at": time.time() + 120,
}

# In text/photo interceptor:
state = context.user_data.get("action_state")
if state:
    if time.time() > state.get("expires_at", 0):
        context.user_data.pop("action_state", None)
    else:
        # Process action state input...
```

**Photo send pattern (1 photo vs media group):**
```python
# Analog: src/bot/handlers/ingest.py:215-218 for photo_id
if len(photo_ids) == 1:
    await context.bot.send_photo(
        chat_id=chat_id,
        photo=photo_ids[0],
        caption=f"📷 Ảnh đính kèm đơn #{order_id}",
    )
else:
    for chunk in [photo_ids[i:i + 10] for i in range(0, len(photo_ids), 10)]:
        media = [InputMediaPhoto(media=fid) for fid in chunk]
        await context.bot.send_media_group(chat_id=chat_id, media=media)
```

---

### `src/db/orders.py` (service / repository, CRUD / query)

**Analog:** `src/db/orders.py` (lines 135-151)

**Date query with UTC+7 modifier pattern:**
```python
# Analog: src/db/orders.py:135-151 list_orders_by_status
async def list_orders_by_date(
    db: aiosqlite.Connection,
    date_str: str,
    limit: int = 5,
    offset: int = 0,
) -> Sequence[Order]:
    """Retrieve orders created on a specific Vietnam date (UTC+7)."""
    query = """
        SELECT * FROM orders
        WHERE date(created_at, '+7 hours') = ?
        ORDER BY created_at DESC, id DESC
        LIMIT ? OFFSET ?
    """
    async with db.execute(query, (date_str, limit, offset)) as cursor:
        rows = await cursor.fetchall()
        return [_row_to_order(row) for row in rows]


async def count_orders_by_date(db: aiosqlite.Connection, date_str: str) -> int:
    """Count total orders created on a specific Vietnam date (UTC+7)."""
    query = """
        SELECT COUNT(*) FROM orders
        WHERE date(created_at, '+7 hours') = ?
    """
    async with db.execute(query, (date_str,)) as cursor:
        row = await cursor.fetchone()
        return row[0] if row else 0
```

---

### `src/bot/app.py` (config / router, request-response / middleware)

**Analog:** `src/bot/app.py` (lines 6-21, 53-73)

**Handler registration ordering pattern:**
```python
# 1. Security Gate group -1
app.add_handler(TypeHandler(Update, whitelist_gate), group=-1)

# 2. Base command handlers group 0
app.add_handler(CommandHandler("start", start_command), group=0)
app.add_handler(CommandHandler("ping", ping_command), group=0)

# 3. Main menu Reply Keyboard handler (BEFORE LLM text ingest)
app.add_handler(
    MessageHandler(filters.Regex(r"^(📦 Đơn hôm nay|📋 Xem theo ngày|📝 Nhập đơn mới|❓ Trợ giúp)$"), handle_menu_reply),
    group=0,
)

# 4. Action callbacks and Order callbacks
app.add_handler(
    CallbackQueryHandler(handle_order_action_callback, pattern=r"^ord_(st|act|st_menu|st_cf):"),
    group=0,
)
app.add_handler(
    CallbackQueryHandler(handle_order_nav_callback, pattern=r"^ord_(dt|pg|v|bk):"),
    group=0,
)
app.add_handler(
    CallbackQueryHandler(handle_order_callback, pattern=r"^ord:(cf|ca|ad):"),
    group=0,
)

# 5. Media & Text handlers (with action state bypass check)
app.add_handler(MessageHandler(filters.PHOTO, handle_photo_order), group=0)
app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text_order), group=0)
```

---

### `src/bot/handlers/base.py` (controller / handler, request-response)

**Analog:** `src/bot/handlers/base.py` (lines 12-26)

**Persistent Reply Keyboard pattern:**
```python
from src.bot.keyboards import build_main_menu_reply_keyboard

# In start_command:
keyboard = build_main_menu_reply_keyboard()
await update.effective_message.reply_text(
    text,
    reply_markup=keyboard,
    parse_mode="Markdown",
)
```

---

### `src/bot/handlers/ingest.py` (controller / handler, request-response / bypass)

**Analog:** `src/bot/handlers/ingest.py` (lines 155-163, 203-214)

**Action state check before LLM extraction pattern:**
```python
# In handle_text_order / handle_photo_order:
state = context.user_data.get("action_state")
if state and time.time() <= state.get("expires_at", 0):
    await handle_action_state_input(update, context, state)
    return
```

---

### `tests/test_orders_ui.py` (test, request-response / UI)

**Analog:** `tests/test_ingest.py` (lines 1-15, 76-120)

**Mock update, callback query, and context pattern:**
```python
from unittest.mock import AsyncMock, MagicMock
import pytest
from telegram import Update
from telegram.ext import CallbackContext

@pytest.mark.asyncio
async def test_order_status_update(test_db):
    update = MagicMock(spec=Update)
    query = MagicMock()
    query.data = "ord_st:1:DANG_LAM"
    query.answer = AsyncMock()
    query.edit_message_text = AsyncMock()
    update.callback_query = query

    context = MagicMock(spec=CallbackContext)
    app_context = MagicMock()
    app_context.db = test_db
    context.application.bot_data = {"app_context": app_context}

    await handle_order_action_callback(update, context)

    query.answer.assert_awaited_once()
    query.edit_message_text.assert_awaited_once()
```

---

### `tests/test_db_orders.py` (test, CRUD / DB)

**Analog:** `tests/test_db_orders.py` (lines 52-88)

**Test roundtrip for date query pattern:**
```python
@pytest.mark.asyncio
async def test_list_and_count_orders_by_date(test_db):
    # Insert order
    order = Order(...)
    order_id = await create_order(test_db, order)

    # Query date
    today_vn = datetime.now(timezone(timedelta(hours=7))).strftime("%Y-%m-%d")
    orders = await list_orders_by_date(test_db, today_vn, limit=5, offset=0)
    total = await count_orders_by_date(test_db, today_vn)

    assert total >= 1
    assert any(o.id == order_id for o in orders)
```

---

## Shared Patterns

### Whitelist Access Control
**Source:** `src/bot/security.py` lines 18-35
**Apply to:** All bot interactions (enforced at `group=-1` globally)

### Database Connection Resolution
**Source:** `src/bot/handlers/callbacks.py` lines 76-89
**Apply to:** All handler callbacks requiring SQLite DB access:
```python
app_context = context.application.bot_data.get("app_context")
db = getattr(app_context, "db", None) if app_context else context.application.bot_data.get("db")
settings = context.application.bot_data.get("settings")
db_path = getattr(settings, "sqlite_db_path", "cassette_store.db") if settings else "cassette_store.db"
db_ctx = nullcontext(db) if db else get_db_connection(db_path)
async with db_ctx as active_db:
    ...
```

### Instant Callback Answer & Error Guard
**Source:** `src/bot/handlers/callbacks.py` lines 27-29 & `RESEARCH.md` Pitfall 3
**Apply to:** All CallbackQuery handlers:
```python
await query.answer()

try:
    await query.edit_message_text(text=card_text, reply_markup=keyboard, parse_mode="HTML")
except BadRequest as e:
    if "Message is not modified" not in str(e):
        raise
```

### Compact Callback Data (<= 64 bytes)
**Source:** `src/bot/handlers/callbacks.py` line 18 & `RESEARCH.md` Pitfall 2
**Apply to:** All inline keyboard buttons:
- Format: `ord_<action>:<id>:<extra>`
- Ensure `len(callback_data.encode("utf-8")) <= 64`

### Vietnam Timezone Standard
**Source:** Stdlib `datetime` & SQLite date modifier
**Apply to:** All date queries and date picker calculations:
```python
VN_TZ = timezone(timedelta(hours=7))
today_vn = datetime.now(VN_TZ).strftime("%Y-%m-%d")
# SQLite query uses: date(created_at, '+7 hours') = ?
```

## No Analog Found

None. All files have exact or strong role-matched analogs in the existing codebase.

## Metadata

**Analog search scope:** `src/bot/`, `src/db/`, `tests/`
**Files scanned:** 7 existing files inspected
**Pattern extraction date:** 2026-10-24
