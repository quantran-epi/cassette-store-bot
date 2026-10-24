---
phase: 03-ergonomic-order-management-low-tech-actions
reviewed: 2026-10-24T19:58:00Z
depth: standard
files_reviewed: 9
files_reviewed_list:
  - src/bot/app.py
  - src/bot/handlers/base.py
  - src/bot/handlers/ingest.py
  - src/bot/handlers/order_actions.py
  - src/bot/handlers/orders.py
  - src/bot/keyboards.py
  - src/db/orders.py
  - tests/test_db_orders.py
  - tests/test_orders_ui.py
findings:
  critical: 2
  warning: 5
  info: 3
  total: 10
status: issues_found
---

# Phase 03: Code Review Report

**Reviewed:** 2026-10-24T19:58:00Z  
**Depth:** standard  
**Files Reviewed:** 9  
**Status:** issues_found  

## Summary

Reviewed Phase 03 implementation for order navigation, status management, tracking codes, photo actions, and UI keyboards. The overall architecture follows python-telegram-bot v20+ async standards, but critical defects exist around state isolation (`action_state` intercepting new orders and corrupting existing data) and unescaped HTML user input causing Telegram API entity parsing crashes. Several warnings regarding Telegram Bot API `CopyTextButton` constraints, double callback query answers, and UTC vs Vietnam timezone display discrepancies were also identified.

## Critical Issues

### CR-01: Uncleaned `action_state` intercepts new order entries and corrupts tracking codes or photos

**File:** `src/bot/handlers/orders.py:36`, `src/bot/handlers/order_actions.py:50`, `src/bot/handlers/orders.py:138`
**Issue:** When a user triggers "Nhập mã vận đơn" (`await_tracking`) or "Gửi thêm ảnh" (`await_photo`), `context.user_data["action_state"]` is stored with a 120s TTL. If the user subsequently taps the reply menu button "📝 Nhập đơn mới", clicks "Quay lại thẻ đơn" (`ord_v_cur`), or clicks "Nhập đơn mới" from the empty list (`ord_act:new`), `action_state` is NOT cleared. When the user proceeds to paste a new order text or send a photo with caption, `handle_text_order` or `handle_photo_order` intercepts the input. In `await_tracking`, the incoming order text is truncated and stored as the previous order's tracking code. In `await_photo`, photos for new orders are silently attached to the previous order while dropping the order caption. The new order is completely lost.
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
**Issue:** In `handle_action_state_text`, `tracking_code` is extracted directly from user input without escaping. It is interpolated into an HTML-formatted message (`parse_mode="HTML"`). If a user pastes a tracking URL with `&` (e.g., query params), or a code with `<` or `>`, Telegram Bot API rejects the message with `BadRequest: Can't parse entities`, crashing the handler and leaving the user with no feedback.
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

## Warnings

### WR-01: Double `query.answer()` call in `view_photo` callback action

**File:** `src/bot/handlers/order_actions.py:271`
**Issue:** `await query.answer()` is called at line 271 immediately when entering `action_type == "view_photo"`. If database access fails (line 275) or the order has no photos (line 280), `await query.answer(..., show_alert=True)` is called a second time. Calling `answerCallbackQuery` twice on the same callback query in Telegram Bot API raises `telegram.error.BadRequest`, aborting the error response.
**Fix:**
Remove line 271 or only answer with alert inside the error checks, calling empty `query.answer()` only before sending photos:
```python
if action_type == "view_photo":
    db_ctx = _get_active_db_context(context)
    async with db_ctx as active_db:
        if not active_db:
            await query.answer("Lỗi kết nối cơ sở dữ liệu!", show_alert=True)
            return
        order = await get_order_by_id(active_db, order_id)
        if not order or not order.photo_file_ids:
            await query.answer("Đơn này chưa có ảnh nào bác nhé!", show_alert=True)
            return
        await query.answer()
        ...
```

### WR-02: Naive UTC timestamps displayed to elderly users and incorrect back date calculation

**File:** `src/bot/keyboards.py:72-76`, `src/bot/handlers/order_actions.py:65, 176`
**Issue:** SQLite `CURRENT_TIMESTAMP` stores dates in UTC. Pydantic loads `order.created_at` as a naive datetime. `render_order_detail_card` formats `order.created_at` with `strftime("%d/%m/%Y %H:%M")` without converting to `TZ_VN` (UTC+7), displaying timestamps 7 hours behind actual local time. Furthermore, in `order_actions.py`, `order.created_at.strftime("%Y-%m-%d")` evaluates to UTC date, so orders created between 00:00 and 06:59 Vietnam time produce yesterday's date, breaking the "Quay lại" button navigation.
**Fix:**
Localize naive UTC datetimes to `timezone.utc` and convert to `TZ_VN`:
```python
def _to_vn_datetime(dt: datetime | None) -> datetime | None:
    if not dt:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(TZ_VN)
```

### WR-03: `CopyTextButton` missing length truncation on `shipping_address`

**File:** `src/bot/keyboards.py:122`
**Issue:** Telegram Bot API strictly limits `CopyTextButton(text=...)` to 1-256 characters. Long Vietnamese addresses with ward/district/city and landmark details exceeding 256 characters cause Telegram to reject the entire message with HTTP 400 `BadRequest: BUTTON_COPY_TEXT_INVALID`. Empty addresses also fail validation.
**Fix:**
Ensure address is clamped between 1 and 256 characters:
```python
safe_address = (order.shipping_address.strip() or "Chưa có địa chỉ")[:256]
InlineKeyboardButton(
    "📍 Copy Địa chỉ",
    copy_text=CopyTextButton(text=safe_address),
)
```

### WR-04: Loss of list date and page context during status transitions and status menu

**File:** `src/bot/keyboards.py:108, 166`, `src/bot/handlers/order_actions.py:66, 177`
**Issue:** `ord_st` and `ord_st_menu` callbacks do not preserve `date_str` and `page`. When a user viewing page 3 of orders from 3 days ago transitions an order status, the redraw in `handle_order_status_callback` defaults `date_str` to `today_str` and `page=1`. When the user taps "⬅️ Quay lại", they lose their position and are booted back to today's page 1.
**Fix:**
Include date and page in the callback payload (e.g., `ord_st:{order_id}:{status}:{date}:{page}`) or track the user's active browsing context in `context.user_data["current_order_nav"]`.

### WR-05: Misleading prompt for photo receipt when entering tracking code

**File:** `src/bot/handlers/order_actions.py:235`
**Issue:** The prompt text says: `"Bác gửi mã vận đơn đối tác ship (hoặc dán ảnh biên lai ship) vào ô chat cho đơn này nhé."` However, `handle_photo_order` does not handle `await_tracking`, and receipt photos sent without caption are rejected with a message asking for order details.
**Fix:**
Adjust prompt to remove the photo receipt mention until receipt OCR/image attachment is implemented:
```python
text = (
    f"🚚 <b>NHẬP MÃ VẬN ĐƠN CHO ĐƠN #{order_id}</b>\n\n"
    f"Bác gõ hoặc dán mã vận đơn vào ô chat cho đơn này nhé.\n\n"
    f"<i>(Thời gian chờ là 2 phút)</i>"
)
```

## Info

### IN-01: Unescaped `first_name` in Markdown `/start` command handler

**File:** `src/bot/handlers/base.py:20-31`
**Issue:** In `start_command`, `first_name` from Telegram profile is interpolated into text parsed with `parse_mode="Markdown"`. If a user's first name contains underscores (`_`) or asterisks (`*`), Telegram's Markdown parser throws `BadRequest`.
**Fix:** Switch to `parse_mode="HTML"` and use `html.escape(first_name)`.

### IN-02: Inconsistent date format on empty order list card

**File:** `src/bot/keyboards.py:234`
**Issue:** When `total_orders == 0`, `render_order_list_card` renders `📅 ĐƠN HÀNG NGÀY {date_str}` (raw `YYYY-MM-DD`), whereas populated cards convert `date_str` to Vietnamese `DD/MM/YYYY`.
**Fix:** Convert `date_str` to `display_date` before formatting the empty state card.

### IN-03: Potential race condition in `append_order_photos`

**File:** `src/db/orders.py:121-129`
**Issue:** `append_order_photos` performs a Python-level read-modify-write cycle (`get_order_by_id`, concat lists, `UPDATE`). If multiple photos arrive in separate updates concurrently, an update could overwrite another.
**Fix:** Use an SQLite atomic JSON update or serialize updates using an order-level lock.

---

_Reviewed: 2026-10-24T19:58:00Z_  
_Reviewer: Claude (gsd-code-reviewer)_  
_Depth: standard_
