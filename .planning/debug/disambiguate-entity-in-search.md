---
status: resolved
trigger: "Khách hạ trắng đã bao lâu rồi ko mua? bot trả lời sai, list bị lẫn cả khách có tên là phạm thị trang"
created: 2026-10-29
updated: 2026-10-29
---

## Current Focus
- hypothesis: "Natural language search uses raw substring tokenized AND (LIKE %ha% AND LIKE %trang%) causing severe accent/token collision (Trang matches Trắng, Ha matches any substring), AND when query asks aggregate/calculation over ambiguous entity, system fails to disambiguate or rank relevance."
- test: "Query for 'Khách hạ trắng đã bao lâu rồi ko mua' or any specific entity search"
- expecting: "High-relevance ranking and disambiguation prompt when multiple entities match an aggregate query"
- next_action: "Complete debug session"

## Symptoms
- expected: "Match exact customer 'Hạ Trắng' (or orders with item 'Hạ Trắng'). If multiple customers match, ask user to clarify which entity before computing aggregate stats."
- actual: "Returned list mixed with 'Phạm Thị Trang' and answered wrong date calculation."
- error: "Wrong entity matching and calculation"
- timeline: "Reported today on Text-to-SQL search"
- reproduction: "Send query: 'Khách hạ trắng đã bao lâu rồi ko mua?'"

## Evidence
- timestamp: 2026-10-29T21:40:00Z
  observation: "unaccent('Phạm Thị Trang') LIKE '%ha%' evaluated to TRUE because 'pham' contains internal substring 'ha'. Tokenized AND with %ha% and %trang% matched 'Phạm Thị Trang' instead of only 'Hạ Trắng'."
- timestamp: 2026-10-29T21:45:00Z
  observation: "Aggregate query computed MAX(datetime(o.created_at, '+7 hours')) across all matched rows including 'Phạm Thị Trang', producing wrong calculation based on Pham Thi Trang's recent order."
- timestamp: 2026-10-29T21:50:00Z
  observation: "is_search_intent and is_customer_analytics lacked patterns for 'bao lâu', 'chưa/ko mua', 'lần cuối/gần nhất', causing queries like 'Khách hạ trắng đã bao lâu rồi ko mua?' to misclassify as pure customer profile lookup instead of order history analytics."

## Specialist Review
LOOKS_GOOD: Replaced substring LIKE on customer names with SQLite custom function `word_match(col, token) = 1` which enforces regex word boundary `\btoken\b` on unaccented text. This cleanly prevents short syllables like 'ha' from matching inside 'Phạm', 'Thanh', 'Phan', etc. Expanded intent regexes to cover 'bao lâu', 'lần cuối', 'lần gần nhất', and 'chưa/ko mua'. Prompt updated to guide LLM to use `word_match` and sort by exact match relevance. All 458 unit and integration tests passing.

## Resolution
- root_cause: "Text-to-SQL prompt instructed tokenized AND substring LIKE '%ha%' for customer names, which matched internal substring 'ha' in 'Phạm'. Inquiries like 'đã bao lâu rồi ko mua' were also missing from search intent patterns."
- fix: "Instructed word_match(col, 'token') = 1 for customer name matching in SQL prompts; documented word_match custom function; expanded regex intent patterns for 'bao lâu' and last-purchase inquiries; verified with new regression tests."
- verification: "tests/test_customer_search.py::test_search_customer_name_word_match_no_substring_collision_ha_trang_vs_pham_thi_trang passed; full 458-test suite green."
- files_changed:
  - "src/db/customers.py"
  - "src/services/order_search.py"
  - "src/services/mutation_extractor.py"
  - "tests/test_customer_search.py"

