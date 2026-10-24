---
phase: 03-ergonomic-order-management-low-tech-actions
plan: 01
status: complete
subsystem: ui-keyboards-db
tags:
  - telegram-bot
  - reply-keyboard
  - inline-keyboard
  - copytextbutton
  - sqlite-wal
  - utc+7
requires:
  - 01-01
  - 01-02
  - 02-01
provides:
  - list_orders_by_date
  - count_orders_by_date
  - build_main_menu_reply_keyboard
  - render_order_detail_card
  - build_order_detail_keyboard
  - build_date_picker_keyboard
  - render_order_list_card
  - build_order_list_keyboard
  - build_status_selection_keyboard
affects:
  - src/db/orders.py
  - src/bot/keyboards.py
  - src/bot/handlers/base.py
  - src/bot/app.py
tech-stack:
  added: []
  patterns:
    - Telegram Bot API 7.3+ CopyTextButton for 1-tap clipboard copying
    - Persistent 2x2 ReplyKeyboardMarkup for elderly one-touch navigation
    - SQLite date(created_at, '+7 hours') filtering for Vietnam timezone
key-files:
  created:
    - src/bot/keyboards.py
    - tests/test_orders_ui.py
  modified:
    - src/db/orders.py
    - src/bot/handlers/base.py
    - src/bot/app.py
    - tests/test_db_orders.py
decisions:
  - "D-01/UI-02: Reply Keyboard 2x2 cố định dưới màn hình ([📦 Đơn hôm nay] [📋 Xem theo ngày] / [📝 Nhập đơn mới] [❓ Trợ giúp]) gắn vào /start"
  - "D-05/UI-04: Thẻ chi tiết kết hợp thẻ <code> HTML và CopyTextButton Telegram Bot API 7.3+ cho SĐT, địa chỉ, mã vận đơn"
  - "UI-03: Lọc đơn theo ngày bằng date(created_at, '+7 hours') trực tiếp trong SQLite query"
metrics:
  duration: 5 min
  completed_date: "2026-10-24"
actuals:
  tokens: 38000
  tasks: 3
  commits: 3
  plan_head_before: "9d3c55beae503fc12888e05d5589e9c0e1073e4b"
  plan_head_after: "74d424a1c0117316fe821e91091c5126dd0ec1c8"
---

# Phase 3 Plan 1: Date Queries and Keyboard UI Foundation Summary

Nền tảng truy vấn CSDL theo ngày UTC+7 và toàn bộ hệ thống bàn phím UI Telegram (Reply Keyboard 2x2, Inline Date Picker, Phân trang 5 đơn/trang, Thẻ chi tiết kèm 1-Tap CopyTextButton).

## Key Accomplishments

1. **CSDL theo ngày chuẩn múi giờ Việt Nam (UTC+7):**
   - Bổ sung `list_orders_by_date` và `count_orders_by_date` trong `src/db/orders.py` sử dụng SQLite query `date(created_at, '+7 hours') = ?` sắp xếp `ORDER BY created_at DESC, id DESC`.
   - Kiểm thử roundtrip chính xác chuyển dịch múi giờ đêm và phân trang offset/limit.

2. **Module bàn phím và định dạng thẻ hiển thị (`src/bot/keyboards.py`):**
   - `build_main_menu_reply_keyboard`: Reply Keyboard 2x2 cố định, kích thước to dễ chạm cho người lớn tuổi.
   - `render_order_detail_card`: Format thẻ chi tiết HTML với `html.escape` chống XSS/tampering (T-03-02), bọc SĐT, địa chỉ, mã vận đơn trong thẻ `<code>`.
   - `build_order_detail_keyboard`: Tích hợp các nút `CopyTextButton` của Telegram Bot API 7.3+ cho SĐT, Địa chỉ, Mã vận đơn cùng các nút hành động (bước tiếp theo, đổi trạng thái, xem/thêm ảnh).
   - `build_date_picker_keyboard`: Chọn nhanh ngày gồm Hôm nay, Hôm qua và 3 ngày liền trước.
   - `render_order_list_card` & `build_order_list_keyboard`: Định dạng danh sách 5 đơn/trang kèm điều hướng `[⬅️ Trước] [Trang X/Y] [Sau ➡️]` và xử lý thân thiện khi ngày trống (D-04).
   - `build_status_selection_keyboard`: Lưới chọn 8 trạng thái có đánh dấu `(Hiện tại)`.

3. **Tích hợp Reply Keyboard vào `/start`:**
   - Cập nhật `start_command` trong `src/bot/handlers/base.py` gửi kèm Reply Keyboard 2x2 cố định.
   - Tinh chỉnh `build_application` trong `src/bot/app.py` hỗ trợ khởi tạo linh hoạt khi API key để trống trong môi trường test.

## Commits

- `11d014c`: feat(03-01): add date-filtered order queries and detail keyboard with CopyTextButtons
- `42187ad`: feat(03-01): add date picker, paginated list card, and status selection keyboards
- `74d424a`: feat(03-01): attach persistent 2x2 reply keyboard to /start command

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Dummy API key for test environment in build_application**
- **Found during:** Task 3 full test suite run
- **Issue:** OpenAI client v1.50+ enforces credentials at initialization, causing `test_build_application_registers_gate_at_group_minus_one` to fail when `nine_router_api_key` is empty.
- **Fix:** Provided fallback `"dummy_key_for_init"` when secret value is empty string so test suite passes without live network API keys.
- **Files modified:** `src/bot/app.py`
- **Commit:** `74d424a`

## Self-Check: PASSED

- `src/db/orders.py`: FOUND
- `src/bot/keyboards.py`: FOUND
- `src/bot/handlers/base.py`: FOUND
- `tests/test_orders_ui.py`: FOUND
- Commit 11d014c: FOUND
- Commit 42187ad: FOUND
- Commit 74d424a: FOUND
- Test suite: 69 passed (100%)
