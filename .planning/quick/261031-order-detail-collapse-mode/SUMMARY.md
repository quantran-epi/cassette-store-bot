---
status: complete
date: 2026-10-31
slug: order-detail-collapse-mode
description: Collapse mode for order details, cleaner list layout with bullet dividers and creation timestamps
---

# Quick Task Summary: Order Detail Collapse Mode & List Cleanups

## Outcomes
1. **Order Detail Collapse Mode**:
   - Mặc định chỉ hiển thị:
     - Nút tiến tiến độ (tự động theo trạng thái)
     - Nút xem ảnh (chỉ khi có ảnh)
     - Nút `[ 🚚 Tạo đơn vận chuyển ]`
     - Nút `[ ⚙️ Thao tác khác ▾ ]`
     - Nút `[ ⬅️ Quay lại ]` (chỉ khi đi từ danh sách)
   - Ẩn toàn bộ nút ít dùng (copy SĐT/Địa chỉ, mã vận đơn, gửi thêm ảnh, nhắc lịch, sửa thông tin, đổi trạng thái khác, xoá đơn) vào menu mở rộng.
   - Bấm `[ ⚙️ Thao tác khác ▾ ]` bung toàn bộ nút kèm nút `[ 🔼 Thu gọn ]`.
   - Bảo toàn navigation callback `back_callback_data` khi expand/collapse.

2. **Order List UI Cleanups**:
   - Bỏ các filter chips trạng thái ("⏳ Chờ làm", "🛠️ Đang làm", "📦 Đã đóng gói") khỏi list inline keyboard.
   - Bỏ nút "📝 Nhập đơn mới" ở chân list (đã có trên Reply Keyboard).
   - Rút gọn tiêu đề item: bỏ chữ `ĐƠN`, hiển thị dạng `📦 #ID — Tên khách`.
   - Bổ sung ngày giờ tạo đơn `🕒 TẠO: DD/MM/YYYY HH:MM` trong từng item.
   - Chuyển `DIVIDER` chính sang dạng chấm bullet `••••••••••••••`.
   - Bổ sung `ITEM_DIVIDER = "────────"` phân tách rõ ràng giữa các item trong list.

3. **Verification**:
   - Tất cả 472/472 unit and integration tests passed.
