# Requirements: Cassette Store Telegram Chatbot

**Defined:** 2026-10-25
**Core Value:** Người lớn tuổi nhập tự do một đoạn tin nhắn đặt hàng bất kỳ qua Telegram, bot dùng LLM tự bóc tách chính xác thông tin (khách, hàng hoá, tiền COD, hình thức), hiển thị nút bấm xác nhận trực quan và lưu trữ an toàn vào DB mà không cần thao tác biểu mẫu phức tạp.

## Milestone v1.1 Requirements

### Natural Language Order Mutation (MUT)

- [ ] **MUT-01**: User có thể nhắn tin tự do chứa ý định chỉnh sửa đơn hàng, hệ thống dùng 3-Way Intent Router tách biệt chính xác với Tạo đơn và Tìm kiếm
- [ ] **MUT-02**: Hệ thống tìm đúng đơn hàng cần sửa dựa trên từ khoá (mã đơn, tên khách, số điện thoại, giá tiền), nếu khớp nhiều đơn thì hiển thị danh sách nút bấm để chọn
- [ ] **MUT-03**: Hệ thống dùng LLM trích xuất delta thay đổi cho 5 nhóm trường: Trạng thái đơn (8 trạng thái), Mã vận đơn, Ghi chú, Tiền COD/tổng đơn, SĐT/địa chỉ nhận hàng
- [ ] **MUT-04**: Hệ thống hiển thị thẻ so sánh Trước ➡️ Sau (Visual Diff) kèm nút bấm Inline `[✅ Xác nhận sửa]` và `[❌ Huỷ]` (hết hạn sau 120s)
- [ ] **MUT-05**: Khi câu chat chưa chỉ định rõ trạng thái đích, hệ thống hiển thị danh sách nút bấm trạng thái gợi ý để người dùng chọn 1-chạm

### Role-Based Access Control & Telegram Admin Suite (RBAC)

- [x] **RBAC-01**: Hệ thống lưu trữ danh sách quản trị viên trong bảng `admin_users` với 2 cấp độ: `SUPER_ADMIN` và `ADMIN`, neo cứng `SUPER_ADMIN_ID` gốc trong cấu hình `.env` để chống tự khoá
- [x] **RBAC-02**: Decorator phân quyền `@require_role` kiểm soát chặt chẽ cả lệnh gõ (`/admin`, `/backup`, `/logs`) lẫn các nút bấm `CallbackQuery` để chống leo thang đặc quyền
- [x] **RBAC-03**: Quản trị viên có thể mở menu `/admin` trên Telegram để xem trạng thái hệ thống (bot, DB, LLM) và cấu hình chuyển đổi model LLM 9router trực tiếp
- [x] **RBAC-04**: Quản trị viên trên Telegram có thể quản lý whitelist người dùng (xem danh sách, thêm mới, xoá Telegram ID khỏi whitelist) với hiệu lực tức thì
- [x] **RBAC-05**: Super Admin có thể xem log gần nhất qua lệnh `/logs` (ring buffer 25-50 dòng định dạng `<pre>` HTML) trực tiếp trên Telegram mà không cần truy cập terminal

### Telegram Database Backup Engine (BKP)

- [x] **BKP-01**: Hệ thống tạo bản sao lưu snapshot SQLite an toàn bằng lệnh `VACUUM INTO` từ live DB đang bật WAL và nén bằng `gzip` giảm 75-85% dung lượng
- [x] **BKP-02**: Hệ thống gửi file nén `.sqlite3.gz` trực tiếp qua Telegram Document tới chat riêng của Super Admin (`TELEGRAM_SUPER_ADMIN_ID`) kèm kiểm tra giới hạn 50MB
- [x] **BKP-03**: Hệ thống tự động sao lưu định kỳ hàng ngày vào lúc 02:00 sáng (giờ Việt Nam, UTC+7) thông qua PTB JobQueue / background scheduler
- [x] **BKP-04**: Super Admin có thể kích hoạt sao lưu thủ công tức thì theo yêu cầu bằng lệnh `/backup` hoặc nút bấm trên menu `/admin` kèm phản hồi file ngay lập tức

### Containerization & Production Deployment (DEP)

- [ ] **DEP-01**: `Dockerfile` tối ưu multi-stage trên nền `python:3.12-slim`, chạy với non-root user (UID 10001) và cấu hình múi giờ `TZ=Asia/Ho_Chi_Minh`
- [ ] **DEP-02**: Thư mục dữ liệu `/app/data` được cấu hình volume mount để bảo toàn file SQLite chính và các file WAL (`-wal`, `-shm`) khi container khởi động lại
- [ ] **DEP-03**: File cấu hình `docker-compose.yml` chuẩn production với biến môi trường, health check, chính sách restart và volume mount dữ liệu bền vững
- [ ] **DEP-04**: Bộ manifest Kubernetes chuẩn: `Deployment` (enforce `replicas: 1` và `strategy.type: Recreate`), PersistentVolumeClaim (RWO), ConfigMap và Secret
- [ ] **DEP-05**: Cơ chế tắt container an toàn (graceful shutdown) bắt tín hiệu `SIGTERM`/`SIGINT`, thực thi `PRAGMA wal_checkpoint(TRUNCATE)` và đóng kết nối DB sạch sẽ

## Future Requirements (v2)

### Voice & Multi-channel

- **VOICE-01**: Bóc tách ghi âm giọng nói (voice message) qua Whisper API để sửa đơn hoặc tạo đơn
- **VOICE-02**: Trả lời xác nhận bằng giọng nói tổng hợp TTS thân thiện với người khiếm thị

### Advanced Operations

- **RESTORE-01**: Wizard khôi phục dữ liệu từ file backup gửi ngược lại vào Telegram chat
- **ANALYTICS-01**: Báo cáo doanh thu biểu đồ nâng cao qua tin nhắn hình ảnh Telegram

## Out of Scope

| Feature | Reason |
|---------|--------|
| Interactive Server Console App (CLI) | Merchant operates 100% on mobile Telegram. Telegram Admin Suite and `/logs` eliminate the need for server SSH terminal access. |
| GitHub Contents API Backup | Native Telegram Document upload to Super Admin is faster, free, zero external credentials, and avoids GitHub token expiration. |
| Multi-replica Kubernetes autoscaling | SQLite is single-writer. Running multiple replicas on shared storage causes database corruption. Strictly enforce `replicas: 1` with `Recreate`. |
| Web-Based Admin Dashboard (FastAPI/React) | Adds port exposure, TLS certificates, and auth attack surface without helping the elderly merchant who lives in Telegram. |
| Direct NL Mutation Without Confirmation | Voice-to-text noise or accidental typos could silently overwrite order records. 2-phase diff preview with 120s TTL is mandatory. |

## Traceability

| Requirement | Phase | Status |
|-------------|-------|--------|
| RBAC-01 | Phase 5 | Validated |
| RBAC-02 | Phase 5 | Validated |
| RBAC-03 | Phase 5 | Complete |
| RBAC-04 | Phase 5 | Complete |
| RBAC-05 | Phase 5 | Validated |
| BKP-01 | Phase 6 | Complete |
| BKP-02 | Phase 6 | Complete |
| BKP-03 | Phase 6 | Complete |
| BKP-04 | Phase 6 | Complete |
| MUT-01 | Phase 7 | Pending |
| MUT-02 | Phase 7 | Pending |
| MUT-03 | Phase 7 | Pending |
| MUT-04 | Phase 7 | Pending |
| MUT-05 | Phase 7 | Pending |
| DEP-01 | Phase 8 | Pending |
| DEP-02 | Phase 8 | Pending |
| DEP-03 | Phase 8 | Pending |
| DEP-04 | Phase 8 | Pending |
| DEP-05 | Phase 8 | Pending |

**Coverage:**

- Milestone v1.1 requirements: 19 total
- Mapped to phases: 19
- Unmapped: 0 ✓

---
*Requirements defined: 2026-10-25*
*Last updated: 2026-10-25 after milestone v1.1 scope adjustment*
