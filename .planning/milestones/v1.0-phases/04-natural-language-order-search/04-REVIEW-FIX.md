---
phase: 04-natural-language-order-search
fixed_at: 2026-10-25T09:12:00Z
review_path: .planning/phases/04-natural-language-order-search/04-REVIEW.md
iteration: 1
findings_in_scope: 4
fixed: 4
skipped: 0
status: all_fixed
---

# Phase 04: Code Review Fix Report

**Fixed at:** 2026-10-25T09:12:00Z
**Source review:** .planning/phases/04-natural-language-order-search/04-REVIEW.md
**Iteration:** 1
**Verification tree:** main checkout (`workflow.use_worktrees=false`)

**Summary:**
- Findings in scope: 4 (1 Critical, 3 Warning)
- Fixed: 4
- Skipped: 0

## Fixed Issues

### CR-01: Overly Broad Search Intent Regex Intercepts Order Ingestion and Drops Orders

**Files modified:** `src/services/order_search.py`, `tests/test_order_search.py`
**Commit:** `e0a3ca9`
**Applied fix:** Defined `PHONE_PATTERN = re.compile(r"(?:(?:\+84|84|0)[35789])\d{8}\b")` and updated `is_search_intent` to return `False` when a phone number is detected in the message, unless an explicit search prefix keyword is present. Added negative regression tests for order texts containing casual questions with phone numbers.

### WR-01: `_get_active_db_context` Does Not Inspect `app_context.settings`

**Files modified:** `src/bot/handlers/search.py`
**Commit:** `74fcb2e`
**Applied fix:** Updated `_get_active_db_context` in `src/bot/handlers/search.py` to check `getattr(app_context, "settings", None)` if `app_context` is present before falling back to `context.application.bot_data.get("settings")`.

### WR-02: Missing `BadRequest` ("Message is not modified") Suppression in `sch_bk`

**Files modified:** `src/bot/handlers/search.py`, `tests/test_order_search.py`
**Commit:** `8c615b1`
**Applied fix:** Wrapped `edit_message_text` calls in `sch_bk:` callback logic in `try ... except BadRequest` blocks suppressing `"Message is not modified"` errors on rapid double clicks. Added regression unit test verifying graceful suppression.

### WR-03: Conversational Search Patterns Miss Multiline Queries Due to Missing `re.DOTALL`

**Files modified:** `src/services/order_search.py`, `tests/test_order_search.py`
**Commit:** `1646347`
**Applied fix:** Added `re.DOTALL` to compiled patterns in `SEARCH_CONVERSATIONAL_PATTERNS` that contain `.*?` across wildcard tokens. Added regression test for multiline inquiry questions.

---

_Fixed: 2026-10-25T09:12:00Z_
_Fixer: Claude (gsd-code-fixer)_
_Iteration: 1_
