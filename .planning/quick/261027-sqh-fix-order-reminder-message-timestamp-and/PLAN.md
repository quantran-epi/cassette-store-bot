# Quick Task: Fix order reminder message timestamp and standardize line dividers

**Task ID:** 261027-sqh
**Slug:** fix-order-reminder-message-timestamp-and
**Date:** 2026-10-27

## Objective
1. Include explicit scheduled time (`remind_at`) and note creation time (`created_at`) in order reminder notification messages (`format_reminder_broadcast`) so that relative notes like "khách hẹn sang ngày kia" have full temporal context.
2. Ensure `get_due_reminders` in DB selects `r.created_at`.
3. Standardize all line dividers across the codebase to the consistent 14-character `DIVIDER = "──────────────"` per D-19, replacing inconsistent 20-character lines (`────────────────────`) that wrap and break on small screens.
4. Add comprehensive unit tests covering reminder broadcast time rendering and divider consistency.

## Tasks
- [ ] Task 1: Update `get_due_reminders` in `src/db/reminders.py` to select `r.created_at`.
- [ ] Task 2: Update `format_reminder_broadcast` in `src/services/notifications.py` to format and display `remind_at` and `created_at`.
- [ ] Task 3: Replace all 20-character line dividers (`────────────────────`) across `src/` with `DIVIDER` (14 chars).
- [ ] Task 4: Add unit tests in `tests/test_notes_maintenance_notifications_reminders.py` and run full pytest suite to verify 100% pass.
