---
phase: 04-natural-language-order-search
plan: 02
status: complete
subsystem: telegram-search-ui
tags: [telegram-ui, search, 2-phase-confirmation, context-preserving-navigation, dual-routing]
requires:
  - Plan 04-01: Text-to-SQL core service and sanitizer
  - Phase 03: Order detail card and 1-tap copy buttons
affects: []
tech-stack:
  added: []
  patterns:
    - 2x2 persistent Reply Keyboard with [🔍 Tra cứu đơn] and /help command registration
    - Dual-routing ingestion (search_state active or search_intent prefix keyword)
    - 2-phase confirmation card with [👁️ Đúng rồi, xem chi tiết] and [🔍 Tìm câu khác]
    - 5-orders-per-page paginated multi-order search result list
    - Context-preserving back navigation restoring saved search snapshot without DB re-query
    - Background ChatAction.TYPING heartbeat during search execution
key-files:
  created:
    - src/bot/handlers/search.py
  modified:
    - src/bot/keyboards.py
    - src/bot/handlers/base.py
    - src/bot/handlers/ingest.py
    - src/bot/handlers/orders.py
    - src/bot/app.py
    - tests/test_orders_ui.py
    - tests/test_order_search.py
    - .planning/REQUIREMENTS.md
decisions:
  - "D-01: Update Reply Keyboard to 2x2 layout containing [🔍 Tra cứu đơn], moving help to /help command"
  - "D-02: Support dual-trigger routing (active search_state or search_intent prefix keywords like 'tìm...', 'tra cứu...')"
  - "D-03: Set 120s TTL on search_state with prompt keyboard containing [❌ Huỷ tra cứu]"
  - "D-08 / SEARCH-02: Implement 2-phase confirmation modal for single order match before displaying sensitive details"
  - "D-09: Paginate multi-order search results (5 orders per page) with [👁️ Xem đơn #ID] buttons"
  - "D-10: Display friendly empty search card with tips, [🔍 Thử tìm lại], and [📝 Nhập đơn mới]"
  - "D-11: Periodically send ChatAction.TYPING in background task during search execution"
  - "D-12 & D-13: Reuse full Phase 3 detail card with custom back_callback_data returning to search result snapshot"
metrics:
  duration: 6m
  completed_date: "2026-10-25"
actuals:
  tokens: 52000
  tasks: 3
  commits: 3
plan_head_before: 425e699f12dadf1087c3409a2f5c5233b574a76b
plan_head_after: 58e75eb255cdd1b96a3b4bc11345772cd59e80b6
---

# Phase 04 Plan 02: Telegram Search UI, Confirmation Workflow, and Navigation Summary

Built complete Telegram search interface, 2x2 Reply Keyboard update, dual-routing text ingestion, 2-phase confirmation cards, paginated multi-order views, and context-preserving back navigation.

## Key Changes

1. **Persistent 2x2 Reply Keyboard & /help (`src/bot/keyboards.py`, `src/bot/handlers/base.py`, `src/bot/app.py`)**:
   - Replaced `[❓ Trợ giúp]` button on 2x2 Reply Keyboard with `[🔍 Tra cứu đơn]` per D-01.
   - Registered `/help` CommandHandler providing bot usage guide per D-01.
   - Updated menu regex in `app.py` and routed `[🔍 Tra cứu đơn]` to `handle_search_menu_reply`.

2. **Search UI Components & Card Renderers (`src/bot/keyboards.py`)**:
   - `render_search_single_order_card`: Displays `#ID`, customer name, mono phone, items, total, and prompt question *"Có phải bác muốn xem đơn này không?"* per D-08.
   - `build_search_single_order_keyboard`: Rows with `[👁️ Đúng rồi, xem chi tiết]` (`sch_v:{search_id}:{order_id}`) and `[🔍 Tìm câu khác]` (`sch_new`).
   - `render_search_empty_card` & `build_search_empty_keyboard`: Friendly message *"Dạ em tìm trong sổ không thấy đơn nào như bác tả rồi!"* with search tips and `[🔍 Thử tìm lại]` / `[📝 Nhập đơn mới]` buttons per D-10.
   - `render_search_multi_card` & `build_search_multi_keyboard`: 5-orders-per-page paginated view with `[👁️ Xem đơn #ID]` and pagination navigation per D-09.
   - `build_order_detail_keyboard`: Updated to accept custom `back_callback_data` (e.g. `sch_bk:{search_id}`) preserving search context per D-13.

3. **Search Handler & Dual-Routing (`src/bot/handlers/search.py`, `src/bot/handlers/ingest.py`, `src/bot/app.py`)**:
   - `run_with_typing`: Background loop sending `ChatAction.TYPING` every 4s while LLM / SQLite search executes per D-11.
   - `handle_search_menu_reply`: Sets `search_state` with 120s expiry and displays prompt with `[❌ Huỷ tra cứu]` per D-03.
   - `handle_search_cancel_callback`: Clears `search_state` and acknowledges cancelation.
   - `process_search_query`: Dispatches search query to `run_order_search`, stores snapshot in `context.user_data["searches"]`, and routes to single confirmation card, multi-order list, empty card, or aggregate summary per D-07, D-08, D-09, D-10.
   - `handle_text_order` in `ingest.py`: Intercepts messages if `search_state` is active or if text matches `is_search_intent` ("tìm...", "tra cứu..."), routing directly to search without requiring phone numbers per D-02.
   - `handle_search_callback`: Handles `sch_new`, `sch_pg`, `sch_v`, `sch_bk`, and `sch_cancel` callbacks.

4. **Context-Preserving Navigation (`src/bot/handlers/search.py`, `src/bot/keyboards.py`)**:
   - Tapping `[👁️ Đúng rồi, xem chi tiết]` opens full Phase 3 detail card with 1-tap copy and status actions, with `[⬅️ Quay lại]` pointing to `sch_bk:{search_id}` per D-12, D-13.
   - Tapping `[⬅️ Quay lại]` from detail view restores the saved search snapshot (single card or exact multi-order page) without re-querying the database.

## Deviations from Plan

None - plan executed exactly as written.

## Self-Check: PASSED

1. Created/modified files exist:
   - `src/bot/handlers/search.py`: FOUND
   - `src/bot/keyboards.py`: FOUND
   - `src/bot/handlers/base.py`: FOUND
   - `src/bot/handlers/ingest.py`: FOUND
   - `src/bot/handlers/orders.py`: FOUND
   - `src/bot/app.py`: FOUND
   - `tests/test_order_search.py`: FOUND
   - `tests/test_orders_ui.py`: FOUND
   - `.planning/phases/04-natural-language-order-search/04-02-SUMMARY.md`: FOUND
2. Commits exist in history:
   - `b56b797`: FOUND (Task 1 tracer)
   - `f05c7f7`: FOUND (Task 2 search trigger & routing)
   - `58e75eb`: FOUND (Task 3 context-preserving detail navigation)
3. Full test suite: 107 tests passing cleanly across the entire repository.
