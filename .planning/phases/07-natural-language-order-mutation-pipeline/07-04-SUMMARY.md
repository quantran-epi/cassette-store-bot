# Phase 7 Plan 4: Generalized Order Matching Gap Closure Summary

**Subsystem:** Order Mutation Pipeline & Intelligent Order Discovery
**Tags:** `mutation`, `search`, `word-match`, `sqlite-custom-function`, `nlp-fallback`, `gap-closure`
**Requires:** `07-01`, `07-02`, `07-03`
**Provides:** Strict word boundary matching and multi-field token resolution for order mutations with Text-to-SQL fallback
**Affects:** `src/db/connection.py`, `src/db/orders.py`, `src/services/mutation_extractor.py`, `src/bot/handlers/mutation.py`, `tests/test_mutation_search_general.py`

## Objective & One-Liner

Unified order discovery engine for Order Mutation that eliminates substring false positives (e.g. "Hà" matching "Thanh") via custom SQLite `word_match` and resolves composite multi-field queries ("anh Tuấn Gia Lâm", "đơn Chế Linh Đà Nẵng") with active-order priority and Text-to-SQL fallback.

## Key Changes Made

1. **Word-Boundary Matching via Custom SQLite Function (`src/db/connection.py`)**:
   - Registered `word_match(haystack, needle)` custom SQLite function on all async database connections.
   - Evaluates Vietnamese unaccented whole-word regex boundaries (`\bneedle\b`) with `re.escape()` to prevent regex injection and substring collisions (e.g., "Hà" never matches "Thanh", "Hải", "Thảo").

2. **Generalized Multi-Token Search (`src/db/orders.py`)**:
   - Implemented `find_orders_by_multi_token` and upgraded `find_orders_for_mutation`.
   - Concatenates composite fields: `customer_name || ' ' || customer_phone || ' ' || shipping_address || ' ' || items_text || ' ' || COALESCE(notes, '')`.
   - Strips conversational prefix fillers (`khach`, `don`, `cua`, `cho`, `giao`).
   - Evaluates every substantive token with `AND` logic using `word_match = 1` or phone `LIKE %token%`.
   - Enforces active status prioritization (`CHO_LAM` .. `SHIPPER_DA_LAY` before terminal states `DA_GIAO`, `BOM_HANG`, `HUY_DON`).

3. **Composite Identifier Extraction Prompt (`src/services/mutation_extractor.py`)**:
   - Refined `MUTATION_SYSTEM_PROMPT` for `target_customer_keyword` to preserve composite entities (names, districts, artists, items) without truncation.

4. **Text-to-SQL Search Fallback (`src/bot/handlers/mutation.py`)**:
   - When `find_orders_for_mutation` yields 0 matches for a natural language keyword and OpenAI client is configured, triggers `execute_natural_language_search` from Phase 4 scoped with active-status filter (`đang xử lý hoặc chưa giao`).
   - Converts returned matching order records to `Order` domain models, seamlessly transitioning into visual diff card or disambiguation buttons.

5. **Automated Test Coverage (`tests/test_mutation_search_general.py`)**:
   - Created test suite covering word boundary isolation, composite multi-field queries, active status priority, prompt instructions, and Text-to-SQL fallback flow.

## Verification

Full Phase 7 automated test suites run cleanly (47 passed in 0.37s):
```bash
./.venv/bin/pytest tests/test_mutation_search_general.py tests/test_mutation_card_and_lock.py tests/test_mutation_extractor.py tests/test_mutation_handler_flow.py tests/test_intent_router.py tests/test_order_audit_trail.py -v
```

## Deviations from Plan

None - plan executed exactly as written.

## Threat Flags

None identified. No new external endpoints or package installations. Regex boundary evaluation uses `re.escape()` to mitigate DoS (T-07-07).

## Self-Check: PASSED
- [x] `src/db/connection.py` registered `word_match`
- [x] `src/db/orders.py` exports `find_orders_for_mutation` and `find_orders_by_multi_token`
- [x] `src/services/mutation_extractor.py` extracts composite entities
- [x] `src/bot/handlers/mutation.py` integrates Text-to-SQL fallback
- [x] `tests/test_mutation_search_general.py` created and passing
- [x] Commits 67c563f and 4d18e44 verified in git log
