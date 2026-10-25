---
phase: 03-ergonomic-order-management-low-tech-actions
plan: 03
status: complete
subsystem: bot-ingest-media-group
tags:
  - telegram-bot
  - media-group
  - debounce
  - photo-buffering
  - asyncio
requires:
  - 02-01
  - 03-01
  - 03-02
provides:
  - media_group_debounce_buffer
  - bundled_album_photo_file_ids
  - single_preview_card_for_album
affects:
  - src/bot/handlers/ingest.py
  - tests/test_ingest.py
tech-stack:
  added: []
  patterns:
    - In-memory asyncio debounce buffer for Telegram media group updates
    - Non-caption album photo update warning suppression
    - Clean TTL cache for processed media group deduplication
key-files:
  created: []
  modified:
    - src/bot/handlers/ingest.py
    - tests/test_ingest.py
decisions:
  - "D-13: Debounce ~0.8s gom toàn bộ ảnh trong cùng media_group_id trước khi gọi LLM bóc tách"
  - "D-14: Bỏ qua cảnh báo thiếu caption cho các ảnh phụ trong media_group_id, chỉ gửi 1 thông báo nếu cả album không có caption"
  - "D-15: Lưu cache _PROCESSED_MEDIA_GROUPS với TTL 60s để bỏ qua an toàn các ảnh straggler đến muộn"
metrics:
  duration: 4 min
  completed_date: "2026-10-24"
actuals:
  tokens: 3118
  tasks: 3
  commits: 2
  plan_head_before: "1a0f4efa6acc5ba01aa826adbad919d983991299"
  plan_head_after: "c23528448ecff2a2e41416e8979313ea203b5f36"
---

# Phase 3 Plan 3: Media Group Album Photo Buffering Summary

Cơ chế debounce buffer gom toàn bộ ảnh của Telegram media group album vào một đơn hàng duy nhất kèm đầy đủ danh sách photo_file_ids và xuất duy nhất một thẻ xem trước (preview card).

## Key Accomplishments

1. **Khắc phục triệt để gap G-03-8 (Media group album photo buffering):**
   - Khai báo bộ nhớ đệm `_MEDIA_GROUP_BUFFERS` và TTL cache `_PROCESSED_MEDIA_GROUPS` trong `src/bot/handlers/ingest.py`.
   - gom toàn bộ `photo_file_id` (chọn ảnh có độ phân giải cao nhất) từ mọi update có cùng `media_group_id` trong cửa sổ debounce.
   - Bỏ qua cảnh báo thiếu caption đối với các ảnh phụ trong album (update có caption rỗng nhưng mang `media_group_id`).
   - Gộp chung logic bóc tách và phản hồi preview card qua helper `_extract_and_process_photo_order`, tái sử dụng tối đa giữa ảnh đơn và album ảnh.
   - Hiển thị đúng số lượng ảnh đính kèm trên preview card (`📷 Ảnh đính kèm: N ảnh`) và lưu trọn vẹn vào `draft_data["photo_file_ids"]`.

2. **Bảo toàn 100% luồng ảnh đơn lẻ:**
   - Tin nhắn ảnh đơn (`media_group_id is None`) giữ nguyên hành vi xử lý trực tiếp không chờ debounce, cảnh báo nếu thiếu caption hoặc bóc tách ngay nếu có caption.

3. **Bộ kiểm thử toàn diện:**
   - `test_media_group_album_bundled_single_preview`: Xác nhận 3 ảnh cùng album chỉ tạo 1 preview card và draft gom đủ 3 photo IDs.
   - `test_media_group_album_missing_all_captions`: Xác nhận chỉ gửi đúng 1 cảnh báo thiếu caption nếu toàn bộ album không có caption nào.
   - `test_single_photo_without_media_group_retains_behavior`: Xác nhận ảnh đơn không bị ảnh hưởng.
   - Toàn bộ test suite 84/84 tests pass 100%.

## Commits

- `6509b33`: feat(03-03): add media group album photo buffering
- `c235284`: test(03-03): test media group album ingestion

## Deviations from Plan

None - plan executed exactly as written.

## Self-Check: PASSED

- `src/bot/handlers/ingest.py`: FOUND
- `tests/test_ingest.py`: FOUND
- Commit 6509b33: FOUND
- Commit c235284: FOUND
- Test suite: 84 passed (100%)
