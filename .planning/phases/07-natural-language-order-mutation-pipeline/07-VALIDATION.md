---
phase: 07
slug: natural-language-order-mutation-pipeline
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-10-25
---

# Phase 07 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 9.1.1 + pytest-asyncio 1.4.0 |
| **Config file** | `pyproject.toml` |
| **Quick run command** | `./.venv/bin/pytest tests/test_mutation*.py tests/test_intent*.py -v` |
| **Full suite command** | `./.venv/bin/pytest -v` |
| **Estimated runtime** | ~2 seconds (quick) / ~5 seconds (full) |

---

## Sampling Rate

- **After every task commit:** Run `./.venv/bin/pytest tests/test_mutation*.py tests/test_intent*.py -v`
- **After every plan wave:** Run `./.venv/bin/pytest -v`
- **Before `/gsd-verify-work`:** Full suite must be green
- **Max feedback latency:** 5 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 07-01-01 | 01 | 1 | MUT-01 | T-07-01 / — | Regex & LLM fallback classify intent, reply context resolution | unit/int | `./.venv/bin/pytest tests/test_intent_router.py -v` | ❌ W0 | ⬜ pending |
| 07-01-02 | 01 | 1 | MUT-02 | T-07-02 / — | Active-first order search, disambiguation keyboard for multi-match | unit/int | `./.venv/bin/pytest tests/test_order_mutation_search.py -v` | ❌ W0 | ⬜ pending |
| 07-01-03 | 01 | 1 | MUT-03 | T-07-03 / — | Pydantic schema validation, 5-group delta extraction, fast-path status | unit | `./.venv/bin/pytest tests/test_mutation_extractor.py -v` | ❌ W0 | ⬜ pending |
| 07-02-01 | 02 | 2 | MUT-04 | T-07-04 / — | Visual Diff card formatting, 14-char divider, TTL expiry & cleanup | unit | `./.venv/bin/pytest tests/test_mutation_card_and_lock.py -v` | ❌ W0 | ⬜ pending |
| 07-02-02 | 02 | 2 | MUT-04 | T-07-05 / — | Optimistic locking UPDATE WHERE updated_at, audit trail logging | unit/db | `./.venv/bin/pytest tests/test_order_audit_trail.py -v` | ❌ W0 | ⬜ pending |
| 07-02-03 | 02 | 2 | MUT-05 | T-07-06 / — | Lifecycle next status suggestions 1-tap inline buttons | unit | `./.venv/bin/pytest tests/test_status_suggestions.py -v` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/test_intent_router.py` — unit tests for 3-way router (regex, reply, fallback)
- [ ] `tests/test_mutation_extractor.py` — unit tests for delta extraction & fast-path
- [ ] `tests/test_mutation_card_and_lock.py` — unit tests for Visual Diff card & optimistic lock
- [ ] `tests/test_order_audit_trail.py` — unit tests for creator attribution & order_history logging
- [ ] `tests/test_status_suggestions.py` — unit tests for next status suggestions

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Thao tác 1-chạm xác nhận sửa trên Telegram | MUT-04 | Visual rendering và UX trên client Telegram thực tế | Nhắn tin đổi địa chỉ đơn hàng, quan sát thẻ Trước ➡️ Sau, bấm `[✅ Xác nhận sửa]` và kiểm tra cập nhật |
| Thao tác 1-chạm chọn đơn gợi ý khi khớp nhiều | MUT-02 | Tương tác bàn phím Inline | Nhắn tin sửa đơn của khách có nhiều đơn active, bấm nút chọn đơn 1-chạm |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 5s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
