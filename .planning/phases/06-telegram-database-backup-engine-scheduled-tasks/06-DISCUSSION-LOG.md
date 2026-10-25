# Phase 6: Telegram Database Backup Engine & Scheduled Tasks - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-10-25
**Phase:** 06-telegram-database-backup-engine-scheduled-tasks
**Areas discussed:** Lưu trữ tạm & Retention local, UX sao lưu thủ công & Caption, Xử lý vượt 50MB & Báo lỗi, Cơ chế Scheduler & Lập lịch, Hoàn thiện Admin Suite (Phase 5 carryover)

---

## 1. Lưu trữ tạm & Retention local

| Option | Description | Selected |
|--------|-------------|----------|
| Thư mục backups/ nội bộ (Recommended) | Tạo thư mục con backups/ cạnh file DB chính, snapshot và nén tại đây. Dễ debug, dễ mount volume trong Docker sau này. | ✓ |
| Thư mục tạm hệ thống /tmp | Dùng tempfile.NamedTemporaryFile của hệ thống OS, tự giải phóng sau khi xử lý. | |
| Nén gzip in-memory qua BytesIO | Dùng tempfile cho VACUUM INTO, nhưng stream thẳng vào io.BytesIO để nén gzip trong RAM trước khi gửi. | |

**User's choice:** Thư mục backups/ nội bộ (Recommended)
**Notes:** Giúp snapshot và lưu trữ có trật tự, dễ quản lý volume docker về sau.

| Option | Description | Selected |
|--------|-------------|----------|
| Giữ 7 ngày gần nhất (Recommended) | Giữ tối đa 7 file gần nhất trong thư mục backups/ làm dự phòng offline, tự dọn file cũ hơn khi chạy job mới. | ✓ |
| Xoá sạch ngay sau khi gửi | Gửi Telegram xong lập tức xoá sạch file khỏi đĩa local. Telegram là nơi lưu trữ duy nhất. | |
| Giữ 30 ngày gần nhất | Giữ 30 bản backup gần nhất (khoảng 1 tháng) trước khi dọn dẹp. | |

**User's choice:** Giữ 7 ngày gần nhất (Recommended)
**Notes:** Cân bằng hoàn hảo giữa dung lượng đĩa và tính sẵn sàng khi Telegram gặp sự cố mạng.

| Option | Description | Selected |
|--------|-------------|----------|
| cassette_store_backup_YYYYMMDD_HHMMSS (Recommended) | cassette_store_backup_YYYYMMDD_HHMMSS.sqlite3.gz — chuẩn ISO, sắp xếp thứ tự tự nhiên, không bao giờ trùng. | ✓ |
| backup_YYYYMMDD | backup_YYYY-MM-DD.sqlite3.gz — ngắn gọn nhưng cần thêm hậu tố nếu chạy thủ công nhiều lần trong ngày. | |

**User's choice:** cassette_store_backup_YYYYMMDD_HHMMSS (Recommended)

| Option | Description | Selected |
|--------|-------------|----------|
| Xoá file thô ngay sau khi nén (Recommended) | File snapshot .sqlite3 thô được xoá lập tức trong khối try/finally ngay sau khi nén thành .gz thành công. | ✓ |
| Giữ cả thô và nén | Giữ cả file thô và file .gz trên đĩa trong suốt thời gian retention. | |

**User's choice:** Xoá file thô ngay sau khi nén (Recommended)
**Notes:** Xoá trong try/finally đảm bảo an toàn kể cả khi quá trình nén gặp trục trặc.

---

## 2. UX sao lưu thủ công & Caption

| Option | Description | Selected |
|--------|-------------|----------|
| Báo tiến trình trước khi gửi file (Recommended) | Báo trạng thái ngay '⏳ Đang snapshot & nén DB...', sau đó gửi file Document kèm thông báo hoàn tất. | ✓ |
| Gửi trực tiếp không qua tin chờ | Không gửi tin nhắn chờ, nén xong gửi thẳng file Document để tiết kiệm số lượng tin nhắn trong chat. | |

**User's choice:** Báo tiến trình trước khi gửi file (Recommended)
**Notes:** Phản hồi UX tức thì giúp người dùng yên tâm bot đang xử lý.

| Option | Description | Selected |
|--------|-------------|----------|
| Chi tiết dung lượng & số lượng đơn (Recommended) | Bao gồm: Thời gian snapshot (UTC+7), dung lượng gốc, dung lượng nén (tỷ lệ nén %), tổng số đơn hàng & khách hàng đang lưu trong DB. | ✓ |
| Chi tiết + SHA-256 Checksum | Bao gồm chi tiết trên + mã băm SHA-256 của file nén để kiểm tra tính toàn vẹn khi tải về. | |
| Tối giản (chỉ giờ & dung lượng) | Chỉ ghi ngày giờ và dung lượng file nén đơn giản. | |

**User's choice:** Chi tiết dung lượng & số lượng đơn (Recommended)

| Option | Description | Selected |
|--------|-------------|----------|
| File thuần túy không kèm nút (Recommended) | Gửi file document nguyên bản không kèm nút bấm, người dùng dễ chạm tải về hoặc chuyển tiếp (forward/save). | ✓ |
| Kèm nút quay lại Menu Admin | Đính kèm hàng nút Inline bên dưới: [🔄 Sao lưu lại] [⬅️ Về Menu Admin] để tiếp tục thao tác. | |

**User's choice:** File thuần túy không kèm nút (Recommended)

| Option | Description | Selected |
|--------|-------------|----------|
| Gửi vào chat của Super Admin gọi lệnh (Recommended) | Luôn gửi tới chat ID của người gọi (đã xác thực vai trò SUPER_ADMIN qua @require_role). | ✓ |
| Cố định theo ID trong .env | Cưỡng chế gửi về TELEGRAM_SUPER_ADMIN_ID cố định trong .env bất kể ai gọi lệnh. | |

**User's choice:** Gửi vào chat của Super Admin gọi lệnh (Recommended)

---

## 3. Xử lý vượt 50MB & Báo lỗi

| Option | Description | Selected |
|--------|-------------|----------|
| Cảnh báo text & giữ file local (Recommended) | Không gửi file, ghi log ERROR, gửi tin nhắn cảnh báo đỏ cho Super Admin kèm đường dẫn file local trên máy chủ để lấy thủ công. | ✓ |
| Chia nhỏ file multi-part | Tự động cắt nhỏ file nén thành nhiều phần <45MB và gửi lần lượt từng phần. | |
| Chỉ ghi log không báo | Chỉ ghi log hệ thống, không gửi tin nhắn cảnh báo. | |

**User's choice:** Cảnh báo text & giữ file local (Recommended)

| Option | Description | Selected |
|--------|-------------|----------|
| Retry 3 lần + Báo lỗi text (Recommended) | Thử lại 3 lần (backoff 2s, 5s, 10s); nếu vẫn thất bại thì gửi tin text báo lỗi cho Super Admin, giữ nguyên file trên ổ đĩa local. | ✓ |
| Thử 1 lần, bỏ qua nếu lỗi | Chỉ thử 1 lần; nếu lỗi thì ghi log và bỏ qua lượt sao lưu đó. | |

**User's choice:** Retry 3 lần + Báo lỗi text (Recommended)

| Option | Description | Selected |
|--------|-------------|----------|
| Bọc try/except an toàn tuyệt đối (Recommended) | Bọc toàn bộ tác vụ backup trong try/except; bất kỳ lỗi nào cũng ghi log stacktrace và không bao giờ crash bot hay ảnh hưởng luồng bán hàng. | ✓ |
| Ném lỗi ra ngoài | Để lỗi bung ra ngoài để supervisor/Docker biết và restart lại bot. | |

**User's choice:** Bọc try/except an toàn tuyệt đối (Recommended)

| Option | Description | Selected |
|--------|-------------|----------|
| Luôn báo tin nhắn lỗi cho Super Admin (Recommended) | Luôn gửi tin nhắn khẩn báo lỗi backup vào chat riêng Super Admin kèm nguyên nhân vắn tắt. | ✓ |
| Chỉ ghi log âm thầm | Chỉ ghi log nội bộ, không gửi tin nhắn ban đêm để tránh làm phiền. | |

**User's choice:** Luôn báo tin nhắn lỗi cho Super Admin (Recommended)

---

## 4. Cơ chế Scheduler & Lập lịch

| Option | Description | Selected |
|--------|-------------|----------|
| PTB JobQueue tích hợp (Recommended) | Cài đặt python-telegram-bot[job-queue] (dựa trên APScheduler), dùng job_queue.run_daily() tích hợp sẵn trong Application. Quản lý lifecycle chuẩn. | ✓ |
| Asyncio Background Task thuần | Dùng asyncio loop nền tự viết với asyncio.sleep tính toán thời gian tới 02:00 sáng, không cần cài thêm thư viện APScheduler. | |

**User's choice:** PTB JobQueue tích hợp (Recommended)

| Option | Description | Selected |
|--------|-------------|----------|
| Chỉ chờ đúng 02:00, không backup lúc boot (Recommended) | Chỉ đăng ký lịch chạy tiếp theo vào 02:00 sáng tới; KHÔNG tự động gửi backup lúc bot vừa khởi động để tránh spam khi reboot. | ✓ |
| Backup bù nếu trong 24h chưa có | Khi bot bật lên, nếu kiểm tra thấy trong 24h qua chưa có bản backup nào thì tự động chạy ngay 1 bản bù. | |

**User's choice:** Chỉ chờ đúng 02:00, không backup lúc boot (Recommended)

| Option | Description | Selected |
|--------|-------------|----------|
| Biến môi trường .env linh hoạt (Recommended) | Cấu hình giờ/phút qua biến môi trường .env (mặc định 02:00 AM UTC+7) qua Pydantic Settings. | |
| Cố định 02:00 trong code | Hardcode cố định 02:00 sáng (Asia/Ho_Chi_Minh) trong code theo đúng đặc tả BKP-03. | |
| admin có thể cấu hình (Free text) | Người dùng yêu cầu admin có thể cấu hình trực tiếp qua menu admin. | ✓ |

**User's choice:** Cấu hình qua menu admin
**Notes:** Lưu cấu hình vào `system_settings` trong DB (key `backup_schedule_time`), áp dụng lại JobQueue tức thì khi thay đổi.

| Option | Description | Selected |
|--------|-------------|----------|
| Chỉ Super Admin toàn quyền (Recommended) | Chỉ SUPER_ADMIN mới được kích hoạt /backup và nhận file backup định kỳ (ADMIN thường bị từ chối với thông báo thiếu quyền). | ✓ |
| Admin được kích hoạt thủ công | Cho phép cả ADMIN thường kích hoạt /backup thủ công, nhưng backup định kỳ chỉ gửi về Super Admin. | |

**User's choice:** Chỉ Super Admin toàn quyền (Recommended)

---

## 5. Hoàn thiện & Tinh chỉnh Admin Suite (Phase 5 carryover)

Người dùng yêu cầu bổ sung/tinh chỉnh từ Phase 5:
1. **Model Switcher**: Danh sách chọn nhanh ban đầu rỗng, admin nhập text thêm model mới (sau khi ping probe thành công), cho phép xoá model khỏi danh sách chọn nhanh.
2. **Whitelist Management**: Cho phép sửa tên/ghi nhớ (rename) cho user trong whitelist (trước đó chỉ có phân quyền và xoá).

**Quyết định:** Gộp trực tiếp 2 hạng mục này vào phạm vi thực hiện của Phase 6 để gom chung vào các module quản trị `admin.py`.

---

## Claude's Discretion

- Định dạng chi tiết chuỗi HTML cho Caption và tin nhắn báo lỗi.
- Chi tiết cấu trúc module `src/services/backup.py`.
- Mức độ nén gzip (sử dụng gzip level 6 cân bằng dung lượng và tốc độ).

## Deferred Ideas

- RESTORE-01: Wizard khôi phục dữ liệu từ file backup gửi ngược lại vào Telegram chat (dành cho v2).
- ANALYTICS-01: Báo cáo biểu đồ doanh thu nâng cao gửi qua Telegram (dành cho v2).
