---
phase: 01-foundation-persistence-security-whitelist
plan: "01"
subsystem: security-and-configuration
tags:
  - pydantic-settings
  - python-telegram-bot
  - security
  - whitelist
requires: []
provides:
  - pyproject.toml project build configuration
  - src/config.py fail-fast settings loader
  - src/bot/security.py whitelist gate middleware
  - src/bot/app.py application factory
  - src/bot/handlers/base.py start and ping commands
affects:
  - 01-02-PLAN.md
  - phase-2
tech-stack:
  added:
    - python-telegram-bot~=22.8
    - pydantic-settings~=2.16.1
    - aiosqlite~=0.22.1
    - openai~=3.37.0
    - pytest-asyncio>=0.24.0
    - ruff>=0.9.0
  patterns:
    - Group -1 TypeHandler security gate halting with ApplicationHandlerStop
    - Fail-fast Pydantic BaseSettings with SecretStr masking
    - CommaOrJsonEnvSettingsSource custom env source for list[int] parsing
key-files:
  created:
    - pyproject.toml
    - .env.example
    - .gitignore
    - src/__init__.py
    - src/config.py
    - src/bot/__init__.py
    - src/bot/security.py
    - src/bot/handlers/__init__.py
    - src/bot/handlers/base.py
    - src/bot/app.py
    - tests/__init__.py
    - tests/test_config.py
    - tests/test_security.py
  modified: []
decisions:
  - "Custom CommaOrJsonEnvSettingsSource in Settings allows comma-separated integers in TELEGRAM_WHITELIST_USER_IDS without JSON decode failure"
  - "Security whitelist gate registered at group -1 with TypeHandler(Update) intercepting stranger requests and halting execution via ApplicationHandlerStop"
metrics:
  duration: 12m
  completed_date: "2026-10-24"
---

# Phase 01 Plan 01: Project Scaffold, Settings & Whitelist Security Gate Summary

Project scaffold, environment settings loader with SecretStr masking, and Telegram bot application factory with an access control whitelist security gate running at Handler Group -1.

## What Was Done

1. **Project Scaffold & Build Configuration**:
   - Declared core runtime dependencies (`python-telegram-bot~=22.8`, `aiosqlite~=0.22.1`, `pydantic~=2.14.1`, `pydantic-settings~=2.16.1`, `openai~=3.37.0`) and dev tools (`pytest`, `pytest-asyncio`, `ruff`) in `pyproject.toml`.
   - Added `.gitignore` and `.env.example` defining all required bot, LLM gateway, and DB settings.

2. **Settings Module (`src/config.py`)**:
   - Implemented `Settings` using Pydantic-Settings v2 with `SecretStr` for `telegram_bot_token` and `nine_router_api_key`.
   - Supported comma-separated user ID strings (`"123, 456"`), JSON arrays (`"[123, 456]"`), and lists via `CommaOrJsonEnvSettingsSource` and `@field_validator("telegram_whitelist_user_ids", mode="before")`.
   - Set sensible defaults for `sqlite_db_path`, `nine_router_base_url`, and `nine_router_model_id`.

3. **Whitelist Security Gate (`src/bot/security.py`)**:
   - Intercepts updates at Handler Group `-1` using `TypeHandler(Update, whitelist_gate)`.
   - Checks `update.effective_user.id` against the configured in-memory whitelist set.
   - For unauthorized users: replies with a polite Vietnamese refusal showing their Telegram User ID (both for messages and inline callback buttons) and halts downstream handlers via `raise ApplicationHandlerStop()`.
   - Halts updates lacking an effective user.

4. **Bot Factory & Base Handlers (`src/bot/app.py`, `src/bot/handlers/base.py`)**:
   - Created `build_application(settings)` registering the whitelist gate at group `-1` and `/start` and `/ping` commands at group `0`.
   - Configured `bot_data` with settings and `whitelist_user_ids` set.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] EnvSettingsSource JSON decode error on comma-separated string**
- **Found during:** Task 1 GREEN step
- **Issue:** Pydantic-Settings v2 default `EnvSettingsSource` attempts `json.loads` on complex types like `list[int]` before running `field_validator`, raising `json.decoder.JSONDecodeError` on `"123, 456, 789"`.
- **Fix:** Subclassed `EnvSettingsSource` to catch `ValueError` in `decode_complex_value` and return the raw string value to the field validator.
- **Files modified:** `src/config.py`
- **Commit:** `dce0b48` & `b2d4c8b`

## Verification Evidence

All 12 automated unit tests passed:
```
tests/test_config.py::test_settings_loads_comma_separated_whitelist PASSED
tests/test_config.py::test_settings_loads_json_array_whitelist PASSED
tests/test_config.py::test_settings_requires_telegram_bot_token PASSED
tests/test_config.py::test_secrets_masked_in_str_and_repr PASSED
tests/test_config.py::test_settings_defaults PASSED
tests/test_security.py::test_whitelist_gate_allows_whitelisted_user PASSED
tests/test_security.py::test_whitelist_gate_rejects_stranger_message PASSED
tests/test_security.py::test_whitelist_gate_rejects_stranger_callback PASSED
tests/test_security.py::test_whitelist_gate_stops_on_none_user PASSED
tests/test_security.py::test_start_command_replies_welcome PASSED
tests/test_security.py::test_ping_command_replies_pong PASSED
tests/test_security.py::test_build_application_registers_gate_at_group_minus_one PASSED
```
Linter check: `ruff check src tests` passed with 0 errors.

## Self-Check: PASSED
- `src/config.py`: FOUND
- `src/bot/security.py`: FOUND
- `src/bot/app.py`: FOUND
- `src/bot/handlers/base.py`: FOUND
- `tests/test_config.py`: FOUND
- `tests/test_security.py`: FOUND
- Commit `dce0b48`: FOUND
- Commit `b2d4c8b`: FOUND
