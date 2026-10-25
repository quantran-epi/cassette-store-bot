---
phase: 04-natural-language-order-search
plan: 03
subsystem: bot-search
tags:
  - natural-language-search
  - sqlite
  - telegram-bot
  - intent-classification
dependency_graph:
  requires:
    - 04-01
    - 04-02
  provides:
    - dynamic-db-search-handlers
    - conversational-search-intent
  affects:
    - src/bot/handlers/search.py
    - src/services/order_search.py
    - tests/test_order_search.py
tech_stack:
  added: []
  patterns:
    - dynamic DB context resolution fallback with get_db_connection
    - conversational regex matching for Vietnamese inquiry sentences
key_files:
  created: []
  modified:
    - src/bot/handlers/search.py
    - src/services/order_search.py
    - tests/test_order_search.py
decisions:
  - "Adopt _get_active_db_context in search.py matching orders.py and callbacks.py to safely resolve SQLite connection when bot_data['db'] is None"
  - "Broaden is_search_intent with SEARCH_CONVERSATIONAL_PATTERNS to capture questions with 'đã mua...chưa nhỉ', 'mấy đơn', 'có mua...không' without interfering with phone number order drafts"
metrics:
  duration: 4m
  completed_date: "2026-10-25"
status: complete
actuals:
  tokens: 3766
  tasks: 2
  commits: 2
  plan_head_before: 59edd1dcc7e78aa7053b3c97c5d239556b50d9d8
  plan_head_after: 25532e2a60037e775133fb8050f468e690dbf9fd
---

# Phase 04 Plan 03: Gap Closure for Natural Language Order Search (G-04-3) Summary

Dynamic SQLite connection resolution for search handlers and broadened natural language search intent classification for conversational Vietnamese inquiry questions.

## Key Changes

1. **Dynamic SQLite Connection Helper in `search.py`:**
   - Implemented `_get_active_db_context(context)` matching pattern from `orders.py` and `callbacks.py` (`nullcontext(db) if db else get_db_connection(db_path)`).
   - Updated `process_search_query` to acquire DB dynamically, eliminating crashes when `bot_data["db"]` is `None`.
   - Updated `handle_search_callback` under `sch_v` to dynamically acquire connection for order detail view.

2. **Broadened Intent Detection in `order_search.py`:**
   - Added `SEARCH_CONVERSATIONAL_PATTERNS` to catch Vietnamese questions asking about prior purchases, order counts, and inquiry suffixes (`bao giờ chưa`, `chưa nhỉ`, `mấy đơn`, `có mua...không`).
   - Kept order ingestion intact for structured order drafts with phone numbers.

3. **Comprehensive Unit & Regression Tests:**
   - Added `test_is_search_intent_conversational_questions` verifying positive and negative conversational phrases.
   - Added `test_process_search_query_without_bot_data_db` and `test_handle_search_callback_detail_without_bot_data_db` verifying end-to-end execution with `bot_data["db"] = None`.

## Deviations from Plan

None - plan executed exactly as written.

## Verification Results

- Unit & integration tests in `tests/test_order_search.py`: 26 passed.
- Full UI tests in `tests/test_orders_ui.py`: 20 passed.
- Full project test suite: 110 passed in 1.78s.

## Self-Check: PASSED
- FOUND: src/bot/handlers/search.py
- FOUND: src/services/order_search.py
- FOUND: tests/test_order_search.py
- FOUND: commit 2ebe829
- FOUND: commit 25532e2
