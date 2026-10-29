---
status: complete
date: 2026-10-29
---

# Quick Task Summary: Fix Customer Search Classification & Pagination

## Objective
Fix search result routing and pagination for customer searches:
1. Prevent customer list queries with aggregates from being classified as `SearchResultType.MIXED` (order cards).
2. Support multi-page customer search navigation via `_render_customer_chooser` and `handle_customer_callback`.
3. Guard `fetch_search_page` against corrupting customer records into empty orders.

## Changes Made
- `src/services/order_search.py`:
  - Enforced `SearchResultType.CUSTOMERS` whenever list query selects customers.
  - Added `fetch_customer_search_page` for DB-backed customer list paging.
  - Guarded `fetch_search_page` so non-order rows return `[]`.
  - Added prompt rule for pure aggregate questions (`list: null`).
- `src/bot/handlers/search.py`:
  - `_render_customer_chooser` now supports `page`, `total_pages`, `total_customers`, `prefix`, and nav buttons `[◀️ Trước] [Trang X/Y] [Sau ➡️]`.
  - `process_search_query` attaches aggregate summary prefix and records pagination metadata for `CUSTOMERS`.
  - `handle_customer_callback` handles `cus_ls_pg` (customer pagination) and preserves page on `cus_bk`.
- `src/db/customers.py`:
  - Added `|\bco\s+khach\b` to `_CUSTOMER_SEARCH_PATTERN` for offline routing.
- `tests/test_customer_search.py`:
  - Added regression tests covering customer search with aggregates, summary prefix, pagination callbacks, and non-order row rejection.

## Verification
- Ran full test suite: 457 passed in 2.08s.
- Ran 10 live scenario test cases against 9router: 100% passed.
