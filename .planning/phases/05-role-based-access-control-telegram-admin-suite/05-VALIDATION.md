---
phase: 5
slug: role-based-access-control-telegram-admin-suite
status: draft
nyquist_compliant: true
wave_0_complete: false
created: 2026-10-25
---

# Phase 5 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 9.1.1 + pytest-asyncio 1.4.0 |
| **Config file** | `pyproject.toml` |
| **Quick run command** | `.venv/bin/pytest tests/test_security_rbac.py` |
| **Full suite command** | `.venv/bin/pytest` |
| **Estimated runtime** | ~3-5 seconds |

---

## Sampling Rate

- **After every task commit:** Run `.venv/bin/pytest tests/test_*.py` for modified component
- **After every plan wave:** Run `.venv/bin/pytest`
- **Before `/gsd-verify-work`:** Full suite must be green (existing 110 tests + Phase 5 tests)
- **Max feedback latency:** 5 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 05-01-01 | 01 | 1 | RBAC-01 | T-05-01 | Root Super Admin immutable; tables created with constraints | unit | `.venv/bin/pytest tests/test_admin_db.py` | ❌ W0 | ⬜ pending |
| 05-01-02 | 01 | 1 | RBAC-02 | T-05-02 | `@require_role` blocks unauthorized commands & callbacks with alert | unit | `.venv/bin/pytest tests/test_security_rbac.py` | ❌ W0 | ⬜ pending |
| 05-01-03 | 01 | 1 | RBAC-05 | T-05-03 | `RingBufferLogHandler` FIFO eviction, HTML escaping, error filter | unit | `.venv/bin/pytest tests/test_logging_buffer.py` | ❌ W0 | ⬜ pending |
| 05-02-01 | 02 | 2 | RBAC-03 | T-05-04 | Dynamic model switch with 1-token probe, rollback on failure | integration | `.venv/bin/pytest tests/test_admin_handlers.py` | ❌ W0 | ⬜ pending |
| 05-02-02 | 02 | 2 | RBAC-04 | T-05-05 | Whitelist CRUD updates DB + bot_data in-memory sync | integration | `.venv/bin/pytest tests/test_admin_whitelist.py` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/test_admin_db.py` — Stubs for `admin_users` and `system_settings` persistence and root sync (RBAC-01)
- [ ] `tests/test_security_rbac.py` — Stubs for `@require_role` dual-dispatch decorator (RBAC-02)
- [ ] `tests/test_logging_buffer.py` — Stubs for `RingBufferLogHandler` (RBAC-05)

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Telegram Inline UI layout rendering | RBAC-03 | Visual alignment of 2-column inline buttons in native Telegram app | Open `/admin` on Telegram mobile/desktop client, verify 2-column grid button layout and dashboard text |
| 60s input prompt timeout UX | RBAC-04 | Verifies real-time conversational timeout in Telegram client | Trigger add user prompt, wait 60s without typing, verify bot cancels input state |

---

## Validation Sign-Off

- [x] All tasks have `<automated>` verify or Wave 0 dependencies
- [x] Sampling continuity: no 3 consecutive tasks without automated verify
- [x] Wave 0 covers all MISSING references
- [x] No watch-mode flags
- [x] Feedback latency < 5s
- [x] `nyquist_compliant: true` set in frontmatter

**Approval:** approved 2026-10-25
