---
phase: 261027-h7d
plan: 01
subsystem: bot-ui
tags: [telegram, orders, quick-search, ui]
requires:
  - src/db/orders.py (list_orders_by_status, count_orders_by_date pattern)
  - src/bot/keyboards.py (render_order_list_card, build_order_detail_keyboard back_callback_data)
provides:
  - count_orders_by_status
  - format_order_compact_line
  - render_status_order_list_card
  - build_status_order_list_keyboard
  - ord_ls / ord_vls callback handling
  - tutorial page "⏳ ĐƠN CHỜ LÀM"
affects:
  - reply keyboard layout (2x2 → 3x2)
  - every order list card (new filter chip row)
tech-stack:
  added: []
  patterns:
    - "Status enum validated from client callback_data before DB access"
    - "Python-side date grouping (query ORDER BY DESC, never SQL GROUP BY)"
key-files:
  created: []
  modified:
    - src/db/orders.py
    - src/bot/keyboards.py
    - src/bot/handlers/orders.py
    - src/bot/app.py
    - src/bot/tutorial.py
    - src/bot/handlers/base.py
    - tests/test_orders_ui.py
    - tests/test_tutorial.py
    - tests/test_db_orders.py
decisions:
  - "Detail view from a status list uses ord_vls + back_callback_data=ord_ls:<STATUS>:<page>, never reuses ord_v (whose back targets the date list)"
  - "Status chips are a helper _build_status_filter_row(); active chip keeps current page, others reset to page 1"
  - "Reply keyboard reordered to 3x2: [Đơn hôm nay | Đơn chờ làm] / [Xem theo ngày | Nhập đơn mới] / [Tra cứu đơn | Trợ giúp]"
metrics:
  duration: ~25m
  completed: 2026-10-27
---

# Phase 261027-h7d Plan 01: Quick Search "Đơn chờ làm" (no LLM) Summary

One-tap pending-order list grouped by Vietnam creation date, paginated 10/page, with status filter chips on every list card and a matching tutorial page.

## What Was Built

**DB layer** — `count_orders_by_status(db, status)` mirrors `count_orders_by_date`, exported via `__all__`. Reused the existing `list_orders_by_status` (`ORDER BY created_at DESC`, `idx_orders_status` already indexed); no schema change.

**Renderers/keyboards** (`src/bot/keyboards.py`):
- `format_order_compact_line(order)` — single line `📦 <b>#id</b> · name · 1.250.000 đ`, HTML-escaped, no newline.
- `render_status_order_list_card(...)` — header `{STATUS_NAMES[status]} — <b>DANH SÁCH ĐƠN</b>` + total/page line, sub-header per VN day `📅 <b>DD/MM/YYYY</b> · k đơn`, compact lines, trailing hint. Grouping is Python-side over the DESC-ordered query result.
- `_vn_date_label(created_at)` — datetime or ISO string → `to_vn_datetime` → `DD/MM/YYYY`, fallback `"Không rõ ngày"`.
- `_build_status_filter_row(current_status, current_page)` — 3 chips (`ord_ls:<STATUS>:<page>`); active chip keeps its page, others reset to 1.
- `build_status_order_list_keyboard(...)` — `ord_vls:<STATUS>:<id>:<page>` detail buttons, paging via `ord_ls`, chip row, empty-state `ord_act:new`.
- `build_main_menu_reply_keyboard()` — now 3x2, persistent + resizable.
- `build_order_list_keyboard` — chip row added to both the populated and empty branches, above `📋 Chọn ngày khác`; existing callbacks unchanged.

**Handlers/wiring**:
- `_render_status_list_page(active_db, status, page, limit=10)` — counts, `ceil`, clamps page 1..total_pages, fetches the page.
- `handle_menu_reply` — new `"⏳ Đơn chờ làm"` branch (CHO_LAM page 1).
- `handle_order_nav_callback` — `ord_ls:` validates `OrderStatus(...)` (ValueError → silent return) and `int` page (fallback 1); `ord_vls:` validates status + id + page, loads order + reminders, renders detail with `back_callback_data=f"ord_ls:{status.value}:{page}"`.
- `app.py` — reply regex includes `⏳ Đơn chờ làm`; nav callback pattern extended to `ord_(dt|pg|v|bk|ls|vls):`.
- `tutorial.py` — new page at index 1 (`⏳ ĐƠN CHỜ LÀM`, `try_kind="pending_orders"`), page 0 body lists all 5 buttons. `PAGE_COUNT` is derived, now 7.
- `base.py` — `TRY_ACTIONS["pending_orders"] = "ord_ls:CHO_LAM:1"`.

## Deviations from Plan

None — plan executed as written. Two adjacent cleanups folded into task 1 (same files, no behavior change): the `format_order_compact_line` / `_vn_date_label` helpers were placed next to `render_order_list_card` rather than at end-of-file, and `FILTER_CHIP_STATUSES` was added as a module constant instead of repeating the tuple.

## Threat Model Outcomes

- T-261027-h7d-01 (Tampering via `ord_ls`/`ord_vls`): mitigated — status validated through `OrderStatus(value)` with silent return, page/id parsed in try/except, page clamped 1..total_pages, all user text HTML-escaped in the renderer. Covered by `test_handle_order_nav_callback_status_list` (`ord_ls:XXX:1` neither raises nor edits).
- T-261027-h7d-02 (Info disclosure): accepted, unchanged (whitelist gate at group -1).
- T-261027-h7d-SC: no dependencies added.

## Verification

`python -m pytest -q` → **374 passed**, 3 pre-existing PTB JobQueue warnings (unrelated, `tests/test_security.py`).

Wiring guard: `test_app_registers_pending_orders_wiring` reads `src/bot/app.py` and asserts both the button text and `ord_(dt|pg|v|bk|ls|vls):` are present, so a forgotten registration fails the suite.

Callback size: max is `ord_vls:SHIPPER_DA_LAY:999999:999` = 34 bytes; asserted `<= 64` across status-list keyboards.

## Known Stubs

None.

## Self-Check: PASSED

- `src/db/orders.py` contains `count_orders_by_status` and exports it.
- `src/bot/keyboards.py` contains `format_order_compact_line`, `render_status_order_list_card`, `build_status_order_list_keyboard`, 3x2 reply keyboard.
- `src/bot/handlers/orders.py` contains `_render_status_list_page`, `ord_ls:` and `ord_vls:` branches.
- `src/bot/app.py` contains `⏳ Đơn chờ làm` and `ord_(dt|pg|v|bk|ls|vls):`.
- `src/bot/tutorial.py` has 7 pages with `⏳ ĐƠN CHỜ LÀM` at index 1.
- Commits: `bc9cf12`, `6fd32d4`, `a4ba08b`.
