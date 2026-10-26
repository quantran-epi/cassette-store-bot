---
phase: quick
plan: 261026-e7m
subsystem: natural-language order search
tags: [search, text-to-sql, pagination, aggregate, telegram]
requires: [QUICK-E7M]
provides: [MIXED search result, DB-backed list pagination, multi-statement read-only validator]
affects: [src/services/order_search.py, src/bot/handlers/search.py, src/bot/keyboards.py]
tech-stack:
  added: []
  patterns: [prepare-once SQL, DB page fetch with placeholders, top-level ORDER BY strip]
key-files:
  created: [tests/test_search_mixed_pagination.py]
  modified:
    - src/services/order_search.py
    - src/bot/handlers/search.py
    - src/bot/keyboards.py
decisions:
  - "keep sanitize_and_validate_sql default LIMIT 20 for the mutation path; opt out via append_default_limit=False"
  - "prepare list SQL once in service, reuse stored list_sql for every page fetch (no double tiebreaker)"
  - "page 1 served from the snapshot; later pages fetched from the DB"
  - "legacy snapshots without list_sql keep in-memory slicing"
metrics:
  duration: ~35m
  tasks: 3
  files_changed: 4
  completed: 2026-10-26
---

# Quick Task 261026-e7m: NL Search Aggregate + List Pagination Summary

Mixed natural-language queries ("hôm nay bán bao nhiêu đơn, liệt kê các đơn") now return the full aggregate over the whole filtered set plus a real DB-paginated list (5 orders/page, stable `created_at DESC, id DESC`, "Xem thêm" button). The old `LIMIT 20` hard cap no longer truncates search results, while the mutation/legacy search API is untouched.

## What Changed

### `src/services/order_search.py`

- Added `SearchResultType.MIXED` and `SearchResult.list_sql`, `total_count`, `page_size` (all defaulted, so existing constructors still work).
- `sanitize_and_validate_sql(raw_sql, *, append_default_limit=True)` — default behaviour unchanged; search pipeline opts out of the injected `LIMIT 20`.
- New `split_and_validate_statements(raw_sql, *, max_statements=2)` — accepts 1–2 SELECTs, rejects >2 statements, non-SELECT statements, leftover `;` inside a statement, and forbidden DDL/DML keywords.
- New SQL preparation helpers:
  - `prepare_list_sql` strips an LLM-emitted LIMIT and guarantees a stable ORDER BY (`created_at DESC, id DESC`, alias-aware, appends `id DESC` tiebreaker only when absent).
  - `prepare_aggregate_sql` strips LIMIT/OFFSET so aggregates run over the full set.
  - `_strip_trailing_limit`, `_strip_order_by` (top-level-aware; keeps nested ORDER BY), `_orders_alias`, `_is_aggregate_statement`.
- New `count_search_results(db, prepared_list_sql)` and `fetch_search_page(db, prepared_list_sql, page, page_size=5)` — count/fetch run only the already-validated SQL; page SQL uses `LIMIT ? OFFSET ?` placeholders.
- New `translate_natural_language_to_sql_multi(...)`; shared LLM call extracted to `_request_sql_translation` so single and multi translation do not duplicate request/retry logic. `translate_natural_language_to_sql` and `execute_natural_language_search` keep their signatures and behaviour (still `LIMIT 20` capped for mutation).
- `run_order_search(..., page=1, page_size=5)` dispatches: 1 aggregate statement → AGGREGATE; 1 list statement → ORDERS with `list_sql`/`total_count`; 2 statements → MIXED with aggregate rows + summary + page-1 list from DB. Keeps 1-shot retry on `sqlite3.OperationalError`.
- System prompt updated: list queries use `ORDER BY o.created_at DESC, o.id DESC` with no self-added LIMIT; aggregates carry no LIMIT; mixed questions return exactly 2 SELECT statements (`aggregate; list`).

### `src/bot/handlers/search.py`

- Added `_summary_prefix`, `_has_db_pagination`, `_load_page_orders`, `_render_list_view`.
- `process_search_query`: AGGREGATE branch unchanged (plain text); ORDERS and MIXED share `_render_list_view`, MIXED prefixes the escaped aggregate summary to the HTML card and still renders an empty card when the count is 0.
- `sch_pg`: with `list_sql`+`total_count`, computes/clamps pages and loads the requested page from the DB (page 1 reuses the snapshot); DB failure replies with the DB error message. Snapshots without `list_sql` keep the old in-memory slicing.
- `sch_bk`: MIXED treated like ORDERS; pages > 1 restored from the DB, legacy snapshots sliced in memory.
- `mutation.py`, confirm and UPDATE flows untouched.

### `src/bot/keyboards.py`

- `build_search_multi_keyboard`: page-forward button relabelled `Trang sau ▶️` → `Xem thêm ➡️`; callback `sch_pg:{search_id}:{page+1}` and back/`Trang X/Y` buttons unchanged.

### `tests/test_search_mixed_pagination.py` (new)

- Validator: valid 2-statement split; rejects 3 statements, trailing INSERT/DROP, leftover `;`.
- Prepare: LIMIT removed; ORDER BY stabilization/tiebreaker (no duplicate when `id` present); aggregate strips LIMIT.
- `run_order_search` MIXED with 7 seeded orders: MIXED type, `total_count=7`, 5 orders, `raw_rows[0]["total_orders"] == 7`, summary populated, `list_sql` has no LIMIT, prompt has the 2-statement guidance.
- List of 25 orders stays uncapped (`total_count=25`, 5 returned).
- DB pagination: pages 1/2 disjoint, no omissions, id DESC ordering.
- `sch_pg` on a new-style snapshot fetches page 2 from the DB, shows `Trang 2/2`, hides "Xem thêm".
- Legacy snapshot pagination unchanged; keyboard label test; `execute_natural_language_search` still appends `LIMIT 20` and returns a 2-tuple.

## Deviations from Plan

None functionally. Implementation detail deviations:

- Plan named `_strip_order_by` as a plain regex strip; implemented it as a depth-aware top-level scan so an `ORDER BY` inside a subquery is not removed. No behaviour change for the plan's cases; prevents broken COUNT SQL.
- Aggregate detection ignores wildcards inside function calls (`COUNT(*)`), otherwise `SELECT COUNT(*) ...` would be misclassified as a list query.
- Added `_has_db_pagination` helper (shared predicate) instead of repeating `list_sql and total_count is not None` in the handler.

## Verification

- `pytest tests/test_search_mixed_pagination.py tests/test_order_search.py tests/test_mutation_search_general.py tests/test_mutation_handler_flow.py tests/test_mutation_card_and_lock.py -q` → **70 passed**.
- `pytest -q` → **263 passed**, 2 warnings.
- `ruff check src/services/order_search.py src/bot/handlers/search.py src/bot/keyboards.py tests/test_search_mixed_pagination.py` → **All checks passed**.
- Deep review of the four changed files: no Critical/Warning findings outstanding (validator read-only guarantees, placeholder-only LIMIT/OFFSET, page clamping, legacy path preserved, mutation untouched).

## Files Changed

- `src/services/order_search.py`
- `src/bot/handlers/search.py`
- `src/bot/keyboards.py`
- `tests/test_search_mixed_pagination.py` (new)
- `.planning/quick/261026-e7m-ch-nh-lu-ng-tra-c-u-nl-h-tr-aggregate-c-/261026-e7m-SUMMARY.md` (this file)

## Known Stubs

None.

## Threat Flags

None — all new SQL paths go through the existing read-only validator and use placeholders for pagination.

## Notes

- No commits were made, per instructions. `.env.example` was left untouched (pre-existing unrelated change preserved).
