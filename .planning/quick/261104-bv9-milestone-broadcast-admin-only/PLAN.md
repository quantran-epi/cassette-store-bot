# Quick Task: Milestone Broadcast Admin Only

## Goal
Sửa cơ chế gửi thông báo chúc mừng mốc (milestone celebration broadcast) để chỉ gửi cho các user có quyền `ADMIN` và `SUPER_ADMIN`, thay vì gửi cho toàn bộ người dùng trong whitelist (bao gồm cả nhân viên `STAFF`).

## Root Cause
Hiện tại trong các handlers (`callbacks.py`, `bulk_status.py`, `order_actions.py`), bot lấy toàn bộ `whitelist_user_ids` từ `context.bot_data` và truyền vào `check_and_trigger_milestones(..., whitelist_ids=whitelist_ids)`. Hàm này sau đó gọi `broadcast_to_whitelist(..., whitelist_ids=unique_whitelist)` gửi tới toàn bộ whitelist.

## Proposed Changes
1. **`src/db/admin.py`**:
   - Thêm hàm `get_admin_user_ids(db: aiosqlite.Connection) -> list[int]`: lấy danh sách `telegram_id` có `role IN ('SUPER_ADMIN', 'ADMIN')` từ bảng `admin_users`.
2. **`src/services/milestones.py`**:
   - Sửa `check_and_trigger_milestones`:
     - Thêm tham số `admin_ids: Iterable[int] | None = None`.
     - `whitelist_ids: Iterable[int] | None = None`.
     - Phân giải `target_ids`: ưu tiên `admin_ids`, nếu không có thì query `get_admin_user_ids(db)`. Fallback `whitelist_ids` nếu `admin_users` chưa seed (dành cho legacy mock tests).
     - Chỉ broadcast tới `target_ids` (ADMIN & SUPER_ADMIN).
3. **`src/bot/handlers/callbacks.py`, `src/bot/handlers/bulk_status.py`, `src/bot/handlers/order_actions.py`**:
   - Bỏ việc truyền `whitelist_ids=whitelist_ids` vào `check_and_trigger_milestones`, để hàm tự resolve danh sách admin/super admin từ DB.
4. **`tests/test_milestones.py`**:
   - Bổ sung unit test xác thực broadcast mốc chỉ gửi cho SUPER_ADMIN và ADMIN, bỏ qua STAFF.

## Verification
- Chạy `pytest tests/test_milestones.py` pass 100%.
- Kiểm tra linter / code check.
