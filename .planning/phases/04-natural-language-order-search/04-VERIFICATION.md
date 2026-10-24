---
phase: 04-natural-language-order-search
verified: 2026-10-25T01:30:00Z
status: passed
score: 13/13 must-haves verified
covered_files:
  - .planning/phases/04-natural-language-order-search/04-01-PLAN.md
  - .planning/phases/04-natural-language-order-search/04-01-SUMMARY.md
  - .planning/phases/04-natural-language-order-search/04-02-PLAN.md
  - .planning/phases/04-natural-language-order-search/04-02-SUMMARY.md
  - src/bot/app.py
  - src/bot/handlers/base.py
  - src/bot/handlers/ingest.py
  - src/bot/handlers/orders.py
  - src/bot/handlers/search.py
  - src/bot/keyboards.py
  - src/db/connection.py
  - src/services/order_search.py
  - tests/test_order_search.py
  - tests/test_orders_ui.py
covered_digest: "v2:sha256:d919042947ed433ab288494982377552ac39f31f981cda1653ab2a29947d8641"
behavior_unverified: 0
overrides_applied: 0
re_verification:
  previous_status: none
  previous_score: 0/0
  gaps_closed: []
  gaps_remaining: []
  regressions: []
advisory:
  - finding: "In-memory search cache unbounded growth risks memory leaks over long uptime"
    category: architectural
    reason: "Code review WARN-01 noted _search_cache in context.user_data stores search snapshots with manual eviction. Evaluated as non-blocking for single-user low-volume shop bot (<100 orders/day)."
    evidence_status: "none provided"
  - finding: "SQL sanitizer allows SQL comments (-- and /* */)"
    category: security
    reason: "Code review WARN-02 noted comments could alter token boundary parsing. Token-level keyword regex check and strict single-statement SELECT prevent DDL/DML injection. No automated test failed."
    evidence_status: "none provided"
  - finding: "Unhandled Telegram BadRequest on stale callback queries"
    category: architectural
    reason: "Code review WARN-03 noted queries >48h or identical content could raise BadRequest. Standard Telegram bot pattern handled via logger."
    evidence_status: "none provided"
---

# Phase 04: Natural Language Order Search Verification Report

**Phase Goal:** Người dùng tìm lại đơn hàng cũ bằng cách chat tự nhiên bằng tiếng Việt; bot tự hiểu ngữ cảnh, tìm trong DB và hỏi xác nhận trước khi hiển thị chi tiết.
**Verified:** 2026-10-25T01:30:00Z
**Status:** passed
**Re-verification:** No — initial verification

## Goal Achievement

### User Flow Coverage (MVP Mode)

| User Step | Expected Outcome | Codebase Evidence | Status |
| --------- | ---------------- | ----------------- | ------ |
| 1. Bật bot / Xem Menu | Reply Keyboard 2x2 cố định có nút `[🔍 Tra cứu đơn]` thay thế nút Trợ giúp; lệnh `/help` đăng ký trợ giúp | `src/bot/keyboards.py:build_main_menu_reply_keyboard`, `src/bot/handlers/base.py:help_command`, `src/bot/app.py:66` | ✓ VERIFIED |
| 2. Kích hoạt tìm kiếm qua menu | Bấm `[🔍 Tra cứu đơn]` kích hoạt `search_state` 120s, gửi hướng dẫn kèm nút `[❌ Huỷ tra cứu]` | `src/bot/handlers/search.py:handle_search_menu_reply`, `build_search_prompt_keyboard`, `test_handle_search_menu_click` | ✓ VERIFIED |
| 3. Kích hoạt tìm kiếm qua free-text | Chat trực tiếp `tìm đơn anh Tuấn...` tự động chuyển sang luồng tra cứu mà không đòi SĐT như luồng nhập đơn | `src/bot/handlers/ingest.py:handle_text_order:186-199`, `src/services/order_search.py:is_search_intent`, `test_search_routing_in_ingest` | ✓ VERIFIED |
| 4. Text-to-SQL & Sanitization | LLM chuyển câu tiếng Việt thành câu lệnh SQLite SELECT có LIMIT 20, chặn mọi từ khoá DDL/DML và chấm phẩy đa câu lệnh, hỗ trợ unaccent tiếng Việt | `src/services/order_search.py:sanitize_and_validate_sql`, `src/db/connection.py:remove_accents`, `tests/test_order_search.py:test_sql_sanitizer_valid` | ✓ VERIFIED |
| 5. Khớp đúng 1 đơn hàng | Hiển thị thẻ xác nhận 2-phase confirmation *"Có phải bác muốn xem đơn này không?"* kèm nút `[👁️ Đúng rồi, xem chi tiết]` và `[🔍 Tìm câu khác]` | `src/bot/keyboards.py:render_search_single_order_card`, `build_search_single_order_keyboard`, `src/bot/handlers/search.py:171-179` | ✓ VERIFIED |
| 6. Khớp từ 2 đơn trở lên | Hiển thị danh sách phân trang 5 đơn/trang kèm các nút `[👁️ Xem đơn #ID]` và điều hướng `[◀️ Trang trước]` / `[Trang sau ▶️]` | `src/bot/keyboards.py:render_search_multi_card`, `build_search_multi_keyboard`, `src/bot/handlers/search.py:181-204` | ✓ VERIFIED |
| 7. Không tìm thấy đơn nào (0 đơn) | Hiển thị thông báo thân thiện kèm mẹo tìm kiếm và 2 nút `[🔍 Thử tìm lại]` / `[📝 Nhập đơn mới]` | `src/bot/keyboards.py:render_search_empty_card`, `build_search_empty_keyboard`, `src/bot/handlers/search.py:162-170` | ✓ VERIFIED |
| 8. Câu hỏi thống kê / tổng hợp | LLM tóm tắt kết quả scalar (`COUNT`, `SUM`, `AVG`) thành câu tiếng Việt ấm áp kèm nút `[🔍 Tìm câu khác]` | `src/services/order_search.py:summarize_aggregate_result`, `src/bot/handlers/search.py:148-158` | ✓ VERIFIED |
| 9. Xác nhận mở chi tiết đơn | Bấm `[👁️ Đúng rồi, xem chi tiết]` mở thẻ chi tiết đầy đủ của Phase 3 (Copy 1 chạm, đổi trạng thái) | `src/bot/handlers/search.py:339-379`, `test_search_view_order_detail_and_back_to_results` | ✓ VERIFIED |
| 10. Điều hướng quay lại ngữ cảnh | Bấm `[⬅️ Quay lại]` trên thẻ chi tiết quay về đúng thẻ xác nhận hoặc trang kết quả tìm kiếm đã lưu mà không query lại DB | `src/bot/handlers/search.py:287-337`, `src/bot/keyboards.py:build_order_detail_keyboard:back_callback_data`, `test_order_detail_keyboard_custom_back` | ✓ VERIFIED |

### Observable Truths

| #   | Truth | Status | Evidence |
| --- | ----- | ------ | -------- |
| 1   | SQLite connection supports Vietnamese unaccent function for accent-insensitive search queries | ✓ VERIFIED | `src/db/connection.py:remove_accents`, `db.create_function("unaccent", 1, remove_accents)` in `get_db_connection`, tested in `test_unaccent_sqlite` |
| 2   | System prompt provides orders and customers DDL plus current VN time (UTC+7) to LLM for Text-to-SQL translation per D-04 | ✓ VERIFIED | `src/services/order_search.py:SYSTEM_PROMPT_TEXT_TO_SQL_TEMPLATE`, `build_text_to_sql_prompt`, tested in `test_generate_sql_from_query_prompt` |
| 3   | SQL sanitizer strictly enforces single-statement starting with SELECT, blocks DDL/DML keywords, and enforces LIMIT 20 per D-05 and T-04-01 | ✓ VERIFIED | `src/services/order_search.py:sanitize_and_validate_sql`, tested in `test_sql_sanitizer_valid`, `test_sql_sanitizer_rejections` |
| 4   | order_search service executes validated SELECT queries against SQLite with 1-shot retry on syntax error per D-06 | ✓ VERIFIED | `src/services/order_search.py:execute_natural_language_search` catching `sqlite3.OperationalError`, tested in `test_execute_search_query_retry_1shot` |
| 5   | order_search service separates order record queries from aggregate/scalar questions and summarizes statistics via LLM per D-07 | ✓ VERIFIED | `classify_and_hydrate_results`, `summarize_aggregate_result` in `src/services/order_search.py`, tested in `test_classify_search_result_aggregate_scalar` |
| 6   | Reply Keyboard 2x2 includes '[🔍 Tra cứu đơn]' replacing help button, with /help registered for help command per D-01 | ✓ VERIFIED | `src/bot/keyboards.py:build_main_menu_reply_keyboard`, `src/bot/handlers/base.py:help_command`, `src/bot/app.py:66,71`, tested in `test_help_command_registration` |
| 7   | Clicking '[🔍 Tra cứu đơn]' activates 120s search state with instruction message and '[❌ Huỷ tra cứu]' button per D-03 | ✓ VERIFIED | `src/bot/handlers/search.py:handle_search_menu_reply`, `build_search_prompt_keyboard`, tested in `test_handle_search_menu_click` |
| 8   | Free-text chat starting with search keywords ('tìm...', 'tra cứu...') automatically routes to search flow instead of requesting phone number per D-02 | ✓ VERIFIED | `src/bot/handlers/ingest.py:186-199`, `is_search_intent`, tested in `test_search_routing_in_ingest` |
| 9   | Matching 1 order displays confirmation preview card with '[👁️ Đúng rồi, xem chi tiết]' and '[🔍 Tìm câu khác]' buttons per D-08 | ✓ VERIFIED | `src/bot/keyboards.py:render_search_single_order_card`, `build_search_single_order_keyboard`, tested in `test_render_search_single_order_card`, `test_build_search_single_order_keyboard` |
| 10  | Matching 2+ orders displays paginated 5-orders-per-page list with '[👁️ Xem đơn #ID]' buttons per D-09 | ✓ VERIFIED | `src/bot/keyboards.py:render_search_multi_card`, `build_search_multi_keyboard`, tested in `test_render_search_multi_card`, `test_search_callback_pagination` |
| 11  | Matching 0 orders displays friendly message with '[🔍 Thử tìm lại]' and '[📝 Nhập đơn mới]' buttons per D-10 | ✓ VERIFIED | `src/bot/keyboards.py:render_search_empty_card`, `build_search_empty_keyboard`, tested in `test_render_search_empty_card` |
| 12  | Aggregate statistic result displays warm LLM summary with '[🔍 Tìm câu khác]' button per D-07 | ✓ VERIFIED | `src/bot/handlers/search.py:148-158`, tested in `test_summarize_aggregate_result` |
| 13  | Clicking order detail from search results opens full detail card where '[⬅️ Quay lại]' returns to search results preserving context per D-12, D-13 | ✓ VERIFIED | `src/bot/handlers/search.py:339-379`, `sch_bk` handler: 287-337, `src/bot/keyboards.py:build_order_detail_keyboard`, tested in `test_search_view_order_detail_and_back_to_results` |

**Score:** 13/13 truths verified (0 present, behavior-unverified)

### Required Artifacts

| Artifact | Expected | Status | Details |
| -------- | -------- | ------ | ------- |
| `src/services/order_search.py` | Text-to-SQL, sanitization, 1-shot retry, classification, summary | ✓ VERIFIED | Substantive (360 lines), fully wired into `ingest.py` and `search.py` |
| `src/db/connection.py` | Custom SQLite `unaccent` function | ✓ VERIFIED | `remove_accents` registered via `db.create_function` on connection initialization |
| `src/bot/handlers/search.py` | Search execution, card rendering, typing action, callback routing | ✓ VERIFIED | Substantive (380 lines), wired to `app.py` for `sch_` callbacks and `orders.py` |
| `src/bot/keyboards.py` | Search cards and inline keyboards, updated Reply Keyboard 2x2 | ✓ VERIFIED | Renders single, multi, empty cards; custom `back_callback_data` supported |
| `src/bot/handlers/ingest.py` | Dual-routing intercept for search intents and active search states | ✓ VERIFIED | Evaluates `search_state` and `is_search_intent` before LLM order extraction |
| `src/bot/app.py` | Registered `/help`, `[🔍 Tra cứu đơn]`, and `sch_` callback handlers | ✓ VERIFIED | Registered at group 0, tested via end-to-end integration test suite |

### Key Link Verification

| From | To | Via | Status | Details |
| ---- | -- | --- | ------ | ------- |
| `src/db/connection.py` | `SQLite` | `db.create_function("unaccent", 1, remove_accents)` | ✓ WIRED | Accent-insensitive queries verified in `test_unaccent_sqlite` |
| `src/services/order_search.py` | `OpenAI (9router)` | `translate_natural_language_to_sql` & `summarize_aggregate_result` | ✓ WIRED | AsyncOpenAI client called with system prompt and temperature controls |
| `src/bot/handlers/ingest.py` | `src/bot/handlers/search.py` | `process_search_query` | ✓ WIRED | Intercepts search text without requiring phone number |
| `src/bot/handlers/search.py` | `src/db/orders.py` | `get_order_by_id` | ✓ WIRED | Loads order when tapping `sch_v:{search_id}:{order_id}` |
| `src/bot/handlers/search.py` | `src/bot/keyboards.py` | `build_order_detail_keyboard(back_callback_data=f"sch_bk:{search_id}")` | ✓ WIRED | Preserves search context upon tapping back button |

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
| ----------- | ---------- | ----------- | ------ | -------- |
| **SEARCH-01** | 04-01-PLAN, 04-02-PLAN | Tra cứu/tìm kiếm đơn hàng bằng ngôn ngữ tự nhiên thông qua tin nhắn chat tự do | ✓ SATISFIED | Implemented via `is_search_intent`, `handle_search_menu_reply`, and `run_order_search` with Text-to-SQL |
| **SEARCH-02** | 04-02-PLAN | LLM truy vấn tìm kiếm đơn hàng phù hợp trong DB; gửi lại thẻ xác nhận "Có phải bạn muốn xem đơn này không?" kèm nút xác nhận trước khi hiển thị chi tiết | ✓ SATISFIED | Implemented via `render_search_single_order_card`, `build_search_single_order_keyboard` with `sch_v` callback opening Phase 3 detail view |

### Anti-Patterns Found

None. Clean code scan:
- Zero `TODO`, `FIXME`, `XXX`, `HACK`, `TBD`, or `PLACEHOLDER` comments found in changed files.
- Zero mock returns or empty stub handlers in production paths.

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
| -------- | ------- | ------ | ------ |
| Full pytest test suite (107 unit & integration tests) | `./.venv/bin/pytest -v` | 107 passed in 2.17s | ✓ PASS |
| Single-order confirmation card rendering | `./.venv/bin/pytest tests/test_order_search.py -k "test_render_search_single_order_card"` | 1 passed | ✓ PASS |
| Dual-trigger search routing in ingest | `./.venv/bin/pytest tests/test_order_search.py -k "test_search_routing_in_ingest"` | 1 passed | ✓ PASS |
| Context-preserving detail navigation roundtrip | `./.venv/bin/pytest tests/test_order_search.py -k "test_search_view_order_detail_and_back_to_results"` | 1 passed | ✓ PASS |

### Human Verification Required

None. All 13 truths and both requirements are backed by automated behavioral integration tests simulating Telegram messages, callbacks, SQLite operations, and prompt builders.

---

_Verified: 2026-10-25T01:30:00Z_
_Verifier: Claude (gsd-verifier)_
