---
status: diagnosed
trigger: "disambiguation-order-not-found: Chọn đơn 1-chạm khi khớp nhiều đơn (Disambiguation) không tìm thấy đơn"
created: 2026-10-25T00:00:00Z
updated: 2026-10-25T17:45:00Z
---

## Current Focus

hypothesis: Disambiguation lookup fails due to (1) SQL exact substring match on customer_name failing when keyword includes honorific/filler words ('khách', 'của', 'đơn') or differs from DB name, (2) LLM JSON extractor failing on markdown/trailing chatter from 9router models, and (3) In UAT test 2, orders for 'Bác Ba' were not persisted in DB while test command searched for 'Bác Ba'.
test: Tested find_orders_for_mutation with keyword variations in SQLite and tested real 9router LLM extraction outputs.
expecting: Confirm exact mechanism of 0 matches and extraction failures.
next_action: Finalize root cause documentation.

## Symptoms

expected: Tạo 2 đơn cùng tên khách "Bác Ba", nhắn `đổi sđt khách Bác Ba thành 0988776655`. Bot hiện danh sách nút inline 1-chạm, bấm chọn chuyển mượt sang thẻ diff.
actual: fail, bot báo không tìm thấy đơn nào của xxx
errors: Bot báo không tìm thấy đơn nào (Screen 1 empty guidance)
reproduction: Test 2 in UAT: Tạo 2 đơn cùng tên khách "Bác Ba", nhắn `đổi sđt khách Bác Ba thành 0988776655`
started: Discovered during Phase 7 UAT

## Eliminated

- hypothesis: Phone filter from delta.new_customer_phone was still passed to find_orders_for_mutation
  evidence: Commit 992edaf already removed phone=delta.new_customer_phone from mutation handler. Tested in code and git history.
  timestamp: 2026-10-25T17:30:00Z

- hypothesis: SQLite custom unaccent function crashed or was not registered
  evidence: unaccent function is properly registered on get_db_connection and works in direct SQLite tests.
  timestamp: 2026-10-25T17:35:00Z

## Evidence

- timestamp: 2026-10-25T17:15:00Z
  checked: orders and customers tables in cassette_store.db
  found: Only 4 orders exist (1: Phan Thanh, 2: Anh Hà, 3: Lại Thanh Tuấn, 4: Anh hà). Zero orders exist with customer_name 'Bác Ba'.
  implication: If test command literally asked for 'Bác Ba', find_orders_for_mutation genuinely returns 0 orders because no such orders exist in DB.

- timestamp: 2026-10-25T17:25:00Z
  checked: extract_mutation_delta on live 9router API with 'đổi sđt khách Bác Ba thành 0988776655'
  found: Model returns markdown code block with trailing chatter ('```json\n{...}\n```\n\nBỏ qua: tra cứu ID đơn. Thêm khi: có API map tên khách ra ID đơn.'). Tier 1 parse fails on markdown, Tier 2 clean_json_markdown fails on trailing text, causing validation error and returning None.
  implication: Extractor intermittently crashes when 9router returns chatter, causing bot to report extraction error.

- timestamp: 2026-10-25T17:38:00Z
  checked: find_orders_for_mutation SQL query with keyword variations
  found: find_orders_for_mutation uses `unaccent(customer_name) LIKE '%kw_clean%'`. When kw_clean has 'khach' ('khách Anh Hà', 'khách Bác Ba'), query returns 0 matches because DB customer_name is 'Anh Hà' / 'Bác Ba' without 'khách'. Also fails if DB has 'Ba' but keyword is 'Bác Ba'.
  implication: Keyword matching is overly strict on substring containment and lacks tokenization / honorific stripping.

## Resolution

root_cause: |
  1. Primary Query Bug in `find_orders_for_mutation`:
     The search uses strict SQL substring matching `unaccent(customer_name) LIKE '%{kw_clean}%'`. When the user says "đổi sđt khách Bác Ba..." or "khách Anh Hà...", the LLM extracts `target_customer_keyword` retaining honorific / conversational prefixes ("khách Bác Ba", "khách Anh Hà", "anh Nam" per prompt examples). Because the stored `customer_name` in the database does not contain "khách" or "đơn", the LIKE pattern fails to match, resulting in 0 matches and triggering the "KHÔNG TÌM THẤY ĐƠN HÀNG CẦN SỬA" card.
  2. Test Precondition & Extraction Failure:
     In the UAT test session, no orders for "Bác Ba" were persisted in `cassette_store.db` (only Order 2 "Anh Hà" and Order 4 "Anh hà" existed). If the tester literally ran the test prompt "đổi sđt khách Bác Ba...", SQLite legitimately had 0 records for "Bác Ba". Furthermore, `_clean_json_markdown` fails to parse 9router responses when the model outputs trailing explanatory text after markdown fences.
fix: 
verification: 
files_changed: []
