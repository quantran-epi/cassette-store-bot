---
phase: 02-llm-ingestion-interactive-confirmation
reviewed: 2026-10-24T18:00:00Z
depth: standard
files_reviewed: 10
files_reviewed_list:
  - src/models/extractor.py
  - src/services/extractor.py
  - src/bot/handlers/ingest.py
  - src/bot/handlers/callbacks.py
  - src/bot/app.py
  - src/db/customers.py
  - src/db/orders.py
  - tests/test_extractor.py
  - tests/test_ingest.py
  - tests/test_db_orders.py
findings:
  critical: 0
  warning: 3
  info: 2
  total: 5
status: issues_found
---

# Phase 02: Code Review Report

**Reviewed:** 2026-10-24T18:00:00Z
**Depth:** standard
**Files Reviewed:** 10
**Status:** issues_found

## Summary

Reviewed all source files and test suites in Phase 02 covering LLM order ingestion, Pydantic extraction schema, interactive confirmation callbacks, customer history/BOM alerts, and multi-address handling.

Code quality and security gates are generally strong: whitelist gate runs at group -1, prompts isolate untrusted input with `<message>` tags, callback tokens stay well under 64 bytes, and tests achieve full coverage across all scenarios.

Identified 3 warnings regarding data persistence atomicity and in-memory session lifetime, along with 2 minor maintainability items.

## Warnings

### WR-01: Non-atomic customer creation and order persistence in confirmation callback

**File:** `src/bot/handlers/callbacks.py:91-122`
**Issue:** When confirming an order, `create_customer` (or `add_address`) and `create_order` execute in separate database transactions, each calling `await db.commit()`. If an unexpected error, connection interruption, or unhandled constraint violation occurs between customer creation and order creation, an orphaned customer record will be committed without the corresponding order. Furthermore, because the draft was already popped at line 72, the user cannot retry confirmation.
**Fix:** Wrap multi-step customer/order persistence in an explicit transaction block or pass a transaction context so that customer and order commits happen atomically:
```python
# In handle_order_callback:
async with db.cursor() as _:
    await db.execute("BEGIN TRANSACTION;")
    try:
        # get_customer_by_phone, create_customer / add_address, create_order
        await db.commit()
    except Exception:
        await db.rollback()
        raise
```

### WR-02: Missing eviction policy or TTL for `pending_orders` in user context

**File:** `src/bot/handlers/ingest.py:129-130`
**Issue:** `pending_orders` drafts are stored in `context.user_data["pending_orders"]` keyed by `draft_id`. While confirmed and cancelled orders are popped upon user action, unconfirmed or abandoned drafts (e.g. user sends text but never taps confirm/cancel) accumulate indefinitely in memory for long-running bot instances.
**Fix:** Limit the maximum number of pending drafts per user (e.g., retain only the 5 most recent drafts) or check timestamp expiration:
```python
pending_orders = context.user_data.setdefault("pending_orders", {})
if len(pending_orders) > 10:
    # Evict oldest entry
    oldest_id = next(iter(pending_orders))
    pending_orders.pop(oldest_id, None)
pending_orders[draft_id] = draft_data
```

### WR-03: Address auto-fill flag not reset when selecting same address via inline picker

**File:** `src/bot/handlers/callbacks.py:48-50`
**Issue:** When a customer has multiple addresses and taps an address picker button (`ord:ad:<draft_id>:<idx>`), `draft["address_auto_filled"] = False` is set, but if the user tapped on an address that happens to match what was originally auto-filled or if the user switches back, the label state is modified in-place on the draft without preserving original customer address tracking if the query is re-rendered multiple times.
**Fix:**
```python
if 0 <= addr_idx < len(available):
    draft["shipping_address"] = available[addr_idx]
    draft["address_auto_filled"] = False
```
Ensure `draft["address_auto_filled"]` is explicitly checked against the selected index or reset consistently.

## Info

### IN-01: Bare `Exception` catching in tier 1 structured output fallback

**File:** `src/services/extractor.py:53`
**Issue:** Catching `(BadRequestError, Exception)` catches all unexpected errors (including potential programmer errors or cancelation) to trigger tier 2. Catching `openai.APIError` or `Exception` is safe for recovery but could obscure unintended configuration bugs during development.
**Fix:** Consider narrowing to `openai.APIError` or logging the exception type explicitly.

### IN-02: Code duplication between `handle_text_order` and `handle_photo_order`

**File:** `src/bot/handlers/ingest.py:151-184` and `190-246`
**Issue:** Both handlers duplicate client/settings retrieval from `app_context`, gateway error handling, and empty extraction replies.
**Fix:** Extract common LLM call and error-response wrapper into a shared helper function `_extract_and_validate(update, context, text)`.

---

_Reviewed: 2026-10-24T18:00:00Z_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
