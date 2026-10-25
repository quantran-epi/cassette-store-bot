---
phase: 06-telegram-database-backup-engine-scheduled-tasks
plan: 02
subsystem: scheduler-and-admin
tags: [jobqueue, apscheduler, telegram, backup, rbac, admin-ui]
dependency_graph:
  requires: [src/services/backup.py, src/bot/app.py, src/bot/handlers/admin.py]
  provides: [schedule_daily_backup, backup_command, update_admin_user_name]
  affects: [src/bot/keyboards.py, src/bot/handlers/ingest.py]
tech-stack:
  added: []
  patterns: [PTB JobQueue run_daily, dynamic rescheduling, 60s TTL prompt state, role guard decorator]
key-files:
  created:
    - src/bot/handlers/backup.py
    - tests/test_backup_scheduler.py
    - tests/test_backup_handlers.py
    - tests/test_admin_suite_refinements.py
  modified:
    - src/bot/app.py
    - src/bot/handlers/admin.py
    - src/bot/handlers/ingest.py
    - src/bot/keyboards.py
    - src/db/admin.py
    - tests/test_admin_handlers.py
decisions:
  - "PTB JobQueue schedules daily backup at target HH:MM Asia/Ho_Chi_Minh without immediate execution on boot"
  - "Dynamic rescheduling clears existing job by name and registers new schedule without bot restart"
  - "/backup and adm:bkp:trigger strictly enforce SUPER_ADMIN role with progress feedback and document dispatch"
  - "Model switcher starts with empty default list, dynamically appends probed models, and protects active model from deletion"
  - "Whitelist user display names can be edited interactively via 60s TTL prompt"
metrics:
  duration: 6m
  completed_date: "2026-10-25"
---

# Phase 06 Plan 02: Backup Scheduler, /backup Command, and Admin Suite Refinements Summary

PTB JobQueue daily automated backups, `/backup` command handler, admin schedule configuration, model deletion, and whitelist user renaming.

## Key Changes

1. **JobQueue Scheduler (`src/bot/app.py`)**:
   - `schedule_daily_backup(app, time_str)` targets `Asia/Ho_Chi_Minh` timezone with `APScheduler 3.11.3`.
   - Cleans up existing jobs registered under `daily_database_backup` for dynamic in-flight rescheduling.
   - `daily_backup_job_callback` runs nightly, gathers database statistics, checks 48MB safety limits, uploads document to `settings.telegram_super_admin_id`, and alerts on errors without interrupting customer chats.
   - Synchronizes `backup_schedule_time` from SQLite `system_settings` on startup without running on boot.

2. **On-Demand Backup & Admin Wiring (`src/bot/handlers/backup.py`, `src/bot/handlers/admin.py`)**:
   - `/backup` command protected by `@require_role(UserRole.SUPER_ADMIN)` sends immediate progress message `⏳ Đang tạo snapshot và nén dữ liệu cơ sở dữ liệu...`, then updates with stats and sends pure Document.
   - In `/admin`, button `[💾 Sao lưu DB]` (`adm:bkp:trigger`) executes in-place backup for Super Admin or shows alert popup for regular Admin.
   - Button `[⏰ Đặt giờ sao lưu]` (`adm:bkp:menu`) presents presets (`01:00`, `02:00`, `03:00`, `04:00`) and custom `HH:MM` prompt with 60s TTL.

3. **Admin Suite Ergonomics Refinements (`src/db/admin.py`, `src/bot/keyboards.py`, `src/bot/handlers/admin.py`)**:
   - `update_admin_user_name` updates `admin_users.name` directly in SQLite.
   - `[✏️ Đổi tên]` button added to whitelist user detail cards (both regular and root Super Admin) with 60s text prompt.
   - Model switcher list starts empty, dynamically appends probed models, provides `[🗑️ Xoá model]` menu, and rejects deletion of active model.

## Verification

- Automated test suites:
  - `tests/test_backup_scheduler.py`: 8 passed
  - `tests/test_backup_handlers.py`: 7 passed
  - `tests/test_admin_suite_refinements.py`: 4 passed
  - `tests/test_admin_handlers.py`: 15 passed
- Full project test suite: 177 passed in 0.90s.
- Ruff code quality: Clean across all modified and created files.

## Deviations from Plan

None - plan executed exactly as written.

## Threat Flags

None - standard PTB handlers and regex validation (`^([01]\d|2[0-3]):([0-5]\d)$`) used.

## Self-Check: PASSED
