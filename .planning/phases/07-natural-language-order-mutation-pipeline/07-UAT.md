---
status: complete
phase: 07-natural-language-order-mutation-pipeline
source: 07-01-SUMMARY.md, 07-02-SUMMARY.md
started: 2026-10-25T16:50:00Z
updated: 2026-10-25T17:20:00Z
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
  artifacts: []
  missing: []
- truth: "Nhắn `chuyển trạng thái đơn 1`. Bot hiển thị các nút trạng thái hợp lý theo vòng đời, ấn sửa cập nhật thành công không bị báo xung đột giả."
  status: failed
  reason: "User reported: có hiện trạng thái hợp lý nhưng khi ấn sửa thì báo xung đột, mặc dù không có ai sửa, báo đơn hàng vừa được chính tôi sửa lúc xxx, khả năng là lúc tạo đơn"
  severity: major
  test: 3
  artifacts: []
  missing: []
- truth: "2 tài khoản cùng sửa đơn #1. Tài khoản bấm sau nhận cảnh báo xung đột nêu rõ tên người sửa, giờ sửa và chi tiết thay đổi."
  status: failed
  reason: "User reported: cái này khả năng cũng lỗi vì theo test 3 thì tính năng check cùng sửa đơn đang hoạt động không đúng"
  severity: major
  test: 5
  artifacts: []
  missing: []
