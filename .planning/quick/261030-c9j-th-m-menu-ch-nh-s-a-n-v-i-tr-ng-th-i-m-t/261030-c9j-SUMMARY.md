---
status: complete
---

# Thêm menu chính sửa đơn

- Nút `✏️ Sửa đơn` có trong Reply Keyboard; dispatcher bắt trước text ingestion.
- Bấm nút mở `mutation_state` 120 giây; tin nhắn kế tiếp đi qua mutation flow một lần, gồm bước xác nhận hiện có.
- Menu khác xoá trạng thái sửa/tra cứu trước đó; giữ nguyên nháp chưa lưu.
- Chế độ sửa còn hạn ưu tiên hơn chỉnh nháp; hết hạn trở về luồng tạo đơn nếu không có ngữ cảnh khác.
- Text ngoài chế độ vẫn theo fast path tạo đơn, không gọi classifier.

## Xác minh

```sh
python -m pytest tests/test_orders_ui.py tests/test_mutation_handler_flow.py tests/test_order_search.py tests/test_ingest.py tests/test_tutorial.py
```

Kết quả: 134 passed in 11.62s. Test dùng mocks, không network/DB production.

Ruff các file sửa: All checks passed. `git diff --check`: pass.

Không chạy lại full suite trong lượt này; lượt trước còn lỗi backup restore không liên quan tại `tests/test_backup_restore.py:150`.

## Git

Code đã commit: `6ed081a`. Các test biên bổ sung còn trong working tree. Không push.
