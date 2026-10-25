---
phase: 06-telegram-database-backup-engine-scheduled-tasks
plan: 01
subsystem: backup
tags: [sqlite, vacuum-into, gzip, telegram, resilience]
dependency_graph:
  requires: [src/db/connection.py, telegram.Bot]
  provides: [src/services/backup.py]
  affects: [backups/]
tech-stack:
  added: []
  patterns: [VACUUM INTO hot snapshotting, stdlib streaming gzip compression, retention cleanup, exponential backoff]
key-files:
  created:
    - src/services/backup.py
    - tests/test_backup_engine.py
  modified: []
decisions:
  - "Hot backup via VACUUM INTO ? guarantees zero lockups and clean WAL checkpoint snapshot"
  - "Raw uncompressed snapshot file is unlinked immediately in try...finally"
  - "Local directory retention caps backup archives at 7 newest files"
  - "Safe size limit 48MB blocks upload and signals warning before hitting Telegram 50MB ceiling"
  - "Telegram document transmission retries 3 times on transient network error with exponential backoff (2s, 5s, 10s)"
metrics:
  duration: 4m
  completed_date: "2026-10-25"
---

# Phase 06 Plan 01: Core Database Backup Engine and Telegram Uploader Summary

Core SQLite hot-snapshotting backup engine with `VACUUM INTO`, streaming `gzip` compression, retention pruning, and resilient Telegram document delivery.

## Key Changes

1. **Hot Snapshot Engine (`src/services/backup.py`)**:
   - `execute_backup(db, backup_dir)` triggers `VACUUM INTO ?` hot copy on the active WAL connection.
   - Streams raw snapshot through `gzip.open(..., compresslevel=6)` in `asyncio.to_thread`.
   - Guarantees immediate deletion of temporary `.sqlite3` file inside `try...finally`.
   - Gathers total orders and customers counts for message captions.
   - Detects file size >= 48MB (`SAFE_SIZE_LIMIT`) to protect against Telegram's 50MB payload limit.

2. **Retention Pruning (`prune_old_backups`)**:
   - Scans `backups/` directory for `cassette_store_backup_*.sqlite3.gz`.
   - Keeps strictly the 7 newest archives based on modification timestamp, safely unlinking older archives.

3. **Resilient Document Upload (`send_backup_document`)**:
   - Transmits `.sqlite3.gz` archives directly via `bot.send_document` with 60-second read/write timeouts.
   - Catches transient network errors (`TimedOut`, `NetworkError`) and applies 3-stage exponential backoff (2.0s, 5.0s, 10.0s).
   - Preserves backup files on disk if all retries fail.

4. **Unit Test Suite (`tests/test_backup_engine.py`)**:
   - `test_snapshot_creation_and_integrity`: verifies SQLite database integrity and table counts after decompression.
   - `test_retention_pruning`: verifies retention caps archives at 7 files.
   - `test_oversized_backup_detection`: verifies 48MB threshold triggers `is_oversized=True`.
   - `test_send_backup_document_success`: verifies timeout configurations and delivery.
   - `test_send_backup_document_retry_on_network_error`: verifies recovery after transient errors.
   - `test_send_backup_document_failure_preserves_file`: verifies file preservation upon delivery failure.

## Verification

- `pytest tests/test_backup_engine.py -v`: 6 passed in 0.15s.
- Full test suite: 158 passed in 0.92s.
- Ruff lint check: 100% clean.

## Deviations from Plan

None - plan executed exactly as written.

## Threat Flags

None - standard library implementations used (`gzip`, `shutil`, `zoneinfo`) with zero untrusted packages.

## Self-Check: PASSED
