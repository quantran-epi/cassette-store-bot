---
phase: 07-natural-language-order-mutation-pipeline
plan: 01
subsystem: mutation-pipeline
tags: [sqlite, audit-trail, intent-routing, structured-outputs, pydantic, fast-path]
requires:
  - phase: 02-core-database-customer-history-engine
    provides: orders and customers tables, OrderStatus enum
  - phase: 03-llm-order-extraction-confirmation-ux
    provides: 2-tier extractor pattern and ExtractedOrder schema
  - phase: 04-natural-language-order-search
    provides: is_search_intent and unaccent SQLite function
provides:
  - table: order_history (id, order_id, user_id, user_name, action, changes_json, created_at)
  - columns: orders.created_by_user_id, orders.created_by_name
  - model: IntentType enum (CREATE, SEARCH, MUTATE)
  - model: OrderMutationDelta Pydantic schema (5 field groups)
  - service: classify_intent, extract_order_id_from_reply, parse_fast_path_status
  - service: extract_mutation_delta (2-tier structured parse)
  - db: find_orders_for_mutation (active-first resolver), record_order_history
affects:
  - src/models/order.py
  - src/models/mutation.py
  - src/db/schema.py
  - src/db/orders.py
  - src/services/intent_router.py
  - src/services/mutation_extractor.py
tech-stack:
  added: []
  patterns:
    - active-first order lookup prioritizing non-terminal lifecycle states
    - 3-way regex fast-path router with lightweight 5-token LLM fallback
    - 2-tier Pydantic structured output extractor with json_object fallback
    - idempotent column migration and audit trail insertion
key-files:
  created:
    - src/models/mutation.py
    - src/services/intent_router.py
    - src/services/mutation_extractor.py
    - tests/test_order_audit_trail.py
    - tests/test_intent_router.py
    - tests/test_mutation_extractor.py
  modified:
    - src/models/order.py
    - src/db/schema.py
    - src/db/orders.py
decisions:
  - "D-01/D-03/D-04: Intent classification combines zero-latency regex prefixes, reply context, and 5-token LLM fallback."
  - "D-05: Reply order ID regex extracts parent order ID directly from replied bot cards."
  - "D-06: Fast-path regex converts short status commands into order_id + target_status in 0ms."
  - "D-07: find_orders_for_mutation prioritizes active states (CHO_LAM to SHIPPER_DA_LAY) before terminal states."
  - "D-16: order_history table records all lifecycle and mutation changes with user attribution."
metrics:
  duration: 4m
  completed_date: "2026-10-25"
  tasks_completed: 3
  files_changed: 9
---

# Phase 07 Plan 01: Audit Migration, Domain Models, 3-Way Intent Router & Delta Extractor Summary

Core persistence migration, domain models, 3-Way Intent Router, and 2-Tier LLM Delta Extractor foundation for Vietnamese natural language order mutations.

## Performance & Architecture

- **0ms Regex Fast-Paths**: Short status commands ("huỷ đơn 12", "đơn 12 đã giao", "đã đóng gói đơn 15") and reply context resolve to mutation targets without calling external LLM APIs.
- **Active-First Resolution**: `find_orders_for_mutation` queries active operational orders (`CHO_LAM` through `SHIPPER_DA_LAY`) before checking completed or cancelled orders.
- **Full Audit Traceability**: `order_history` captures every action (`CREATE`, `MUTATE`, `STATUS_CHANGE`, `TRACKING_UPDATE`) with actor ID, actor name, timestamp, and field diffs in JSON format.
- **Dual-Tier Mutation Extraction**: `extract_mutation_delta` attempts strict `beta.chat.completions.parse` with `OrderMutationDelta` and falls back automatically to `response_format={"type": "json_object"}`.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Column introspection compatibility with tuple row factories**
- **Found during:** Running full test suite after Task 3
- **Issue:** `test_security.py` initializes a bare SQLite connection without setting `db.row_factory = aiosqlite.Row`, causing `row["name"]` in `init_db` to raise `TypeError: tuple indices must be integers or slices, not str`.
- **Fix:** Switched `row["name"]` to `row[1]` in `src/db/schema.py`, which is valid for both plain tuples and `aiosqlite.Row`.
- **Files modified:** `src/db/schema.py`
- **Commit:** `0d98cc3`

## Key Decisions Made

- Added `created_by_user_id` and `created_by_name` to `Order` domain model and schema with idempotent column addition on startup.
- Configured `OrderMutationDelta` to cover all 5 required field groups (Status, Tracking, Notes, Money, Customer/Shipping) with 10-digit phone normalization.
- Prioritized `MUTATE` intent over `CREATE` when ambiguous text contains both mutation keywords and customer phone numbers.

## Verification

All 15 plan tests and all 192 total project tests pass:
```bash
./.venv/bin/pytest tests/test_order_audit_trail.py tests/test_intent_router.py tests/test_mutation_extractor.py -v
```

## Self-Check: PASSED

- Created files exist:
  - `src/models/mutation.py`: FOUND
  - `src/services/intent_router.py`: FOUND
  - `src/services/mutation_extractor.py`: FOUND
  - `tests/test_order_audit_trail.py`: FOUND
  - `tests/test_intent_router.py`: FOUND
  - `tests/test_mutation_extractor.py`: FOUND
- Task commits verified:
  - `01e7374`: feat(07-01): order audit trail migration and active-first search
  - `b670048`: feat(07-01): 3-way intent router with fast-path status and reply context
  - `0d98cc3`: feat(07-01): pydantic mutation delta schema and 2-tier llm extractor
