---
phase: "03"
slug: "ergonomic-order-management-low-tech-actions"
# status lifecycle: draft (seeded by plan-phase) → validated (set by validate-phase §6)
# audit-milestone §5.5 distinguishes NOT-VALIDATED (draft) from PARTIAL (validated + nyquist_compliant: false) (#2117)
status: draft
nyquist_compliant: false
wave_0_complete: false
created: "2026-10-24"
---

# Phase 03 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 9.1.1 + pytest-asyncio 1.4.0 |
| **Config file** | `pyproject.toml` |
| **Quick run command** | `./.venv/bin/pytest tests/test_orders_ui.py -x` |
| **Full suite command** | `./.venv/bin/pytest` |
| **Estimated runtime** | ~5 seconds |

---

## Sampling Rate

- **After every task commit:** Run `./.venv/bin/pytest tests/test_orders_ui.py -x`
- **After every plan wave:** Run `./.venv/bin/pytest`
- **Before `/gsd-verify-work`:** Full suite must be green
- **Max feedback latency:** 10 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 03-01-01 | 01 | 1 | UI-01, UI-02 | T-03-01 | Phím menu chỉ nhận lệnh từ user trong whitelist | Integration | `./.venv/bin/pytest tests/test_orders_ui.py -k "test_start_command_reply_keyboard or test_main_menu_routing"` | ❌ W0 | ⬜ pending |
| 03-01-02 | 01 | 1 | UI-03 | T-03-02 | Truy vấn theo ngày chuẩn SQL injection resistant | Unit / DB | `./.venv/bin/pytest tests/test_db_orders.py -k test_list_orders_by_date` | ❌ W0 | ⬜ pending |
| 03-02-01 | 02 | 2 | UI-04 | T-03-03 | Output HTML thẻ đơn escape đúng ký tự đặc biệt | Unit | `./.venv/bin/pytest tests/test_orders_ui.py -k test_copy_buttons_rendering` | ❌ W0 | ⬜ pending |
| 03-02-02 | 02 | 2 | UI-05 | T-03-04 | Trạng thái BOM_HANG/HUY bắt buộc modal xác nhận | Integration | `./.venv/bin/pytest tests/test_orders_ui.py -k test_status_transition_and_confirmation` | ❌ W0 | ⬜ pending |
| 03-03-01 | 03 | 3 | DATA-05, UI-06 | T-03-05 | Mã vận đơn validate độ dài, media group xử lý 1 vs n ảnh an toàn | Integration | `./.venv/bin/pytest tests/test_orders_ui.py -k "test_update_order_tracking or test_photo_view_and_append"` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/test_orders_ui.py` — stubs cho UI-01, UI-02, UI-04, UI-05, UI-06
- [ ] `tests/test_db_orders.py` — bổ sung tests cho `list_orders_by_date()` và `count_orders_by_date()` (UI-03)

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Thao tác 1 chạm copy SĐT/Địa chỉ vào clipboard | UI-04 | CopyTextButton yêu cầu Telegram Client thực tế | Mở Telegram desktop hoặc mobile, bấm nút Copy trên thẻ đơn và dán vào ô chat |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 10s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending 2026-10-24
