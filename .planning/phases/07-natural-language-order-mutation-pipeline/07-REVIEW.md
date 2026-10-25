---
phase: 07-natural-language-order-mutation-pipeline
reviewed: 2026-10-25T11:00:00Z
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
  info: 4
  total: 9
status: issues_found
---

# Phase 07: Code Review Report

**Reviewed:** 2026-10-25T11:00:00Z
**Depth:** standard
**Files Reviewed:** 17
**Status:** issues_found

## Summary

Code review conducted across 17 files covering Phase 7 Natural Language Order Mutation Pipeline. Core architecture is well structured: 3-way intent routing, active-first order lookup, dual-tier extraction, visual diff card with 14-char divider, and optimistic locking audit trails.

However, adversarial analysis revealed 2 Critical defects and 3 Warnings that risk functional correctness, order creation interception, and false-positive concurrency conflicts:
1. **CR-01 (Blocker):** Step 5 of `classify_intent` uses unconditional substring search `cue in trimmed` for `"sửa"`, `"đổi"`, `"huỷ"`, `"hủy"` before checking `PHONE_PATTERN`. Real new order messages containing common address landmarks (e.g. `"tiệm sửa xe"`, `"sửa khoá"`, or telex typo `"đổi diện"`) are misrouted to MUTATE, dropping the order creation pipeline.
2. **CR-02 (Blocker):** `find_orders_for_mutation` without criteria (`order_id=None, keyword=None, phone=None`) builds an empty SQL filter and fetches the latest active orders. A mutation query without target identifiers (e.g. "sửa ghi chú giao sau 18h") silently targets an arbitrary recent order.
3. **WR-01 (Warning):** `_normalize_ts` does not match timestamps when one string lacks fractional seconds (`2026-10-25 08:30:00`) and the other contains `.000` or `.000000`, causing false optimistic lock conflicts.
4. **WR-02 (Warning):** `target_order_id` in `OrderMutationDelta` lacks `mode="before"` string cleaning, causing Tier 2 fallback to fail when models return `"#12"`.
5. **WR-03 (Warning):** Cancellation and TTL expiry in `handle_mutation_callback` print `Đơn hàng # được giữ nguyên` when triggered on disambiguation keyboards where `order_id` is empty.

## Narrative Findings (AI reviewer)

## Critical Issues

### CR-01: Intent router misclassifies new orders containing common landmark words as MUTATE

**File:** `src/services/intent_router.py:83-84`
**Issue:** Step 5 of `classify_intent` tests `if any(cue in trimmed for cue in ("sửa", "đổi", "huỷ", "hủy")):` across the entire trimmed text without word boundary checks and before checking `PHONE_PATTERN` at Step 6. Any new order containing address landmark words like `"gần tiệm sửa xe"`, `"đối diện tiệm sửa khoá"`, or common Vietnamese keyboard typos like `"đổi diện"` is misclassified as `IntentType.MUTATE`. The bot sends the message to `handle_mutation_flow`, dropping new order creation.
**Fix:**
```python
    # Step 5: Ambiguity check (mutation phrase with field/order intent) -> prioritize MUTATE per D-02
    MUTATION_ACTION_REGEX = re.compile(
        r"\b(?:sửa|đổi|huỷ|hủy|cập nhật|thay)\s+(?:đơn|địa chỉ|sđt|số điện thoại|tiền|cod|ghi chú|trạng thái|mã vận đơn|băng|sang|lại)\b",
        re.IGNORECASE,
    )
    if MUTATION_ACTION_REGEX.search(trimmed):
        return IntentType.MUTATE

    # Step 6: Contains Vietnamese phone number -> CREATE
    if PHONE_PATTERN.search(text):
        return IntentType.CREATE
```

### CR-02: `find_orders_for_mutation` with empty criteria matches arbitrary active orders

**File:** `src/db/orders.py:340-384`
**Issue:** If `order_id`, `keyword`, and `phone` are all `None`, `conds` remains empty, making `where_filter = ""` in `find_orders_for_mutation`. The query executes `SELECT * FROM orders WHERE status IN ('CHO_LAM', ...) LIMIT 5`. When a user sends a command without target identifiers (e.g. `"sửa ghi chú giao sau 18h"` without replying to an order), `handle_mutation_flow` receives the newest active orders. If exactly 1 active order exists, it silently targets that order, leading to unintended data mutation on unrelated orders.
**Fix:**
```python
async def find_orders_for_mutation(
    db: aiosqlite.Connection,
    order_id: int | None = None,
    keyword: str | None = None,
    phone: str | None = None,
    limit: int = 5,
) -> list[Order]:
    """Retrieve orders for mutation prioritizing active lifecycle states before completed ones (D-07)."""
    if order_id is not None:
        ord_obj = await get_order_by_id(db, order_id)
        return [ord_obj] if ord_obj else []

    if not phone and not keyword:
        return []
```

## Warnings

### WR-01: `_normalize_ts` fails equality comparison between timestamps with and without `.000`

**File:** `src/db/orders.py:11-21`
**Issue:** When an order is created or updated via `CURRENT_TIMESTAMP`, SQLite stores `"2026-10-25 08:30:00"` (no fractional seconds). If caller supplies `expected_updated_at` formatted from Python `datetime` with microsecond 0 (`"2026-10-25 08:30:00.000000"`), `_normalize_ts` returns `"2026-10-25 08:30:00"` for the database row and `"2026-10-25 08:30:00.000"` for expected. The string comparison fails, triggering a false-positive optimistic concurrency conflict.
**Fix:**
```python
def _normalize_ts(ts: object) -> str:
    """Normalize timestamp string/datetime to millisecond precision for safe equality comparison."""
    if not ts:
        return ""
    s = str(ts).strip().replace("T", " ")
    if "." in s:
        base, frac = s.split(".", 1)
        frac_digits = "".join(c for c in frac if c.isdigit())[:3].ljust(3, "0")
        if frac_digits == "000":
            return base
        return f"{base}.{frac_digits}"
    return s
```

### WR-02: `target_order_id` in `OrderMutationDelta` fails validation on `"#12"` string from LLM

**File:** `src/models/mutation.py:23-25`
**Issue:** `target_order_id` is typed `int | None`. In Tier 2 JSON fallback mode, models frequently output strings with prefix like `"#12"` or `"đơn 12"`. Without a pre-validator, Pydantic throws `ValidationError`, causing Tier 2 extraction to abort and presenting an error to the user.
**Fix:**
```python
    @field_validator("target_order_id", mode="before")
    @classmethod
    def validate_order_id(cls, v: object) -> int | None:
        if v is None:
            return None
        if isinstance(v, int):
            return v
        if isinstance(v, str):
            digits = re.sub(r"\D", "", v)
            return int(digits) if digits else None
        return None
```

### WR-03: Mutation cancellation and TTL expiry display empty order ID `#` on disambiguation cards

**File:** `src/bot/handlers/callbacks.py:203, 215`
**Issue:** During disambiguation, `order_id` is not yet set in `pending_mutations[draft_id]`. If the user taps `[❌ Huỷ]` or the draft expires (120s TTL), the message formats `f"Đơn hàng #{oid} được giữ nguyên"`, displaying `Đơn hàng # được giữ nguyên` with an empty number.
**Fix:**
```python
    # Handle cancellation (ord_mut_ca) per D-12
    if action == "ca":
        oid = draft.get("order_id")
        oid_str = f" #{oid}" if oid else ""
        pending_mutations.pop(draft_id, None)
        await query.edit_message_text(
            f"❌ <b>ĐÃ HUỶ YÊU CẦU SỬA ĐƠN</b>\n"
            f"<i>Đơn hàng{oid_str} được giữ nguyên, không có thay đổi nào được lưu.</i>",
            reply_markup=None,
            parse_mode="HTML",
        )
        return
```

## Info

### IN-01: Order detail card omits `order.notes` field

**File:** `src/bot/keyboards.py:82-124`
**Issue:** `render_order_detail_card` does not include `order.notes`. Order mutations modify `notes` (MUT-03 Group 3), but the card never displays them to staff.
**Fix:** Include `notes_line = f"📝 <b>Ghi chú:</b> {html.escape(order.notes)}\n" if order.notes else ""` in `render_order_detail_card`.

### IN-02: Fast-path status falls through to LLM when order ID does not exist

**File:** `src/bot/handlers/mutation.py:56-76`
**Issue:** When `parse_fast_path_status` matches (e.g. `"huỷ đơn 9999"`) but the order does not exist in SQLite, `handle_mutation_flow` falls through to LLM delta extraction. The LLM extracts order 9999 again, taking 15s and consuming tokens, only to confirm that order 9999 does not exist.
**Fix:** If `fast_path` matches and `target_order` is `None`, immediately reply with the friendly not-found message using `target_oid` without calling the LLM.

### IN-03: Unused imports in mutation and callback handlers

**File:** `src/bot/handlers/mutation.py:21-22`, `src/bot/handlers/callbacks.py:19`
**Issue:** `OrderMutationDelta` and `Order` imported in `mutation.py`, and `STATUS_NAMES` imported in `callbacks.py` are unused, causing linter warnings.
**Fix:** Remove unused imports.

### IN-04: `render_mutation_diff_card` displays notes diff when notes are unchanged

**File:** `src/bot/keyboards.py:986-989`
**Issue:** Diff card checks `if new_notes:` without verifying `new_notes != order.notes`, displaying a diff line even if notes remain identical.
**Fix:** Change to `if new_notes and new_notes != order.notes:`.

---

_Reviewed: 2026-10-25T11:00:00Z_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
