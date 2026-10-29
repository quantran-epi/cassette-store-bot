---
status: complete
quick_id: 261029-qye
slug: unify-natural-language-search-under-text
created: 2026-10-29
completed: 2026-10-29
---

# Quick Task Summary: Unify Natural Language Search under Text-to-SQL

## Accomplished
1. **Unified Text-to-SQL Search Engine**:
   - Upgraded `src/services/order_search.py` to support querying both `orders` and `customers` seamlessly within JSON query plans (`list` and `aggregates`).
   - Added `SearchResultType.CUSTOMERS` and customer hydration to `SearchResult`.
   - Updated `prepare_list_sql` to inject stable `ORDER BY` for both `orders` and `customers`.
2. **Fixed Name Matching with Spaces & Honorifics ("tìm đơn của xxx")**:
   - Instructed LLM to strip conversational honorifics (`anh`, `chị`, `bác`, `ông`, `bà`, `cô`, `chú`, `em`).
   - Enforced tokenized `AND` matching for multi-word names (`unaccent(customer_name) LIKE '%part1%' AND unaccent(customer_name) LIKE '%part2%'`), avoiding exact contiguous substring failures due to missing middle names or irregular spacing.
   - Enforced `LEFT JOIN customers c ON c.id = o.customer_id` to match both order snapshots and customer master profile.
3. **Fixed Field Isolation & Multi-field Combination ("tìm khách tên lâm ở hà nội")**:
   - Replaced bypass in `process_search_query` so natural language customer searches now leverage Text-to-SQL.
   - Enforced strict field boundary rules: person names match only `c.name` / `o.customer_name` (never addresses), places match only `c.addresses` / `o.shipping_address`.
   - Improved deterministic `search_customers` fallback to recognize slot cues (`tên`, `ở`, `tại`).
4. **Enhanced Mutation Target Isolation**:
   - Updated `MUTATION_TARGET_SEARCH_PROMPT` in `src/services/mutation_extractor.py` to align with the tokenized name matching and customer join rules.

## Verification
- `pytest tests/` passed all 456 tests cleanly.
- End-to-end live testing with 9router (`ag/gemini-3.8-flash`):
  - `tìm khách tên lâm ở hà nội` -> matched only customer named Lâm, excluded customer named Tuấn living in Gia Lâm.
  - `tìm đơn của anh Kiên` -> matched order for customer "Kiên" after honorific stripping.
  - `tìm đơn của Tuấn Thắm` -> matched order for customer "Tuấn Thắm" via tokenized AND.
  - `tìm đơn của Nguyễn Lâm` -> matched order for customer "Nguyễn Văn Lâm".
  - `đơn chuyển khoản ở Hải Phòng` -> multi-field combination query succeeded.
  - `đổi sđt khách anh Kiên thành 0912345678` -> mutation search correctly matched target order.
