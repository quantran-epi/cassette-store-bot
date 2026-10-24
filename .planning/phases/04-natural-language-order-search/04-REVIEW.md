---
phase: 04-natural-language-order-search
reviewed: 2026-10-25T01:05:00Z
depth: standard
files_reviewed: 10
files_reviewed_list:
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
findings:
  critical: 0
  warning: 3
  info: 3
  total: 6
status: issues_found
---

# Phase 04: Code Review Report

**Reviewed:** 2026-10-25T01:05:00Z  
**Depth:** standard  
**Files Reviewed:** 10  
**Status:** issues_found  

## Summary

Phase 04 source code implements Text-to-SQL order search, dual-trigger query ingestion, SQL security sanitization, and 2-phase confirmation UX. 0 Critical vulnerabilities found. 3 Warnings identified regarding cache eviction, SQL comment sanitization, and Telegram callback error resilience.

## Findings

### Warnings

#### WARN-01: In-memory search cache unbounded growth
- **File:** `src/bot/handlers/search.py`
- **Issue:** `_search_cache` stores query results by `search_id` with timestamp eviction only on new search queries. If bot runs for a long time with many unique searches, memory usage grows continuously.
- **Recommendation:** Implement max-size LRU eviction or explicit max items bound (e.g., max 100 entries).

#### WARN-02: SQL sanitizer allows SQL comments (`--`, `/* */`)
- **File:** `src/services/order_search.py`
- **Issue:** The regex sanitizer checks for forbidden keywords (`INSERT`, `UPDATE`, `DROP`, etc.) but does not strip comments like `--` or `/* ... */`, which could mask tokens or alter clause parsing.
- **Recommendation:** Strip SQL comments before checking keyword boundaries or checking semicolons.

#### WARN-03: Unhandled Telegram BadRequest on stale callback queries
- **File:** `src/bot/handlers/search.py`
- **Issue:** `query.answer()` or `query.edit_message_text()` does not catch `telegram.error.BadRequest` for queries older than 48 hours or when message content is unchanged.
- **Recommendation:** Wrap callback answer and edit calls in `try...except BadRequest` logging warnings.

### Info

#### INFO-01: Escaped unicode in system prompt
- **File:** `src/services/order_search.py`
- **Detail:** System prompt contains `đ` escapes rather than direct UTF-8 Vietnamese strings.

#### INFO-02: Broad exception suppression in base state cleanup
- **File:** `src/bot/handlers/base.py`
- **Detail:** `clear_user_state` uses `except Exception: pass` which might mask unexpected errors during context dictionary access.

#### INFO-03: Function length in `handle_search_query_text`
- **File:** `src/bot/handlers/search.py`
- **Detail:** Handler combines typing loop, LLM call, SQL execution, error retry, and result routing in one ~150-line block. Could be factored into smaller helpers in future refactors.
