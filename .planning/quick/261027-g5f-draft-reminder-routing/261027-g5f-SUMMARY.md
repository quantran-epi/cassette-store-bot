---
phase: 261027-g5f
plan: 01
type: execute
subsystem: bot-ux
tags: [mutation, reminder, prompt-context, draft]
requires:
  - src/services/mutation_extractor.py
provides:
  - OrderMutationDelta.new_reminder_at / new_reminder_note / clear_reminder
  - src/services/mutation_extractor.py#build_mutation_system_prompt
affects:
  - src/bot/handlers/ingest.py
tech-stack:
  added: []
  patterns: [prompt-time-injection, field-routing]
key-files:
  created: []
  modified:
    - src/models/mutation.py
    - src/services/mutation_extractor.py
    - src/bot/handlers/ingest.py
    - tests/test_ingest.py
decisions:
  - "Giờ hẹn giao/gửi thuộc nhóm nhắc việc, không thuộc ghi chú; prompt cấm rõ ràng"
  - "new_notes giữ ngữ nghĩa THAY THẾ, không nối chuỗi, tránh ghi chú rác tích luỹ"
  - "clear_reminder là cờ riêng thay vì nhét 'không nhắc nữa' vào notes"
metrics:
  duration: ~20m
  completed: 2026-10-27
---

# Quick 261027-g5f: Reminder routing in the draft-edit flow

## What shipped

- `OrderMutationDelta` thêm `new_reminder_at`, `new_reminder_note`, `clear_reminder`.
- `MUTATION_SYSTEM_PROMPT`: nhóm 6 "Nhắc việc"; cấm đưa ngày/giờ hẹn vào `new_notes`;
  đổi ví dụ `new_notes` từ "ghi chú giao sau 18h" (mẫu gây nhiễu) sang "khách dặn gọi trước".
- `build_mutation_system_prompt(now_vn=None)` bơm mốc thời gian VN (hôm nay, thứ, ngày mai)
  giống `extractor.py`; `MUTATION_SYSTEM_PROMPT` vẫn là hằng số cho test.
- Merge draft trong `ingest.py`: reminder đi vào `draft["reminder_at"]`/`["reminder_note"]`,
  `clear_reminder` xoá cả hai, `new_notes` vẫn thay thế.
- `<current_order>` bổ sung dòng "Lịch nhắc" để LLM biết đơn đang có reminder hay không.

## Verification

- `python -m pytest -q` → 366 passed (4 test mới).
- `ruff check src/` clean.
- Render thật `render_preview_card` với draft có reminder: thẻ hiện cả
  `GHI CHÚ` và `LỊCH NHẮC: 2026-10-28 10:00 (Gửi hàng cho khách)`.

## Deviations

Không. Luồng sửa đơn đã lưu (`mutate_order_with_lock`) giữ nguyên.
