---
phase: 06
slug: telegram-database-backup-engine-scheduled-tasks
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-10-25
---

# Phase 06 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 9.1.1 + pytest-asyncio 1.4.0 |
| **Config file** | `pyproject.toml` |
| **Quick run command** | `.venv/bin/pytest tests/test_backup*.py -v` |
| **Full suite command** | `.venv/bin/pytest` |
| **Estimated runtime** | ~10 seconds |

---

## Sampling Rate

- **After every task commit:** Run `.venv/bin/pytest tests/test_backup*.py -v`
- **After every plan wave:** Run `.venv/bin/pytest`
- **Before `/gsd-verify-work`:** Full suite must be green
- **Max feedback latency:** 15 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 06-01-01 | 01 | 1 | BKP-01 | T-06-01 | Atomically snapshot live SQLite with VACUUM INTO, compress with gzip, unlink raw snapshot | unit | `.venv/bin/pytest tests/test_backup_engine.py -k test_snapshot` | ❌ W0 | ⬜ pending |
| 06-01-02 | 01 | 1 | BKP-01 | T-06-02 | Retention cleanup preserves latest 7 backups, unlinks older files safely | unit | `.venv/bin/pytest tests/test_backup_engine.py -k test_retention` | ❌ W0 | ⬜ pending |
| 06-01-03 | 01 | 1 | BKP-02 | T-06-03 | File >= 48MB aborts upload, logs warning, notifies admin without crashing | unit | `.venv/bin/pytest tests/test_backup_engine.py -k test_oversized` | ❌ W0 | ⬜ pending |
| 06-02-01 | 02 | 1 | BKP-03 | T-06-04 | JobQueue schedules daily backup at 02:00 Asia/Ho_Chi_Minh with dynamic reschedule | unit | `.venv/bin/pytest tests/test_backup_scheduler.py` | ❌ W0 | ⬜ pending |
| 06-02-02 | 02 | 2 | BKP-04 | T-06-05 | `/backup` and `adm:bkp:trigger` restrict execution to Super Admin only | integration | `.venv/bin/pytest tests/test_backup_handlers.py` | ❌ W0 | ⬜ pending |
| 06-02-03 | 02 | 2 | D-17, D-18 | T-06-06 | Admin model deletion & whitelist user rename handlers with timeouts | integration | `.venv/bin/pytest tests/test_admin_suite_refinements.py` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/test_backup_engine.py` — unit tests for snapshot creation, gzip compression, retention, and size threshold
- [ ] `tests/test_backup_scheduler.py` — unit tests for job queue scheduling, timezone handling, and reschedule callbacks
- [ ] `tests/test_backup_handlers.py` — integration tests for `/backup` command, admin menu trigger, and document delivery
- [ ] `tests/test_admin_suite_refinements.py` — integration tests for model deletion safeguards and user rename conversations

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Super Admin receives `.sqlite3.gz` in real Telegram client and can decompress/open in DB Browser | BKP-04 | Telegram Bot API live network delivery check | Trigger `/backup` from Super Admin Telegram account, download file, verify content integrity |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 15s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
