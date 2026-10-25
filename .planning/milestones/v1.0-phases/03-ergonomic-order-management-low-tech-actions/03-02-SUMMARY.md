---
phase: 03-ergonomic-order-management-low-tech-actions
plan: 02
status: complete
subsystem: ui-handlers-order-management
tags:
  - telegram-bot
  - reply-keyboard
  - inline-navigation
  - order-status
  - tracking-code
  - media-group
  - ttl-state
requires:
  - 03-01
provides:
  - handle_menu_reply
  - handle_order_nav_callback
  - handle_order_status_callback
  - handle_order_action_callback
  - handle_action_state_text
  - handle_action_state_photo
affects:
  - src/bot/handlers/orders.py
  - src/bot/handlers/order_actions.py
  - src/bot/handlers/ingest.py
  - src/bot/app.py
tech-stack:
  added: []
  patterns:
    - Reply Keyboard regex interception before LLM ingestion
    - 2-step confirmation modal for sensitive terminal statuses (BOM_HANG, HUY_DON)
    - 1-tap status transition with instant toast alerts and BadRequest suppression
    - 120s TTL action_state for prompt workflows (tracking code, photo appending)
    - Photo viewing with send_photo (1 image) vs send_media_group chunked to 10 (>=2 images)
key-files:
  created:
    - src/bot/handlers/orders.py
    - src/bot/handlers/order_actions.py
  modified:
    - src/bot/handlers/ingest.py
    - src/bot/app.py
    - tests/test_orders_ui.py
decisions:
  - "D-01/D-03: Menu Reply Keyboard regex được đăng ký trước LLM text ingestion trong app.py để chống tốn token và nhầm lẫn"
  - "D-07/UI-05: Trạng thái nhạy cảm (BOM_HANG, HUY_DON) bắt buộc qua modal xác nhận 2 bước trước khi ghi CSDL"
  - "D-09/D-11/D-12: Luồng nhập tracking code và gửi thêm ảnh sử dụng action_state TTL 120s, bypass LLM trong ingest.py, hỗ trợ nút bấm huỷ bỏ"
  - "D-10/UI-06: Xem ảnh tự động phân nhánh: 1 ảnh dùng send_photo, từ 2 ảnh trở lên dùng send_media_group chia chunk 10 ảnh"
metrics:
  duration: 6 min
  completed_date: "2026-10-24"
actuals:
  tokens: 42000
  tasks: 3
  commits: 3
  plan_head_before: "2815e4cb06c993549344290916c02bc6b7187d6c"
  plan_head_after: "b5d8e2929e4d74236357154eddf7333da569abed"
---

# Phase 3 Plan 2: Order Handlers, Status Transitions, and Media Actions Summary

Xây dựng trọn vẹn toàn bộ các controller handler cho giao diện quản lý đơn hàng hàng ngày trên Telegram: điều hướng menu Reply Keyboard 2x2, xem danh sách đơn theo ngày phân trang, mở thẻ chi tiết đơn kèm 1-Tap CopyTextButton, chuyển trạng thái vòng đời đơn 1 chạm kèm modal xác nhận 2 bước cho trạng thái nhạy cảm, và quy trình nhập mã vận đơn / album ảnh với timeout 120s.

## Key Accomplishments

1. **Điều hướng Menu Reply Keyboard & Danh sách theo ngày (`src/bot/handlers/orders.py`):**
   - `handle_menu_reply`: Bắt text các phím bấm Reply Keyboard `[📦 Đơn hôm nay]`, `[📋 Xem theo ngày]`, `[📝 Nhập đơn mới]`, `[❓ Trợ giúp]`. Bọc múi giờ Việt Nam UTC+7, phân trang 5 đơn/trang.
   - `handle_order_nav_callback`: Xử lý mượt mà chuyển trang (`ord_pg`), chọn ngày (`ord_dt`), quay lại (`ord_bk`), và mở thẻ chi tiết đơn hàng (`ord_v`) kèm xử lý an toàn lỗi `BadRequest: Message is not modified`.
   - Đăng ký regex handler trước `handle_text_order` trong `src/bot/app.py` loại trừ hoàn toàn rủi ro bị LLM extractor nuốt nhầm text menu (T-03-07).

2. **Chuyển đổi trạng thái đơn hàng vòng đời (`src/bot/handlers/order_actions.py`):**
   - Chuyển trạng thái 1 chạm tức thì (`CHO_LAM` -> `DANG_LAM` -> `DA_DONG_GOI` -> `DA_TAO_DON` -> `SHIPPER_DA_LAY` -> `DA_GIAO`) với thông báo toast alert không xoay spinner (D-08).
   - Bảo vệ trạng thái nhạy cảm (`BOM_HANG`, `HUY_DON`): Hiển thị modal xác nhận 2 bước chống bấm nhầm (D-07, UI-05).
   - Menu chọn nhanh trong 8 trạng thái (`ord_st_menu`) và nút quay lại thẻ đơn (`ord_v_cur`).

3. **Mã vận đơn đối tác ship & Quản lý album ảnh (`src/bot/handlers/order_actions.py`, `src/bot/handlers/ingest.py`):**
   - `action_state` TTL 120s được kiểm tra ngay đầu `handle_text_order` và `handle_photo_order` trong `src/bot/handlers/ingest.py` để bypass qua LLM, lưu trực tiếp mã vận đơn hoặc ảnh vào đơn hàng tương ứng (DATA-05, UI-06).
   - Cung cấp nút `[❌ Huỷ bỏ thao tác]` (`ord_act:cancel`) cho phép người dùng huỷ bỏ trạng thái chờ bất kỳ lúc nào.
   - Xem album ảnh (`ord_act:view_photo`) tự động chọn `send_photo` cho 1 ảnh và `send_media_group` chunk tối đa 10 ảnh cho >=2 ảnh chống lỗi Telegram BadRequest (T-03-06, Pitfall 4).

## Commits

- `d381d55`: feat(03-02): add reply menu routing, date order listing, and detail navigation
- `f34d743`: feat(03-02): implement order status transitions with 2-step confirmation for sensitive states
- `b5d8e29`: feat(03-02): implement tracking code management, photo album viewer, and 120s action timeout

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Tuple index unpacking in handle_menu_reply test assert**
- **Found during:** Task 1 test run
- **Issue:** Test code attempted to unpack positional args from `message.reply_text.call_args` when `reply_text` was called using keyword argument `text=...`.
- **Fix:** Extracted `text` from `kwargs.get("text")` or `args[0]` safely.
- **Files modified:** `tests/test_orders_ui.py`
- **Commit:** `d381d55`

## Self-Check: PASSED

- `src/bot/handlers/orders.py`: FOUND
- `src/bot/handlers/order_actions.py`: FOUND
- `src/bot/handlers/ingest.py`: FOUND
- `src/bot/app.py`: FOUND
- `tests/test_orders_ui.py`: FOUND
- Commit d381d55: FOUND
- Commit f34d743: FOUND
- Commit b5d8e29: FOUND
- Test suite: 80 passed in 1.43s (100%)
