---
phase: 03-ergonomic-order-management-low-tech-actions
reviewed: 2026-10-24T23:45:00Z
depth: standard
files_reviewed: 10
files_reviewed_list:
  - src/bot/app.py
  - src/bot/handlers/base.py
  - src/bot/handlers/ingest.py
  - src/bot/handlers/order_actions.py
  - src/bot/handlers/orders.py
  - src/bot/keyboards.py
  - src/db/orders.py
  - tests/test_db_orders.py
  - tests/test_ingest.py
  - tests/test_orders_ui.py
findings:
  critical: 4
  warning: 6
  info: 4
  total: 14
status: issues_found
---

# Phase 03: Code Review Report

**Reviewed:** 2026-10-24T23:45:00Z  
**Depth:** standard  
**Files Reviewed:** 10  
**Status:** issues_found  

## Summary

Reviewed Phase 03 source files (including Wave 1 order management / UI and Wave 2 photo album ingestion) at standard depth. The bot architecture follows async `python-telegram-bot` patterns and SQLite WAL practices, but adversarial review identified 4 Critical blockers and 6 Warnings.

Key concerns:
1. **Telegram API crashes** when sending media groups with trailing single photos (mod 10 == 1), when Telegram names contain Markdown characters on `/start`, and when orders lack shipping addresses for `CopyTextButton`.
2. **State leakage (`action_state`)** intercepting new order text/photos and corrupting previous orders.
3. **Dead / duplicate code** in `ingest.py` where `handle_photo_order` was duplicated and shadowed.
4. **Timezone bugs** where UTC timestamps from SQLite are displayed raw (7 hours behind local Vietnam time) and break date-based back navigation.

## Critical Issues

### CR-01: Uncleaned `action_state` intercepts new order entries and corrupts tracking codes or photos

**File:** `src/bot/handlers/orders.py:36`, `src/bot/handlers/order_actions.py:50`, `src/bot/handlers/orders.py:138`
**Issue:** When a user initiates "Nhập mã vận đơn" (`await_tracking`) or "Gửi thêm ảnh" (`await_photo`), `context.user_data["action_state"]` is stored with a 120s TTL. If the user subsequently taps the reply menu button "📝 Nhập đơn mới", clicks "Quay lại thẻ đơn" (`ord_v_cur`), or clicks "Nhập đơn mới" from the empty list (`ord_act:new`), `action_state` is NOT cleared. When the user pastes a new order or sends a photo with caption, `handle_text_order` or `handle_photo_order` intercepts the input. In `await_tracking`, the incoming order text is truncated and stored as the previous order's tracking code. In `await_photo`, photos for new orders are silently attached to the previous order while dropping the order caption. The new order is completely lost.
**Fix:**
Clear `context.user_data.pop("action_state", None)` in `handle_menu_reply`, `ord_v_cur`, and `ord_act:new`:
```python
# In src/bot/handlers/orders.py: handle_menu_reply
async def handle_menu_reply(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    context.user_data.pop("action_state", None)
    ...
```

### CR-02: Unescaped `tracking_code` in Telegram HTML message causes crash on special characters

**File:** `src/bot/handlers/order_actions.py:337`
**Issue:** In `handle_action_state_text`, `tracking_code` is extracted directly from user input without escaping and interpolated into an HTML-formatted message (`parse_mode="HTML"`). If a user pastes a tracking URL with `&` (e.g. tracking links with query params), or a code containing `<` or `>`, Telegram Bot API rejects the message with `BadRequest: Can't parse entities`, crashing the handler and leaving the user with no feedback.
**Fix:**
```python
import html

# In src/bot/handlers/order_actions.py:337
escaped_code = html.escape(tracking_code)
card_text = (
    f"✅ <b>ĐÃ CẬP NHẬT MÃ VẬN ĐƠN</b>\n\n"
    f"📦 <b>Đơn:</b> <code>#{order_id}</code>\n"
    f"🚚 <b>Mã vận đơn:</b> <code>{escaped_code}</code>"
)
```

### CR-03: `send_media_group` fails with Telegram API `BadRequest` when album photo count mod 10 equals 1

**File:** `src/bot/handlers/order_actions.py:293-302`
**Issue:** In `handle_order_action_callback` (`view_photo`), photos are chunked in batches of 10 (`[photo_ids[i:i+10] for i in range(0, len(photo_ids), 10)]`). Each chunk is passed directly to `context.bot.send_media_group(chat_id=chat_id, media=media)`. Telegram Bot API specification requires `sendMediaGroup` to contain between 2 and 10 items. For orders with 11, 21, etc. photos, the trailing chunk contains exactly 1 photo (`len(chunk) == 1`). Calling `send_media_group` with 1 item raises `telegram.error.BadRequest: Media group must include 2-10 items`, crashing the handler and failing to show the photos.
**Fix:**
```python
# In src/bot/handlers/order_actions.py:293-303
for chunk in [photo_ids[i : i + 10] for i in range(0, len(photo_ids), 10)]:
    if len(chunk) == 1:
        await context.bot.send_photo(
            chat_id=chat_id,
            photo=chunk[0],
            caption=f"📷 Ảnh đính kèm đơn #{order_id}",
        )
    else:
        media = [
            InputMediaPhoto(
                media=fid,
                caption=f"📷 Ảnh đính kèm đơn #{order_id}" if fid == chunk[0] else None,
            )
            for fid in chunk
        ]
        await context.bot.send_media_group(chat_id=chat_id, media=media)
```

### CR-04: Unescaped `first_name` in Markdown `/start` command causes crash for users with underscore/asterisk in display name

**File:** `src/bot/handlers/base.py:20-31`
**Issue:** `start_command` formats `first_name` directly into the welcome string using `parse_mode="Markdown"` without escaping special characters. If a Telegram user's `first_name` contains Markdown special characters (specifically underscores `_`, asterisks `*`, or backticks `` ` ``, e.g. `Bác_Hùng`, `shop_cassette`), Telegram's legacy Markdown parser throws `BadRequest: Can't parse entities: can't find end of italic entity at byte offset ...`, preventing whitelisted users from starting the bot.
**Fix:**
Switch `start_command` to `parse_mode="HTML"`, use `html.escape(first_name)`, and format user ID with `<code>{user_id}</code>`:
```python
import html

# In src/bot/handlers/base.py:start_command
safe_name = html.escape(first_name)
text = (
    f"Xin chào {safe_name}!\n\n"
    f"🤖 Bot Quản Lý Đơn Hàng Băng Cassette sẵn sàng phục vụ.\n"
    f"Telegram User ID nhận diện: <code>{user_id}</code>\n\n"
    f"Bác chỉ cần bấm các nút to bên dưới để xem đơn hoặc gửi tin nhắn đặt hàng bất kỳ lúc nào nhé!"
)
await update.effective_message.reply_text(
    text,
    reply_markup=keyboard,
    parse_mode="HTML",
)
```

## Warnings

### WR-01: Duplicate `handle_photo_order` function definition leaves dead code in `ingest.py`

**File:** `src/bot/handlers/ingest.py:223-241`
**Issue:** `handle_photo_order` is defined twice in `src/bot/handlers/ingest.py` (at line 223 and line 294). The first definition (lines 223-241) is completely shadowed and dead code left over from before the media group album implementation was added.
**Fix:** Delete lines 223-241.

### WR-02: Double `query.answer()` call in `view_photo` callback action raises `BadRequest` on error

**File:** `src/bot/handlers/order_actions.py:271, 275, 280`
**Issue:** `await query.answer()` is called at line 271 immediately upon entering `action_type == "view_photo"`. If database access fails (line 275) or the order has no photos (line 280), `await query.answer(..., show_alert=True)` is called a second time. Calling `answerCallbackQuery` twice on the same callback query in Telegram Bot API raises `telegram.error.BadRequest`, aborting the error response.
**Fix:** Call `await query.answer()` only once along the execution path: inside error branches with `show_alert=True`, or before sending photos on success.

### WR-03: `CopyTextButton` missing length bounds and empty string check

**File:** `src/bot/keyboards.py:134-137`
**Issue:** Telegram Bot API strictly requires `CopyTextButton(text=...)` to have 1-256 characters. When an order does not yet have a shipping address (`order.shipping_address == ""`), `CopyTextButton(text="")` violates the 1-character minimum. Telegram Bot API rejects the message edit/send with `BadRequest: BUTTON_COPY_TEXT_INVALID`. Conversely, addresses exceeding 256 characters also trigger HTTP 400.
**Fix:**
```python
# In src/bot/keyboards.py:build_order_detail_keyboard
safe_address = (order.shipping_address.strip() or "Chưa có địa chỉ")[:256]
buttons.append(
    [
        InlineKeyboardButton(
            "📋 Copy SĐT",
            copy_text=CopyTextButton(text=(order.customer_phone or "")[:256]),
        ),
        InlineKeyboardButton(
            "📍 Copy Địa chỉ",
            copy_text=CopyTextButton(text=safe_address),
        ),
    ]
)
```

### WR-04: Naive UTC timestamps displayed to users and incorrect back date calculation

**File:** `src/bot/keyboards.py:84-89`, `src/bot/handlers/order_actions.py:65, 176, 341`
**Issue:** SQLite `CURRENT_TIMESTAMP` stores dates in UTC. Pydantic loads `order.created_at` as a naive datetime. `render_order_detail_card` formats `order.created_at` with `strftime("%d/%m/%Y %H:%M")` without converting to `TZ_VN` (UTC+7), displaying timestamps 7 hours behind actual local time. Furthermore, in `order_actions.py`, `order.created_at.strftime("%Y-%m-%d")` evaluates to UTC date, so orders created between 00:00 and 06:59 Vietnam time produce yesterday's date, breaking the "Quay lại" button navigation.
**Fix:** Localize naive UTC datetimes to `timezone.utc` and convert to `TZ_VN`:
```python
def _to_vn_datetime(dt: datetime | None) -> datetime | None:
    if not dt:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(TZ_VN)
```

### WR-05: Potential race condition in `append_order_photos` with concurrent media group uploads

**File:** `src/db/orders.py:110-134` and `src/bot/handlers/ingest.py:299-312`
**Issue:** `append_order_photos` performs a non-atomic read-modify-write cycle (`get_order_by_id`, concat lists, `UPDATE`). When in `await_photo` action state, if multiple photos arrive concurrently from an album, concurrent coroutines read the same initial state, resulting in lost photo updates.
**Fix:** Serialize photo appending using an asyncio lock per order or atomic SQLite updates.

### WR-06: Misleading prompt for photo receipt when entering tracking code

**File:** `src/bot/handlers/order_actions.py:235`
**Issue:** The prompt text says: `"Bác gửi mã vận đơn đối tác ship (hoặc dán ảnh biên lai ship) vào ô chat cho đơn này nhé."` However, `handle_photo_order` does not handle `await_tracking`, and receipt photos sent without caption are rejected with a message asking for order details.
**Fix:** Adjust prompt text to remove reference to photo receipts until receipt OCR is supported:
```python
text = (
    f"🚚 <b>NHẬP MÃ VẬN ĐƠN CHO ĐƠN #{order_id}</b>\n\n"
    f"Bác gõ hoặc dán mã vận đơn vào ô chat cho đơn này nhé.\n\n"
    f"<i>(Thời gian chờ là 2 phút)</i>"
)
```

## Info

### IN-01: Inconsistent date format on empty order list card

**File:** `src/bot/keyboards.py:246-249`
**Issue:** When `total_orders == 0`, `render_order_list_card` renders `📅 ĐƠN HÀNG NGÀY {date_str}` (raw `YYYY-MM-DD`), whereas populated cards convert `date_str` to Vietnamese `DD/MM/YYYY`.
**Fix:** Convert `date_str` to `display_date` before formatting the empty state card.

### IN-02: Unused dead code `extract_province_or_city`

**File:** `src/bot/keyboards.py:31-40`
**Issue:** `extract_province_or_city` is defined in `keyboards.py` but never called anywhere in the codebase.
**Fix:** Remove unused function.

### IN-03: Duplicate database connection helper `_get_active_db_context` across handlers

**File:** `src/bot/handlers/order_actions.py:32-38`, `src/bot/handlers/orders.py:27-33`
**Issue:** Identical logic resolving `app_context.db` or fallback connection is duplicated across multiple handler modules.
**Fix:** Refactor into shared helper in `src.db.connection`.

### IN-04: Trailing blank lines in `tests/test_orders_ui.py`

**File:** `tests/test_orders_ui.py:804-809`
**Issue:** Six redundant blank lines at EOF.
**Fix:** Remove trailing blank lines.

---

_Reviewed: 2026-10-24T23:45:00Z_  
_Reviewer: Claude (gsd-code-reviewer)_  
_Depth: standard_
