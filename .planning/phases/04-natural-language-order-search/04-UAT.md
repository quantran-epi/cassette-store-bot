---
status: diagnosed
phase: 04-natural-language-order-search
source:
  - .planning/phases/04-natural-language-order-search/04-01-SUMMARY.md
  - .planning/phases/04-natural-language-order-search/04-02-SUMMARY.md
started: "2026-10-25T01:30:00Z"
updated: "2026-10-25T01:45:00Z"
---

## Current Test

[testing paused — 5 items outstanding]

## Tests

### 1. Cold Start Smoke Test
expected: Kill any running server/service. Start bot application or run test suite from scratch. All handlers, SQLite connection with `unaccent` custom function, and Telegram app initialize without error.
result: pass

### 2. 2x2 Reply Keyboard & /help Registration
expected: Sending /start shows the updated 2x2 Reply Keyboard with [🔍 Tra cứu đơn] in place of [❓ Trợ giúp]. Tapping [🔍 Tra cứu đơn] prompts the user to enter search query with [❌ Huỷ tra cứu] button (120s TTL). Sending /help displays the full bot usage guide.
result: pass

### 3. Natural Language Single Order Search with 2-Phase Confirmation
expected: Sending a search query matching a single order (e.g., "tìm đơn anh Tuấn mua cassette" or tapping [🔍 Tra cứu đơn] then typing "đơn giao cho chị Lan") displays a 2-phase confirmation snippet card showing customer name, phone, items, total, and buttons: [👁️ Đúng rồi, xem chi tiết] and [🔍 Tìm câu khác]. Sensitive order actions remain hidden until confirmed.
result: issue
reported: "bấm Tra cứu, hỏi a Biên đã mua băng bao giờ chưa nhỉ? bot trả lời Hej thống tra cứu đang bận hoặc gián đoạn ..., log 2026-10-25 08:22:48,141 - src.bot.handlers.search - ERROR - OpenAI client, settings, or db missing from application data. nếu hỏi luôn câu hỏi kia mà không ấn tra cứu, hệ thống không nhận ra, trả lời là Em không nhận diện được đơn hàng tư tin nhắn ..."
severity: blocker

### 4. Context-Preserving Detail Navigation
expected: From single order search confirmation, tapping [👁️ Đúng rồi, xem chi tiết] opens the full Phase 3 order card with 1-tap copy buttons and status buttons. Tapping [⬅️ Quay lại] returns directly to the search result card without re-querying the database or losing context.
result: blocked
blocked_by: prior-phase
reason: "tính năng tra cứu không work theo issue ở trên kia, nên khả năng block hết các test phía sau"

### 5. Multi-Order Paginated Search Results
expected: Searching with a broad query matching multiple orders (e.g., "tìm các đơn hôm nay" or "các đơn đã giao") displays a list of orders (up to 5 per page) with [👁️ Xem đơn #ID] buttons and pagination controls [Trang X/Y] [⬅️ Trang trước] [Trang sau ➡️]. Tapping [👁️ Xem đơn #ID] views details, and [⬅️ Quay lại] returns to the exact search page.
result: blocked
blocked_by: prior-phase
reason: "tính năng tra cứu không work theo issue ở trên kia, nên khả năng block hết các test phía sau"

### 6. Statistical Aggregate Search & LLM Summary
expected: Searching for summary/statistics (e.g., "hôm nay bán được bao nhiêu đơn" or "tổng tiền các đơn chưa giao") triggers an aggregate SQL query (COUNT/SUM/AVG) and returns a friendly, warm Vietnamese sentence summarizing the statistics instead of a raw order card.
result: blocked
blocked_by: prior-phase
reason: "tính năng tra cứu không work theo issue ở trên kia, nên khả năng block hết các test phía sau"

### 7. Accent-Insensitive (Unaccent) Search
expected: Searching in Vietnamese without diacritics (e.g., "tim don cua Tuan" or "bang cassette Trinh Cong Son") successfully matches accented records in the database ("Tuấn", "băng cassette Trịnh Công Sơn").
result: blocked
blocked_by: prior-phase
reason: "tính năng tra cứu không work theo issue ở trên kia, nên khả năng block hết các test phía sau"

### 8. Empty Search Handling
expected: Searching for non-existent records (e.g., "tìm đơn anh Nobita ở Sao Hỏa") displays a friendly empty result message ("Dạ em tìm trong sổ không thấy đơn nào như bác tả rồi!") with search tips and quick buttons: [🔍 Thử tìm lại] and [📝 Nhập đơn mới].
result: blocked
blocked_by: prior-phase
reason: "tính năng tra cứu không work theo issue ở trên kia, nên khả năng block hết các test phía sau"

## Summary

total: 8
passed: 2
issues: 1
pending: 0
skipped: 0
blocked: 5

## Gaps

- gap_id: G-04-3
  truth: "Sending a search query matching a single order displays a 2-phase confirmation snippet card showing customer name, phone, items, total, and buttons: [👁️ Đúng rồi, xem chi tiết] and [🔍 Tìm câu khác]."
  status: failed
  reason: "User reported: bấm Tra cứu, hỏi a Biên đã mua băng bao giờ chưa nhỉ? bot trả lời Hej thống tra cứu đang bận hoặc gián đoạn ..., log 2026-10-25 08:22:48,141 - src.bot.handlers.search - ERROR - OpenAI client, settings, or db missing from application data. nếu hỏi luôn câu hỏi kia mà không ấn tra cứu, hệ thống không nhận ra, trả lời là Em không nhận diện được đơn hàng tư tin nhắn ..."
  severity: blocker
  test: 3
  root_cause: "1) `main.py` calls `build_application(settings)` without passing `db`, leaving `app.bot_data['db']` as None, and `src/bot/handlers/search.py` (lines 104 and 354) strictly requires `db` instead of using the fallback `_get_active_db_context(context)` (`nullcontext(db) if db else get_db_connection(db_path)`) used by all other handlers; 2) `is_search_intent` in `src/services/order_search.py` only checks `trimmed.startswith(prefix)` against 5 static keywords ('tìm', 'tra cứu', 'kiểm tra', 'xem lại đơn', 'hỏi đơn'), missing natural conversational inquiries (e.g. 'a Biên đã mua băng bao giờ chưa nhỉ?') which fall through to order ingestion and fail without a phone number."
  artifacts:
    - path: "src/bot/handlers/search.py"
      issue: "Lacks _get_active_db_context fallback for database connection in process_search_query and handle_search_callback"
    - path: "src/services/order_search.py"
      issue: "is_search_intent uses strict startswith prefix matching only, missing natural Vietnamese inquiry question patterns"
  missing:
    - "Add _get_active_db_context helper in src/bot/handlers/search.py and use dynamic db connection context manager"
    - "Broaden is_search_intent in src/services/order_search.py with regex/keyword matching for conversational inquiry questions ('đã...bao giờ chưa', 'chưa nhỉ', 'có mua...không', 'mấy đơn', 'bao nhiêu đơn')"
  debug_session: ".planning/debug/search-application-data-missing.md"
