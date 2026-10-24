---
status: diagnosed
phase: 03-ergonomic-order-management-low-tech-actions
source:
  - .planning/phases/03-ergonomic-order-management-low-tech-actions/03-01-SUMMARY.md
  - .planning/phases/03-ergonomic-order-management-low-tech-actions/03-02-SUMMARY.md
started: "2026-10-24T20:00:00Z"
updated: "2026-10-24T21:10:00Z"
---

## Current Test

[testing complete]

## Tests

### 1. Cold Start Smoke Test
expected: Start the bot application from scratch or execute the test suite. All handlers, SQLite WAL queries, and keyboard definitions initialize without error.
result: pass

### 2. Main Menu Reply Keyboard Navigation
expected: Sending /start displays the persistent 2x2 Reply Keyboard with buttons: [📦 Đơn hôm nay], [📋 Xem theo ngày], [📝 Nhập đơn mới], [❓ Trợ giúp]. Tapping them triggers menus instantly without consuming LLM extraction tokens.
result: pass

### 3. Date Filtering and Order Listing
expected: Tapping [📦 Đơn hôm nay] queries orders for today in Vietnam timezone (UTC+7). Tapping [📋 Xem theo ngày] opens a date picker (Today, Yesterday, previous 3 days). Orders display paginated at 5 per page with navigation controls.
result: pass

### 4. Order Detail Card with 1-Tap Copy Buttons
expected: Tapping [Xem đơn #ID] opens an HTML monospace order card with 1-tap CopyTextButton buttons for Customer Phone, Shipping Address, and Tracking Code.
result: pass

### 5. Instant Status Transitions
expected: Tapping forward status buttons (e.g., CHO_LAM -> DANG_LAM -> DA_DONG_GOI -> DA_TAO_DON -> SHIPPER_DA_LAY -> DA_GIAO) updates the order status immediately in SQLite and refreshes the Telegram message card with an instant toast alert.
result: pass

### 6. Sensitive Status 2-Step Confirmation
expected: Selecting a destructive/sensitive status (BOM_HANG or HUY_DON) prompts a 2-step confirmation modal preventing accidental cancellation before writing to the database.
result: pass

### 7. Tracking Code Entry with 120s TTL
expected: Tapping [Nhập mã vận đơn] enters a 120s action state that bypasses LLM extraction, allows typing a tracking code or tapping [❌ Huỷ bỏ thao tác], and saves the code to the order.
result: pass

### 8. Photo Album Viewer and Appending
expected: Tapping [Xem ảnh] sends 1 photo via send_photo or 2+ photos via send_media_group chunked to 10 images max. Tapping [Thêm ảnh] enters photo upload mode with 120s timeout.
result: issue
reported: "thêm ảnh vào đơn đã tạo thì ok, thêm nhiều ảnh cũng được, nhưng thêm mới đơn mà chọn nhiều ảnh từ đầu thì chỉ lưu được 1 ảnh, các ảnh còn lại bot rep thêm 1 tin nhắn là bác vui lòng gửi ..."
severity: major

## Summary

total: 8
passed: 7
issues: 1
pending: 0
skipped: 0

## Gaps

- gap_id: G-03-8
  truth: "Gửi nhiều ảnh (media group album) khi tạo mới đơn hàng lưu toàn bộ ảnh vào đơn và không báo lỗi thiếu caption cho các ảnh phụ trong album."
  status: failed
  reason: "User reported: thêm ảnh vào đơn đã tạo thì ok, thêm nhiều ảnh cũng được, nhưng thêm mới đơn mà chọn nhiều ảnh từ đầu thì chỉ lưu được 1 ảnh, các ảnh còn lại bot rep thêm 1 tin nhắn là bác vui lòng gửi ..."
  severity: major
  test: 8
  root_cause: "Telegram sends multi-photo albums as separate updates with the same media_group_id where only one update carries the caption and siblings have caption=None. handle_photo_order processes each update individually without media_group_id buffering, causing caption=None siblings to trigger warning replies while only 1 photo ID is saved to the draft."
  artifacts:
    - path: "src/bot/handlers/ingest.py"
      issue: "handle_photo_order lacks media_group_id buffering"
  missing:
    - "Add media_group_id debounce buffer in handle_photo_order so all sibling photo_file_ids are collected and passed together into process_extracted_order without sending duplicate missing-caption warnings."
  debug_session: ".planning/debug/media-group-album-photos.md"
