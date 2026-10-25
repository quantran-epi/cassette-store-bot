---
slug: order-notes-maintenance-notifications-reminders
date: 2026-10-25
status: complete
description: Save notes to order (not customer), add maintenance mode with broadcast, order lifecycle event broadcasts, and natural language reminder system
---

# Quick Task: Order Notes, Maintenance Mode, Lifecycle Broadcasts & NL Reminders

## Goal
Implement 4 interconnected features:
1. Save notes to `orders.notes` instead of `customers.notes`, displaying notes on order detail card.
2. Super Admin maintenance mode: toggle via admin panel, broadcast alerts to all whitelist users on ON/OFF, and block non-Super-Admin interactions while active.
3. Broadcast notifications to all users on order events: creation (`CHO_LAM`), packed (`DA_DONG_GOI`), shipping label created (`DA_TAO_DON`).
4. Reminder system: extract natural language reminder during order creation, button on order detail card to add/edit reminder via natural language prompt, and background worker broadcasting due reminders.

## Proposed Changes

### 1. Database & Models
- `src/db/schema.py`:
  - Add `reminders` table with foreign key to `orders(id)`.
  - Ensure `orders.notes` exists and index on reminders.
- `src/models/extractor.py`:
  - Add `reminder_at: str | None` and `reminder_note: str | None` to `ExtractedOrder`.
- `src/models/order.py` / `src/models/reminder.py`:
  - Create `Reminder` dataclass/model.
- `src/db/reminders.py`:
  - CRUD operations: `create_reminder`, `get_reminders_by_order_id`, `get_due_reminders`, `mark_reminder_sent`, `cancel_reminder`.
- `src/db/settings.py`:
  - Add `get_maintenance_mode(db)` and `set_maintenance_mode(db, enabled)`.

### 2. Note Handling
- `src/bot/handlers/callbacks.py`:
  - On order confirmation: save `draft.get("notes")` to `Order.notes`. Do NOT overwrite `Customer.notes`.
- `src/bot/keyboards.py`:
  - Display `notes` in `render_order_detail_card`.

### 3. Maintenance Mode
- `src/bot/security.py`:
  - Add `maintenance_gate` TypeHandler or gate check right after whitelist gate.
  - If maintenance enabled and user is not `SUPER_ADMIN`, halt execution with polite notice.
- `src/bot/keyboards.py` & `src/bot/handlers/admin.py`:
  - Add `adm:maint:toggle` button in Admin Suite (SUPER_ADMIN only).
  - Toggling broadcasts status change to all whitelist users.

### 4. Broadcast Service & Order Lifecycle Notifications
- `src/services/notifications.py`:
  - Central broadcast helper `broadcast_message(bot, whitelist_ids, text)`.
  - Helper formatters for new order, packed, shipping label, maintenance, and reminders.
- Call broadcast in:
  - `callbacks.py` (order created -> broadcast).
  - `order_actions.py` (status -> DA_DONG_GOI, DA_TAO_DON).
  - `callbacks.py` mutation confirm (if status mutated -> DA_DONG_GOI, DA_TAO_DON).

### 5. Reminder System
- `src/services/extractor.py`:
  - Add reminder instructions and prompt context (current time in VN).
  - Function `extract_reminder_from_text(client, model_id, text, now_vn)`.
- `src/bot/handlers/callbacks.py`:
  - On order creation: if `reminder_at` extracted, insert into `reminders`.
- `src/bot/keyboards.py`:
  - Add `⏰ Đặt/Xem lịch nhắc` button to `build_order_detail_keyboard`.
- `src/bot/handlers/order_actions.py` or new `reminder.py` handler:
  - Handle `ord_act:remind:{order_id}` click -> prompt text input.
  - Handle message reply -> parse text with LLM/fallback -> save reminder.
- `src/bot/app.py`:
  - Register reminder JobQueue repeating job (every 60s) to scan due reminders and broadcast.

## Verification
- Unit & integration tests for:
  - Order notes persistence vs Customer notes.
  - Maintenance mode gating and toggling.
  - Lifecycle broadcast formatting and dispatch.
  - Reminder creation, extraction, and scheduled broadcast execution.
