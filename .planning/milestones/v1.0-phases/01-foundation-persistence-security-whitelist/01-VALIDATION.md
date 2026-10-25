# Phase 1: Foundation, Persistence & Security Whitelist - Validation Strategy

**Generated:** 2026-10-24
**Phase:** 01-foundation-persistence-security-whitelist
**Status:** Approved

## Test Framework & Harness

| Property | Value |
|----------|-------|
| Test Runner | `pytest` |
| Async Plugin | `pytest-asyncio` (`asyncio_mode = "auto"`) |
| Lint & Formatting | `ruff check .` |
| Test Execution Mode | Fast, local-only, zero network dependencies |
| Database Backend for Tests | SQLite in-memory (`sqlite:///:memory:` via `aiosqlite`) |
| Telegram Interaction Mock | PTB mock fixtures (`Update`, `User`, `Message`, `CallbackQuery`, `ContextTypes.DEFAULT_TYPE`) |

## Command Reference

- Quick suite run: `pytest tests/ -q`
- Detailed suite run: `pytest tests/ -v`
- Lint check: `ruff check .`
- Plan 01-01 check: `pytest tests/test_config.py tests/test_security.py -v`
- Plan 01-02 check: `pytest tests/test_db_customers.py -v`
- Plan 01-03 check: `pytest tests/test_db_orders.py tests/test_e2e_ping.py -v`

## Requirement to Test Map

| Requirement | Target Component | Test File | Test Case Name | Pass Criteria |
|-------------|------------------|-----------|----------------|---------------|
| **CFG-01** | `src/config.py` (`Settings`) | `tests/test_config.py` | `test_settings_load_env`, `test_whitelist_csv_parser`, `test_secret_masking` | Settings load correctly from env variables; comma-separated IDs parsed to `list[int]`; `SecretStr` masks bot token. |
| **SEC-01** | `src/bot/security.py` (`whitelist_gate`) | `tests/test_security.py` | `test_whitelisted_user_allowed`, `test_non_whitelisted_user_blocked_with_id_message`, `test_callback_query_blocked` | Whitelisted users pass through gate; non-whitelisted users receive denial with their user ID and `ApplicationHandlerStop` is raised. |
| **DATA-01** | `src/db/customers.py`, `src/models/customer.py` | `tests/test_db_customers.py` | `test_customer_create_and_get`, `test_customer_multi_phones_and_addresses` | Customer saved and retrieved with `phones` and `addresses` as JSON arrays; updates persist correctly. |
| **DATA-02** | `src/db/orders.py`, `src/models/order.py` | `tests/test_db_orders.py` | `test_order_create_snapshot_and_get`, `test_order_tracking_and_amounts` | Order snapshot captures customer name/phone/address, free text items, total amount, COD amount, payment method, tracking code. |
| **DATA-03** | `src/models/order.py` (`OrderStatus`), `src/db/schema.py` | `tests/test_db_orders.py` | `test_order_status_transitions`, `test_order_invalid_status_db_constraint` | 8 order statuses supported; DB check constraint rejects invalid status strings. |
| **DATA-04** | `src/db/orders.py` | `tests/test_db_orders.py` | `test_order_photos_append_and_retrieve` | `photo_file_ids` stores array of Telegram `file_id`s in JSON; supports appending new photos to existing orders. |

## Nyquist Quality Gates

1. **Per-Task Verification**: Mỗi task hoàn thành phải chạy bộ test tương ứng và pass 100%.
2. **Per-Plan Verification**: Kết thúc mỗi plan, toàn bộ unit & integration tests liên quan phải pass.
3. **Phase-End Verification**: Chạy toàn bộ test suite `pytest tests/ -v` đạt 100% pass với thời gian thực thi < 5 giây (nhờ SQLite in-memory và mock).
