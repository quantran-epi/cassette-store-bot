---
phase: 03-ergonomic-order-management-low-tech-actions
verified: 2026-10-24T19:35:00Z
status: passed
score: 14/14 must-haves verified
covered_files:
  - .planning/phases/03-ergonomic-order-management-low-tech-actions/03-01-PLAN.md
  - .planning/phases/03-ergonomic-order-management-low-tech-actions/03-01-SUMMARY.md
  - .planning/phases/03-ergonomic-order-management-low-tech-actions/03-02-PLAN.md
  - .planning/phases/03-ergonomic-order-management-low-tech-actions/03-02-SUMMARY.md
  - src/bot/app.py
  - src/bot/handlers/base.py
  - src/bot/handlers/ingest.py
  - src/bot/handlers/order_actions.py
  - src/bot/handlers/orders.py
  - src/bot/keyboards.py
  - src/db/orders.py
  - tests/test_db_orders.py
  - tests/test_orders_ui.py
covered_digest: "v2:sha256:e2af49d2f264d17df7c0043e14a88a474932df429abca70d5cee8c5b7d7f0e36"
behavior_unverified: 0
overrides_applied: 0
---

# Phase 03: Ergonomic Order Management & Low-Tech Actions Verification Report

**Phase Goal:** Người lớn tuổi vận hành đơn hàng hàng ngày 100% bằng phím bấm to một chạm trên Telegram: xem đơn theo ngày, đổi trạng thái, gắn mã vận đơn, copy thông tin sang app ship và quản lý ảnh.
**Verified:** 2026-10-24T19:35:00Z
**Status:** passed
**Re-verification:** No — initial verification

## Goal Achievement

### User Flow Coverage (MVP Mode)

| User Step | Expected Outcome | Codebase Evidence | Status |
| --------- | ---------------- | ----------------- | ------ |
| 1. Bật bot / khởi động (`/start`) | Reply Keyboard 2x2 cố định ghim dưới màn hình: `[📦 Đơn hôm nay]`, `[📋 Xem theo ngày]`, `[📝 Nhập đơn mới]`, `[❓ Trợ giúp]` | `src/bot/handlers/base.py:start_command`, `src/bot/keyboards.py:build_main_menu_reply_keyboard` | ✓ VERIFIED |
| 2. Bấm [📦 Đơn hôm nay] | Lấy danh sách đơn ngày hiện tại theo giờ VN (UTC+7), hiển thị phân trang 5 đơn/trang kèm badge trạng thái | `src/bot/handlers/orders.py:handle_menu_reply`, `src/db/orders.py:list_orders_by_date` | ✓ VERIFIED |
| 3. Bấm [📋 Xem theo ngày] | Mở bảng nút chọn ngày nhanh: Hôm nay, Hôm qua, 3 ngày liền trước | `src/bot/keyboards.py:build_date_picker_keyboard`, `src/bot/handlers/orders.py:77-84` | ✓ VERIFIED |
| 4. Bấm [Xem đơn #ID] | Mở thẻ chi tiết đơn HTML mono kèm các nút CopyTextButton 1 chạm cho SĐT, Địa chỉ, Mã vận đơn | `src/bot/keyboards.py:render_order_detail_card`, `build_order_detail_keyboard`, `src/bot/handlers/orders.py:207-236` | ✓ VERIFIED |
| 5. Chuyển trạng thái thông thường | 1 chạm tức thì, update DB và giao diện bằng `edit_message_text`, toast alert, không bị lỗi `Message is not modified` | `src/bot/handlers/order_actions.py:handle_order_status_callback`, `update_order_status` | ✓ VERIFIED |
| 6. Chuyển trạng thái nhạy cảm (Bom hàng, Huỷ đơn) | Hiện modal xác nhận 2 bước chống bấm nhầm trước khi ghi DB | `src/bot/handlers/order_actions.py:127-156` (`ord_st_cf:`) | ✓ VERIFIED |
| 7. Nhập mã vận đơn | Kích hoạt `action_state` TTL 120s, bypass LLM, lưu vào DB và hiển thị trên thẻ | `src/bot/handlers/order_actions.py:handle_action_state_text`, `src/bot/handlers/ingest.py:166-178` | ✓ VERIFIED |
| 8. Xem và thêm ảnh | Xem 1 ảnh (`send_photo`) hoặc >=2 ảnh (`send_media_group` chunk 10); gửi thêm ảnh qua TTL state | `src/bot/handlers/order_actions.py:handle_action_state_photo`, `view_photo` branch | ✓ VERIFIED |

### Observable Truths

| #   | Truth | Status | Evidence |
| --- | ----- | ------ | -------- |
| 1   | Dưới khung chat luôn có Reply Keyboard cố định với các nút to rõ: "Đơn hôm nay", "Nhập đơn mới", "Xem theo ngày", "Trợ giúp" giúp thao tác không cần gõ lệnh slash `/` | ✓ VERIFIED | `src/bot/keyboards.py:build_main_menu_reply_keyboard`, `src/bot/handlers/base.py:start_command`, tested in `test_build_main_menu_reply_keyboard_structure` |
| 2   | Bấm "Đơn hôm nay" hoặc chọn "Hôm qua" / ngày cụ thể, bot trả về danh sách đơn gọn gàng kèm badge trạng thái rõ ràng | ✓ VERIFIED | `src/bot/handlers/orders.py:handle_menu_reply`, `src/bot/keyboards.py:render_order_list_card`, tested in `test_handle_menu_reply_today_orders` |
| 3   | Mở thẻ chi tiết một đơn hàng, người dùng chạm 1 lần vào nút Inline Copy (hoặc chạm khối code mono) để copy SĐT, địa chỉ hoặc mã vận đơn trực tiếp vào bộ nhớ tạm | ✓ VERIFIED | `src/bot/keyboards.py:render_order_detail_card`, `build_order_detail_keyboard` with `CopyTextButton`, tested in `test_render_order_detail_card_html_and_code` |
| 4   | Người dùng chuyển trạng thái đơn (sang Đang làm, Đã đóng gói, Đã tạo đơn, Shipper đã lấy, Đã giao, Bom hàng, Huỷ) chỉ bằng 1 chạm và nhận phản hồi tức thì không bị lỗi `Message is not modified` | ✓ VERIFIED | `src/bot/handlers/order_actions.py:handle_order_status_callback`, tested in `test_order_status_normal_transition`, `test_order_status_bad_request_ignored` |
| 5   | Người dùng có thể nhập/cập nhật mã vận đơn cho đơn hàng và xem lại hoặc gửi thêm ảnh đính kèm (qua `file_id` Telegram) trực tiếp trong chat | ✓ VERIFIED | `src/bot/handlers/order_actions.py:handle_action_state_text`, `handle_action_state_photo`, tested in `test_order_action_track_state_and_cancel`, `test_handle_order_action_view_photos` |
| 6   | SQLite query lọc chính xác đơn hàng theo ngày giờ Việt Nam (UTC+7) và phân trang 5 đơn/trang | ✓ VERIFIED | `src/db/orders.py:list_orders_by_date` using `date(created_at, '+7 hours') = ?`, tested in `test_list_and_count_orders_by_date_utc7` |
| 7   | Reply Keyboard cố định 2x2 gồm [📦 Đơn hôm nay], [📋 Xem theo ngày], [📝 Nhập đơn mới], [❓ Trợ giúp] sẵn sàng xuất ra | ✓ VERIFIED | `src/bot/keyboards.py:build_main_menu_reply_keyboard`, tested in `test_build_main_menu_reply_keyboard_structure` |
| 8   | Thẻ chi tiết đơn hàng render chuẩn HTML `<code>` và CopyTextButton cho SĐT, Địa chỉ, Mã vận đơn theo chuẩn Telegram Bot API 7.3+ | ✓ VERIFIED | `src/bot/keyboards.py:render_order_detail_card`, `build_order_detail_keyboard`, tested in `test_build_order_detail_keyboard_copy_buttons_and_callbacks` |
| 9   | Bàn phím chọn nhanh ngày (Hôm nay, Hôm qua, 3 ngày gần nhất) và bàn phím phân trang điều hướng [⬅️ Trước] [Trang X/Y] [Sau ➡️] render đúng | ✓ VERIFIED | `src/bot/keyboards.py:build_date_picker_keyboard`, `build_order_list_keyboard`, tested in `test_build_date_picker_keyboard`, `test_build_order_list_keyboard_empty_and_pagination` |
| 10  | Bấm nút Reply Keyboard [📦 Đơn hôm nay] hoặc [📋 Xem theo ngày] hiển thị danh sách đơn hoặc bảng chọn ngày ngay lập tức mà không bị LLM extractor nuốt mất | ✓ VERIFIED | `src/bot/app.py:67-73` regex registered before LLM text handler, tested in `test_handle_menu_reply_today_orders`, `test_handle_menu_reply_other_buttons` |
| 11  | Bấm [Xem đơn #ID] mở thẻ chi tiết đơn hàng với 1-tap CopyTextButton và các phím tác vụ | ✓ VERIFIED | `src/bot/handlers/orders.py:handle_order_nav_callback` (`ord_v:`), tested in `test_handle_order_nav_callback_flow` |
| 12  | Đổi trạng thái đơn hàng thông thường thực hiện tức thì 1 chạm, cập nhật DB và giao diện bằng edit_message_text kèm toast alert | ✓ VERIFIED | `src/bot/handlers/order_actions.py:41-187`, tested in `test_order_status_normal_transition` |
| 13  | Đổi trạng thái nhạy cảm (BOM_HANG, HUY_DON) hiển thị modal xác nhận 2 bước chống bấm nhầm | ✓ VERIFIED | `src/bot/handlers/order_actions.py:127-156`, tested in `test_order_status_sensitive_requires_confirmation` |
| 14  | Nhập mã vận đơn và xem album ảnh đính kèm (send_photo cho 1 ảnh, send_media_group cho 2-10 ảnh) hoặc gửi thêm ảnh hoạt động trơn tru qua cơ chế action_state timeout 120s | ✓ VERIFIED | `src/bot/handlers/order_actions.py:189-392`, `src/bot/handlers/ingest.py:166-178`, tested in `test_handle_action_state_text_tracking_updates_db`, `test_handle_action_state_photo_appends_photos` |

**Score:** 14/14 truths verified (0 present, behavior-unverified)

### Required Artifacts

| Artifact | Expected | Status | Details |
| -------- | -------- | ------ | ------- |
| `src/db/orders.py` | Query đơn theo ngày UTC+7 (`list_orders_by_date`, `count_orders_by_date`) | ✓ VERIFIED | Substantive, parameterized SQL `date(created_at, '+7 hours') = ?`, tested and flowing real data |
| `src/bot/keyboards.py` | Reply Keyboard 2x2, CopyTextButton keyboards, date picker, list card, status selection | ✓ VERIFIED | Formats cards, incorporates Telegram Bot API 7.3+ CopyTextButtons, handles Vietnamese timezone |
| `src/bot/handlers/orders.py` | Menu routing và navigation callbacks | ✓ VERIFIED | Intercepts menu reply text, handles `ord_dt`, `ord_pg`, `ord_v`, `ord_bk`, suppresses BadRequest |
| `src/bot/handlers/order_actions.py` | Đổi trạng thái 1 chạm, modal xác nhận nhạy cảm, tracking & photo TTL state | ✓ VERIFIED | Toast alerts via `query.answer()`, 120s action TTL, chunking max 10 photos |
| `src/bot/handlers/ingest.py` | Bắt action_state trước LLM extractor | ✓ VERIFIED | Bypasses LLM text/photo ingestion when action_state is active and within 120s |
| `src/bot/app.py` | Đăng ký pipeline handlers đúng thứ tự ưu tiên | ✓ VERIFIED | Menu regex handler registered before `handle_text_order` |
| `src/bot/handlers/base.py` | Ghim Reply Keyboard 2x2 vào `/start` | ✓ VERIFIED | Sends `build_main_menu_reply_keyboard()` with `is_persistent=True` |
| `tests/test_orders_ui.py` | Bộ test tự động UI & handlers | ✓ VERIFIED | 19 tests dedicated to Phase 3 UI, all passing |
| `tests/test_db_orders.py` | Bộ test queries DB theo ngày UTC+7 | ✓ VERIFIED | Roundtrip tests for UTC+7 date boundaries |

### Key Link Verification

| From | To | Via | Status | Details |
| ---- | -- | --- | ------ | ------- |
| `src/bot/handlers/orders.py` | `src/db/orders.py` | `list_orders_by_date`, `count_orders_by_date` | ✓ WIRED | Parameterized queries with `date(created_at, '+7 hours') = ?` |
| `src/bot/keyboards.py` | Telegram Bot API | `CopyTextButton` | ✓ WIRED | Attached to phone, address, and tracking code inline buttons |
| `src/bot/app.py` | `src/bot/handlers/orders.py` | `MessageHandler(Regex(...), handle_menu_reply)` | ✓ WIRED | Registered before `handle_text_order` in `group=0` |
| `src/bot/handlers/ingest.py` | `src/bot/handlers/order_actions.py` | `handle_action_state_text`, `handle_action_state_photo` | ✓ WIRED | Intercepts input before LLM call when `action_state` active |
| `src/bot/handlers/order_actions.py` | Telegram Media API | `send_photo` vs `send_media_group` | ✓ WIRED | 1 photo -> `send_photo`, >=2 photos -> `send_media_group` in 10-item chunks |

### Data-Flow Trace (Level 4)

| Artifact | Data Variable | Source | Produces Real Data | Status |
| -------- | ------------- | ------ | ------------------ | ------ |
| `render_order_list_card` | `orders` | `list_orders_by_date()` SQLite query | Yes (Real Order instances) | ✓ FLOWING |
| `render_order_detail_card` | `order` | `get_order_by_id()` SQLite query | Yes (Full Order record) | ✓ FLOWING |
| `build_order_detail_keyboard` | `customer_phone`, `shipping_address`, `tracking_code` | `Order` domain model fields | Yes (Real strings passed to CopyTextButton) | ✓ FLOWING |
| `handle_action_state_text` | `tracking_code` | User chat input text | Yes (Persisted into orders table via SQL update) | ✓ FLOWING |
| `handle_action_state_photo` | `file_id` | User chat photo message | Yes (Appended into photo_file_ids JSON array) | ✓ FLOWING |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
| -------- | ------- | ------ | ------ |
| Date filtering in Vietnam timezone (UTC+7) | `pytest tests/test_db_orders.py::test_list_and_count_orders_by_date_utc7` | 1 passed in 0.03s | ✓ PASS |
| Reply Keyboard 2x2 and CopyTextButtons generation | `pytest tests/test_orders_ui.py -k "reply_keyboard or copy_buttons"` | 2 passed in 0.17s | ✓ PASS |
| Status transition 1-tap & sensitive modal confirmation | `pytest tests/test_orders_ui.py -k "order_status"` | 3 passed in 0.25s | ✓ PASS |
| Tracking state TTL 120s and LLM bypass | `pytest tests/test_orders_ui.py -k "action_state or tracking"` | 4 passed in 0.40s | ✓ PASS |
| Full project test suite regression check | `pytest` | 80 passed in 2.01s | ✓ PASS |

### Probe Execution

No probe scripts declared or required for Phase 3 (pure Telegram bot application and SQLite UI integration).

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
| ----------- | ----------- | ----------- | ------ | -------- |
| **DATA-05** | 03-02-PLAN.md | Nhập và cập nhật mã vận đơn cho đơn hàng cụ thể | ✓ SATISFIED | `src/db/orders.py:update_order_tracking`, `src/bot/handlers/order_actions.py:handle_action_state_text` |
| **UI-01** | 03-01-PLAN.md, 03-02-PLAN.md | 100% tính năng vận hành trên giao diện chat Telegram qua Inline Buttons và Reply Keyboard | ✓ SATISFIED | Persistent 2x2 Reply Keyboard + complete Inline Keyboard navigation pipeline |
| **UI-02** | 03-01-PLAN.md, 03-02-PLAN.md | Menu phím bấm to, cố định dưới khung chat cho các thao tác chính | ✓ SATISFIED | `build_main_menu_reply_keyboard()` with `resize_keyboard=True`, `is_persistent=True` |
| **UI-03** | 03-01-PLAN.md, 03-02-PLAN.md | Liệt kê danh sách đơn theo ngày: Hôm nay, Hôm qua, hoặc ngày cụ thể tuỳ chọn | ✓ SATISFIED | `list_orders_by_date()` (UTC+7), `build_date_picker_keyboard()`, pagination 5 orders/page |
| **UI-04** | 03-01-PLAN.md, 03-02-PLAN.md | Thẻ chi tiết cung cấp các nút bấm Inline "Sao chép nhanh" 1 chạm (CopyTextButton / code mono) | ✓ SATISFIED | `<code>` tags in `render_order_detail_card` and `CopyTextButton` in `build_order_detail_keyboard` |
| **UI-05** | 03-02-PLAN.md | Đổi trạng thái đơn hàng trực tiếp bằng 1 chạm thông qua danh sách nút bấm Inline | ✓ SATISFIED | `handle_order_status_callback`, natural next step, 8-state menu, 2-step sensitive confirmation |
| **UI-06** | 03-02-PLAN.md | Xem lại danh sách ảnh đính kèm (media group/từng ảnh) và nút thêm ảnh mới | ✓ SATISFIED | `send_photo` (1 photo) / `send_media_group` (>=2 photos), `append_order_photos()` |

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
| ---- | ---- | ------- | -------- | ------ |
| None | - | None | - | Scan completed with zero debt markers (TODO/FIXME/XXX) and zero stubs |

### Human Verification Required

None required. All phase deliverables are covered by automated unit and integration tests passing at 100% (80/80 passed).

### Gaps Summary

No gaps identified. All 7 requirements (DATA-05, UI-01, UI-02, UI-03, UI-04, UI-05, UI-06) and all 14 observable truths are fully implemented, wired, and verified in the codebase.

---

_Verified: 2026-10-24T19:35:00Z_
_Verifier: Claude (gsd-verifier)_
