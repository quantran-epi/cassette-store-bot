---
phase: "04"
slug: "natural-language-order-search"
# status lifecycle: draft (seeded by plan-phase) → validated (set by validate-phase §6)
# audit-milestone §5.5 distinguishes NOT-VALIDATED (draft) from PARTIAL (validated + nyquist_compliant: false) (#2117)
status: draft
nyquist_compliant: false
wave_0_complete: false
created: "2026-10-25"
---

# Phase 04 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 9.1.1 + pytest-asyncio 1.4.0 |
| **Config file** | pyproject.toml |
| **Quick run command** | `./.venv/bin/pytest tests/test_order_search.py -v` |
| **Full suite command** | `./.venv/bin/pytest` |
| **Estimated runtime** | ~5 seconds |

---

## Sampling Rate

- **After every task commit:** Run `./.venv/bin/pytest tests/test_order_search.py -v`
- **After every plan wave:** Run `./.venv/bin/pytest`
- **Before `/gsd-verify-work`:** Full suite must be green
- **Max feedback latency:** 5 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 04-01-01 | 01 | 1 | SEARCH-01 | T-04-01 | SQL Sanitizer chỉ cho phép SELECT, cấm DDL/DML, cấm multi-statement | unit | `./.venv/bin/pytest tests/test_order_search.py::test_sql_sanitizer` | ❌ W0 | ⬜ pending |
| 04-01-02 | 01 | 1 | SEARCH-01 | T-04-02 | Phân loại intent tìm kiếm regex tiếng Việt chuẩn xác | unit | `./.venv/bin/pytest tests/test_order_search.py::test_is_search_intent` | ❌ W0 | ⬜ pending |
| 04-01-03 | 01 | 1 | SEARCH-01 | — | Text-to-SQL thực thi an toàn với schema SQLite và UTC+7 | integration | `./.venv/bin/pytest tests/test_order_search.py::test_text_to_sql_execution` | ❌ W0 | ⬜ pending |
| 04-02-01 | 02 | 2 | SEARCH-02 | — | Thẻ xác nhận 1 đơn kèm 2 nút bấm Inline xác nhận | unit | `./.venv/bin/pytest tests/test_order_search.py::test_search_single_order_card` | ❌ W0 | ⬜ pending |
| 04-02-02 | 02 | 2 | SEARCH-02 | — | Danh sách kết quả nhiều đơn kèm phân trang 5 đơn/trang | unit | `./.venv/bin/pytest tests/test_order_search.py::test_search_multi_order_card` | ❌ W0 | ⬜ pending |
| 04-02-03 | 02 | 2 | SEARCH-02 | — | Điều hướng quay lại bảo toàn ngữ cảnh tra cứu | integration | `./.venv/bin/pytest tests/test_order_search.py::test_search_navigation_back` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/test_order_search.py` — test stubs cho SEARCH-01, SEARCH-02

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| ChatAction.TYPING hiển thị liên tục khi gọi LLM | SEARCH-01 | Telegram client-side rendering | Gửi tin nhắn tra cứu và quan sát trạng thái bot đang gõ |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 5s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending 2026-10-25
