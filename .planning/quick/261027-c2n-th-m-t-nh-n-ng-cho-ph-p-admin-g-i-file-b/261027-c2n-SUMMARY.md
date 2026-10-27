# Quick Task 261027-c2n Summary

**Task:** Cho phép Super Admin gửi file backup `.sqlite3.gz` qua Telegram để khôi phục DB
**Commits:** `1c5aa7b` (feature), `f601587` (stale-button token fix)
**Status:** Complete

## One-liner

Super Admin uploads a gzipped SQLite backup; bot validates it, shows stats + confirm buttons, snapshots the live DB, then restores with rollback-on-failure and refreshes bot caches.

## Files

| File | Change |
|------|--------|
| `src/services/backup.py` | `RestoreValidationError`, `RestoreApplyError`, `stage_restore_archive`, `apply_staged_restore`, read-only URI helper, gzip-bomb cap, schema/integrity validation, pre-restore snapshot + rollback |
| `src/bot/handlers/backup.py` | `handle_backup_document`, `handle_restore_callback`, staging cleanup, stale temp-dir pruning, TTL/owner checks, `startup_sync` refresh |
| `src/bot/app.py` | Registers `Document.ALL` message handler before TEXT and `^adm:rst:` callback before `^adm:` |
| `tests/test_backup_restore.py` | 15 tests: round-trip, invalid gzip/non-SQLite/missing table, size cap, apply failure truthfulness, upload/confirm/cancel/owner/TTL/role, handler registration |

## Test Results

```
python -m pytest tests/test_backup_restore.py -q   -> 17 passed
python -m pytest tests/ -q                          -> 348 passed
python -m ruff check src tests                      -> All checks passed!
```

No `restore_*` directories left in OS temp after tests.

## Follow-up (f601587)

Runtime verification found that uploading a second file while the first confirm message was still open made the older buttons confirm the newer file. Fixed by binding each confirm/cancel button to a per-upload `secrets.token_urlsafe` token in `callback_data`; a stale token now edits the message and leaves the newer pending upload intact. Added regression tests.

## Deviations from Plan

**1. [Rule 1 - Bug] SQLite read-only URI needed `file:` prefix on Windows**
The plan's URI form `{abs_path}?mode=ro` fails on Windows with `unable to open database file`. Added `file:` prefix in `_readonly_uri`.

**2. [Rule 2 - Missing critical functionality] Accurate failure reporting + rollback**
Plan proposed unconditionally telling the user "Dữ liệu cũ được giữ nguyên." after any apply error, which is false if `source.backup(dest)` fails mid-write. Implemented:
- `RestoreApplyError.current_data_safe` flag.
- If failure occurs before destination modification: message states current data unchanged.
- If failure occurs mid-write: automatically restores the pre-restore snapshot, then reports whether rollback succeeded.
- Handler surfaces the true state and points at logs/backups when rollback could not be confirmed.

**3. [Rule 2 - Missing critical functionality] Snapshot directory creation inside guarded block**
`os.makedirs(backup_dir)` moved inside the try so a bad backup directory fails before any DB write and is reported accurately.

**4. [Rule 2 - Missing critical functionality] Validate object is a real table**
`PRAGMA table_info` succeeds for views; added `sqlite_master` type check so a malicious `customers` view cannot satisfy validation.

**5. [Rule 3 - Blocking issue] Pre-existing test required a gitignored fixture DB**
`tests/test_notes_maintenance_notifications_reminders.py::test_order_detail_card_and_reminder_prompt` opens `test.db` (gitignored, absent in fresh worktrees). Copied `test.db`/`cassette_store.db` from the main checkout to run the full suite; no test code changed.

**6. [Rule 1 - Bug] Test import order / unused variable**
Fixed Ruff `I001` and `F841` findings in the new test file before commit.

## Notes

- Restore runs while polling continues; documented as `ponytail:` tradeoff. A global lock / polling stop is the upgrade path if zero-downtime restores become required.
- Staged archives live in `tempfile.mkdtemp(prefix="restore_")`; uploads are capped at 20 MB, decompression at 256 MB.
- Summary, PLAN, and STATE were intentionally not committed, per task constraints.

## Self-Check: PASSED

- All created/modified source and test files exist.
- Commit `1c5aa7b` exists in worktree history.
