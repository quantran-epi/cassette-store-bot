---
phase: 07-natural-language-order-mutation-pipeline
plan: 03
subsystem: order-mutation
tags: [gap-closure, optimistic-lock, timestamp-normalization, json-extraction, disambiguation-search]
requires:
  - Phase 07 Plan 01 (3-way intent router, order snapshot, audit trail)
  - Phase 07 Plan 02 (visual diff card, optimistic locking callback flow)
provides:
  - Millisecond-normalized timestamp optimistic locking in mutate_order_with_lock
  - Regex-isolated JSON parser resilient against trailing 9router chatter
  - Prefix-stripped conversational keyword matching for disambiguation order queries
affects:
  - src/db/orders.py
  - src/services/mutation_extractor.py
tech-stack:
  added: []
  patterns:
    - Fractional second normalization to 3 decimal digits for cross-runtime SQLite timestamp comparisons
    - Outermost regex `{...}` isolation over markdown fences
    - Conversational prefix peeling for Vietnamese natural language queries
key-files:
  created: []
  modified:
    - src/db/orders.py
    - src/services/mutation_extractor.py
    - tests/test_mutation_card_and_lock.py
    - tests/test_mutation_extractor.py
decisions:
  - Truncate and normalize fractional seconds to 3-digit millisecond string before comparing updated_at in optimistic locking.
  - Strip leading conversational prefixes ('khách', 'đơn', 'của', 'cho', 'giao') and query `unaccent(customer_name) LIKE ? OR customer_phone LIKE ?` to prevent false positive address matches.
  - Isolate JSON object block using `re.search(r"\{[\s\S]*\}", cleaned)` to eliminate trailing commentary chatter from LLM.
metrics:
  duration: 6m
  completed_date: "2026-10-25"
---

# Phase 07 Plan 03: Gap Closure for Order Mutation Pipeline Summary

Closed UAT gaps in Phase 7 Natural Language Order Mutation Pipeline: resolved false-positive optimistic lock conflicts on consecutive order edits, handled trailing commentary text in LLM JSON extraction, and enabled resilient disambiguation search when queries contain conversational prefixes.

## Key Changes

1. **Optimistic Locking Timestamp Normalization (`src/db/orders.py`)**:
   - Added `_normalize_ts` helper standardizing timestamps to 3-decimal millisecond format (`YYYY-MM-DD HH:MM:SS.mmm`).
   - Fixed comparison mismatch between SQLite's 3-digit millisecond string and Python `datetime`'s 6-digit microsecond string.
   - Consecutive mutations on the same order now succeed deterministically.

2. **Resilient JSON Markdown Chatter Stripping (`src/services/mutation_extractor.py`)**:
   - Upgraded `_clean_json_markdown` to strip code block fences and isolate the outermost JSON block `{...}` via `re.search(r"\{[\s\S]*\}", cleaned)`.
   - Updated `MUTATION_SYSTEM_PROMPT` to instruct LLM to exclude conversational prefixes (`khách`, `đơn`, `của`, `anh`, `chị`, `bác`) from `target_customer_keyword`.

3. **Conversational Prefix Stripping in Order Search (`src/db/orders.py`)**:
   - Enhanced `find_orders_for_mutation` to strip conversational prefixes (`khách`, `đơn`, `của`, `cho`, `giao`).
   - Targeted query to `unaccent(customer_name) LIKE ? OR customer_phone LIKE ?`, preventing false-positive substring matches on address names (e.g. 'Hải Phòng' matching 'Hà').

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Address field matching substring 'ha' from 'anh Hà' in 'Hải Phòng'**
- **Found during:** Task 2 verification
- **Issue:** Querying `shipping_address LIKE '%ha%'` caused order for customer 'Bác Ba' residing at 'Hải Phòng' to match when searching for 'anh Hà'.
- **Fix:** Confined `keyword` search in `find_orders_for_mutation` to `customer_name` and `customer_phone`.
- **Files modified:** `src/db/orders.py`
- **Commit:** `ebbe911`

## Verification

All 40 Phase 7 tests and all 223 project tests pass:
```bash
./.venv/bin/pytest tests/test_mutation_card_and_lock.py tests/test_mutation_extractor.py tests/test_intent_router.py tests/test_order_audit_trail.py tests/test_mutation_handler_flow.py -v
./.venv/bin/pytest -v
```

## Self-Check: PASSED
- `src/db/orders.py`: FOUND
- `src/services/mutation_extractor.py`: FOUND
- Commit `197c866`: FOUND
- Commit `ebbe911`: FOUND
