---
status: complete
date: 2026-10-27
slug: fix-order-reminder-message-timestamp-and
description: Fix order reminder message timestamp and standardize line dividers
---

# Summary: Fix order reminder message timestamp and standardize line dividers

## What was done
1. **Reminder timestamps in reminder messages (`src/services/notifications.py`, `src/db/reminders.py`)**:
   - Updated `get_due_reminders` query in `src/db/reminders.py` to select `r.created_at`.
   - Updated `format_reminder_broadcast` in `src/services/notifications.py` to format and display:
     - `⏰ HẸN LÚC: <code>{remind_at_fmt}</code>`
     - `🕒 GHI CHÚ LÚC: {created_at_fmt}` (converted from UTC to Vietnam UTC+7)
   - Also enriched reminder inspection prompt in `src/bot/handlers/order_actions.py` to display note creation time if available.
   - Now when a note says relative phrasing such as "khách hẹn sang ngày kia", the notification explicitly shows the target appointment time and the exact time the note was recorded.

2. **Standardized line dividers across codebase**:
   - Replaced all 20-character line dividers (`────────────────────`) across `src/bot/app.py`, `src/bot/handlers/admin.py`, `src/bot/handlers/backup.py`, `src/bot/handlers/ingest.py`, `src/bot/handlers/logs.py`, `src/bot/handlers/order_actions.py`, and `src/services/notifications.py` with consistent 14-character `DIVIDER = "──────────────"`.
   - Prevents divider line wraps/breaks on small screen devices.

3. **Tests & Quality**:
   - Added unit tests in `tests/test_notes_maintenance_notifications_reminders.py` for timestamp formatting, relative notes, and `get_due_reminders` created_at selection.
   - 405 unit tests pass (100%).
   - `ruff check` passed cleanly.
