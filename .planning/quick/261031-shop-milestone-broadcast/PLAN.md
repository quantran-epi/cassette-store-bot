# Quick Task: Shop Milestone Broadcast (Mốc Chúc Mừng & Bắn Pháo Hoa)

## Goal
Bổ sung tính năng cấu hình các mốc kỷ lục shop (số đơn, doanh thu) theo chu kỳ (tuần, tháng, năm, toàn bộ). Khi shop chạm mốc, bot tự động bắn tin nhắn chúc mừng kèm hiệu ứng pháo hoa (Telegram message effect) tới toàn bộ danh sách quản lý (whitelist). Admin có toàn quyền xem, thêm, bật/tắt, xóa các mốc và tùy biến nội dung (AI gợi ý sẵn).

## Key Requirements
1. **Phạm vi tính toán**:
   - Chu kỳ: Tuần (`week`), Tháng (`month`), Năm (`year`), Toàn bộ (`all_time`).
   - Loại chỉ số: Số đơn (`order_count`) hoặc Doanh số (`revenue`).
   - Điều kiện lọc: Chỉ đơn giao thành công (`only_delivered=1`) hoặc Tất cả đơn trừ bom/hủy (`only_delivered=0`).
2. **Điểm kích hoạt (Trigger)**:
   - Khi tạo đơn mới: quét các mốc `only_delivered=0`.
   - Khi đơn đổi sang `DA_GIAO`: quét các mốc `only_delivered=1`.
   - Chỉ bắn 1 lần duy nhất cho mỗi mốc trong mỗi chu kỳ (lưu vào `milestone_logs`).
3. **Hiệu ứng pháo hoa Telegram**:
   - `message_effect_id = "5046509860389126442"` (Party Popper 🎉).
   - Cho phép bật/tắt hiệu ứng trên từng mốc.
4. **Quản trị Admin (/admin -> 🎯 Mốc chúc mừng)**:
   - Danh sách mốc hiện tại kèm trạng thái.
   - Thêm mốc mới tương tác từng bước qua nút bấm.
   - AI sinh lời chúc mẫu hào hứng, admin có thể chọn dùng ngay hoặc gõ lời chúc riêng.
   - Bật/tắt hoặc xoá mốc.

## Architecture & Files
1. `src/db/schema.py`:
   - Tạo bảng `milestone_rules` và `milestone_logs`.
2. `src/models/milestone.py`:
   - Pydantic models: `MilestoneRule`, `MilestoneLog`, enums `MilestonePeriod`, `MilestoneTargetType`.
3. `src/db/milestones.py`:
   - CRUD functions cho rules và logs, hàm tính `get_current_milestone_metric(db, period, target_type, only_delivered)`.
4. `src/services/milestones.py`:
   - `check_and_trigger_milestones(...)`: logic quét mốc, format message, broadcast to whitelist.
   - `suggest_milestone_template(...)`: sinh mẫu lời chúc qua LLM hoặc fallback local template.
5. `src/services/notifications.py`:
   - Bổ sung tham số `message_effect_id` vào `broadcast_to_whitelist`.
6. `src/bot/keyboards.py`:
   - Thêm nút "🎯 Mốc chúc mừng" vào `build_admin_main_keyboard`.
   - Keyboards quản lý mốc: danh sách rules, detail rule, wizard tạo rule (chọn period, type, filter, effect).
7. `src/bot/handlers/admin_milestones.py`:
   - Xử lý các callback `adm:ms:*` và input wizard nhập số / sửa lời chúc.
8. Hooks tích hợp:
   - `src/bot/handlers/callbacks.py` (sau khi tạo đơn).
   - `src/bot/handlers/order_actions.py` (sau khi chuyển trạng thái DA_GIAO).
   - `src/bot/handlers/bulk_status.py` (sau khi bulk chuyển sang DA_GIAO).
9. Tests:
   - `tests/test_milestones.py`: kiểm tra schema, CRUD, metric query theo tuần/tháng/năm, trigger broadcast, effect ID, deduplication.
