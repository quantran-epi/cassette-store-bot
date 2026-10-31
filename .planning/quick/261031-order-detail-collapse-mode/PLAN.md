# Quick Task: Order Detail Collapse Mode

## Goal
Tối ưu UI chi tiết đơn hàng cho người lớn tuổi / low-tech:
- Mặc định ở chế độ thu gọn (collapsed mode): chỉ hiển thị nút tiến tiến độ (nếu có), nút xem ảnh (chỉ khi có ảnh), nút tạo đơn vận chuyển, nút "⚙️ Thao tác khác ▾", và nút "⬅️ Quay lại" (nếu đi từ danh sách).
- Ẩn các nút ít dùng (copy SĐT/địa chỉ, mã vận đơn, gửi thêm ảnh, nhắc lịch, sửa thông tin, đổi trạng thái khác, xoá đơn) vào menu mở rộng.
- Khi bấm "⚙️ Thao tác khác ▾": bung toàn bộ các nút hành động kèm nút "🔼 Thu gọn thao tác" để thu lại.

## Key Changes
1. `src/bot/keyboards.py`:
   - Cập nhật `build_order_detail_keyboard` hỗ trợ `expanded: bool = False` và `show_back: bool | None = None`.
   - Collapsed mode: chỉ render tiến độ, xem ảnh (nếu có ảnh), tạo đơn vận chuyển, "⚙️ Thao tác khác ▾", và nút quay lại (nếu `show_back`).
   - Expanded mode: render toàn bộ các nút cũ + nút "🔼 Thu gọn thao tác" + nút quay lại.
2. `src/bot/handlers/order_actions.py`:
   - Thêm `more` và `less` vào `ACTION_CALLBACK_PATTERN`.
   - Trong `handle_order_action_callback`: xử lý `action_type in ("more", "less")` để edit reply_markup giữa collapsed và expanded mode, bảo toàn `back_callback_data`.
3. `tests/`:
   - Cập nhật và bổ sung test cases cho collapsed mode, expanded mode, bảo toàn navigation.
