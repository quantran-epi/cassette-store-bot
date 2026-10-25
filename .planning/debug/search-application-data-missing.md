---
status: resolved
trigger: "User reported: bấm Tra cứu, hỏi a Biên đã mua băng bao giờ chưa nhỉ? bot trả lời Hej thống tra cứu đang bận hoặc gián đoạn ..., log 2026-10-25 08:22:48,141 - src.bot.handlers.search - ERROR - OpenAI client, settings, or db missing from application data. nếu hỏi luôn câu hỏi kia mà không ấn tra cứu, hệ thống không nhận ra, trả lời là Em không nhận diện được đơn hàng tư tin nhắn ..."
created: 2026-10-25T08:30:00Z
updated: 2026-10-25T10:15:00Z
---

## Current Focus

hypothesis: Resolved in Phase 04 Plan 03 (Gap Closure). Root causes (1) and (2) fixed and verified via automated test suite and UAT 8/8 passing.
test: Passed via tests/test_order_search.py, tests/test_orders_ui.py, and 04-UAT.md.
expecting: Closed.
next_action: None.

## Symptoms

expected: Tapping [🔍 Tra cứu đơn] then typing "a Biên đã mua băng bao giờ chưa nhỉ?" runs Text-to-SQL search and returns result card. Typing the query directly without tapping [🔍 Tra cứu đơn] is recognized as search intent and also routes to search.
actual: When tapping Tra cứu: bot logs "OpenAI client, settings, or db missing from application data" and returns error message. When typing directly: bot treats query as new order and replies "Em không nhận diện được đơn hàng từ tin nhắn này. Bác vui lòng gửi lại tin nhắn có số điện thoại khách nhé!".
errors: 2026-10-25 08:22:48,141 - src.bot.handlers.search - ERROR - OpenAI client, settings, or db missing from application data.
reproduction: Send "a Biên đã mua băng bao giờ chưa nhỉ?" in search mode or directly in chat.
started: UAT phase 04 test 3.

## Eliminated

- hypothesis: Settings or OpenAI client missing from application data.
  evidence: main.py initializes Settings and build_application creates AsyncOpenAI client and stores them in app.bot_data. Only db is None because main.py does not pass db.
  timestamp: 2026-10-25T08:35:00Z

- hypothesis: Search state not captured when tapping search menu.
  evidence: handle_search_menu_reply sets context.user_data['search_state'], handle_text_order correctly detects search_state and forwards query to process_search_query. The failure happens inside process_search_query at db validation.
  timestamp: 2026-10-25T08:38:00Z

## Evidence

- timestamp: 2026-10-25T08:33:00Z
  checked: main.py line 32 and src/bot/app.py line 38
  found: main.py calls app = build_application(settings) without db argument. In src/bot/app.py, db defaults to None. app.bot_data['db'] and app_context.db are None in production.
  implication: Any handler that expects a non-None db directly in bot_data will fail.

- timestamp: 2026-10-25T08:35:00Z
  checked: src/bot/handlers/search.py lines 94-110 and lines 351-356
  found: process_search_query checks `if not openai_client or not settings or not db:` and logs ERROR 'OpenAI client, settings, or db missing from application data'. handle_search_callback checks `if not db:`. Neither has fallback to get_db_connection(db_path).
  implication: When user taps search menu and enters query, process_search_query immediately hits this error because db is None.

- timestamp: 2026-10-25T08:36:00Z
  checked: src/bot/handlers/orders.py lines 27-34, src/bot/handlers/callbacks.py lines 80-87, src/bot/handlers/ingest.py lines 107-116
  found: All other handlers use fallback pattern: `db_ctx = nullcontext(db) if db else get_db_connection(db_path)` with `async with db_ctx as active_db:`.
  implication: search.py broke established architectural pattern by demanding persistent db in bot_data.

- timestamp: 2026-10-25T08:38:00Z
  checked: src/services/order_search.py lines 18-25 and 122-126
  found: `is_search_intent(text)` checks `return any(trimmed.startswith(prefix) for prefix in SEARCH_PREFIX_KEYWORDS)` where keywords are only `('tìm', 'tra cứu', 'kiểm tra', 'xem lại đơn', 'hỏi đơn')`.
  implication: Query "a Biên đã mua băng bao giờ chưa nhỉ?" starts with "a biên", not any search keyword prefix. is_search_intent returns False.

- timestamp: 2026-10-25T08:40:00Z
  checked: src/bot/handlers/ingest.py lines 195-201 and lines 100-104
  found: When is_search_intent is False and search_state is not active, handle_text_order forwards to extract_order_from_text (LLM order ingestion). Since the question contains no phone number, it hits line 101: "Em không nhận diện được đơn hàng từ tin nhắn này. Bác vui lòng gửi lại tin nhắn có số điện thoại khách nhé!".
  implication: Explains symptom where asking the question without tapping search menu is treated as an invalid new order.

## Resolution

root_cause: 1. DB connection missing in search handler: main.py calls build_application(settings) without db, so bot_data['db'] is None in production. src/bot/handlers/search.py (process_search_query and handle_search_callback) requires db to be directly present in bot_data and lacks the db fallback pattern (`nullcontext(db) if db else get_db_connection(db_path)`) used by all other handlers; 2. Incomplete search intent recognition: is_search_intent in src/services/order_search.py only checks if the query starts with 5 fixed prefixes ('tìm', 'tra cứu', 'kiểm tra', 'xem lại đơn', 'hỏi đơn'). Natural question syntax (e.g., 'a Biên đã mua băng bao giờ chưa nhỉ?') starts with subject/addressing ('a Biên...') and contains question markers ('đã ... bao giờ chưa', 'chưa nhỉ'), failing startswith and dropping into order ingestion.
fix: Implemented in commits 74fcb2e, e0a3ca9, 8c615b1, and 1646347. (1) Used _get_active_db_context in search.py; (2) Expanded conversational regex patterns in order_search.py with phone number exclusion guard.
verification: All 110 automated tests passing; 04-UAT.md 8/8 passed.
files_changed:
  - src/bot/handlers/search.py
  - src/services/order_search.py
  - src/bot/handlers/ingest.py
  - tests/test_order_search.py
  - tests/test_orders_ui.py
