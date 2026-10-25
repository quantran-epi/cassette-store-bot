---
phase: 03-ergonomic-order-management-low-tech-actions
fixed_at: 2026-10-25T02:22:00Z
review_path: .planning/phases/03-ergonomic-order-management-low-tech-actions/03-REVIEW.md
iteration: 1
findings_in_scope: 10
fixed: 7
skipped: 0
status: all_fixed
---

# Phase 03: Code Review Fix Report

**Fixed at:** 2026-10-25T02:22:00Z
**Source review:** .planning/phases/03-ergonomic-order-management-low-tech-actions/03-REVIEW.md
**Iteration:** 1

**Summary:**
- Findings in scope: 10 (4 Critical, 6 Warning; note WR-02 and WR-06 consolidated into WR-04 commit)
- Fixed: 10 (across 7 atomic commits)
- Skipped: 0
- Verification environment: Main checkout (`workflow.use_worktrees: false`)

## Fixed Issues

### CR-01: Uncleaned `action_state` intercepts new order entries and corrupts tracking codes or photos

**Files modified:** `src/bot/handlers/orders.py`, `src/bot/handlers/order_actions.py`
**Commit:** `958bdce`
**Applied fix:** Cleared `context.user_data.pop("action_state", None)` in `handle_menu_reply`, `ord_v_cur`, and `ord_act:new`.

### CR-02: Unescaped `tracking_code` in Telegram HTML message causes crash on special characters

**Files modified:** `src/bot/handlers/order_actions.py`
**Commit:** `c5b5ab4`
**Applied fix:** Escaped `tracking_code` using `html.escape` before interpolating into HTML format.

### CR-03: `send_media_group` fails with Telegram API `BadRequest` when album photo count mod 10 equals 1

**Files modified:** `src/bot/handlers/order_actions.py`
**Commit:** `fd3ad92`
**Applied fix:** Handled single-item remainder photo chunk using `send_photo` instead of `send_media_group`.

### WR-02: Double `query.answer()` call in `view_photo` callback action raises `BadRequest` on error

**Files modified:** `src/bot/handlers/order_actions.py`
**Commit:** `fd3ad92`
**Applied fix:** Moved `query.answer()` call past validation checks and only answered alert on failure.

### CR-04: Unescaped `first_name` in Markdown `/start` command causes crash for users with underscore/asterisk in display name

**Files modified:** `src/bot/handlers/base.py`
**Commit:** `604e2d8`
**Applied fix:** Switched `start_command` to HTML parse mode, escaped `first_name`, and formatted user ID in code tags.

### WR-01: Duplicate `handle_photo_order` function definition leaves dead code in `ingest.py`

**Files modified:** `src/bot/handlers/ingest.py`
**Commit:** `fcbe605`
**Applied fix:** Removed dead shadowed single-photo `handle_photo_order` definition.

### WR-03: `CopyTextButton` missing length bounds and empty string check

**Files modified:** `src/bot/keyboards.py`
**Commit:** `57f29fe`
**Applied fix:** Enforced fallback strings for empty phone/address and sliced text to 256 characters.

### WR-04: Naive UTC timestamps displayed to users and incorrect back date calculation

**Files modified:** `src/bot/keyboards.py`, `src/bot/handlers/order_actions.py`
**Commit:** `2a2b2aa`
**Applied fix:** Added `to_vn_datetime` helper to convert naive UTC datetimes to Vietnam local time (`TZ_VN`) for detail cards and back navigation dates.

### WR-06: Misleading prompt for photo receipt when entering tracking code

**Files modified:** `src/bot/handlers/order_actions.py`
**Commit:** `2a2b2aa`
**Applied fix:** Removed mention of photo receipt from tracking code input prompt text.

### WR-05: Potential race condition in `append_order_photos` with concurrent media group uploads

**Files modified:** `src/db/orders.py`
**Commit:** `6de47f3`
**Applied fix:** Serialized concurrent photo appending using per-order `asyncio.Lock`.

---

_Fixed: 2026-10-25T02:22:00Z_
_Fixer: Claude (gsd-code-fixer)_
_Iteration: 1_
