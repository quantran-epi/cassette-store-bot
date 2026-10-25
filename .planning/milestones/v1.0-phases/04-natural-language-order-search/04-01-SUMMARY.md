---
phase: 04-natural-language-order-search
plan: 01
status: complete
subsystem: search-engine
tags: [text-to-sql, sqlite, unaccent, sanitization, natural-language]
requires:
  - Phase 01: Core data schema and SQLite infrastructure
  - Phase 02: LLM client and OpenAI gateway
affects:
  - Plan 04-02: Telegram search handler and confirmation UI
tech-stack:
  added: []
  patterns:
    - Text-to-SQL prompt with UTC+7 conversion rules
    - Strict read-only SQL sanitizer (single-statement, forbidden DDL/DML, LIMIT 20)
    - Vietnamese unaccent custom SQLite function
    - 1-shot retry on sqlite3.OperationalError
    - Result classification into Order domain records vs statistical aggregate summary
key-files:
  created:
    - src/services/order_search.py
    - tests/test_order_search.py
  modified:
    - src/db/connection.py
decisions:
  - "D-04: Enforce Text-to-SQL architecture with orders and customers DDL schema and UTC+7 rules in system prompt"
  - "D-05 / T-04-01: Sanitize SQL strictly by enforcing single-statement SELECT, blocking DDL/DML keywords, and enforcing LIMIT 20"
  - "D-06: Implement 1-shot retry passing error message back to LLM when SQLite returns OperationalError"
  - "D-07: Separate order records from scalar aggregates; summarize aggregates into warm Vietnamese via LLM"
metrics:
  duration: 4m
  completed_date: "2026-10-25"
actuals:
  tokens: 28000
  tasks: 3
  commits: 3
plan_head_before: 54561b5d5f98de56e5f4d87f1e977f6b59185a05
plan_head_after: a623b7f18103f49b2c8e465cf4a881226a12c5e7
---

# Phase 04 Plan 01: Text-to-SQL Core Service and Sanitizer Summary

Built production-grade Text-to-SQL translation, SQL sanitization, Vietnamese unaccent SQLite support, 1-shot error recovery, and result classification/summarization.

## Key Changes

1. **Vietnamese Unaccent SQLite Support (`src/db/connection.py`)**:
   - Implemented `remove_accents(input_str)` normalizing Unicode NFKD, mapping 'đ'/'Đ' to 'd'/'D', and stripping combining accents.
   - Registered custom SQLite function `unaccent` in `get_db_connection` for accent-insensitive search queries.

2. **Strict SQL Sanitizer & Search Intent (`src/services/order_search.py`)**:
   - `is_search_intent`: checks if query starts with keywords (`tìm`, `tra cứu`, `kiểm tra`, `xem lại đơn`, `hỏi đơn`).
   - `sanitize_and_validate_sql`: strips code fences/trailing semicolons, rejects semicolons (multi-statement injection defense per T-04-01), ensures statement starts with `SELECT`, verifies no forbidden DDL/DML keywords (`INSERT`, `UPDATE`, `DELETE`, `DROP`, `ALTER`, `CREATE`, `REPLACE`, `ATTACH`, `DETACH`, `PRAGMA`, `VACUUM`, `EXEC`), and enforces `LIMIT 20`.

3. **Text-to-SQL Engine with 1-Shot Retry (`src/services/order_search.py`)**:
   - `build_text_to_sql_prompt`: formats DDL schema and current VN time (UTC+7) with relative date rules. Wraps user input in `<query>...</query>` per T-04-02.
   - `translate_natural_language_to_sql`: calls OpenAI client at temperature 0.0 and applies sanitization.
   - `execute_natural_language_search`: executes query on SQLite; on `sqlite3.OperationalError`, retries 1-shot sending error feedback to LLM per D-06.

4. **Result Classification & LLM Aggregate Summarizer (`src/services/order_search.py`)**:
   - `classify_and_hydrate_results`: detects order columns vs scalar aggregates (`COUNT`, `SUM`, `AVG`), hydrating orders into domain `Order` models.
   - `summarize_aggregate_result`: summarizes statistical rows into a friendly, warm Vietnamese sentence for elderly shop owners per D-07.
   - `run_order_search`: high-level coordinator returning structured `SearchResult`.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] SQL Sanitizer regex pattern test mismatch**
- **Found during:** Task 1 tracer verify
- **Issue:** Multi-statement test case with semicolon and `ALTER TABLE` was matching multi-statement semicolon rejection before the forbidden keyword check.
- **Fix:** Placed `ALTER TABLE` inside parenthesis subquery to test keyword check independently from multi-statement semicolon check.
- **Files modified:** `tests/test_order_search.py`
- **Commit:** `608f2fb`

## Self-Check: PASSED

1. Created files exist:
   - `src/services/order_search.py`: FOUND
   - `tests/test_order_search.py`: FOUND
2. Commits exist in history:
   - `608f2fb`: FOUND (Task 1 tracer)
   - `496220c`: FOUND (Task 2 Text-to-SQL prompt & retry)
   - `a623b7f`: FOUND (Task 3 classification & summary)
3. Full test suite: 96 tests passing cleanly.
