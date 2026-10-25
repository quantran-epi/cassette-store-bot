---
status: diagnosed
phase: 07-natural-language-order-mutation-pipeline
source: 07-01-SUMMARY.md, 07-02-SUMMARY.md
started: 2026-10-25T16:50:00Z
updated: 2026-10-25T17:40:00Z
---

## Current Test

[testing complete]

## Tests

### 1. Thẻ Visual Diff Before ➡️ After trên Telegram Mobile
expected: Gửi tin nhắn sửa địa chỉ đơn 1. Thẻ diff hiển thị divider 14 ký tự chuẩn D-19, chỉ in trường thay đổi kèm 2 nút xác nhận / huỷ.
result: pass

### 2. Chọn đơn 1-chạm khi khớp nhiều đơn (Disambiguation)
expected: Tạo 2 đơn cùng tên khách "Bác Ba", nhắn `đổi sđt khách Bác Ba thành 0988776655`. Bot hiện danh sách nút inline 1-chạm, bấm chọn chuyển mượt sang thẻ diff.
result: issue
reported: "fail, bot báo không tìm thấy đơn nào của xxx"
severity: blocker

### 3. Gợi ý trạng thái tiếp theo 1-chạm (MUT-05)
expected: Nhắn `chuyển trạng thái đơn 1`. Bot hiển thị các nút trạng thái hợp lý theo vòng đời và nút `[❌ Huỷ bỏ]`.
result: issue
reported: "có hiện trạng thái hợp lý nhưng khi ấn sửa thì báo xung đột, mặc dù không có ai sửa, báo đơn hàng vừa được chính tôi sửa lúc xxx, khả năng là lúc tạo đơn"
severity: major

### 4. Hết hạn TTL 120s
expected: Gửi yêu cầu sửa đơn, đợi quá 120s rồi bấm nút xác nhận. Bot báo hết hạn, gỡ sạch inline keyboard buttons, DB giữ nguyên.
result: pass

### 5. Cảnh báo xung đột (Optimistic Lock)
expected: 2 tài khoản cùng sửa đơn #1. Tài khoản bấm sau nhận cảnh báo xung đột nêu rõ tên người sửa, giờ sửa và chi tiết thay đổi.
result: issue
reported: "cái này khả năng cũng lỗi vì theo test 3 thì tính năng check cùng sửa đơn đang hoạt động không đúng"
severity: major

## Summary

total: 5
passed: 2
issues: 3
pending: 0
skipped: 0
blocked: 0

## Gaps

- truth: "Tạo 2 đơn cùng tên khách \"Bác Ba\", nhắn `đổi sđt khách Bác Ba thành 0988776655`. Bot hiện danh sách nút inline 1-chạm, bấm chọn chuyển mượt sang thẻ diff."
  status: failed
  reason: "User reported: fail, bot báo không tìm thấy đơn nào của xxx"
  severity: blocker
  test: 2
  root_cause: "find_orders_for_mutation dùng LIKE '%{kw}%' nguyên văn mà LLM bóc tách keyword kèm từ xưng hô/tiền tố ('khách Bác Ba'), DB chỉ lưu 'Bác Ba' nên không khớp; ngoài ra _clean_json_markdown không lọc được text giải thích ngoài JSON block khi 9router trả về markdown chatter."
  artifacts:
    - path: "src/db/orders.py"
      issue: "find_orders_for_mutation chưa chuẩn hoá lọc bỏ từ đệm/xưng hô (khách, anh, chị, bác, đơn, của) hoặc chưa tách từ khoá token"
    - path: "src/services/mutation_extractor.py"
      issue: "_clean_json_markdown chưa dùng regex bóc tách khối {...} an toàn khi có text giải thích thừa"
  missing:
    - "Lọc bỏ từ xưng hô/từ đệm và tìm kiếm linh hoạt trong find_orders_for_mutation"
    - "Dùng regex trích xuất {...} an toàn trong _clean_json_markdown và tinh chỉnh prompt trích xuất keyword gọn"
  debug_session: .planning/debug/disambiguation-order-not-found.md

- truth: "Nhắn `chuyển trạng thái đơn 1`. Bot hiển thị các nút trạng thái hợp lý theo vòng đời, ấn sửa cập nhật thành công không bị báo xung đột giả."
  status: failed
  reason: "User reported: có hiện trạng thái hợp lý nhưng khi ấn sửa thì báo xung đột, mặc dù không có ai sửa, báo đơn hàng vừa được chính tôi sửa lúc xxx, khả năng là lúc tạo đơn"
  severity: major
  test: 3
  root_cause: "mutate_order_with_lock so sánh chuỗi thô current_updated_at_str != expected_updated_at_str. SQLite strftime format 3 số thập phân (.024) trong khi datetime string format 6 số thập phân (.024000), khiến so sánh chuỗi bị lệch và kích hoạt cảnh báo xung đột giả."
  artifacts:
    - path: "src/db/orders.py"
      issue: "mutate_order_with_lock so sánh chuỗi thời gian thô thay vì chuẩn hoá ISO/datetime"
    - path: "src/bot/handlers/mutation.py"
      issue: "lưu expected_updated_at dạng str(datetime) lệch định dạng với SQLite string"
  missing:
    - "Chuẩn hoá timestamp về cùng định dạng hoặc parse datetime trước khi so sánh optimistic lock"
  debug_session: .planning/debug/false-positive-conflict-detection.md

- truth: "2 tài khoản cùng sửa đơn #1. Tài khoản bấm sau nhận cảnh báo xung đột nêu rõ tên người sửa, giờ sửa và chi tiết thay đổi."
  status: failed
  reason: "User reported: cái này khả năng cũng lỗi vì theo test 3 thì tính năng check cùng sửa đơn đang hoạt động không đúng"
  severity: major
  test: 5
  root_cause: "Cùng root cause với Test 3: logic optimistic lock so sánh lệch định dạng timestamp millisecond (SQLite) vs microsecond (Python datetime)."
  artifacts:
    - path: "src/db/orders.py"
      issue: "mutate_order_with_lock timestamp format mismatch"
  missing:
    - "Chuẩn hoá so sánh timestamp trong mutate_order_with_lock"
  debug_session: .planning/debug/false-positive-conflict-detection.md
