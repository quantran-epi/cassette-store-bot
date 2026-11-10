---
status: complete
date: 2026-11-04
---

# Quick Task Summary: Milestone Broadcast Admin Only

## Overview
Đã cập nhật cơ chế broadcast chúc mừng shop đạt mốc kỷ lục (milestone celebration broadcast) để chỉ gửi cho các tài khoản có vai trò `ADMIN` hoặc `SUPER_ADMIN`, không gửi cho nhân viên (`STAFF`) hoặc toàn bộ whitelist.

## Changes Made
1. **`src/db/admin.py`**:
   - Thêm hàm `get_admin_user_ids(db)` để query các `telegram_id` có `role IN ('SUPER_ADMIN', 'ADMIN')`.
2. **`src/services/milestones.py`**:
   - Cập nhật hàm `check_and_trigger_milestones`:
     - Tự động lấy danh sách người nhận từ `get_admin_user_ids(db)` (hoặc nhận `admin_ids` ghi đè).
     - Duy trì fallback `whitelist_ids` đối với các mock test chưa seed bảng `admin_users`.
     - Chỉ gửi broadcast chúc mừng tới danh sách admin và super admin này.
3. **`src/bot/handlers/callbacks.py`, `src/bot/handlers/bulk_status.py`, `src/bot/handlers/order_actions.py`**:
   - Dọn dẹp việc truyền `whitelist_ids` vào `check_and_trigger_milestones`, để tầng service tự truy vấn admin/super admin từ DB.
4. **`tests/test_milestones.py`**:
   - Bổ sung test `test_milestone_broadcast_admin_only` kiểm tra:
     - `SUPER_ADMIN` và `ADMIN` nhận được thông báo.
     - `STAFF` không nhận được thông báo.
     - Tùy chọn override qua `admin_ids`.

## Verification
- Chạy `pytest tests/test_milestones.py tests/test_admin_handlers.py`: 25 passed 100%.
