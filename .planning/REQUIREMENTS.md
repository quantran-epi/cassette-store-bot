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

- [ ] **RBAC-01**: Hệ thống lưu trữ danh sách quản trị viên trong bảng `admin_users` với 2 cấp độ: `SUPER_ADMIN` và `ADMIN`, neo cứng `SUPER_ADMIN_ID` gốc trong cấu hình `.env` để chống tự khoá
- [ ] **RBAC-02**: Decorator phân quyền `@require_role` kiểm soát chặt chẽ cả lệnh gõ (`/admin`, `/backup`) lẫn các nút bấm `CallbackQuery` để chống leo thang đặc quyền
- [ ] **RBAC-03**: Quản trị viên có thể mở menu `/admin` trên Telegram để xem trạng thái hệ thống, thống kê doanh thu, và kích hoạt backup dữ liệu
- [ ] **RBAC-04**: Super Admin có thể thêm hoặc xoá user khỏi nhóm Admin qua giao diện Telegram; Admin cấp 2 bị chặn hoàn toàn quyền can thiệp danh sách Admin

### Interactive Server Console App (CLI)

- [ ] **CLI-01**: Console chạy trực tiếp trên terminal server, đọc input không đồng bộ không làm nghẽn event loop của Telegram và tự phát hiện chế độ headless (`isatty`)
- [ ] **CLI-02**: Quản trị viên console có thể xem bảng điều khiển trạng thái (trạng thái bot, SQLite DB, kết nối LLM 9router) và log gần nhất
- [ ] **CLI-03**: Quản trị viên console có thể quản lý danh sách whitelist (xem danh sách, thêm Telegram ID mới, xoá Telegram ID)
- [ ] **CLI-04**: Quản trị viên console có thể điều chỉnh cấu hình model LLM (xem model hiện tại, đổi Model ID 9router) áp dụng ngay lập tức
- [ ] **CLI-05**: Quản trị viên console có thể kích hoạt sao lưu cơ sở dữ liệu lên GitHub ngay lập tức bằng lệnh dòng lệnh

### GitHub Database Backup Engine (BKP)

- [ ] **BKP-01**: Hệ thống tạo bản sao lưu snapshot SQLite an toàn bằng lệnh `VACUUM INTO` từ live DB đang bật WAL và nén bằng `gzip` giảm 75-85% dung lượng
- [ ] **BKP-02**: Hệ thống tải trực tiếp file nén `.db.gz` lên private GitHub repository qua GitHub Contents REST API bằng `httpx` không cần Git CLI hoặc SSH key
- [ ] **BKP-03**: Hệ thống tự động sao lưu định kỳ hàng ngày vào lúc 02:00 sáng (giờ Việt Nam, UTC+7) thông qua PTB JobQueue (APScheduler)
- [ ] **BKP-04**: Hệ thống hỗ trợ kích hoạt sao lưu thủ công tức thì theo yêu cầu từ cả Console server lẫn nút bấm Telegram của Admin kèm thông báo kết quả

## Future Requirements (v2)

### Voice & Multi-channel
- **VOICE-01**: Bóc tách ghi âm giọng nói (voice message) qua Whisper API để sửa đơn hoặc tạo đơn
- **VOICE-02**: Trả lời xác nhận bằng giọng nói tổng hợp TTS thân thiện với người khiếm thị

### Advanced Operations
- **RESTORE-01**: Wizard khôi phục dữ liệu từ GitHub backup trực tiếp trên console
- **ANALYTICS-01**: Báo cáo doanh thu biểu đồ nâng cao qua tin nhắn hình ảnh Telegram

## Out of Scope

| Feature | Reason |
|---------|--------|
| Web-based Dashboard (Flask/FastAPI/React) | Vi phạm nguyên tắc zero-maintenance, tăng bề mặt tấn công; Telegram + Console terminal đáp ứng 100% nhu cầu quản trị |
| Git CLI subprocess & SSH keys on server | Dễ xung đột merge, lỗi key SSH; dùng trực tiếp GitHub Contents REST API qua `httpx` gọn nhẹ hơn |
| Sửa đơn trực tiếp không qua xác nhận 2-phase | Rủi ro xoá nhầm hoặc sai lệch dữ liệu do nhận diện giọng nói/text; bắt buộc phải có thẻ so sánh và nút bấm xác nhận |
| Đồng bộ tự động 2 chiều API vận chuyển | Người dùng tự tạo đơn app ngoài; bot giữ vai trò sổ tay số hoá thông minh |

## Traceability

| Requirement | Phase | Status |
|-------------|-------|--------|
| MUT-01 | TBD | Pending |
| MUT-02 | TBD | Pending |
| MUT-03 | TBD | Pending |
| MUT-04 | TBD | Pending |
| MUT-05 | TBD | Pending |
| RBAC-01 | TBD | Pending |
| RBAC-02 | TBD | Pending |
| RBAC-03 | TBD | Pending |
| RBAC-04 | TBD | Pending |
| CLI-01 | TBD | Pending |
| CLI-02 | TBD | Pending |
| CLI-03 | TBD | Pending |
| CLI-04 | TBD | Pending |
| CLI-05 | TBD | Pending |
| BKP-01 | TBD | Pending |
| BKP-02 | TBD | Pending |
| BKP-03 | TBD | Pending |
| BKP-04 | TBD | Pending |

**Coverage:**
- v1.1 requirements: 18 total
- Mapped to phases: 0
- Unmapped: 18 ⚠️ (Will be mapped during Roadmap creation)

---
*Requirements defined: 2026-10-25*
*Last updated: 2026-10-25 after milestone v1.1 scoping*
