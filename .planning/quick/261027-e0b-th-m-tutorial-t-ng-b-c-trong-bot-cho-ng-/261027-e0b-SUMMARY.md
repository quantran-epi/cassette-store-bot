---
phase: 261027-e0b
plan: 01
type: execute
subsystem: bot-ui
tags: [tutorial, help, telegram, elderly-ux]
requires:
  - src/bot/keyboards.py
provides:
  - src/bot/tutorial.py
  - src/bot/handlers/base.py#handle_tutorial_callback
  - help:page / help:try callbacks
affects:
  - src/bot/handlers/orders.py
  - src/bot/app.py
tech-stack:
  added: []
  patterns: [static-content-module, callback-dispatch-reuse]
key-files:
  created:
    - src/bot/tutorial.py
    - tests/test_tutorial.py
  modified:
    - src/bot/handlers/base.py
    - src/bot/handlers/orders.py
    - src/bot/app.py
decisions:
  - "Tutorial content lives only in src/bot/tutorial.py; /help and ❓ Trợ giúp both call send_tutorial"
  - "try-now reuses existing handlers via a cloned CallbackQuery carrying ord_dt/ord_act/sch_new callbacks"
metrics:
  duration: ~12m
  completed: 2026-10-27
---

# Phase 261027 Plan 01: Multi-page tutorial Summary

Six-page Vietnamese tutorial reachable from both `/help` and the `❓ Trợ giúp` reply button, with back/next navigation, boundary clamping, and one-tap "Thử ngay" shortcuts into existing order/search screens. Duplicate help text removed from `base.py` and `orders.py`.

## Tasks

1. `src/bot/tutorial.py` — `TUTORIAL_PAGES` (6 pages), `PAGE_COUNT`, `_clamp_page`, `build_tutorial_keyboard`, `render_tutorial_page`.
2. Wiring — `send_tutorial`, `help_command`, `handle_tutorial_callback` in `base.py`; `orders.py` menu branch delegates; `app.py` registers `^help:` CallbackQueryHandler.

## Deviations from Plan

- `send_tutorial` gained an optional `message=` parameter. Reason: `handle_menu_reply` in `orders.py` receives updates built with `update.message` in existing tests; using `update.effective_message` would silently send nothing. Rule 1 (bug: help button produced no reply).
- `tutorial.py` imports `InlineKeyboardMarkup` from `telegram` directly; the plan's test imports it from `src.bot.keyboards` where it is re-exported. No functional difference.

## Follow-up fix (`94161ca`)

Runtime verification (driving the real `Application.process_update`) showed every "▶️ Thử ngay" button was dead: PTB 22.x freezes `CallbackQuery`, so `query.data = action` raised `AttributeError`, and `set_bot()` returns `None` (in-place mutation), so the chained clone was `None`. The original tests passed because they used `MagicMock` queries, which accept any assignment.

Fixed by building an explicit `CallbackQuery` clone with the mapped `data`, calling `set_bot()` on its own line, and wrapping it in a new `Update`. Added `test_try_now_works_with_immutable_real_callback_query` using `Update.de_json` so a real frozen object guards this path.

Also fixed the tutorial test helpers, which had the same two pitfalls (mutable mock query, `set_bot().` chaining).

## Verification

- `tests/test_tutorial.py`: 12 passed.
- Targeted (`test_tutorial`, `test_backup_restore`, `test_orders_ui`, `test_order_search`): 83 passed.
- Full suite: 360 passed.
- `python -m ruff check src tests`: clean.
- `grep -rn "HƯỚNG DẪN SỬ DỤNG BOT" src`: exactly 1 hit in `src/bot/tutorial.py`.
- Driven through `Application.process_update`: `/help` and `❓ Trợ giúp` produce identical page 1; `help:page:99` clamps to 6/6; all four `help:try:*` open the right screen; `help:try:bogus` and `help:page:abc` only answer.
- No new dependencies, no DB/schema changes.

## Commits

- `9a6bd80` feat(261027-e0b): multi-page tutorial for elderly users
- `94161ca` fix(261027-e0b): make tutorial try-now dispatch on immutable CallbackQuery

## Self-Check: PASSED
