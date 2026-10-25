---
phase: 04-natural-language-order-search
verified: 2026-10-25T10:00:00Z
status: passed
score: 16/16 must-haves verified
covered_files:
  - .planning/phases/04-natural-language-order-search/04-01-PLAN.md
  - .planning/phases/04-natural-language-order-search/04-01-SUMMARY.md
  - .planning/phases/04-natural-language-order-search/04-02-PLAN.md
  - .planning/phases/04-natural-language-order-search/04-02-SUMMARY.md
  - .planning/phases/04-natural-language-order-search/04-03-PLAN.md
  - .planning/phases/04-natural-language-order-search/04-03-SUMMARY.md
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
covered_digest: "v2:sha256:0d72287cd27257a41e51ffa7c28d96c4fd6b09b05c00070fad524b0423e0870c"
behavior_unverified: 0
overrides_applied: 0
re_verification:
  previous_status: gaps_found
  previous_score: 15/16
  gaps_closed:
    - "CR-01: Order creation text containing customer phone numbers and casual inquiry phrases MUST NOT be falsely routed to search flow"
    - "WR-01: _get_active_db_context inspects app_context.settings"
    - "WR-02: BadRequest ('Message is not modified') suppressed in sch_bk"
    - "WR-03: Conversational search patterns use re.DOTALL for multiline queries"
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
  - finding: "Unhandled Telegram BadRequest on stale callback queries (>48h)"
    category: architectural
    reason: "Code review WARN-03 noted queries >48h could raise BadRequest. Standard Telegram bot pattern handled via logger."
    evidence_status: "none provided"
---

# Phase 04: Natural Language Order Search Verification Report

**Phase Goal:** Allow elderly store owners to search order history using natural language Vietnamese queries via Telegram with 2-phase confirmation and context preservation.
**Verified:** 2026-10-25T10:00:00Z
**Status:** passed
**Re-verification:** Yes — after gap closure 04-03, CR-01 fix, and UAT completion (8/8 passed)

## Goal Achievement

### User Flow Coverage (MVP Mode)

| User Step | Expected Outcome | Codebase Evidence | Status |
| --------- | ---------------- | ----------------- | ------ |
| 1. Bật bot / Xem Menu | Reply Keyboard 2x2 cố định có nút `[🔍 Tra cứu đơn]` thay thế nút Trợ giúp; lệnh `/help` đăng ký trợ giúp | `src/bot/keyboards.py:build_main_menu_reply_keyboard`, `src/bot/handlers/base.py:help_command`, `src/bot/app.py:66` | ✓ VERIFIED |
| 2. Kích hoạt tìm kiếm qua menu | Bấm `[🔍 Tra cứu đơn]` kích hoạt `search_state` 120s, gửi hướng dẫn kèm nút `[❌ Huỷ tra cứu]` | `src/bot/handlers/search.py:handle_search_menu_reply`, `build_search_prompt_keyboard`, `test_handle_search_menu_click` | ✓ VERIFIED |
| 3. Kích hoạt tìm kiếm qua free-text | Chat trực tiếp câu hỏi hoặc từ khoá tra cứu tự động chuyển sang luồng tra cứu mà không đòi SĐT như luồng nhập đơn; tin nhắn đơn hàng có SĐT không bị bắt nhầm | `src/bot/handlers/ingest.py:handle_text_order:186-199`, `src/services/order_search.py:is_search_intent`, `PHONE_PATTERN` guard | ✓ VERIFIED |
| 4. Text-to-SQL & Sanitization | LLM chuyển câu tiếng Việt thành câu lệnh SQLite SELECT có LIMIT 20, chặn mọi từ khoá DDL/DML và chấm phẩy đa câu lệnh, hỗ trợ unaccent tiếng Việt | `src/services/order_search.py:sanitize_and_validate_sql`, `src/db/connection.py:remove_accents`, `tests/test_order_search.py:test_sql_sanitizer_valid` | ✓ VERIFIED |
| 5. Khớp đúng 1 đơn hàng | Hiển thị thẻ xác nhận 2-phase confirmation *"Có phải bác muốn xem đơn này không?"* kèm nút `[👁️ Đúng rồi, xem chi tiết]` và `[🔍 Tìm câu khác]` | `src/bot/keyboards.py:render_search_single_order_card`, `build_search_single_order_keyboard`, `src/bot/handlers/search.py:171-179` | ✓ VERIFIED |
| 6. Khớp từ 2 đơn trở lên | Hiển thị danh sách phân trang 5 đơn/trang kèm các nút `[👁️ Xem đơn #ID]` và điều hướng `[◀️ Trang trước]` / `[Trang sau ▶️]` | `src/bot/keyboards.py:render_search_multi_card`, `build_search_multi_keyboard`, `src/bot/handlers/search.py:181-204` | ✓ VERIFIED |
| 7. Không tìm thấy đơn nào (0 đơn) | Hiển thị thông báo thân thiện kèm mẹo tìm kiếm và 2 nút `[🔍 Thử tìm lại]` / `[📝 Nhập đơn mới]` | `src/bot/keyboards.py:render_search_empty_card`, `build_search_empty_keyboard`, `src/bot/handlers/search.py:162-170` | ✓ VERIFIED |
| 8. Câu hỏi thống kê / tổng hợp | LLM tóm tắt kết quả scalar (`COUNT`, `SUM`, `AVG`) thành câu tiếng Việt ấm áp kèm nút `[🔍 Tìm câu khác]` | `src/services/order_search.py:summarize_aggregate_result`, `src/bot/handlers/search.py:148-158` | ✓ VERIFIED |
| 9. Xác nhận mở chi tiết đơn | Bấm `[👁️ Đúng rồi, xem chi tiết]` mở thẻ chi tiết đầy đủ của Phase 3 (Copy 1 chạm, đổi trạng thái) | `src/bot/handlers/search.py:358-395`, `test_search_view_order_detail_and_back_to_results` | ✓ VERIFIED |
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
| 13  | Clicking order detail from search results opens full detail card where '[⬅️ Quay lại]' returns to search results preserving context per D-12, D-13 | ✓ VERIFIED | `src/bot/handlers/search.py:358-395`, `sch_bk` handler: 287-337, `src/bot/keyboards.py:build_order_detail_keyboard`, tested in `test_search_view_order_detail_and_back_to_results` |
| 14  | search.py uses _get_active_db_context dynamic connection helper so process_search_query and handle_search_callback succeed when db is None in bot_data per G-04-3 | ✓ VERIFIED | `src/bot/handlers/search.py:29-35, 123-131, 370-375`, tested in `test_process_search_query_without_bot_data_db` and `test_handle_search_callback_detail_without_bot_data_db` |
| 15  | is_search_intent detects natural Vietnamese inquiry question patterns in addition to startswith prefix keywords per G-04-3 | ✓ VERIFIED | `src/services/order_search.py:26-43, 141-154`, `SEARCH_CONVERSATIONAL_PATTERNS`, tested in `test_is_search_intent_conversational_questions` |
| 16  | Order creation text containing customer phone numbers and casual inquiry phrases MUST NOT be falsely routed to search flow | ✓ VERIFIED | `PHONE_PATTERN = re.compile(r"(?:(?:\+84\|84\|0)[35789])\d{8}\b")` in `src/services/order_search.py:26, 150-151`. Verified via `test_is_search_intent_conversational_questions` (commit `e0a3ca9`). |

**Score:** 16/16 truths verified (0 present, behavior-unverified)

### Advisory (New Scope, Unevidenced)

| # | Finding | Category | Why Advisory |
|---|---------|----------|--------------|
| 1 | In-memory search cache unbounded growth risks memory leaks over long uptime | architectural | Non-blocking for single-user low-volume shop bot (<100 orders/day) |
| 2 | SQL sanitizer allows SQL comments (-- and /* */) | security | Single-statement SELECT check and token-level forbidden keywords block injection; no failing test |
| 3 | Unhandled Telegram BadRequest on stale callback queries (>48h) | architectural | Standard Telegram bot pattern handled via logger |

### Required Artifacts

| Artifact | Expected | Status | Details |
| -------- | -------- | ------ | ------- |
| `src/services/order_search.py` | Text-to-SQL, sanitization, 1-shot retry, classification, summary, intent detection with phone guard | ✓ VERIFIED | Substantive (393 lines), `is_search_intent` guarded with `PHONE_PATTERN` |
| `src/db/connection.py` | Custom SQLite `unaccent` function | ✓ VERIFIED | `remove_accents` registered via `db.create_function` on connection initialization |
| `src/bot/handlers/search.py` | Dynamic DB context manager inspecting `app_context.settings`, search execution, card rendering, typing action, callback routing, BadRequest suppression | ✓ VERIFIED | Substantive (400 lines), wired to `app.py` for `sch_` callbacks, respects `app_context.settings` |
| `src/bot/keyboards.py` | Search cards and inline keyboards, updated Reply Keyboard 2x2 | ✓ VERIFIED | Renders single, multi, empty cards; custom `back_callback_data` supported |
| `src/bot/handlers/ingest.py` | Dual-routing intercept for search intents and active search states | ✓ VERIFIED | Evaluates `search_state` and `is_search_intent` before LLM order extraction |
| `src/bot/app.py` | Registered `/help`, `[🔍 Tra cứu đơn]`, and `sch_` callback handlers | ✓ VERIFIED | Registered at group 0, tested via end-to-end integration test suite |

### Key Link Verification

| From | To | Via | Status | Details |
| ---- | -- | --- | ------ | ------- |
| `src/bot/handlers/search.py` | `src/db/connection.py` | `_get_active_db_context` calls `get_db_connection` | ✓ WIRED | Dynamically resolves DB connection inspecting `app_context.settings` |
| `src/bot/handlers/ingest.py` | `src/bot/handlers/search.py` | `is_search_intent(text)` routes to `process_search_query` | ✓ WIRED | Guarded by `PHONE_PATTERN` so valid orders are not intercepted |
| `src/bot/handlers/search.py` | `src/services/order_search.py` | `run_order_search` calls `execute_natural_language_search` | ✓ WIRED | Executes Text-to-SQL and hydrates results |
| `src/bot/handlers/search.py` | `src/bot/keyboards.py` | Renders cards and inline keyboards | ✓ WIRED | Full 2-phase confirmation and multi-order pagination cards rendered |
| `src/bot/handlers/search.py` | `src/db/orders.py` | `get_order_by_id` in `sch_v` callback | ✓ WIRED | Opens Phase 3 detail view with custom back button `sch_bk:{search_id}` |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
| -------- | ------- | ------ | ------ |
| Conversational search query detected | `python -c "from src.services.order_search import is_search_intent; assert is_search_intent('a Biên đã mua băng bao giờ chưa nhỉ?') is True"` | `True` | ✓ PASS |
| Order draft with phone number and question note NOT flagged as search | `python -c "from src.services.order_search import is_search_intent; assert is_search_intent('Khách mua 2 cuốn Tuấn Vũ (hỏi xem có chưa nhỉ) gửi 123 Lê Lợi 0903123456') is False"` | `False` | ✓ PASS |
| Search query with explicit prefix and phone number preserved | `python -c "from src.services.order_search import is_search_intent; assert is_search_intent('tìm đơn số 0903123456 xem mua gì chưa nhỉ') is True"` | `True` | ✓ PASS |
| SQL sanitizer enforces SELECT and LIMIT 20 | `python -c "from src.services.order_search import sanitize_and_validate_sql; res = sanitize_and_validate_sql('SELECT * FROM orders WHERE customer_name = \"Tuấn\"'); assert 'LIMIT 20' in res"` | `SELECT * FROM orders WHERE customer_name = "Tuấn" LIMIT 20` | ✓ PASS |
| Unaccent function registered in SQLite | `pytest tests/test_order_search.py -k test_unaccent_sqlite -q` | `1 passed in 0.03s` | ✓ PASS |
| Entire test suite (all unit and integration tests) | `pytest` | `110 passed in 1.83s` | ✓ PASS |

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
| ----------- | ---------- | ----------- | ------ | -------- |
| SEARCH-01 | 04-01, 04-02, 04-03 | Tra cứu/tìm kiếm đơn hàng bằng ngôn ngữ tự nhiên thông qua tin nhắn chat tự do | ✓ SATISFIED | Text-to-SQL engine, Reply Keyboard search button, conversational Vietnamese intent detection with phone exclusion guard |
| SEARCH-02 | 04-01, 04-02, 04-03 | LLM truy vấn tìm kiếm đơn hàng phù hợp trong DB; gửi lại thẻ xác nhận "Có phải bạn muốn xem đơn này không?" kèm nút xác nhận | ✓ SATISFIED | 2-phase confirmation cards, detail navigation, context preservation, aggregate summary, UAT 8/8 passed |

### Anti-Patterns Found

None blocking. Previous blockers CR-01, WR-01, WR-02, WR-03 all resolved:
- CR-01 resolved in commit `e0a3ca9` with `PHONE_PATTERN` guard.
- WR-01 resolved in commit `74fcb2e` checking `app_context.settings`.
- WR-02 resolved in commit `8c615b1` suppressing `BadRequest("Message is not modified")` in `sch_bk`.
- WR-03 resolved in commit `1646347` adding `re.DOTALL` to multiline regex patterns.

### UAT Execution Results

All 8 conversational and functional UAT scenarios from `04-UAT.md` passed:
1. Cold Start Smoke Test: `pass`
2. 2x2 Reply Keyboard & /help Registration: `pass`
3. Natural Language Single Order Search with 2-Phase Confirmation: `pass`
4. Context-Preserving Detail Navigation: `pass`
5. Multi-Order Paginated Search Results: `pass`
6. Statistical Aggregate Search & LLM Summary: `pass`
7. Accent-Insensitive (Unaccent) Search: `pass`
8. Empty Search Handling: `pass`

---

_Verified: 2026-10-25T10:00:00Z_
_Verifier: Claude (gsd-verifier)_
