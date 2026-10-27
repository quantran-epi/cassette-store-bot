---
phase: 261027-jb2
plan: 01
subsystem: natural-language-order-search
tags: [search, llm, json-plan, telegram, sqlite]
requires:
  - src/services/order_search.py (SQL translation, pagination, sanitization)
  - src/bot/keyboards.py (search card renderers)
  - src/bot/handlers/search.py (search result routing/pagination)
provides:
  - SearchPlan / PlannedQuery / parse_search_plan / translate_natural_language_to_search_plan
  - _execute_search_plan / summarize_search_results / run_order_search JSON path
  - SearchResult.list_purpose and purpose-aware search cards
affects:
  - Natural language order search behavior
  - Search summary envelope and card headings
tech-stack:
  added: []
  patterns: [labeled JSON query plan, one-shot plan regeneration, envelope summarization]
key-files:
  created: []
  modified:
    - src/services/order_search.py
    - src/bot/keyboards.py
    - src/bot/handlers/search.py
    - tests/test_order_search.py
    - tests/test_search_mixed_pagination.py
decisions:
  - LLM returns a labeled JSON plan (0/1 list + 0-3 aggregates) instead of 1-2 raw SQL statements
  - Roles come from JSON keys, never inferred from projection shape
  - List cards get a deterministic purpose heading; legacy snapshots keep query heading
metrics:
  duration: ~25m
  completed: 2026-10-27
---

# Phase 261027-jb2 Plan 01: Refactor NL Order Search to JSON Plan Summary

Search pipeline now asks the LLM for a labeled JSON plan (max 1 list + 3 aggregates), executes every query, validates roles at runtime, regenerates once on bad plans, and renders list cards with an escaped purpose heading that survives pagination and restore.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | JSON plan + envelope execution in order_search.py | d92e7d8 | src/services/order_search.py |
| 2 | Purpose heading in search renderers and handler | d84e281 | src/bot/keyboards.py, src/bot/handlers/search.py |
| 3 | Tests for JSON plan, envelope, role validation, heading | 1f0d0a0 | tests/test_order_search.py, tests/test_search_mixed_pagination.py |

## What Was Built

- `SearchPlan` / `PlannedQuery` dataclasses and `parse_search_plan` enforcing 0/1 list, 0-3 aggregates, at least one query, and per-SQL `sanitize_and_validate_sql(..., append_default_limit=False)`.
- `_clean_purpose` trims/collapses whitespace, caps at 120 chars, rejects non-strings/empty; renderer escapes it.
- `build_search_plan_prompt` / `_request_search_plan` with `response_format={"type": "json_object"}` and one retry without that parameter when the gateway raises.
- `translate_natural_language_to_search_plan` with a single parse-retry carrying the failed plan plus error text.
- `_execute_search_plan`: count + one DB page for list, all aggregates executed in order, list role rejects non-order rows, aggregate role rejects order rows.
- `summarize_search_results` envelope: aggregates with purpose+rows, list only as `{"purpose", "count"}`; zero summary calls for list-only plans.
- `run_order_search` regenerates the whole plan once on `sqlite3.OperationalError` or `ValueError`, then propagates.
- Purpose-aware `render_search_multi_card`, `render_search_single_order_card`, `render_search_empty_card`; `_render_list_view` passes `result.list_purpose` for first render, `sch_pg`, and `sch_bk`.
- Removed `_can_list_statement`, `_run_aggregate`, `_run_list`, `_execute_search_statements`, `translate_natural_language_to_sql_multi`, `MULTI_STATEMENT_RULES`, `summarize_aggregate_result`, and the `multi` prompt parameter. Legacy mutation search (`execute_natural_language_search`, LIMIT 20) is unchanged.

## Verification

- `python -m pytest tests/test_order_search.py tests/test_search_mixed_pagination.py -q` -> 74 passed.
- `python -m pytest -q` -> 397 passed, 1 failed (pre-existing, see below).
- Grep confirms no references remain to `_can_list_statement`, `_execute_search_statements`, `matched_order_count`, `list_total`, `summarize_aggregate_result`, `translate_natural_language_to_sql_multi`, or `MULTI_STATEMENT_RULES`.

## Deviations from Plan

None functionally. Task 3 selected one concrete envelope assertion detail: the mixed summary test checks purpose/count presence and absence of `items_text` and customer names rather than asserting the query's own phrase is absent (the user question legitimately repeats it).

## Deferred Issues

`tests/test_notes_maintenance_notifications_reminders.py::test_order_detail_card_and_reminder_prompt` fails with `sqlite3.OperationalError: no such table: reminders`. Confirmed failing on the untouched base commit (stash test) — pre-existing and unrelated to this plan; left untouched per scope boundary.

## Known Stubs

None.

## Threat Flags

None beyond the plan's threat model. All plan SQL passes the existing read-only validator; purpose is escaped at render time; no new dependencies.

## Self-Check: PASSED

All 5 modified files and 3 task commits (d92e7d8, d84e281, 1f0d0a0) exist on branch `worktree-agent-afde646053be89ed5`.
