---
status: complete
date: 2026-10-25
quick_id: 261025-vo9
slug: fix-reminder-weekday-parsing-and-enhance
---

# Quick Task Summary: Fix Reminder Weekday Parsing & Enhance Card Contrast / Uppercase Labels

## What was done:
1. **Reminder Weekday Parsing Fix (`src/services/extractor.py`)**:
   - Replaced buggy `strftime("%Y-%m-%d %H:%M (Thứ %u)")` with `VN_WEEKDAYS` lookup map (`0: "Thứ 2 (Thứ Hai)", ..., 6: "Chủ Nhật"`). Sunday 2026-10-25 is now accurately presented as "Chủ Nhật" instead of "Thứ 7".
   - Aligned deterministic fallback in `_parse_vietnamese_relative_time` and `extract_reminder_from_text`:
     - When called on Sunday with "thứ 2 tuần sau", correctly calculates target as next week's Monday (2026-11-02).
     - When called on Sunday with "thứ 2", correctly targets tomorrow (2026-10-26).
     - When called on Wednesday with "thứ 2 tuần sau", targets next week's Monday (2026-10-26).
   - Removed misleading note in prompt `(Lưu ý: Thứ 2 = Thứ 2, Thứ 7 = Thứ 7, Chủ nhật = Thứ 7+1)`.

2. **Unified High-Contrast Uppercase Labels Across All Cards**:
   - Standardized bold uppercase title labels across all order card presentations (`src/bot/keyboards.py`, `src/bot/handlers/ingest.py`, `src/bot/handlers/callbacks.py`, `src/services/notifications.py`, `src/bot/handlers/order_actions.py`):
     - `👤 <b>KHÁCH:</b>`
     - `📞 <b>SĐT:</b>`
     - `📍 <b>ĐỊA CHỈ:</b>` / `📍 <b>Đ/C:</b>`
     - `📼 <b>BĂNG CASSETTE:</b>` / `📼 <b>BĂNG:</b>`
     - `💰 <b>TỔNG TIỀN:</b>` / `💰 <b>TIỀN:</b>`
     - `💵 <b>TIỀN COD THU:</b>`
     - `🚚 <b>MÃ VẬN ĐƠN:</b>`
     - `📷 <b>ẢNH ĐÍNH KÈM:</b>`
     - `📝 <b>GHI CHÚ:</b>`
     - `⏰ <b>LỊCH NHẮC:</b>`
     - `🕒 <b>THỜI GIAN TẠO:</b>`
     - `🔄 <b>TRẠNG THÁI:</b>`
   - Values remain normal / monospace (`<code>`) for clear visual contrast for elderly users.

3. **Bot Avatar Assets (`assets/`)**:
   - Generated `assets/bot_avatar.png` (512x512) and `assets/bot_avatar.svg` (vector) with a warm retro cassette tape design.

4. **Testing**:
   - Added unit tests for Sunday parsing and uppercase label rendering in `tests/test_notes_maintenance_notifications_reminders.py`.
   - Verified 249/249 tests passing.
