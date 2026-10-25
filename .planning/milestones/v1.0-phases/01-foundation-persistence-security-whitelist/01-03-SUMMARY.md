---
phase: 01-foundation-persistence-security-whitelist
plan: "03"
subsystem: order-persistence-and-e2e-skeleton
tags:
  - orders
  - sqlite
  - domain-model
  - walking-skeleton
  - telegram-bot
requires:
  - "01-01"
  - "01-02"
provides:
  - src/models/order.py OrderStatus enum and Order domain model
  - src/db/orders.py order CRUD, status lifecycle, and photo management
  - src/db/schema.py orders table DDL with CHECK constraint
  - src/bot/handlers/base.py database health check integration in /ping
  - main.py root application entrypoint
affects:
  - phase-2
  - phase-3
tech-stack:
  added: []
  patterns:
    - 8-state OrderStatus enum enforced at Python domain level and SQLite CHECK constraint
    - Snapshot persistence of customer name, phone, and address into orders table
    - Telegram photo file_ids serialized as SQLite JSON arrays
    - Asynchronous SELECT 1 probe with 5s timeout in bot /ping handler
key-files:
  created:
    - src/models/order.py
    - src/db/orders.py
    - main.py
    - tests/test_db_orders.py
    - tests/test_e2e_ping.py
  modified:
    - src/db/schema.py
    - src/bot/handlers/base.py
decisions:
  - "Enforce 8 order lifecycle states (CHO_LAM, DANG_LAM, DA_DONG_GOI, DA_TAO_DON, SHIPPER_DA_LAY, DA_GIAO, BOM_HANG, HUY_DON) both at Pydantic layer and SQLite CHECK constraint level"
  - "Store customer snapshot (customer_name, customer_phone, shipping_address) in order record for immutable historical order integrity"
  - "Serialize photo_file_ids as JSON array to allow multiple Telegram photos per order with append support"
  - "Execute SELECT 1 DB probe with 5s timeout during /ping to ensure non-blocking health check"
metrics:
  duration: 10m
  completed_date: "2026-10-24"
---

# Phase 01 Plan 03: Order Domain Model, Schema & Walking Skeleton Verification Summary

Order domain model with 8-state lifecycle enum and customer snapshot persistence, SQLite schema with CHECK constraints, Telegram photo JSON array attachments, end-to-end DB health check in `/ping`, and executable `main.py` entrypoint completing the Walking Skeleton.

## What Was Done

1. **Order Domain Model & Lifecycle Enum (`src/models/order.py`)**:
   - Implemented `OrderStatus(str, Enum)` with 8 states: `CHO_LAM`, `DANG_LAM`, `DA_DONG_GOI`, `DA_TAO_DON`, `SHIPPER_DA_LAY`, `DA_GIAO`, `BOM_HANG`, `HUY_DON` per DATA-03 and D-06.
   - Implemented `Order(BaseModel)` storing customer snapshot (`customer_name`, `customer_phone`, `shipping_address`), items text, `total_amount`, `cod_amount`, `payment_method`, `tracking_code`, `photo_file_ids` list, and timestamps per DATA-02 and DATA-04.

2. **Database Schema & Order Repository (`src/db/schema.py`, `src/db/orders.py`)**:
   - Updated `orders` table DDL with `CHECK (status IN (...))` constraint, foreign key to `customers(id) ON DELETE SET NULL`, and indexes on `customer_id`, `status`, and `created_at`.
   - Implemented `create_order`, `get_order_by_id`, `update_order_status`, `update_order_tracking`, `append_order_photos`, and `list_orders_by_status`.

3. **E2E /ping DB Health Probe & Root Entrypoint (`src/bot/handlers/base.py`, `main.py`)**:
   - Enhanced `/ping` to query `SELECT 1` on the SQLite database with a 5.0s timeout, replying with `"🏓 Pong!\nBot: Running\nDatabase: OK (WAL mode)"` or graceful error handling.
   - Built `main.py` executing `init_database(settings.sqlite_db_path)` schema creation and launching `app.run_polling()`.

## Deviations from Plan

None - plan executed exactly as written.

## Verification Evidence

All 35 automated tests passing:
```
tests/test_config.py::test_settings_loads_comma_separated_whitelist PASSED [  2%]
tests/test_config.py::test_settings_loads_json_array_whitelist PASSED    [  5%]
tests/test_config.py::test_settings_requires_telegram_bot_token PASSED   [  8%]
tests/test_config.py::test_secrets_masked_in_str_and_repr PASSED         [ 11%]
tests/test_config.py::test_settings_defaults PASSED                      [ 14%]
tests/test_db_customers.py::test_connection_pragmas_and_row_factory PASSED [ 17%]
tests/test_db_customers.py::test_connection_closes_after_context_manager PASSED [ 20%]
tests/test_db_customers.py::test_init_db_creates_customers_schema PASSED [ 22%]
tests/test_db_customers.py::test_customer_model_instantiation PASSED     [ 25%]
tests/test_db_customers.py::test_create_and_get_customer_roundtrip PASSED [ 28%]
tests/test_db_customers.py::test_get_customer_by_id_not_found PASSED     [ 31%]
tests/test_db_customers.py::test_get_customer_by_phone PASSED            [ 34%]
tests/test_db_customers.py::test_update_customer PASSED                  [ 37%]
tests/test_db_customers.py::test_update_customer_non_existent PASSED     [ 40%]
tests/test_db_customers.py::test_list_customers PASSED                   [ 42%]
tests/test_db_orders.py::test_order_status_enum_values PASSED            [ 45%]
tests/test_db_orders.py::test_order_domain_model_defaults PASSED         [ 48%]
tests/test_db_orders.py::test_create_and_get_order_roundtrip PASSED      [ 51%]
tests/test_db_orders.py::test_order_status_db_check_constraint PASSED    [ 54%]
tests/test_db_orders.py::test_update_order_status PASSED                 [ 57%]
tests/test_db_orders.py::test_update_order_tracking PASSED               [ 60%]
tests/test_db_orders.py::test_append_and_get_photos PASSED               [ 62%]
tests/test_db_orders.py::test_append_photos_to_empty PASSED              [ 65%]
tests/test_db_orders.py::test_list_orders_by_status PASSED               [ 68%]
tests/test_db_orders.py::test_get_non_existent_order PASSED              [ 71%]
tests/test_e2e_ping.py::test_ping_command_db_ok PASSED                   [ 74%]
tests/test_e2e_ping.py::test_ping_command_db_error PASSED                [ 77%]
tests/test_e2e_ping.py::test_main_module_importable PASSED               [ 80%]
tests/test_security.py::test_whitelist_gate_allows_whitelisted_user PASSED [ 82%]
tests/test_security.py::test_whitelist_gate_rejects_stranger_message PASSED [ 85%]
tests/test_security.py::test_whitelist_gate_rejects_stranger_callback PASSED [ 88%]
tests/test_security.py::test_whitelist_gate_stops_on_none_user PASSED    [ 91%]
tests/test_security.py::test_start_command_replies_welcome PASSED        [ 94%]
tests/test_security.py::test_ping_command_replies_pong PASSED            [ 97%]
tests/test_security.py::test_build_application_registers_gate_at_group_minus_one PASSED [100%]
```
Linter check: `ruff check src tests` passed with 0 errors.

## Self-Check: PASSED
- `src/models/order.py`: FOUND
- `src/db/orders.py`: FOUND
- `src/db/schema.py`: FOUND
- `src/bot/handlers/base.py`: FOUND
- `main.py`: FOUND
- `tests/test_db_orders.py`: FOUND
- `tests/test_e2e_ping.py`: FOUND
- Commit `d6c5ee8`: FOUND
- Commit `f6bedb4`: FOUND
