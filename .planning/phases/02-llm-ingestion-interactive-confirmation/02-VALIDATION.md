---
phase: 02
slug: llm-ingestion-interactive-confirmation
status: draft
nyquist_compliant: true
wave_0_complete: false
created: 2026-10-24
---

# Phase 02 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 8.x + pytest-asyncio |
| **Config file** | pyproject.toml |
| **Quick run command** | `./.venv/bin/pytest tests/test_extractor.py tests/test_ingest.py -q` |
| **Full suite command** | `./.venv/bin/pytest -q` |
| **Estimated runtime** | ~2 seconds |

---

## Sampling Rate

- **After every task commit:** Run `./.venv/bin/pytest tests/test_extractor.py tests/test_ingest.py -q`
- **After every plan wave:** Run `./.venv/bin/pytest -q`
- **Before `/gsd-verify-work`:** Full suite must be green
- **Max feedback latency:** 5 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 02-01-01 | 01 | 1 | INGEST-01 | T-02-01 | Pydantic model parses unstructured text, normalizes currency ("250k", "1tr2"), handles phone format | unit | `./.venv/bin/pytest tests/test_extractor.py -k test_pydantic_schema` | ❌ W0 | ⬜ pending |
| 02-01-02 | 01 | 1 | INGEST-02 | T-02-02 | 2-tier LLM extractor (structured parse fallback to json_object), system prompt injection boundary | unit/mock | `./.venv/bin/pytest tests/test_extractor.py -k test_2tier_fallback` | ❌ W0 | ⬜ pending |
| 02-02-01 | 02 | 2 | INGEST-03 | T-02-03 | Customer history query (order count, spend, BOM_HANG warning tag), HTML card rendering with escaped text | unit | `./.venv/bin/pytest tests/test_ingest.py -k test_preview_card` | ❌ W0 | ⬜ pending |
| 02-02-02 | 02 | 2 | INGEST-04 | T-02-04 | 2-phase confirmation callback: save to DB on confirm, discard on cancel, callback_data <= 64 bytes | integration | `./.venv/bin/pytest tests/test_ingest.py -k test_callbacks` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/test_extractor.py` — unit tests for `ExtractedOrder`, currency normalization, and mocked `AsyncOpenAI` 2-tier fallback
- [ ] `tests/test_ingest.py` — unit & integration tests for preview card formatting, customer stats lookup, and confirmation callback handlers

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Real Telegram Chat UX & 1-tap buttons | INGEST-03, INGEST-04 | Visual layout verification on mobile screen | Paste sample order in Telegram bot, observe card format, tap ✅ Xác nhận và ❌ Huỷ bỏ |

---

## Validation Sign-Off

- [x] All tasks have `<automated>` verify or Wave 0 dependencies
- [x] Sampling continuity: no 3 consecutive tasks without automated verify
- [x] Wave 0 covers all MISSING references
- [x] No watch-mode flags
- [x] Feedback latency < 5s
- [x] `nyquist_compliant: true` set in frontmatter

**Approval:** pending 2026-10-24
