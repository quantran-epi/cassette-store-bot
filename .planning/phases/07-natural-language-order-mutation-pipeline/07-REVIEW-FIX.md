---
phase: 07-natural-language-order-mutation-pipeline
fixed_at: 2026-10-25T17:15:00Z
review_path: .planning/phases/07-natural-language-order-mutation-pipeline/07-REVIEW.md
iteration: 1
findings_in_scope: 5
fixed: 5
skipped: 0
status: all_fixed
---

# Phase 07: Code Review Fix Report

**Fixed at:** 2026-10-25T17:15:00Z
**Source review:** .planning/phases/07-natural-language-order-mutation-pipeline/07-REVIEW.md
**Iteration:** 1

**Summary:**
- Findings in scope: 5
- Fixed: 5
- Skipped: 0

## Fixed Issues

### CR-01: `new_customer_phone` Passed as Search Filter Breaks Order Discovery on Phone Updates

**Files modified:** `src/bot/handlers/mutation.py`, `tests/test_mutation_handler_flow.py`
**Commit:** 992edaf
**Applied fix:** Removed `phone=delta.new_customer_phone` from `find_orders_for_mutation` invocation so order discovery matches by customer keyword/reply order ID instead of querying for unpersisted new phone numbers.

### CR-02: `new_notes` Extracted and Displayed on Confirmation Card but Silently Dropped by Database Layer

**Files modified:** `src/db/schema.py`, `src/models/order.py`, `src/db/orders.py`, `tests/test_mutation_card_and_lock.py`
**Commit:** 150d39d
**Applied fix:** Added `notes` column with migration to `orders` table in `init_db`, added `notes: str = ""` to `Order` domain model, and mapped `notes` in `_row_to_order` and `create_order` to prevent notes data loss during order mutations.

### WR-01: Duplicate SQL Column Assignment in `mutate_order_with_lock`

**Files modified:** `src/db/orders.py`, `tests/test_mutation_card_and_lock.py`
**Commit:** cd288d8
**Applied fix:** Added `seen_cols` set tracking to deduplicate target columns when building SQL update parameters for overlapping delta keys.

### WR-02: `update_order_status` and `update_order_tracking` Do Not Write Audit Trail to `order_history`

**Files modified:** `src/db/orders.py`, `src/bot/handlers/order_actions.py`, `tests/test_order_audit_trail.py`
**Commit:** 50e6fea
**Applied fix:** Added `record_order_history` calls for status and tracking updates, capturing old and new values and operator identity for conflict detection.

### WR-03: Status Suggestion Keyboard Back Button Misleadingly Triggers Cancellation

**Files modified:** `src/bot/keyboards.py`, `tests/test_status_suggestions.py`
**Commit:** 7227f1c
**Applied fix:** Renamed misleading `"⬅️ Quay lại thẻ đơn"` button label to `"❌ Huỷ bỏ"` in `build_mutation_status_keyboard` to accurately reflect the cancellation callback.

---

_Fixed: 2026-10-25T17:15:00Z_
_Fixer: Claude (gsd-code-fixer)_
_Iteration: 1_
