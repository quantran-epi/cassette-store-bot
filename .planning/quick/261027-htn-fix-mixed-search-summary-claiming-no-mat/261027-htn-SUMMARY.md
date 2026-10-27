---
phase: 261027-htn
plan: 01
subsystem: order-search
tags: [search, summary, prompt, mixed-query]
dependency_graph:
  requires: []
  provides:
    - "summarize_aggregate_result(list_total=) keyword arg"
    - "matched_order_count fact in summary user content"
  affects:
    - src/services/order_search.py
tech_stack:
  added: []
  patterns:
    - "deterministic fact injection into LLM summary prompt"
key_files:
  created: []
  modified:
    - src/services/order_search.py
    - tests/test_order_search.py
    - tests/test_search_mixed_pagination.py
decisions:
  - "Enforce absence-claim ban via prompt rule + deterministic fact, no new post-filter"
  - "MIXED runs list statement first so summarizer gets the real match count"
metrics:
  duration: ~8m
  completed: 2026-10-27
---

# Phase 261027-htn Plan 01: Fix MIXED Search Summary Claiming No Matches Summary

## One-liner

MIXED search summaries now receive a deterministic `matched_order_count` fact plus a prompt rule that forbids claiming "không bán được ... nào" when the count is positive.

## What Changed

- `SYSTEM_PROMPT_SUMMARY` gained the `QUY TẮC SỐ ĐƠN KHỚP` paragraph; all prior content untouched.
- `summarize_aggregate_result(*, list_total: int | None = None)` appends
  `matched_order_count: N (số đơn khớp câu hỏi; bot hiển thị danh sách các đơn này bên dưới câu trả lời)`
  to the user message only when `list_total > 0`. `raw_rows` is not mutated.
- `_run_aggregate(*, list_total=None)` forwards the value.
- `_execute_search_statements` MIXED branch runs `_run_list` first, then passes
  `list_total=total_count if rows_are_orders else None`. The 1-statement ORDERS/AGGREGATE
  path and the `total_count and not rows_are_orders` fallback are unchanged and never pass the fact.

## Verification

- `python -m pytest tests/test_order_search.py tests/test_search_mixed_pagination.py -q` -> 50 passed.
- `python -m pytest -q` -> 378 passed, 3 warnings (pre-existing PTB JobQueue warnings).

## Deviations from Plan

None - plan executed exactly as written.

## Known Stubs

None.

## Self-Check: PASSED

- src/services/order_search.py exists
- tests/test_order_search.py exists
- tests/test_search_mixed_pagination.py exists
- commits bbd8129, 2d3e6e1 present
