# Roadmap: Cassette Store Telegram Chatbot

## Milestones

- ✅ **v1.0 MVP** — Phases 1-4 (shipped 2026-10-25)
- 🚧 **v1.1 NL Order Mutation, Console Admin, Phân quyền & GitHub Backup** — Phases 5-8 (active)

## Phases

<details>
<summary>✅ v1.0 MVP (Phases 1-4) — SHIPPED 2026-10-25</summary>

- [x] Phase 1: Foundation, Persistence & Security Whitelist (3/3 plans) — completed 2026-10-24
- [x] Phase 2: LLM Ingestion & Interactive Confirmation (2/2 plans) — completed 2026-10-24
- [x] Phase 3: Ergonomic Order Management & Low-Tech Actions (3/3 plans) — completed 2026-10-24
- [x] Phase 4: Natural Language Order Search (3/3 plans) — completed 2026-10-25

</details>

### 🚧 v1.1 NL Order Mutation, Console Admin, Phân quyền & GitHub Backup

- [ ] **Phase 5: Database Backup Engine & Scheduled Tasks** - Tự động sao lưu SQLite snapshot định kỳ lên GitHub qua REST API và kích hoạt thủ công
- [ ] **Phase 6: Role-Based Access Control & Telegram Admin Suite** - Phân quyền 2 cấp độ Super Admin vs Admin, menu /admin Telegram và quản trị ủy quyền an toàn
- [ ] **Phase 7: Interactive Server Console App** - Terminal console quản lý bot, xem trạng thái, quản lý whitelist và đổi model LLM không làm nghẽn bot
- [ ] **Phase 8: Natural Language Order Mutation Pipeline** - 3-Way Intent Router, bóc tách delta thay đổi bằng LLM, thẻ so sánh trực quan Trước/Sau và xác nhận 1-chạm

## Phase Details

### Phase 5: Database Backup Engine & Scheduled Tasks
**Goal**: Dữ liệu đơn hàng và khách hàng được tự động sao lưu định kỳ lên GitHub an toàn mà không làm gián đoạn hoạt động của bot
**Depends on**: Milestone v1.0
**Requirements**: BKP-01, BKP-02, BKP-03, BKP-04
**Success Criteria** (what must be TRUE):
  1. Hệ thống tự động tạo bản sao lưu snapshot SQLite nén `.db.gz` và tải lên private repository GitHub mỗi ngày vào lúc 02:00 sáng (giờ Việt Nam) mà không gây gián đoạn đơn hàng đang xử lý
  2. Quản trị viên có thể kích hoạt sao lưu thủ công tức thì qua hàm dịch vụ hệ thống và nhận được thông báo xác nhận kèm tên file, dung lượng nén và link commit GitHub
  3. Khi sao lưu thành công, file `.db.gz` trên GitHub giải nén được thành file SQLite nguyên vẹn, đọc được toàn bộ bảng và dữ liệu đơn hàng mới nhất
  4. Khi xảy ra sự cố mạng hoặc lỗi GitHub API (sai token, repo không tồn tại), hệ thống ghi log lỗi chi tiết, không làm crash bot Telegram và gửi thông báo cảnh báo thất bại
**Plans**: TBD

### Phase 6: Role-Based Access Control & Telegram Admin Suite
**Goal**: Quản trị viên có thể quản lý quyền truy cập và kiểm soát toàn diện bot trực tiếp từ Telegram với đầy đủ tính năng ngang bằng console tại server (trạng thái, whitelist CRUD, đổi model LLM, backup, phân quyền an toàn)
**Depends on**: Phase 5
**Requirements**: RBAC-01, RBAC-02, RBAC-03, RBAC-04, RBAC-05
**Success Criteria** (what must be TRUE):
  1. Quản trị viên gõ `/admin` trên Telegram mở ra menu điều khiển hiển thị trạng thái hệ thống (bot, DB, LLM), thống kê doanh thu, nút bấm kích hoạt sao lưu tức thì và cấu hình đổi model LLM
  2. Quản trị viên có thể xem danh sách whitelist, thêm mới hoặc xoá Telegram User ID trực tiếp qua giao diện nút bấm/nhập liệu trên Telegram với hiệu lực tức thì
  3. Super Admin có thể thêm hoặc thu hồi quyền Admin của một Telegram User ID trực tiếp qua nút bấm trên Telegram; tài khoản Super Admin gốc trong `.env` không thể bị xoá hay hạ quyền
  4. Người dùng có quyền Admin thường (không phải Super Admin) khi bấm các nút quản trị phân quyền hoặc gõ lệnh hạn chế sẽ bị từ chối truy cập và thông báo cảnh báo
  5. Mọi lệnh quản trị và callback query nhạy cảm đều được bảo vệ bởi kiểm tra vai trò chặt chẽ; người lạ ngoài danh sách bị chặn ngay lập tức
**Plans**: TBD
**UI hint**: yes

### Phase 7: Interactive Server Console App
**Goal**: Quản trị viên máy chủ có thể giám sát trạng thái, điều chỉnh cấu hình và vận hành bot trực tiếp từ cửa sổ dòng lệnh terminal server
**Depends on**: Phase 5, Phase 6
**Requirements**: CLI-01, CLI-02, CLI-03, CLI-04, CLI-05
**Success Criteria** (what must be TRUE):
  1. Quản trị viên mở terminal chạy bot có thể gõ các lệnh console tương tác mà bot Telegram vẫn tiếp tục nhận và trả lời tin nhắn bình thường không bị nghẽn
  2. Quản trị viên có thể xem bảng điều khiển trạng thái bot, kết nối SQLite DB, kết nối LLM 9router và các dòng log mới nhất trực tiếp trên terminal
  3. Quản trị viên có thể tra cứu, thêm mới hoặc xoá Telegram User ID trong danh sách whitelist từ console mà thay đổi có hiệu lực ngay lập tức trên bot
  4. Quản trị viên có thể xem Model ID hiện tại và đổi sang model LLM khác trên 9router ngay trong console mà không cần khởi động lại tiến trình bot
  5. Quản trị viên gõ lệnh sao lưu trên console kích hoạt tiến trình sao lưu GitHub ngay lập tức và in kết quả chi tiết lên màn hình terminal
**Plans**: TBD

### Phase 8: Natural Language Order Mutation Pipeline
**Goal**: Người dùng có thể chỉnh sửa bất kỳ thông tin nào của đơn hàng bằng tin nhắn chat tiếng Việt tự nhiên và xác nhận qua thẻ so sánh trực quan một chạm
**Depends on**: Phase 5
**Requirements**: MUT-01, MUT-02, MUT-03, MUT-04, MUT-05
**Success Criteria** (what must be TRUE):
  1. Người dùng nhắn tin yêu cầu sửa đơn (đổi trạng thái, gán mã vận đơn, sửa ghi chú, sửa COD/giá tiền, đổi sđt/địa chỉ), hệ thống tự động nhận diện đúng ý định chỉnh sửa thay vì tạo đơn mới hay tìm kiếm
  2. Hệ thống tìm chính xác đơn hàng cần sửa dựa trên từ khoá; nếu khớp nhiều đơn thì hiển thị danh sách nút bấm để người dùng chọn đơn đúng trong 1 chạm
  3. Hệ thống hiển thị thẻ so sánh trực quan Trước ➡️ Sau (Visual Diff) nêu rõ các trường thay đổi kèm hai nút bấm `[✅ Xác nhận sửa]` và `[❌ Huỷ]` (tự động hết hạn an toàn sau 120 giây)
  4. Khi người dùng bấm `[✅ Xác nhận sửa]`, đơn hàng trong cơ sở dữ liệu được cập nhật chính xác và bot gửi thông báo xác nhận thành công; nếu bấm huỷ hoặc quá 120s thì dữ liệu cũ giữ nguyên
  5. Khi tin nhắn chat chưa nói rõ trạng thái muốn chuyển, bot hiển thị danh sách nút bấm gợi ý các trạng thái hợp lệ để người dùng chọn nhanh mà không cần gõ lại
**Plans**: TBD
**UI hint**: yes

## Progress Table

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 1. Foundation, Persistence & Security Whitelist | 3/3 | Completed | 2026-10-24 |
| 2. LLM Ingestion & Interactive Confirmation | 2/2 | Completed | 2026-10-24 |
| 3. Ergonomic Order Management & Low-Tech Actions | 3/3 | Completed | 2026-10-24 |
| 4. Natural Language Order Search | 3/3 | Completed | 2026-10-25 |
| 5. Database Backup Engine & Scheduled Tasks | 0/TBD | Not started | - |
| 6. Role-Based Access Control & Telegram Admin Suite | 0/TBD | Not started | - |
| 7. Interactive Server Console App | 0/TBD | Not started | - |
| 8. Natural Language Order Mutation Pipeline | 0/TBD | Not started | - |
