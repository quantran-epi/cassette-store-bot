# Quick Task 261026-e7m — Code Review (high)

**Scope:** `src/services/order_search.py`, `src/bot/handlers/search.py`, `src/bot/keyboards.py`
**Mode:** high effort — 8 finder angles, then fix-in-place, then runtime replay.

## Findings fixed

| # | Defect | Fix |
|---|--------|-----|
| 1 | Non-aggregate partial projection (`SELECT customer_name, total_amount`) hydrated phantom `Order` rows with `id=None`, rendering `Đơn #None` and a callback that raised `ValueError` on `int(parts[2])`. | `_rows_are_orders()` gate: rows without the canonical order fields are routed to aggregate summary instead of a list. |
| 2 | `_is_aggregate_statement` matched `COUNT/SUM` anywhere, so `WHERE total_amount > (SELECT AVG(...))` order lists were summarized and the user never saw matches. | Classification is now projection-based: aggregate only when the top-level projection has an aggregate function and no `*`/`id`. |
| 3 | `_strip_trailing_limit` removed every `LIMIT`, including user-requested top-n ("5 đơn gần nhất") and top-n aggregates. | Only the legacy safety cap (`LIMIT 20`) is stripped; explicit limits survive. |
| 4 | `prepare_list_sql` used a DOTALL `ORDER BY` regex and bare `FROM orders` alias detection → nested/window/joined queries got the tiebreaker appended outside the query or unqualified columns (`ambiguous column name`). | Top-level `ORDER BY` detection is paren-depth aware and literal-masked; alias resolution returns `None` (leave SQL untouched) when the table is unaliased in a join; explicit LIMIT is preserved around the injected `ORDER BY`. |
| 5 | A trailing SQL comment after `LIMIT 20` left the cap in place, later producing `LIMIT ? OFFSET ?` with no bindings and an `OperationalError` the retry could not recover. | `_strip_sql_comments` removes `--`/`/* */` outside literals before parsing. |
| 6 | `;` splitting was naive: `LIKE '%';` inside a literal split the statement, and the second statement was validated but could target any table (`customers`). | Splitting uses a literal-masked scan; every part must independently start with `SELECT` and pass the forbidden-keyword check. Empty statements are rejected. |
| 7 | The shared retry prompt demanded "duy nhất một câu SELECT", so a failed MIXED retry silently dropped the aggregate half. | Retry prompt now preserves the original statement count; the single-statement path uses its own explicit rule. |
| 8 | New DB-error branches in `sch_pg`/`sch_bk` did not tolerate `BadRequest: Message is not modified`, so a double-tap raised out of the handler. | Added `_safe_edit` and used it on the new error paths. |
| 9 | `sch_bk` restored a stale saved page without clamping → empty card labelled `Trang 3/2`. | One `_total_pages` / `_clamp_page` pair used by both `sch_pg` and `sch_bk`. |
| 10 | `sch_v` with a malformed callback (`sch_v:sid:None`) raised `ValueError` outside any guard. | Parsed defensively with a user-facing fallback message. |
| 11 | `_dict_to_order` dropped `notes`, `created_by_user_id`, `created_by_name`, unlike `_row_to_order`. | All optional order fields are now mapped. |
| 12 | Ambiguous two-statement fallback discarded a statement silently. | Logged at warning level before falling back to the first statement. |

## Considered, deliberately not changed

- `count_search_results` + page fetch remain two queries. Merging into `COUNT(*) OVER ()` would reduce scans but complicates the aggregate/detail split; the shop volume is <100 orders/day.
- `_get_active_db_context` is duplicated across six handlers (pre-existing). Out of scope; changing it would touch every handler.
- Legacy in-memory pagination branch is kept for snapshots created before this change (process-local `user_data`).
- `sch_v` still reads the order fresh from the DB rather than from the snapshot — intentional, so the detail card never shows stale data.

## Second wave (line-scan angle)

| # | Defect | Fix |
|---|--------|-----|
| 13 | `_orders_alias` took the first `orders` token anywhere, so a nested `EXISTS (SELECT 1 FROM orders o ...)` leaked alias `o` into the outer query → `no such column: o.created_at`. | Alias resolution is scoped to the top-level `FROM` segment only. |
| 14 | Unaliased `FROM orders JOIN customers` produced unqualified `ORDER BY created_at` → ambiguous column. | The table name itself is the qualifier when `orders` is joined without an alias; single-table queries stay unqualified. |
| 15 | `UNION`/`INTERSECT`/`EXCEPT` got table columns appended, which are not in the compound result set. | Compound statements order by the projected `id` column only, and only when the first branch projects `id`. |
| 16 | `LIMIT 10, 5` and `LIMIT -1` were not recognised as trailing limits → `ORDER BY` injected after `LIMIT` → syntax error. | `_TRAILING_LIMIT` accepts comma and negative forms. |
| 17 | A user-requested `LIMIT 20` was indistinguishable from the legacy cap and got stripped. | The search path never appends the legacy cap, so `prepare_list_sql`/`prepare_aggregate_sql` preserve every limit verbatim. |

Not fixed (accepted): page fetches from a stored snapshot have no LLM repair path. They only fail if SQLite rejects SQL that already succeeded at search time; the clamp plus explicit error message covers it.

## Verification

- `pytest -q` → 267 passed.
- `ruff check` on the four changed files → clean.
- Runtime replay against a real SQLite file: MIXED reply (aggregate + page 1), `sch_pg` page 2 fetched from DB, out-of-range page clamped to 1/1, stale `sch_bk` page clamped, malformed `sch_v` handled, mutation fallback still returns `SELECT * FROM orders LIMIT 20`, `DROP`/`DELETE` rejected, semicolon inside a literal accepted, `LIMIT 20 -- comment` now parses and runs.
