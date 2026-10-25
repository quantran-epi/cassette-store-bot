---
phase: 01-foundation-persistence-security-whitelist
reviewed: 2026-10-24T00:00:00Z
depth: standard
files_reviewed: 17
files_reviewed_list:
  - main.py
  - src/config.py
  - src/bot/app.py
  - src/bot/security.py
  - src/bot/handlers/base.py
  - src/db/connection.py
  - src/db/schema.py
  - src/db/customers.py
  - src/db/orders.py
  - src/models/customer.py
  - src/models/order.py
  - tests/conftest.py
  - tests/test_config.py
  - tests/test_security.py
  - tests/test_db_customers.py
  - tests/test_db_orders.py
  - tests/test_e2e_ping.py
findings:
  critical: 0
  warning: 3
  info: 3
  total: 6
status: issues_found
---

# Phase 01: Code Review Report

**Reviewed:** 2026-10-24T00:00:00Z
**Depth:** standard
**Files Reviewed:** 17
**Status:** issues_found

## Summary

Reviewed Phase 01 implementation across configuration, bot application scaffolding, access whitelist security gate, SQLite connection management, and domain models / repositories for customers and orders.

Overall architecture aligns with project constraints: PTB v20+ async with group -1 gate, `aiosqlite` WAL mode with busy timeout, and Pydantic-based configuration. 35 unit/integration tests pass.

Identified 3 warnings regarding data integrity and concurrent modifications:
1. `append_order_photos` has a read-modify-write race condition under concurrent requests.
2. `get_customer_by_phone` relies on SQLite `json_each` without phone normalization, causing lookup misses on formatting variations.
3. Unsanitized `user.id` interpolation in Markdown-formatted rejection/start messages could trigger `BadRequest` if formatted incorrectly.

## Critical Issues

No critical issues identified.

## Warnings

### WR-01: Read-Modify-Write Race Condition in Photo Append

**File:** `/Users/tranducquan/Working/cassette-store/src/db/orders.py:110-132`
**Issue:** `append_order_photos` reads existing `photo_file_ids` via `get_order_by_id`, concatenates new photos in Python memory, and issues an `UPDATE`. Under concurrent photo uploads for the same order, interleaved reads cause earlier uploaded photos to be overwritten and dropped.
**Fix:**
Perform append via atomic SQLite JSON functions (`json_insert` / `json_array`) or wrap operation in an explicit transaction:
```python
async def append_order_photos(
    db: aiosqlite.Connection, order_id: int, new_photo_ids: list[str]
) -> bool:
    if not new_photo_ids:
        return True

    # Use SQLite json_insert with json_array length to append atomically
    cursor = await db.execute(
        """
        UPDATE orders
        SET photo_file_ids = (
            SELECT json_insert(
                photo_file_ids,
                '$[' || json_array_length(photo_file_ids) || ']',
                val.value
            )
            FROM json_each(?) val
        ),
        updated_at = CURRENT_TIMESTAMP
        WHERE id = ?
        """,
        (json.dumps(new_photo_ids), order_id),
    )
    # Ponytail: alternatively lock order row in transaction before read-modify-write
```

---

### WR-02: Missing Phone Normalization on Customer Lookup

**File:** `/Users/tranducquan/Working/cassette-store/src/db/customers.py:51-64`
**Issue:** `get_customer_by_phone` queries exact value match `p.value = ?` on `json_each(c.phones)`. Vietnamese phone numbers arrive in multiple formats (`+8490...`, `090...`, `8490...`, spaces/dots like `090.123.4567`). Exact string match fails to recognize returning customers across varying input formats.
**Fix:**
Normalize phone digits before storing into `c.phones` and normalize search query in `get_customer_by_phone`:
```python
def normalize_phone(phone: str) -> str:
    digits = "".join(ch for ch in phone if ch.isdigit())
    if digits.startswith("84"):
        digits = "0" + digits[2:]
    return digits
```

---

### WR-03: Telegram Markdown Parse Mode Failure on Malformed Input

**File:** `/Users/tranducquan/Working/cassette-store/src/bot/security.py:25-30`
**Issue:** `whitelist_gate` sends rejection using `parse_mode="Markdown"` with raw interpolated `user.id`:
```python
f"Telegram User ID của bạn: `{user.id}`\n"
```
While `user.id` is an integer, `first_name` in `start_command` (`src/bot/handlers/base.py:19-25`) also sends Markdown without escaping special characters (`_`, `*`, `[`). Telegram returns HTTP 400 `BadRequest: Can't parse entities` if user display name contains Markdown tokens.
**Fix:**
Use `parse_mode="HTML"` with `html.escape(first_name)` or omit parse mode when plain text suffices:
```python
import html

# In start_command:
safe_name = html.escape(user.first_name if user else "bạn")
text = (
    f"Xin chào <b>{safe_name}</b>!\n\n"
    f"🤖 Bot Quản Lý Đơn Hàng Băng Cassette sẵn sàng phục vụ.\n"
    f"Telegram User ID nhận diện: <code>{user_id}</code>\n\n"
    f"Sử dụng lệnh /ping để kiểm tra trạng thái hoạt động."
)
await update.effective_message.reply_text(text, parse_mode="HTML")
```

## Info

### IN-01: Default In-Memory Isolation between Long-Lived Tasks

**File:** `/Users/tranducquan/Working/cassette-store/src/db/connection.py:8-18`
**Issue:** `get_db_connection` opens a new connection per context manager invocation. While WAL mode handles concurrent readers and one writer safely, connection pooling or persistent connection reuse in handler context can reduce file descriptor churn.
**Fix:**
Keep current per-operation context manager for now; consider passing single connection or pool when order throughput increases.

---

### IN-02: Missing Schema Versioning / Migration Table

**File:** `/Users/tranducquan/Working/cassette-store/src/db/schema.py:4-72`
**Issue:** `init_db` uses raw `CREATE TABLE IF NOT EXISTS`. Future schema alterations (adding new order columns in Phase 2/3) will require manual table migration or `PRAGMA user_version` tracking.
**Fix:**
Add `PRAGMA user_version` check or migration helper before adding columns in upcoming phases.

---

### IN-03: Unused Exception Detail in `/ping` Logs

**File:** `/Users/tranducquan/Working/cassette-store/src/bot/handlers/base.py:41-43`
**Issue:** `except Exception as e:` logs exception message but excludes stack trace (`logger.exception` or `exc_info=True`).
**Fix:**
Use `logger.exception("Database health probe failed during /ping")` to capture full stack trace when SQLite errors occur.

---

_Reviewed: 2026-10-24T00:00:00Z_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
