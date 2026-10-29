# Quick Plan: Fix Customer Search Classification & Pagination

## Objective
Fix search result routing and pagination for customer searches:
1. Classification bug: When a customer query has aggregates (e.g. "có khách nào ở Thái Nguyên/Quảng Ninh không?"), `_execute_search_plan` classified it as `SearchResultType.MIXED`. The bot handled `MIXED` as an order list card, resulting in "tìm thấy X đơn hàng" with an empty page 1, and page 2 converting customer rows into bogus orders.
2. Pagination bug: Customer search had no pagination in `_render_customer_chooser`, making results beyond page 1 inaccessible.
3. Fallback pattern: Update customer search intent regex to include `co khach`.

## Proposed Changes

### 1. `src/services/order_search.py`
- In `_execute_search_plan`:
  Ensure any list query that targets `customers` produces `SearchResultType.CUSTOMERS` (even when aggregate queries are also present with `summary_text`).
- Guard `fetch_search_page`:
  If rows do not match order schema, return `[]` instead of converting customer rows into bogus `Order` objects.
- Add `fetch_customer_search_page`:
  Paginate customer list queries safely from the DB returning `list[Customer]`.

### 2. `src/bot/handlers/search.py`
- In `_render_customer_chooser`:
  Support `page`, `total_pages`, `total_customers`, `prefix`.
  Add navigation buttons `cus_ls_pg:{search_id}:{page}` when `total_pages > 1`.
- In `process_search_query`:
  Route `SearchResultType.CUSTOMERS` with `_summary_prefix(result)` and full pagination state in `customer_searches`.
- In `handle_customer_callback`:
  Handle `cus_ls_pg` for paginating customer results.
  Update `cus_bk` to restore the exact customer page.

### 3. `src/db/customers.py`
- Add `|\bco\s+khach\b` to `_CUSTOMER_SEARCH_PATTERN`.

### 4. Tests
- Add tests in `tests/test_customer_search.py` verifying customer search with aggregates produces `SearchResultType.CUSTOMERS`, renders customer chooser with summary, and supports pagination.
