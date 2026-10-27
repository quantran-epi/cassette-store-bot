---
phase: 261027-fay
plan: 01
type: execute
wave: 1
depends_on: []
files_modified:
  - src/services/mutation_extractor.py
  - src/bot/handlers/base.py
  - src/bot/handlers/ingest.py
  - src/bot/handlers/mutation.py
  - src/bot/handlers/search.py
  - src/bot/handlers/order_actions.py
  - src/bot/handlers/callbacks.py
  - tests/test_mutation_extractor.py
autonomous: true
requirements: ["QUICK-261027-DRAFT-CONTEXT", "QUICK-261027-TYPING"]
user_setup: []

must_haves:
  truths:
    - "Sửa đơn nháp: LLM nhận được thông tin đơn hiện tại qua thẻ <current_order>, nên câu mơ hồ như 'sửa địa chỉ cho đúng' vẫn hiểu đúng trường"
    - "Sửa đơn nháp thêm/bớt băng: new_items_text trả về TOÀN BỘ danh sách sau khi sửa, không mất băng cũ"
    - "Luồng sửa đơn đã lưu trong DB giữ nguyên hành vi cũ (không gửi current_order) — không đổi latency"
    - "Mọi chỗ gọi LLM/DB chậm (tạo đơn, sửa draft, sửa đơn DB, tra cứu, nhắc việc, broadcast) đều hiện 'đang nhập…' lặp lại mỗi 4s cho tới khi có kết quả"
  artifacts:
    - path: "src/bot/handlers/base.py"
      provides: "run_with_typing helper dùng chung"
    - path: "src/services/mutation_extractor.py"
      provides: "extract_mutation_delta(current_order=...)"
  key_links:
    - from: "src/bot/handlers/ingest.py"
      to: "src/services/mutation_extractor.py"
      via: "extract_mutation_delta(current_order=draft) trong run_with_typing"
---

# Plan: Draft order context + typing indicator

## Task 1 — `<current_order>` cho luồng sửa draft
- `mutation_extractor.py`: thêm param `current_order: dict | None = None`; chèn message `<current_order>` trước `<message>`.
- System prompt: thêm 2 quy tắc (chỉ trả field được yêu cầu đổi; `new_items_text` = toàn bộ danh sách sau sửa).
- `ingest.py`: hoist `draft` lên trước lời gọi extract, truyền `current_order=draft`.

## Task 2 — Typing tới khi có kết quả
- `base.py`: `run_with_typing(chat, coro)` — gửi `ChatAction.TYPING` mỗi 4s, dừng khi coro xong.
- Thay `send_action` một-lần bằng `run_with_typing` tại: `ingest.py` (extract đơn, extract draft, classify_intent), `mutation.py` (extract delta, fallback Text-to-SQL), `order_actions.py` (extract reminder), `callbacks.py` (broadcast sau khi lưu đơn).
- `search.py`: xoá bản sao `run_with_typing` trùng lặp, import từ `base`.
