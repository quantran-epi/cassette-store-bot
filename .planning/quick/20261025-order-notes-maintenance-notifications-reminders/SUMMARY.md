---
slug: order-notes-maintenance-notifications-reminders
date: 2026-10-25
status: complete
description: Save order notes to orders table, add super-admin maintenance mode with broadcast, lifecycle event broadcasts, and NL reminders system
---

# Quick Task Summary: Order Notes, Maintenance Mode, Lifecycle Broadcasts & Reminders

## Completed Work

1. **Order Notes vs Customer Notes**:
   - `src/bot/handlers/callbacks.py`: Customer created with `notes=""`, Order created with `notes=draft.get("notes") or ""`.
   - `src/bot/keyboards.py`: `render_order_detail_card` displays `📝 Ghi chú: {order.notes}`.
   - `src/bot/handlers/ingest.py`: `render_preview_card` renders notes if extracted.

2. **Maintenance Mode (Tạm dừng chat)**:
   - `src/db/settings.py`: `get_maintenance_mode` & `set_maintenance_mode`.
   - `src/bot/security.py`: `maintenance_gate` runs at group -1 right after `whitelist_gate`. Halts non-Super-Admin execution with polite notice while allowing `SUPER_ADMIN` to pass.
   - `src/bot/handlers/admin.py`: Added `adm:maint:toggle` for `SUPER_ADMIN` which updates setting and broadcasts status change to all whitelist users.
   - `src/bot/keyboards.py`: Admin main keyboard renders maintenance toggle button for `SUPER_ADMIN`.

3. **Lifecycle Broadcasts**:
   - `src/services/notifications.py`: `broadcast_to_whitelist` safely iterates all whitelist users with `exclude_user_id` parameter to exclude performer. Gắn kèm nút `[📦 Xem chi tiết đơn]` (`ord_v:{order_id}`) cho mọi thông báo đơn. Formatters cho:
     - New order created (`CHO_LAM`)
     - Order packed (`DA_DONG_GOI`)
     - Shipping label created (`DA_TAO_DON`)
     - System maintenance state changes
     - Due reminders
   - Dispatches in `callbacks.py` (order create & mutation status change), `order_actions.py` (status change), `admin.py` (maintenance toggle), and `app.py` (reminder worker).

4. **Reminders System**:
   - `src/models/reminder.py`: `Reminder` dataclass and `ReminderStatus` enum.
   - `src/db/schema.py`: `reminders` table with indices on `(status, remind_at)` and `order_id`.
   - `src/db/reminders.py`: CRUD operations (`create_reminder`, `get_reminders_by_order_id`, `get_due_reminders`, `mark_reminder_sent`, `cancel_reminder`, `cancel_reminders_by_order_id`). Enforces 1 active pending reminder per order by superseding old pending reminders.
   - `src/models/extractor.py` & `src/services/extractor.py`: LLM schema + prompt support for `reminder_at` and `reminder_note`, plus `extract_reminder_from_text` with deterministic fallback. Added current time injection and deterministic regex fallback for relative phrases like "mai gửi", "chiều mai", "thứ 2 tuần sau".
   - `src/bot/keyboards.py`: `render_order_detail_card` displays active reminder `⏰ Lịch nhắc: YYYY-MM-DD HH:MM (Nội dung)`. `build_order_detail_keyboard` dynamically renders `"⏰ Sửa/Xem lịch nhắc"` (nếu đã có lịch) hoặc `"⏰ Thêm nhắc lịch"`.
   - `src/bot/handlers/order_actions.py`: Handles `ord_act:remind:{order_id}` (hiển thị lịch hẹn hiện tại, cho phép sửa hoặc xoá qua `ord_act:remind_del:{order_id}`) và `handle_action_state_text` lưu lịch mới.
   - `src/bot/app.py`: Updated `CallbackQueryHandler` pattern to match `remind` and `remind_del`. `schedule_reminder_checker` runs repeating JobQueue task every 30s to check and broadcast due reminders.

## Verification
- Added 13 unit/integration tests in `tests/test_notes_maintenance_notifications_reminders.py`.
- 247 / 247 tests passing.
- Ruff linter completely clean with 0 errors.
