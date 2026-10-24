---
phase: 03
review: 03-REVIEW.md
titles: json
findings:
  - id: CR-01
    severity: critical
    disposition: open
    title: "Uncleaned `action_state` intercepts new order entries and corrupts tracking codes or photos"
  - id: CR-02
    severity: critical
    disposition: open
    title: "Unescaped `tracking_code` in Telegram HTML message causes crash on special characters"
  - id: CR-03
    severity: critical
    disposition: open
    title: "`send_media_group` fails with Telegram API `BadRequest` when album photo count mod 10 equals 1"
  - id: CR-04
    severity: critical
    disposition: open
    title: "Unescaped `first_name` in Markdown `/start` command causes crash for users with underscore/asterisk in display name"
  - id: WR-01
    severity: warning
    disposition: open
    title: "Duplicate `handle_photo_order` function definition leaves dead code in `ingest.py`"
  - id: WR-02
    severity: warning
    disposition: open
    title: "Double `query.answer()` call in `view_photo` callback action raises `BadRequest` on error"
  - id: WR-03
    severity: warning
    disposition: open
    title: "`CopyTextButton` missing length bounds and empty string check"
  - id: WR-04
    severity: warning
    disposition: open
    title: "Naive UTC timestamps displayed to users and incorrect back date calculation"
  - id: WR-05
    severity: warning
    disposition: open
    title: "Potential race condition in `append_order_photos` with concurrent media group uploads"
  - id: WR-06
    severity: warning
    disposition: open
    title: "Misleading prompt for photo receipt when entering tracking code"
  - id: IN-01
    severity: info
    disposition: open
    title: "Inconsistent date format on empty order list card"
  - id: IN-02
    severity: info
    disposition: open
    title: "Unused dead code `extract_province_or_city`"
  - id: IN-03
    severity: info
    disposition: open
    title: "Duplicate database connection helper `_get_active_db_context` across handlers"
  - id: IN-04
    severity: info
    disposition: open
    title: "Trailing blank lines in `tests/test_orders_ui.py`"
open: 14
total: 14
recorded: 2026-10-24T16:42:44.426Z
---

# Phase 03: Code Review Disposition

| Finding | Severity | Disposition | Source |
|---------|----------|-------------|--------|
| CR-01 | critical | open | - |
| CR-02 | critical | open | - |
| CR-03 | critical | open | - |
| CR-04 | critical | open | - |
| WR-01 | warning | open | - |
| WR-02 | warning | open | - |
| WR-03 | warning | open | - |
| WR-04 | warning | open | - |
| WR-05 | warning | open | - |
| WR-06 | warning | open | - |
| IN-01 | info | open | - |
| IN-02 | info | open | - |
| IN-03 | info | open | - |
| IN-04 | info | open | - |

Dispositions: `open` (recorded, not yet triaged), `fixed`, `skipped`, `deferred`.
