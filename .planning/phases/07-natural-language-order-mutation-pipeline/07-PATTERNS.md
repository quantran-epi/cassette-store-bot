# Phase 07: Natural Language Order Mutation Pipeline - Pattern Map

**Mapped:** 2026-10-25  
**Files analyzed:** 11 (6 new, 5 modified)  
**Analogs found:** 11 / 11 (all matched)  

---

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|-------------------|------|-----------|----------------|---------------|
| `src/models/mutation.py` (NEW) | model | transform | `src/models/extractor.py` | exact |
| `src/models/order.py` (MODIFIED) | model | CRUD | `src/models/order.py` | exact |
| `src/db/schema.py` (MODIFIED) | migration / config | CRUD | `src/db/schema.py` | exact |
| `src/db/orders.py` (MODIFIED) | service / DAO | CRUD | `src/db/orders.py` | exact |
| `src/services/intent_router.py` (NEW) | service / utility | request-response | `src/services/order_search.py` | exact |
| `src/services/mutation_extractor.py` (NEW) | service | request-response / transform | `src/services/extractor.py` | exact |
| `src/bot/keyboards.py` (MODIFIED) | component / utility | transform | `src/bot/keyboards.py` | exact |
| `src/bot/handlers/mutation.py` (NEW) | controller | event-driven / request-response | `src/bot/handlers/order_actions.py` | exact |
| `src/bot/handlers/ingest.py` (MODIFIED) | controller | event-driven / request-response | `src/bot/handlers/ingest.py` | exact |
| `src/bot/handlers/callbacks.py` (MODIFIED) | controller | event-driven / CRUD | `src/bot/handlers/callbacks.py` | exact |
| `src/bot/app.py` (MODIFIED) | config / router | event-driven | `src/bot/app.py` | exact |

---

## Pattern Assignments

### 1. `src/models/mutation.py` (model, transform)
**Analog:** `src/models/extractor.py` (lines 1-42)

**Imports pattern:**
```python
import re
from enum import Enum
from pydantic import BaseModel, Field, field_validator
from src.models.order import OrderStatus
```

**Core pattern (Pydantic schema with validators):**
```python
# Analog: src/models/extractor.py lines 8-41
VN_PHONE_REGEX = re.compile(r"^0[35789]\d{8}$")

class IntentType(str, Enum):
    CREATE = "CREATE"
    SEARCH = "SEARCH"
    MUTATE = "MUTATE"

class OrderMutationDelta(BaseModel):
    """Structured mutation delta for 5 field groups per MUT-03."""
    target_order_id: int | None = Field(default=None, description="Mã đơn hàng cần sửa nếu có")
    target_customer_keyword: str | None = Field(default=None, description="Tên khách hoặc từ khoá định danh đơn cũ")
    new_status: OrderStatus | None = Field(default=None, description="Trạng thái mới nếu có")
    status_disambiguation_needed: bool = Field(default=False, description="Cần chọn trạng thái kế tiếp")
    new_tracking_code: str | None = Field(default=None, description="Mã vận đơn mới")
    new_notes: str | None = Field(default=None, description="Ghi chú mới hoặc sửa")
    new_total_amount: int | None = Field(default=None, ge=0, description="Tổng tiền mới")
    new_cod_amount: int | None = Field(default=None, ge=0, description="Tiền COD mới")
    new_customer_phone: str | None = Field(default=None, description="Số điện thoại nhận hàng mới")
    new_shipping_address: str | None = Field(default=None, description="Địa chỉ giao hàng mới")
    new_customer_name: str | None = Field(default=None, description="Tên khách hàng mới")
    new_items_text: str | None = Field(default=None, description="Danh sách món/băng mới")

    @field_validator("new_customer_phone", mode="before")
    @classmethod
    def normalize_vietnamese_phone(cls, v: str | None) -> str | None:
        if not v or not isinstance(v, str):
            return None
        cleaned = re.sub(r"[\s.\-()]", "", v)
        if cleaned.startswith("+84"):
            cleaned = "0" + cleaned[3:]
        elif cleaned.startswith("84") and len(cleaned) == 11:
            cleaned = "0" + cleaned[2:]
        return cleaned if VN_PHONE_REGEX.match(cleaned) else None
```

---

### 2. `src/models/order.py` (model, CRUD)
**Analog:** `src/models/order.py` (lines 20-38)

**Core pattern (Add audit fields):**
```python
# Analog: src/models/order.py lines 20-37
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
    tracking_code: str | None = None
    photo_file_ids: list[str] = Field(default_factory=list)
    raw_text: str = ""
    # Per D-16:
    created_by_user_id: int | None = None
    created_by_name: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None
```

---

### 3. `src/db/schema.py` (migration, CRUD)
**Analog:** `src/db/schema.py` (lines 4-93)

**Core migration pattern:**
```python
# Analog: src/db/schema.py lines 6-56, 74-92
# 1. Create order_history table per D-16
await db.execute(
    """
    CREATE TABLE IF NOT EXISTS order_history (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        order_id INTEGER NOT NULL,
        user_id INTEGER,
        user_name TEXT,
        action TEXT NOT NULL CHECK (action IN ('CREATE', 'MUTATE', 'STATUS_CHANGE', 'TRACKING_UPDATE')),
        changes_json TEXT NOT NULL DEFAULT '{}',
        created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (order_id) REFERENCES orders(id) ON DELETE CASCADE
    );
    """
)
await db.execute(
    """
    CREATE INDEX IF NOT EXISTS idx_order_history_order_id ON order_history(order_id);
    """
)

# 2. Add columns created_by_user_id and created_by_name to orders if not existing
async with db.execute("PRAGMA table_info(orders);") as cursor:
    cols = {row[1] for row in await cursor.fetchall()}
    if "created_by_user_id" not in cols:
        await db.execute("ALTER TABLE orders ADD COLUMN created_by_user_id INTEGER;")
    if "created_by_name" not in cols:
        await db.execute("ALTER TABLE orders ADD COLUMN created_by_name TEXT;")
```

---

### 4. `src/db/orders.py` (service / DAO, CRUD)
**Analog:** `src/db/orders.py` (lines 40-111, 140-182)

**Imports pattern:**
```python
import asyncio
import json
from collections.abc import Sequence
from datetime import datetime
import aiosqlite
from src.models.order import Order, OrderStatus
```

**Optimistic lock update & audit history pattern (D-15, D-16, D-17):**
```python
# Analog: src/db/orders.py lines 79-94
async def mutate_order_with_lock(
    db: aiosqlite.Connection,
    order_id: int,
    expected_updated_at: str | datetime,
    delta_dict: dict,
    user_id: int | None,
    user_name: str | None,
) -> tuple[bool, dict | None, Order | None]:
    """Execute atomic update with optimistic lock WHERE id=? AND updated_at=?."""
    async with db.execute("SELECT * FROM orders WHERE id = ?", (order_id,)) as cursor:
        row = await cursor.fetchone()
        if not row:
            return False, None, None

    # Verify optimistic lock
    current_updated_at = str(row["updated_at"])
    if current_updated_at != str(expected_updated_at):
        # Conflict! Read latest history record per D-17
        async with db.execute(
            "SELECT * FROM order_history WHERE order_id = ? ORDER BY id DESC LIMIT 1",
            (order_id,)
        ) as h_cur:
            last_change = await h_cur.fetchone()
            return False, dict(last_change) if last_change else {}, _row_to_order(row)

    # Build dynamic UPDATE fields
    fields: list[str] = []
    params: list = []
    changes: dict = {}
    for col, new_val in delta_dict.items():
        if col in row.keys() and row[col] != new_val:
            fields.append(f"{col} = ?")
            params.append(new_val)
            changes[col] = {"old": row[col], "new": new_val}

    if not fields:
        return True, {}, _row_to_order(row)

    fields.append("updated_at = CURRENT_TIMESTAMP")
    sql = f"UPDATE orders SET {', '.join(fields)} WHERE id = ? AND updated_at = ?"
    params.extend([order_id, row["updated_at"]])

    cursor = await db.execute(sql, params)
    if cursor.rowcount == 0:
        return False, {}, _row_to_order(row)

    # Record audit trail per D-16
    await db.execute(
        """
        INSERT INTO order_history (order_id, user_id, user_name, action, changes_json)
        VALUES (?, ?, ?, 'MUTATE', ?)
        """,
        (order_id, user_id, user_name, json.dumps(changes, ensure_ascii=False))
    )
    await db.commit()

    fresh_order = await get_order_by_id(db, order_id)
    return True, changes, fresh_order
```

**Active-first search resolver pattern (D-07):**
```python
# Analog: src/db/orders.py lines 166-182
ACTIVE_STATUSES = ('CHO_LAM', 'DANG_LAM', 'DA_DONG_GOI', 'DA_TAO_DON', 'SHIPPER_DA_LAY')
TERMINAL_STATUSES = ('DA_GIAO', 'BOM_HANG', 'HUY_DON')

async def find_orders_for_mutation(
    db: aiosqlite.Connection,
    order_id: int | None = None,
    keyword: str | None = None,
    phone: str | None = None,
    limit: int = 5,
) -> list[Order]:
    """Find orders prioritizing active lifecycle states before completed/cancelled ones (D-07)."""
    # 1. Exact order_id match
    if order_id:
        ord_obj = await get_order_by_id(db, order_id)
        return [ord_obj] if ord_obj else []

    # 2. Query active orders first
    # Uses unaccent for diacritic-insensitive customer_name / shipping_address match
    ...
```

---

### 5. `src/services/intent_router.py` (service / utility, request-response)
**Analog:** `src/services/order_search.py` (lines 18-43, 60-100)

**Imports pattern:**
```python
import logging
import re
from openai import AsyncOpenAI
from src.models.mutation import IntentType
from src.services.order_search import is_search_intent, PHONE_PATTERN
```

**Regex patterns & context parsing:**
```python
# Analog: src/services/order_search.py lines 18-43
MUTATION_PREFIXES: tuple[str, ...] = (
    "sửa", "đổi", "huỷ", "hủy", "cập nhật", "thay", "chuyển",
    "bỏ", "bớt", "thêm ghi chú", "mã vận đơn", "vận đơn là",
)

REPLY_ORDER_ID_PATTERN = re.compile(r"(?:CHI TIẾT ĐƠN HÀNG|Mã đơn:?)\s*#?(\d+)")

def extract_order_id_from_reply(reply_text: str | None) -> int | None:
    if not reply_text:
        return None
    match = REPLY_ORDER_ID_PATTERN.search(reply_text)
    return int(match.group(1)) if match else None
```

**Fast-path status regex pattern (D-06):**
```python
FAST_PATH_STATUS_PATTERNS = [
    (re.compile(r"^(?:huỷ|hủy)\s+đơn\s*(?:#|số)?\s*(\d+)$", re.IGNORECASE), "HUY_DON"),
    (re.compile(r"^đơn\s*(?:#|số)?\s*(\d+)\s+(?:đã\s+giao|giao\s+thành\s+công)$", re.IGNORECASE), "DA_GIAO"),
    (re.compile(r"^đơn\s*(?:#|số)?\s*(\d+)\s+bom(?:\s+hàng)?$", re.IGNORECASE), "BOM_HANG"),
    (re.compile(r"^(?:làm|bắt\s+đầu\s+làm)\s+đơn\s*(?:#|số)?\s*(\d+)$", re.IGNORECASE), "DANG_LAM"),
    (re.compile(r"^đã\s+đóng\s+gói\s+đơn\s*(?:#|số)?\s*(\d+)$", re.IGNORECASE), "DA_DONG_GOI"),
]
```

**3-Way classify_intent pattern (D-01, D-02, D-03, D-04, D-05):**
```python
async def classify_intent(
    text: str,
    client: AsyncOpenAI,
    model_id: str,
    has_reply_order: bool = False,
) -> IntentType:
    trimmed = text.strip().lower()
    if has_reply_order:
        return IntentType.MUTATE

    # Fast-path: Regex prefixes
    if any(trimmed.startswith(p) for p in MUTATION_PREFIXES):
        return IntentType.MUTATE

    # Search intent
    if is_search_intent(text):
        return IntentType.SEARCH

    # Ambiguity check (D-02): prioritize MUTATE
    if any(cue in trimmed for cue in ("sửa", "đổi", "huỷ", "hủy")):
        return IntentType.MUTATE

    if PHONE_PATTERN.search(text):
        return IntentType.CREATE

    # LLM fallback (10-20 tokens per D-04)
    resp = await client.chat.completions.create(
        model=model_id,
        messages=[{"role": "user", "content": prompt}],
        max_tokens=5,
        temperature=0.0,
    )
    ...
```

---

### 6. `src/services/mutation_extractor.py` (service, request-response / transform)
**Analog:** `src/services/extractor.py` (lines 89-183)

**Imports pattern:**
```python
import logging
from openai import AsyncOpenAI, BadRequestError
from src.models.mutation import OrderMutationDelta
```

**2-tier extractor pattern with JSON mode fallback:**
```python
# Analog: src/services/extractor.py lines 145-185
async def extract_mutation_delta(
    client: AsyncOpenAI,
    model_id: str,
    text: str,
) -> OrderMutationDelta | None:
    messages = [
        {"role": "system", "content": MUTATION_SYSTEM_PROMPT},
        {"role": "user", "content": f"<message>{text}</message>"},
    ]
    # Tier 1: Strict parse
    try:
        response = await client.beta.chat.completions.parse(
            model=model_id,
            messages=messages,
            response_format=OrderMutationDelta,
            timeout=15.0,
        )
        parsed = response.choices[0].message.parsed
        if parsed:
            return parsed
    except (BadRequestError, Exception) as e:
        logger.warning("Tier 1 mutation parse failed, falling back to JSON mode: %s", e)

    # Tier 2: json_object fallback
    try:
        response = await client.chat.completions.create(
            model=model_id,
            messages=messages,
            response_format={"type": "json_object"},
            timeout=15.0,
        )
        content = response.choices[0].message.content
        if content:
            return OrderMutationDelta.model_validate_json(content)
    except Exception as e:
        logger.error("Tier 2 mutation extraction failed: %s", e)
    return None
```

---

### 7. `src/bot/keyboards.py` (component / utility, transform)
**Analog:** `src/bot/keyboards.py` (lines 80-116, 256-296)

**Card styling & divider constant (D-19):**
```python
# Analog: src/bot/keyboards.py line 105
DIVIDER = "──────────────"  # Rút ngắn 14 ký tự chống vỡ màn hình nhỏ per D-19
```

**Visual Diff card formatter pattern (D-11, D-19):**
```python
def render_mutation_diff_card(order: Order, delta: dict) -> str:
    """Format elderly-friendly Visual Diff card showing ONLY changed fields Before ➡️ After."""
    diff_lines = []
    # Status, Phone, Address, Money, Tracking, Items, Notes diff lines
    # Pure HTML escaping with html.escape()
    ...
```

**Disambiguation keyboard pattern (D-08, D-13):**
```python
# Multi-order picker buttons
def build_mutation_disambiguation_keyboard(orders: list[Order], draft_id: str) -> InlineKeyboardMarkup:
    # 1 button per order: [Đơn #12 - Nam - 250k - Chờ làm]
    buttons = [
        [InlineKeyboardButton(
            f"📦 Đơn #{o.id} - {o.customer_name} - {o.total_amount:,} đ - {STATUS_NAMES.get(o.status)}",
            callback_data=f"ord_mut_sel:{draft_id}:{o.id}"
        )]
        for o in orders[:5]
    ]
    buttons.append([InlineKeyboardButton("❌ Huỷ bỏ", callback_data=f"ord_mut_ca:{draft_id}")])
    return InlineKeyboardMarkup(buttons)

# Visual diff confirmation buttons (MUT-04)
def build_mutation_confirm_keyboard(draft_id: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("✅ Xác nhận sửa", callback_data=f"ord_mut_cf:{draft_id}"),
            InlineKeyboardButton("❌ Huỷ", callback_data=f"ord_mut_ca:{draft_id}"),
        ]
    ])
```

---

### 8. `src/bot/handlers/mutation.py` (controller, event-driven / request-response)
**Analog:** `src/bot/handlers/order_actions.py` (lines 35-65) & `src/bot/handlers/search.py` (lines 29-63)

**Imports & DB context helper:**
```python
# Analog: src/bot/handlers/order_actions.py lines 35-43
from contextlib import nullcontext
from telegram import Update
from telegram.constants import ChatAction
from telegram.ext import ContextTypes
from src.db.connection import get_db_connection

def _get_active_db_context(context: ContextTypes.DEFAULT_TYPE):
    app_context = context.application.bot_data.get("app_context")
    db = getattr(app_context, "db", None) if app_context else context.application.bot_data.get("db")
    settings = getattr(app_context, "settings", None) if app_context else context.application.bot_data.get("settings")
    db_path = getattr(settings, "sqlite_db_path", "cassette_store.db") if settings else "cassette_store.db"
    return nullcontext(db) if db else get_db_connection(db_path)
```

**Draft TTL 120s lifecycle pattern:**
```python
# Analog: src/bot/handlers/ingest.py lines 132-153 & order_actions.py line 67
draft_id = uuid.uuid4().hex[:8]
pending_mutations = context.user_data.setdefault("pending_mutations", {})
pending_mutations[draft_id] = {
    "draft_id": draft_id,
    "order_id": target_order.id,
    "expected_updated_at": str(target_order.updated_at),
    "delta": delta_dict,
    "expires_at": time.time() + 120,
}
```

---

### 9. `src/bot/handlers/callbacks.py` (controller, event-driven / CRUD)
**Analog:** `src/bot/handlers/callbacks.py` (lines 21-75)

**Callback dispatch & optimistic lock error handling (D-12, D-14, D-15, D-17, D-18):**
```python
# Pattern prefix: ord_mut_cf, ord_mut_ca, ord_mut_sel, ord_mut_st
async def handle_mutation_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    # 1. Check TTL expiry
    if time.time() > draft["expires_at"]:
        await query.edit_message_text("⏰ Yêu cầu sửa đơn đã hết hạn 120s...", reply_markup=None)
        return
    # 2. Cancel: edit message and remove buttons (D-12)
    if action == "ca":
        await query.edit_message_text("❌ Đã huỷ yêu cầu sửa đơn.", reply_markup=None)
        return
    # 3. Confirm: execute mutate_order_with_lock
    success, changes, order = await mutate_order_with_lock(...)
    if not success:
        # Conflict notice per D-17 & fresh card per D-18
        ...
```

---

## Shared Patterns

### 1. Database Context Resolution
**Source:** `src/bot/handlers/ingest.py` (lines 115-117), `src/bot/handlers/order_actions.py` (lines 35-42)  
**Apply to:** `src/bot/handlers/mutation.py`, `src/bot/handlers/callbacks.py`
```python
def _get_active_db_context(context: ContextTypes.DEFAULT_TYPE):
    app_context = context.application.bot_data.get("app_context")
    db = getattr(app_context, "db", None) if app_context else context.application.bot_data.get("db")
    settings = getattr(app_context, "settings", None) if app_context else context.application.bot_data.get("settings")
    db_path = getattr(settings, "sqlite_db_path", "cassette_store.db") if settings else "cassette_store.db"
    return nullcontext(db) if db else get_db_connection(db_path)
```

### 2. Elderly-Friendly Card Formatting (14-char Divider & HTML Escaping)
**Source:** `src/bot/keyboards.py` (lines 80-116), per Decision D-19
**Apply to:** All Telegram output cards in `src/bot/keyboards.py` and `src/bot/handlers/mutation.py`
```python
DIVIDER = "──────────────"  # 14 chars, no wrapping on small mobile screens
safe_text = html.escape(str(user_val))
```

### 3. In-Memory TTL Expiry (120s)
**Source:** `src/bot/handlers/ingest.py` (lines 151-153), `src/bot/handlers/order_actions.py` (lines 182-192)  
**Apply to:** `pending_mutations` state stored in `context.user_data`
```python
expires_at = time.time() + 120
if time.time() > draft.get("expires_at", 0):
    await query.edit_message_text("⏰ Thao tác đã hết hạn sau 120s...", reply_markup=None)
    pending_mutations.pop(draft_id, None)
    return
```

### 4. 2-Tier LLM Extraction with Fallback
**Source:** `src/services/extractor.py` (lines 158-185)  
**Apply to:** `src/services/mutation_extractor.py`
```python
# Tier 1: client.beta.chat.completions.parse(response_format=Schema)
# Tier 2: client.chat.completions.create(response_format={"type": "json_object"}) -> Schema.model_validate_json()
```

---

## No Analog Found

None. All Phase 7 components have clear analogs in the existing codebase:
- `intent_router.py` mirrors `order_search.py` (regex + LLM router)
- `mutation_extractor.py` mirrors `extractor.py` (2-tier extraction)
- `mutate_order_with_lock` mirrors `update_order_status` in `orders.py` (extended with concurrency lock)
- `mutation.py` handler mirrors `order_actions.py` (callback transitions & prompt states)

---

## Metadata

**Analog search scope:** `src/models/`, `src/db/`, `src/services/`, `src/bot/`, `tests/`  
**Files scanned:** 32  
**Pattern extraction date:** 2026-10-25
