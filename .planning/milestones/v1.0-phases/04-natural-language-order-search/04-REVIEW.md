---
phase: 04-natural-language-order-search
reviewed: 2026-10-25T08:55:00Z
depth: standard
files_reviewed: 3
files_reviewed_list:
  - src/bot/handlers/search.py
  - src/services/order_search.py
  - tests/test_order_search.py
findings:
  critical: 1
  warning: 3
  info: 2
  total: 6
status: issues_found
---

# Phase 04: Code Review Report

**Reviewed:** 2026-10-25T08:55:00Z
**Depth:** standard
**Files Reviewed:** 3
**Status:** issues_found

## Summary

Reviewed changes from gap closure G-04-3 covering dynamic SQLite connection resolution in search handlers and natural language conversational inquiry intent detection. Found 1 critical blocker where overly broad regex in `is_search_intent` captures real order drafts containing casual questions and customer phone numbers, hijacking order ingestion into search and dropping the order. Also identified 3 warnings (inconsistent settings resolution in `_get_active_db_context`, unhandled `BadRequest` in `sch_bk`, missing `re.DOTALL` on multiline inquiry patterns) and 2 info findings.

## Critical Issues

### CR-01: Overly Broad Search Intent Regex Intercepts Order Ingestion and Drops Orders

**File:** `src/services/order_search.py:26-41, 139-145`
**Issue:** `SEARCH_CONVERSATIONAL_PATTERNS` pattern 7 (`re.compile(r"\b(?:mua|đơn)\b.*?\b(?:bao\s+giờ\s+chưa|chưa\s+nhỉ|chưa\s+bác|chưa\s+shop|không\s+nhỉ)\b", re.IGNORECASE)`) matches incoming order messages containing polite questions or notes (e.g. `"Khách mua 2 cuốn Tuấn Vũ (hỏi xem có chưa nhỉ) gửi 123 Lê Lợi 0903123456"` or `"Đơn anh Tuấn 2 cuốn ship hôm nay được không nhỉ 0912345678"`). In `src/bot/handlers/ingest.py:195`, `handle_text_order` routes any message where `is_search_intent(text) == True` to `process_search_query` instead of `extract_order_from_text`. This results in the incoming order being evaluated as a search query, returning 0 matching records, and silently discarding the new order creation. This violates the explicit plan requirement to ensure order creation text with customer phone numbers or order items is not falsely flagged.
**Fix:**
```python
PHONE_PATTERN = re.compile(r"(?:(?:\+84|84|0)[3|5|7|8|9])\d{8}\b")

def is_search_intent(text: str) -> bool:
    """Check if text indicates order search intent via keywords or conversational inquiry patterns (G-04-3)."""
    trimmed = text.strip().lower()
    # Explicit search prefix commands always take precedence
    if any(trimmed.startswith(prefix) for prefix in SEARCH_PREFIX_KEYWORDS):
        return True

    # Do not treat conversational text as search if it contains a valid phone number,
    # unless it explicitly starts with search prefix keywords
    if PHONE_PATTERN.search(text):
        return False

    return any(pattern.search(trimmed) for pattern in SEARCH_CONVERSATIONAL_PATTERNS)
```

## Warnings

### WR-01: `_get_active_db_context` Does Not Inspect `app_context.settings`

**File:** `src/bot/handlers/search.py:31-35`
**Issue:** `_get_active_db_context` attempts to read `settings` only from `context.application.bot_data.get("settings")`. When bot context is injected via `app_context` container (e.g. `bot_data = {"app_context": app_context}` as tested in multiple modules), `settings` is `None` and `db_path` falls back to hardcoded `"cassette_store.db"`. This diverges from `process_search_query:110` which inspects `getattr(app_context, "settings", None)`.
**Fix:**
```python
def _get_active_db_context(context: ContextTypes.DEFAULT_TYPE):
    """Resolve active database connection or create context connection per G-04-3."""
    app_context = context.application.bot_data.get("app_context")
    db = getattr(app_context, "db", None) if app_context else context.application.bot_data.get("db")
    settings = getattr(app_context, "settings", None) if app_context else context.application.bot_data.get("settings")
    db_path = getattr(settings, "sqlite_db_path", "cassette_store.db") if settings else "cassette_store.db"
    return nullcontext(db) if db else get_db_connection(db_path)
```

### WR-02: Missing `BadRequest` ("Message is not modified") Suppression in `sch_bk`

**File:** `src/bot/handlers/search.py:325, 332, 355`
**Issue:** In `handle_search_callback`, the `sch_bk:` callback handler invokes `query.edit_message_text()` without wrapping in `try ... except BadRequest` checking for `"Message is not modified"`. All other callback cases (`sch_cancel`, `sch_new`, `sch_pg`, `sch_v`) handle this exception. Rapid double-taps by users on the back button will raise unhandled `BadRequest` exceptions.
**Fix:**
Wrap `edit_message_text` calls in `sch_bk:` with:
```python
        try:
            await query.edit_message_text(text=card_text, reply_markup=kb, parse_mode="HTML")
        except BadRequest as e:
            if "Message is not modified" not in str(e):
                raise
```

### WR-03: Conversational Search Patterns Miss Multiline Queries Due to Missing `re.DOTALL`

**File:** `src/services/order_search.py:26-41`
**Issue:** Patterns in `SEARCH_CONVERSATIONAL_PATTERNS` using `.*?` without `re.DOTALL` fail when query keywords and inquiry question markers span across line breaks (e.g., `"Anh Tuấn đã từng mua băng\nbao giờ chưa?"`).
**Fix:**
Add `re.DOTALL` flag to compiled conversational patterns:
```python
SEARCH_CONVERSATIONAL_PATTERNS: tuple[re.Pattern, ...] = (
    re.compile(r"\b(?:đã|từng)\s+mua\b.*?\b(?:chưa|bao\s+giờ\s+chưa|không)\b", re.IGNORECASE | re.DOTALL),
    re.compile(r"\bcó\s+mua\b.*?\b(?:không|chưa|bao\s+giờ\s+chưa)\b", re.IGNORECASE | re.DOTALL),
    re.compile(r"\b(?:mấy|bao\s+nhiêu)\s+đơn\b", re.IGNORECASE),
    re.compile(r"\bbán\s+(?:được\s+)?(?:bao\s+nhiêu|mấy)\b", re.IGNORECASE),
    re.compile(r"\blịch\s+sử\s+(?:mua|đơn)\b", re.IGNORECASE),
    re.compile(r"\b(?:tra\s+cứu|tìm\s+kiếm|xem\s+lại\s+đơn|kiểm\s+tra\s+đơn)\b", re.IGNORECASE),
    re.compile(r"\b(?:mua|đơn)\b.*?\b(?:bao\s+giờ\s+chưa|chưa\s+nhỉ|chưa\s+bác|chưa\s+shop|không\s+nhỉ)\b", re.IGNORECASE | re.DOTALL),
)
```

## Info

### IN-01: Unchecked Integer Casting on Callback Data

**File:** `src/bot/handlers/search.py:260, 368`
**Issue:** `int(parts[2])` in `sch_pg:` and `sch_v:` will throw uncaught `ValueError` if callback data payload is non-numeric or malformed.
**Fix:** Parse integer inside a helper or `try ... except ValueError` fallback.

### IN-02: Trailing Empty Lines in Test File

**File:** `tests/test_order_search.py:798-803`
**Issue:** Six consecutive trailing blank lines at end of file.
**Fix:** Remove redundant blank lines to adhere to PEP 8 single trailing newline standard.

---

_Reviewed: 2026-10-25T08:55:00Z_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
