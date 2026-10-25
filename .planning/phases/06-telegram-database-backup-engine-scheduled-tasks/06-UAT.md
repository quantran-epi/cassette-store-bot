---
status: complete
phase: 06-telegram-database-backup-engine-scheduled-tasks
source: [06-VERIFICATION.md]
started: 2026-10-25T14:46:00Z
updated: 2026-10-25T14:50:00Z
---

## Current Test

[testing complete]

## Tests

### 1. Gõ lệnh /backup trong chat Telegram với bot bằng tài khoản Super Admin
expected: Bot lập tức gửi tin nhắn tiến trình '⏳ Đang tạo snapshot...', sau đó cập nhật thông số và gửi file Document 'cassette_store_backup_YYYYMMDD_HHMMSS.sqlite3.gz' không kèm inline keyboard.
result: pass

### 2. Mở menu /admin, bấm nút [💾 Sao lưu DB] bằng tài khoản Super Admin
expected: Tin nhắn được sửa thành thông báo tiến trình, tạo snapshot và gửi file Document nén trực tiếp vào chat. Tài khoản không có quyền Super Admin bấm vào sẽ hiện popup từ chối.
result: pass

### 3. Tải file .sqlite3.gz từ Telegram về máy tính cá nhân và giải nén
expected: File giải nén thành file .sqlite3 nguyên vẹn, mở được bằng DB Browser for SQLite hoặc sqlite3 CLI, đọc đủ bảng orders và customers với dữ liệu khớp với DB bot.
result: pass

### 4. Vào menu /admin -> [⏰ Đặt giờ sao lưu] -> chọn mốc giờ hoặc bấm [✏️ Nhập giờ khác] và nhập '04:15'
expected: Giao diện cập nhật giờ sao lưu mới với biểu tượng tích xanh, bot xác nhận đặt lịch thành công mà không cần restart.
result: pass

### 5. Vào menu /admin -> [👥 Quản lý danh sách truy cập] -> chọn 1 user -> bấm [✏️ Đổi tên] -> gửi tin nhắn tên mới
expected: Thẻ thông tin người dùng được cập nhật tên hiển thị mới ngay lập tức.
result: pass

## Summary

total: 5
passed: 5
issues: 0
pending: 0
skipped: 0
blocked: 0

## Gaps

[none]
