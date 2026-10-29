# Quick Plan: Unify Natural Language Search under Text-to-SQL for Customers & Orders

## Objective
Unify all natural language searches (orders, customers, and analytics) under a single, robust Text-to-SQL pipeline.
Resolve:
1. Multi-word customer name searches failing when searching orders ("tìm đơn của xxx" with spaces).
2. Customer search muddling fields ("tìm khách tên lâm ở hà nội" returning non-Lâm customers who live in Gia Lâm).
3. Field recognition and multi-field combination (name + address + items + phone + date).

## Proposed Changes

### 1. `src/services/order_search.py`
- Add `SearchResultType.CUSTOMERS = "CUSTOMERS"` to `SearchResultType`.
- Add `customers: list[Customer] = field(default_factory=list)` to `SearchResult`.
- Update `SYSTEM_PROMPT_SEARCH_PLAN_TEMPLATE` and `SQL_DOMAIN_RULES`:
  - Teach schema: `customers` (id, name, phones, addresses, notes, created_at) and `orders`.
  - Distinguish customer lookups vs order lookups:
    - If user asks for customer profiles/info (e.g., "tìm khách tên X ở Y", "thông tin khách X", "tìm số điện thoại của anh Nam"): list query must SELECT from `customers c` (`SELECT c.* FROM customers c WHERE ... ORDER BY c.id DESC`).
    - If user asks for orders (e.g., "tìm đơn...", "đơn anh Kiên", "hôm nay bán gì"): list query must SELECT from `orders o` (`SELECT o.* FROM orders o ...`).
  - Explicit field boundary recognition:
    - "tên X" / "anh/chị/bác X" -> filter strictly on `name` / `customer_name`. NEVER match name keyword on address or notes.
    - "ở Y" / "tại Y" / "địa chỉ Y" / "gửi về Y" -> filter strictly on `addresses` / `shipping_address`.
    - "SĐT / số điện thoại W" -> filter strictly on `phones` / `customer_phone`.
    - "băng Z / ca sĩ Z / thể loại Z" -> filter strictly on `items_text` / `tape_artist_json` / `tape_genre_json`.
    - Combine fields with `AND`.
  - Multi-word & honorific handling for names:
    - Strip conversational honorifics (`anh`, `chị`, `bác`, `ông`, `bà`, `cô`, `chú`, `em`).
    - For multi-word names (e.g., "Nguyễn Văn Lâm", "Tuấn Thắm"), use tokenized AND conditions:
      `unaccent(customer_name) LIKE '%nguyen%' AND unaccent(customer_name) LIKE '%lam%'`
      so intervening words, nicknames, or abbreviations still match.
- Update `prepare_list_sql`:
  - Support both `orders` and `customers` tables (alias `c` or `customers` -> order by `created_at DESC, id DESC` or `id DESC`).
- Update `_execute_search_plan`:
  - Detect whether list query returned `orders` or `customers`.
  - If columns include `phones` or `addresses` (customer model), hydrate into `Customer` objects and set `result_type = SearchResultType.CUSTOMERS`.
  - If columns include `items_text` / `total_amount` (order model), hydrate into `Order` objects and set `result_type = SearchResultType.ORDERS`.

### 2. `src/bot/handlers/search.py`
- In `process_search_query`:
  - Pass all search intents (`CUSTOMER_PROFILE`, `ORDER_SEARCH`, `CUSTOMER_ANALYTICS`) through `run_order_search`.
  - Handle `result.result_type == SearchResultType.CUSTOMERS`:
    - If 1 customer found -> render `_render_customer_detail`.
    - If multiple customers found -> render `_render_customer_chooser`.
    - If 0 customers found -> render `_render_customer_empty_card`.
  - Keep deterministic `search_customers` as fallback only if OpenAI client is unavailable or fails.

### 3. Tests
- Update/add tests in `tests/test_order_search.py` and `tests/test_customer_search.py`:
  - Test "tìm khách tên lâm ở hà nội" -> filters `c.name` and `c.addresses`, excludes customer named khác with address Gia Lâm.
  - Test "tìm đơn của anh Kiên" / multi-word customer names with spaces -> matches order with customer name "Anh Kiên" and "Kiên".
  - Test combined search queries (name + address + items).

## Verification
- Run `pytest tests/test_order_search.py tests/test_customer_search.py tests/test_search_mixed_pagination.py`.
- Run real LLM evaluation against 9router with specific test queries.
