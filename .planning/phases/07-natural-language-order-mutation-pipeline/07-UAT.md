---
status: diagnosed
phase: 07-natural-language-order-mutation-pipeline
source: 07-01-SUMMARY.md, 07-02-SUMMARY.md, 07-03-SUMMARY.md
started: 2026-10-25T16:50:00Z
updated: 2026-10-25T19:05:00Z
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
reported: "tìm anh hà nhưng bot tìm ra cả người là tên là thanh (khớp substring 'ha' thay vì từ nguyên vẹn); ngoài ra câu hỏi kết hợp như 'anh tuấn gia lâm' bot không tìm được trong khi tính năng tra cứu tìm được."
severity: major

### 3. Gợi ý trạng thái tiếp theo 1-chạm (MUT-05)
expected: Nhắn `chuyển trạng thái đơn 1`. Bot hiển thị các nút trạng thái hợp lý theo vòng đời, ấn sửa cập nhật thành công không bị báo xung đột giả.
result: pass

### 4. Hết hạn TTL 120s
expected: Gửi yêu cầu sửa đơn, đợi quá 120s rồi bấm nút xác nhận. Bot báo hết hạn, gỡ sạch inline keyboard buttons, DB giữ nguyên.
result: pass

### 5. Cảnh báo xung đột (Optimistic Lock)
expected: 2 tài khoản cùng sửa đơn #1. Tài khoản bấm sau nhận cảnh báo xung đột nêu rõ tên người sửa, giờ sửa và chi tiết thay đổi.
result: pass

## Summary

total: 5
passed: 4
issues: 1
pending: 0
skipped: 0
blocked: 0

## Gaps

- truth: "Tạo 2 đơn cùng tên khách \"Bác Ba\", nhắn `đổi sđt khách Bác Ba thành 0988776655`. Bot hiện danh sách nút inline 1-chạm, bấm chọn chuyển mượt sang thẻ diff."
  status: failed
  reason: "User reported: tìm anh hà nhưng bot tìm ra cả người là tên là thanh (khớp substring 'ha' thay vì từ nguyên vẹn); ngoài ra câu hỏi kết hợp như 'anh tuấn gia lâm' bot không tìm được trong khi tính năng tra cứu tìm được."
  severity: major
  test: 2
  root_cause: "1) find_orders_for_mutation dùng LIKE '%ha%' không xét word boundary làm 'thanh' bị match nhầm khi tìm 'ha'. 2) find_orders_for_mutation chỉ tìm trên customer_name/customer_phone mà bỏ qua shipping_address, đồng thời tìm nguyên cụm từ đơn lẻ nên truy vấn kết hợp tên + địa chỉ ('anh tuấn gia lâm') trả về 0 kết quả."
  artifacts:
    - path: "src/db/orders.py"
      issue: "find_orders_for_mutation thiếu word boundary matching (gây khớp nhầm chuỗi con) và thiếu tìm kiếm liên trường tên + địa chỉ (shipping_address) với token AND logic"
    - path: "src/bot/handlers/mutation.py"
      issue: "handle_mutation_request gọi SQL tĩnh hạn chế thay vì hỗ trợ tìm kiếm đa trường hoặc tận dụng logic tìm kiếm ngôn ngữ tự nhiên"
  missing:
    - "Cơ chế word boundary matching (' ' || unaccent(customer_name) || ' ' LIKE '% kw %') để loại trừ khớp chuỗi con không mong muốn"
    - "Tìm kiếm đa trường (customer_name + shipping_address + items_text) với token tách biệt và AND logic cho các truy vấn kết hợp như 'anh tuấn gia lâm'"
  debug_session: .planning/debug/disambiguation-substring-and-composite-search.md
