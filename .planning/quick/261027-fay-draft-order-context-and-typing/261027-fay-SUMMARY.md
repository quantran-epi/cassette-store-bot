---
phase: 261027-fay
plan: 01
type: execute
subsystem: bot-ux
tags: [mutation, llm, prompt-context, typing-indicator, telegram]
requires:
  - src/services/mutation_extractor.py
provides:
  - src/services/mutation_extractor.py#extract_mutation_delta(current_order=...)
  - src/bot/handlers/base.py#run_with_typing
affects:
  - src/bot/handlers/ingest.py
  - src/bot/handlers/mutation.py
  - src/bot/handlers/search.py
  - src/bot/handlers/order_actions.py
  - src/bot/handlers/callbacks.py
tech-stack:
  added: []
  patterns: [prompt-context-injection, long-running-typing-heartbeat]
key-files:
  created: []
  modified:
    - src/services/mutation_extractor.py
    - src/bot/handlers/base.py
    - src/bot/handlers/ingest.py
    - src/bot/handlers/mutation.py
    - src/bot/handlers/search.py
    - src/bot/handlers/order_actions.py
    - src/bot/handlers/callbacks.py
    - tests/test_mutation_extractor.py
decisions:
  - "current_order chỉ áp cho luồng draft; luồng DB giữ nguyên vì extract chạy trước khi biết đơn đích"
  - "run_with_typing đặt ở handlers/base để tránh vòng import; search.py re-export qua import"
metrics:
  duration: ~25m
  completed: 2026-10-27
---

# Quick 261027-fay: Draft order context + typing until result

## What shipped

**Sửa đơn nháp có ngữ cảnh.** `extract_mutation_delta(..., current_order=draft)` chèn thẻ
`<current_order>` (tên, SĐT, địa chỉ, hàng hoá, tổng, COD, ghi chú) trước `<message>`.
Prompt thêm 2 quy tắc: chỉ trả field được yêu cầu đổi, và `new_items_text` phải là toàn bộ
danh sách sau thêm/bớt. Luồng sửa đơn trong DB giữ nguyên (param optional).

**Typing bền tới khi có kết quả.** `src/bot/handlers/base.py::run_with_typing(chat, coro)`
gửi `ChatAction.TYPING` mỗi 4s và dừng khi coro xong. Áp dụng cho: extract đơn text/ảnh,
extract delta (draft + DB), `classify_intent`, fallback Text-to-SQL khi sửa đơn, extract
reminder, broadcast sau khi lưu đơn. `search.py` bỏ bản sao trùng, import từ `base`.

## Verification

- `python -m pytest -q` → 362 passed.
- `ruff check src/` → clean.
- Runtime check của `run_with_typing` với coro 9s: 3 lần gõ phím, dừng ngay khi coro xong.
- 2 test mới trong `tests/test_mutation_extractor.py` xác nhận thứ tự message và
  việc không gửi `<current_order>` khi param bỏ trống.

## Deviations

Không. Scope giữ đúng luồng draft và typing.
