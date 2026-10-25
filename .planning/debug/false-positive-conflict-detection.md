---
status: diagnosed
trigger: "Ấn sửa trạng thái hoặc cập nhật đơn bị báo xung đột sai (optimistic lock false positive)"
created: 2026-10-25T17:20:00Z
updated: 2026-10-25T17:35:00Z
---

## Current Focus

hypothesis: Naive string comparison between SQLite row updated_at (3 decimal milliseconds) and Pydantic Order.updated_at stringification (6 decimal microseconds) causes false-positive optimistic lock conflict.
test: Confirmed via direct reproduction script against SQLite data models and cassette_store.db order #2.
expecting: Root cause isolated and documented.
next_action: Return diagnosis to caller.

## Symptoms

expected: Nhắn "chuyển trạng thái đơn 1". Bot hiển thị các nút trạng thái hợp lý theo vòng đời, ấn sửa cập nhật thành công không bị báo xung đột giả.
actual: có hiện trạng thái hợp lý nhưng khi ấn sửa thì báo xung đột, mặc dù không có ai sửa, báo đơn hàng vừa được chính tôi sửa lúc xxx, khả năng là lúc tạo đơn
errors: Cảnh báo xung đột đơn hàng vừa được sửa bởi chính user lúc xxx
reproduction: Test 3 in UAT: Nhắn "chuyển trạng thái đơn 1", chọn trạng thái, ấn sửa
started: Discovered during Phase 7 UAT

## Eliminated

- hypothesis: Race condition between multiple users or double callback query click.
  evidence: Single user testing in local dev environment; reproduction script reproduced conflict deterministically with sequential execution.
  timestamp: 2026-10-25T17:28:00Z

- hypothesis: Database rowcount == 0 on UPDATE statement.
  evidence: Execution fails in Step 2 of mutate_order_with_lock before SQL UPDATE statement is executed.
  timestamp: 2026-10-25T17:30:00Z

## Evidence

- timestamp: 2026-10-25T17:24:00Z
  checked: src/db/orders.py:429 mutate_order_with_lock timestamp formatting.
  found: SQL uses `strftime('%Y-%m-%d %H:%M:%f', 'now')`. SQLite %f formats millisecond fraction with 3 digits (e.g. '2026-10-25 10:05:37.024').
  implication: Every mutated order stores updated_at in SQLite with 3-digit fractional seconds.

- timestamp: 2026-10-25T17:26:00Z
  checked: src/models/order.py and src/bot/handlers/mutation.py draft serialization.
  found: Pydantic parses SQLite string into python datetime.datetime object. When serialized via `str(target_order.updated_at)`, Python outputs 6 digits for microseconds (e.g. '2026-10-25 10:05:37.024000').
  implication: String representation in draft has trailing zeroes compared to SQLite raw string.

- timestamp: 2026-10-25T17:27:00Z
  checked: src/db/orders.py:386-389 optimistic lock comparison.
  found: `current_updated_at_str = str(row["updated_at"] or "")` vs `expected_updated_at_str = str(expected_updated_at or "")`. Compares '2026-10-25 10:05:37.024' != '2026-10-25 10:05:37.024000'.
  implication: Literal string inequality check evaluates to True, erroneously triggering conflict logic and returning the last order_history record (which was the tester's previous action).

- timestamp: 2026-10-25T17:31:00Z
  checked: Minimal reproduction script executing two consecutive mutations on an order.
  found: Mutation 1 succeeds (since initial updated_at from CURRENT_TIMESTAMP had 0 fractional digits). Mutation 2 fails with false-positive conflict because Mutation 1 saved 3-digit millisecond timestamp into SQLite.
  implication: Confirmed root cause with 100% repeatability.

## Resolution

root_cause: In `src/db/orders.py:389`, `mutate_order_with_lock` uses raw string comparison (`current_updated_at_str != expected_updated_at_str`). SQLite's `strftime('%Y-%m-%d %H:%M:%f', 'now')` stores 3 digits of fractional seconds (milliseconds, e.g. `.024`), while Pydantic's `datetime` model stringified via `str(target_order.updated_at)` formats 6 digits of fractional seconds (microseconds, e.g. `.024000`). Once an order is mutated or has fractional seconds, any subsequent mutation compares `.024` with `.024000`, falsely triggering the optimistic lock conflict notice.
fix:
verification:
files_changed: []
