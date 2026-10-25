---
phase: 07-natural-language-order-mutation-pipeline
reviewed: 2026-10-25T16:45:00Z
depth: standard
files_reviewed: 17
files_reviewed_list:
  - src/models/mutation.py
  - src/services/intent_router.py
  - src/services/mutation_extractor.py
  - tests/test_order_audit_trail.py
  - tests/test_intent_router.py
  - tests/test_mutation_extractor.py
  - src/models/order.py
  - src/db/schema.py
  - src/db/orders.py
  - src/bot/handlers/mutation.py
  - tests/test_mutation_card_and_lock.py
  - tests/test_status_suggestions.py
  - tests/test_mutation_handler_flow.py
  - src/bot/keyboards.py
  - src/bot/handlers/ingest.py
  - src/bot/handlers/callbacks.py
  - src/bot/app.py
findings:
  critical: 2
  warning: 3
  info: 2
  total: 7
status: issues_found
---

# Phase 7: Code Review Report

**Reviewed:** 2026-10-25T16:45:00Z
**Depth:** standard
**Files Reviewed:** 17
**Status:** issues_found

## Summary

Adversarial review of Phase 7 (Natural Language Order Mutation Pipeline) identified 2 BLOCKER bugs, 3 WARNING defects, and 2 INFO quality issues.

The primary issues are:
1. `find_orders_for_mutation` receives `phone=delta.new_customer_phone`, which causes order search to fail when updating a customer's phone number because the search queries for the *new* unpersisted phone instead of searching by keyword/existing phone.
2. `new_notes` (Group 3 per MUT-03) is extracted and displayed on the Visual Diff Card, but the `orders` SQLite table and `Order` domain model lack a `notes` column. `mutate_order_with_lock` silently drops `notes`, leading to data loss on confirmation.

## Narrative Findings (AI reviewer)

## Critical Issues

### CR-01: `new_customer_phone` Passed as Search Filter Breaks Order Discovery on Phone Updates

**File:** `/Users/tranducquan/Working/cassette-store/src/bot/handlers/mutation.py:128`
**Issue:** Line 128 calls `find_orders_for_mutation(..., phone=delta.new_customer_phone)`. `delta.new_customer_phone` contains the *new* phone number to be applied to the order, not the current phone number on the existing order. In `find_orders_for_mutation`, the presence of `phone` takes priority over `keyword`, executing `customer_phone LIKE '%new_phone%'`. The existing order has the old phone number, so 0 orders match and the user receives "KHÔNG TÌM THẤY ĐƠN HÀNG CẦN SỬA".
**Fix:**
```python
        matches = await find_orders_for_mutation(
            db,
            order_id=effective_order_id,
            keyword=delta.target_customer_keyword,
            limit=5,
        )
```

### CR-02: `new_notes` Extracted and Displayed on Confirmation Card but Silently Dropped by Database Layer

**File:** `/Users/tranducquan/Working/cassette-store/src/db/orders.py:366`, `/Users/tranducquan/Working/cassette-store/src/models/order.py:20`, `/Users/tranducquan/Working/cassette-store/src/db/schema.py:26`
**Issue:** `OrderMutationDelta` models `new_notes` (Group 3 per MUT-03), and `render_mutation_diff_card` displays `📝 Ghi chú mới: {new_notes}`. However, neither the `orders` table in SQLite nor the `Order` model contains a `notes` column (only `customers` table has `notes`). In `mutate_order_with_lock`, `target_col = "notes"` is filtered out by `if target_col in row_keys:`. The notes update is silently ignored; no SQL update is run, no audit history is written, and notes changes are lost upon confirmation.
**Fix:**
1. In `src/db/schema.py`, add column migration:
```python
        if "notes" not in cols:
            await db.execute("ALTER TABLE orders ADD COLUMN notes TEXT DEFAULT '';")
```
2. In `src/models/order.py`, add `notes: str = ""` to `Order`.
3. In `src/db/orders.py`, map `notes=row["notes"] if "notes" in keys else ""` in `_row_to_order`.

## Warnings

### WR-01: Duplicate SQL Column Assignment in `mutate_order_with_lock`

**File:** `/Users/tranducquan/Working/cassette-store/src/db/orders.py:360-374`
**Issue:** If `delta_dict` contains both `"new_status"` (from extractor) and `"status"` (set by `handle_status_suggestion_selection` or fast-path), both map to `target_col = "status"`. `mutate_order_with_lock` appends `status = ?` twice to `fields` and appends `val_to_save` twice to `params`, generating `UPDATE orders SET status = ?, status = ? WHERE ...`.
**Fix:** Deduplicate target columns before building SQL parameters:
```python
    seen_cols: set[str] = set()
    for col, new_val in delta_dict.items():
        target_col = col[4:] if col.startswith("new_") else col
        if target_col in row_keys and target_col not in seen_cols:
            seen_cols.add(target_col)
            val_to_save = new_val.value if hasattr(new_val, "value") else new_val
            current_val = row[target_col]
            if current_val != val_to_save:
                fields.append(f"{target_col} = ?")
                params.append(val_to_save)
                changes[target_col] = {"old": current_val, "new": val_to_save}
```

### WR-02: `update_order_status` and `update_order_tracking` Do Not Write Audit Trail to `order_history`

**File:** `/Users/tranducquan/Working/cassette-store/src/db/orders.py:101-133`
**Issue:** `update_order_status` and `update_order_tracking` update `orders.updated_at = CURRENT_TIMESTAMP` without creating a record in `order_history`. When concurrent conflict occurs in `mutate_order_with_lock`, it fetches the most recent history row from `order_history` per D-17. Because button actions leave no audit records, the conflict dialog attributes the collision to an older action (such as the initial `CREATE`) rather than the actual status transition.
**Fix:** Insert an audit record in `update_order_status` and `update_order_tracking` using `record_order_history`.

### WR-03: Status Suggestion Keyboard Back Button Misleadingly Triggers Cancellation

**File:** `/Users/tranducquan/Working/cassette-store/src/bot/keyboards.py:1056-1062`
**Issue:** In `build_mutation_status_keyboard`, the bottom button displays `"⬅️ Quay lại thẻ đơn"`, but its callback is `ord_mut_ca:{draft_id}`. Clicking it clears the mutation draft and permanently cancels the request with `"❌ ĐÃ HUỶ YÊU CẦU SỬA ĐƠN"`.
**Fix:** Change button text to `"❌ Huỷ bỏ"` or support proper back navigation:
```python
    buttons.append(
        [
            InlineKeyboardButton(
                "❌ Huỷ bỏ",
                callback_data=f"ord_mut_ca:{draft_id}",
            )
        ]
    )
```

## Info

### IN-01: Redundant LLM Call When Fast-Path Matches Non-Existent Order ID

**File:** `/Users/tranducquan/Working/cassette-store/src/bot/handlers/mutation.py:57-77`
**Issue:** When `parse_fast_path_status(text)` successfully parses an order ID and status (e.g. `huỷ đơn 9999`), but `target_order` is not found, the function falls through to the LLM extraction step rather than immediately replying with the empty guidance message.
**Fix:** Return empty guidance immediately when `fast_path` matches but the order is not in DB:
```python
    fast_path = parse_fast_path_status(text)
    if fast_path:
        target_oid, new_status = fast_path
        async with db_ctx as db:
            target_order = await get_order_by_id(db, target_oid) if db else None
        if not target_order:
            empty_msg = (
                f"🔍 <b>KHÔNG TÌM THẤY ĐƠN HÀNG CẦN SỬA</b>\n\n"
                f"Dạ em tìm trong sổ không thấy đơn hàng #{target_oid} để sửa!"
            )
            await update.message.reply_text(empty_msg, parse_mode="HTML")
            return
```

### IN-02: Dangling `#` in Cancel Message When Cancelled from Disambiguation View

**File:** `/Users/tranducquan/Working/cassette-store/src/bot/handlers/callbacks.py:214-222`
**Issue:** Cancelling from disambiguation view leaves `oid = ""` because `order_id` has not been picked yet. Message renders as `Đơn hàng # được giữ nguyên`.
**Fix:** Format message conditionally:
```python
    target_desc = f"Đơn hàng #{oid}" if oid else "Yêu cầu sửa đơn"
    await query.edit_message_text(
        f"❌ <b>ĐÃ HUỶ YÊU CẦU SỬA ĐƠN</b>\n"
        f"<i>{target_desc} được giữ nguyên, không có thay đổi nào được lưu.</i>",
        reply_markup=None,
        parse_mode="HTML",
    )
```

---

_Reviewed: 2026-10-25T16:45:00Z_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
