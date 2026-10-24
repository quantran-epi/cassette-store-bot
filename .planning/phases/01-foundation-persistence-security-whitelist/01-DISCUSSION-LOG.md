# Phase 1: Foundation, Persistence & Security Whitelist - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-10-24
**Phase:** 1-foundation-persistence-security-whitelist
**Areas discussed:** Bảo mật Whitelist, Schema DB SQLite, Cấu hình & Cấu trúc mã, Khởi động & Diagnostics

---

## Bảo mật Whitelist

| Option | Description | Selected |
|--------|-------------|----------|
| Báo từ chối kèm User ID | Gửi tin nhắn lịch sự từ chối kèm Telegram User ID của họ (để chủ shop dễ lấy ID thêm vào whitelist khi cần) | ✓ |
| Im lặng tuyệt đối (Drop) | Không gửi bất kỳ tin nhắn phản hồi nào khi User ID không nằm trong whitelist, log cảnh báo ở terminal | |

**User's choice:** Báo từ chối kèm User ID
**Notes:** Giúp chủ shop dễ dàng lấy ID người thân/nhân viên để thêm vào .env mà không cần dùng bot phụ lấy ID.

---

## Schema DB SQLite (Lưu ảnh)

| Option | Description | Selected |
|--------|-------------|----------|
| JSON string file_id | Mỗi đơn hàng có 1 mảng JSON chứa các Telegram file_id (đơn giản, đủ cho nhu cầu lưu và xem lại ảnh trong chat) | ✓ |
| Bảng riêng order_images | Tạo bảng order_images riêng liên kết order_id với file_id và timestamp tải lên | |

**User's choice:** JSON string file_id
**Notes:** Giữ DB tinh gọn, không cần tạo thêm quan hệ bảng phức tạp khi nhu cầu chỉ là xem lại ảnh đính kèm theo đơn.

---

## Schema DB SQLite (Khách hàng)

| Option | Description | Selected |
|--------|-------------|----------|
| Bảng customers + JSON array | Bảng customers lưu name, notes, phones (JSON array), addresses (JSON array) + bảng orders lưu snapshot tên, SĐT, địa chỉ lúc đặt | ✓ |
| Tách bảng riêng 1-N chuẩn | Tách hẳn bảng customer_phones và customer_addresses riêng có foreign key tới customers | |

**User's choice:** Bảng customers + JSON array
**Notes:** Giảm thiểu JOIN nhiều bảng, truy vấn nhanh và phù hợp hoàn toàn với quy mô cửa hàng nhỏ.

---

## Cấu hình & Cấu trúc mã

| Option | Description | Selected |
|--------|-------------|----------|
| Thư mục src/ mô-đun hoá | Gói trọn trong package `src/` (config.py, database.py, models.py, bot.py, security.py) kèm file chạy `main.py` ở root | ✓ |
| Flat files ở root | Tất cả gom trong 1-2 file script ở thư mục gốc | |

**User's choice:** Thư mục src/ mô-đun hoá
**Notes:** Đảm bảo khả năng mở rộng code và viết test độc lập cho DB/Bot/LLM trong các phase tiếp theo.

---

## Claude's Discretion

- Chi tiết câu lệnh SQL CREATE TABLE và định dạng phản hồi `/start`, `/ping`.

## Deferred Ideas

None — discussion stayed within phase scope.
