---
phase: 05-role-based-access-control-telegram-admin-suite
plan: 01
subsystem: rbac-security-persistence
tags: [rbac, security, logging, sqlite, ptb]
requires: []
provides:
  - "admin_users and system_settings SQLite tables with role constraints"
  - "Immutable root Super Admin protection via .env settings"
  - "@require_role dual-dispatch decorator for commands and callbacks"
  - "RingBufferLogHandler thread-safe logging sink with HTML escaping"
affects:
  - src/config.py
  - src/db/schema.py
  - src/db/admin.py
  - src/db/settings.py
  - src/bot/security.py
  - src/bot/logging_handler.py
tech-stack:
  added: []
  patterns:
    - "Dual-dispatch security decorator inspecting context.bot_data['admin_roles']"
    - "aiosqlite UPSERT ON CONFLICT persistence for role and settings sync"
    - "collections.deque thread-safe bounded buffer for runtime log capture"
key-files:
  created:
    - src/db/admin.py
    - src/db/settings.py
    - src/bot/logging_handler.py
    - tests/test_admin_db.py
    - tests/test_security_rbac.py
    - tests/test_logging_buffer.py
  modified:
    - src/config.py
    - src/db/schema.py
    - src/bot/security.py
decisions:
  - "Root Super Admin ID configured in .env is immutable against deletion or demotion"
  - "Security decorator @require_role raises alert popups for CallbackQuery and HTML messages for commands"
  - "RingBufferLogHandler sanitizes all log outputs using html.escape and truncates earlier lines if exceeding 3800 chars"
metrics:
  duration: 4m
  completed_date: "2026-10-25"
  tasks_completed: 3
  files_created: 6
  files_modified: 3
---

# Phase 05 Plan 01: RBAC Foundation, Persistence & Ring Buffer Logging Summary

Built the persistence, security, and logging foundation for Role-Based Access Control (RBAC). Established the dual-tier role model (`SUPER_ADMIN` and `ADMIN`), immutable root authority guard via `.env`, the `@require_role` dual-dispatch decorator for commands and inline callbacks, and a thread-safe in-memory ring buffer logging handler.

## Accomplishments

1. **Schema & Persistence Services**:
   - Added `telegram_super_admin_id: int | None = None` to `Settings` in `src/config.py`.
   - Created SQLite DDL for `admin_users` (with role CHECK constraint `'SUPER_ADMIN', 'ADMIN', 'STAFF'`) and `system_settings` key-value table in `src/db/schema.py`.
   - Implemented `src/db/admin.py` with `create_or_update_admin_user`, `get_admin_user`, `list_admin_users`, `delete_admin_user` (protecting root Super Admin from deletion/demotion with `PermissionError`), and `sync_root_super_admin`.
   - Implemented `src/db/settings.py` providing string and JSON setting retrieval/persistence.

2. **Hierarchical RBAC Security Decorator**:
   - Defined `UserRole` StrEnum and `ROLE_HIERARCHY` mapping in `src/bot/security.py`.
   - Implemented `get_user_role` resolving from `context.bot_data["admin_roles"]` with default fallback to `STAFF`.
   - Implemented `@require_role(min_role)` handling dual-dispatch:
     - For `CallbackQuery`: answers with `show_alert=True` pop-up stating required role.
     - For commands/messages: replies with polite HTML-formatted refusal stating minimum required role.

3. **In-Memory Ring Buffer Logging Handler**:
   - Created `RingBufferLogHandler(logging.Handler)` in `src/bot/logging_handler.py` backed by `collections.deque(maxlen=capacity)`.
   - Supported filtering by log level (`errors_only=True` returning WARNING, ERROR, CRITICAL).
   - Sanitized all messages via `html.escape` to prevent Telegram HTML parse errors.
   - Implemented `format_logs_for_telegram` truncating earlier entries with a notice prefix when exceeding 3800 chars.

4. **TDD Coverage**:
   - Added unit and integration tests across `tests/test_admin_db.py`, `tests/test_security_rbac.py`, and `tests/test_logging_buffer.py`.
   - All 16 new tests passing, total test suite: 126 passed.

## Deviations from Plan

None - plan executed exactly as written.

## Known Stubs

None - all methods and queries are fully implemented.

## Self-Check: PASSED

- FOUND: src/config.py
- FOUND: src/db/schema.py
- FOUND: src/db/admin.py
- FOUND: src/db/settings.py
- FOUND: src/bot/security.py
- FOUND: src/bot/logging_handler.py
- FOUND: tests/test_admin_db.py
- FOUND: tests/test_security_rbac.py
- FOUND: tests/test_logging_buffer.py
- FOUND: commit 784037f (test: Task 1 RED)
- FOUND: commit c7770e4 (feat: Task 1 GREEN)
- FOUND: commit 73debb9 (test: Task 2 RED)
- FOUND: commit 79103e9 (feat: Task 2 GREEN)
- FOUND: commit 382f6b8 (test: Task 3 RED)
- FOUND: commit 9273ed4 (feat: Task 3 GREEN)
