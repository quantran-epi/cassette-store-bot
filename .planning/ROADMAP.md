# Roadmap: Cassette Store Telegram Chatbot

## Milestones

- ✅ **v1.0 MVP** — Phases 1-4 (shipped 2026-10-25)
- 🚧 **v1.1 NL Mutation, Telegram Admin, Telegram Backup & Container Deployment** — Phases 5-8 (active)

## Phases

<details>
<summary>✅ v1.0 MVP (Phases 1-4) — SHIPPED 2026-10-25</summary>

- [x] **Phase 1: Foundation, Persistence & Security Whitelist** - Nền tảng SQLite WAL, xác thực Telegram Whitelist Group -1 và schema đơn hàng/khách hàng (completed 2026-10-24)
- [x] **Phase 2: LLM Ingestion & Interactive Confirmation** - Bóc tách đơn hàng tiếng Việt qua 9router LLM, thẻ xác nhận 2-phase và cảnh báo bom hàng (completed 2026-10-24)
- [x] **Phase 3: Ergonomic Order Management & Low-Tech Actions** - Reply keyboard 2x2, nút CopyTextButton 1-chạm, danh sách đơn lọc ngày và cập nhật mã vận đơn (completed 2026-10-24)
- [x] **Phase 4: Natural Language Order Search** - Tìm kiếm đơn hàng tự nhiên Text-to-SQL, unaccent tiếng Việt, thống kê doanh thu và xác nhận điều hướng (completed 2026-10-25)

</details>

### 🚧 v1.1 NL Mutation, Telegram Admin, Telegram Backup & Container Deployment

- [x] **Phase 5: Role-Based Access Control & Telegram Admin Suite** - Phân quyền 2 cấp độ Super Admin vs Admin, menu /admin Telegram và xem log trực tiếp (completed 2026-10-25)
- [ ] **Phase 6: Telegram Database Backup Engine & Scheduled Tasks** - Snapshot SQLite atomic qua VACUUM INTO, nén gzip gửi định kỳ và thủ công vào chat Super Admin
- [ ] **Phase 7: Natural Language Order Mutation Pipeline** - 3-Way Intent Router, bóc tách delta thay đổi bằng LLM, thẻ so sánh trực quan Trước/Sau và xác nhận 1-chạm
- [ ] **Phase 8: Containerization & Kubernetes Deployment** - Multi-stage Dockerfile non-root, Docker Compose và Kubernetes manifests RWO Recreate

## Phase Details

### Phase 5: Role-Based Access Control & Telegram Admin Suite

**Goal**: Quản trị viên có thể phân quyền truy cập 2 cấp độ và quản trị vận hành bot trực tiếp từ Telegram với menu tương tác an toàn (trạng thái hệ thống, cấu hình model LLM, whitelist CRUD, xem log trực tiếp)
**Depends on**: Milestone v1.0
**Requirements**: RBAC-01, RBAC-02, RBAC-03, RBAC-04, RBAC-05
**Success Criteria** (what must be TRUE):

  1. Quản trị viên mở menu `/admin` trên Telegram thấy giao diện nút bấm inline hiển thị trạng thái hệ thống (bot, DB, LLM) và có thể chuyển đổi model 9router đang hoạt động tức thì
  2. Quản trị viên có thể xem danh sách whitelist, thêm mới hoặc xoá Telegram User ID trực tiếp qua tin nhắn/nút bấm trên Telegram với hiệu lực tức thì
  3. Hệ thống phân định 2 vai trò `SUPER_ADMIN` và `ADMIN`; tài khoản root `SUPER_ADMIN_ID` cấu hình trong `.env` luôn được bảo vệ chống tự khoá, và decorator `@require_role` chặn đứng người lạ hoặc admin thường khi cố truy cập lệnh/callback trái thẩm quyền
  4. Super Admin có thể xem 25-50 dòng log gần nhất trực tiếp qua lệnh `/logs` định dạng HTML `<pre>` ngay trong chat Telegram mà không cần mở terminal máy chủ

**Plans**: 2 plansPlans:
**Wave 1**

- [x] 05-01-PLAN.md — Foundation persistence, RBAC role decorator, and ring buffer log handler (RBAC-01, RBAC-02, RBAC-05)

**Wave 2** *(blocked on Wave 1 completion)*

- [x] 05-02-PLAN.md — Telegram Admin Suite UI, LLM model switcher with probe, whitelist CRUD, and /logs viewer (RBAC-03, RBAC-04)

**UI hint**: yes

### Phase 6: Telegram Database Backup Engine & Scheduled Tasks

**Goal**: Cơ sở dữ liệu SQLite được tự động sao lưu định kỳ và sao lưu thủ công tức thì dưới dạng snapshot an toàn gửi trực tiếp vào Telegram Super Admin
**Depends on**: Phase 5
**Requirements**: BKP-01, BKP-02, BKP-03, BKP-04
**Success Criteria** (what must be TRUE):

  1. Hệ thống tự động snapshot DB bằng `VACUUM INTO` từ live SQLite đang bật WAL, nén `gzip` và gửi file `.sqlite3.gz` vào chat riêng của Super Admin lúc 02:00 sáng hàng ngày (UTC+7) qua background scheduler
  2. Super Admin gõ lệnh `/backup` hoặc bấm nút trên menu `/admin` nhận được ngay file nén `.sqlite3.gz` đính kèm trong chat Telegram kèm thông báo dung lượng và thời gian snapshot
  3. File `.sqlite3.gz` tải về từ Telegram giải nén thành file SQLite nguyên vẹn, đọc được toàn bộ dữ liệu đơn hàng và khách hàng mới nhất
  4. Khi dung lượng vượt 48MB hoặc gặp lỗi gửi Telegram, hệ thống ghi log cảnh báo chi tiết và không làm gián đoạn hay crash tiến trình bot đang phục vụ khách

**Plans**: TBD

### Phase 7: Natural Language Order Mutation Pipeline

**Goal**: Người dùng có thể chỉnh sửa các thông tin đơn hàng bằng tin nhắn chat tự nhiên tiếng Việt và xác nhận 1-chạm qua thẻ so sánh Trước ➡️ Sau an toàn
**Depends on**: Phase 5, Phase 6
**Requirements**: MUT-01, MUT-02, MUT-03, MUT-04, MUT-05
**Success Criteria** (what must be TRUE):

  1. Người dùng nhắn tin chat tự nhiên chứa ý định sửa đơn, 3-Way Intent Router phân loại chính xác sang luồng chỉnh sửa thay vì tạo đơn mới hay tìm kiếm
  2. Hệ thống tìm đúng đơn hàng cần sửa dựa trên từ khoá; nếu khớp nhiều đơn thì hiển thị bàn phím inline các đơn gợi ý để người dùng chọn trong 1 chạm
  3. Hệ thống dùng LLM bóc tách delta thay đổi (trạng thái, mã vận đơn, ghi chú, tiền COD/tổng đơn, địa chỉ/sđt) và hiển thị thẻ so sánh trực quan Trước ➡️ Sau kèm 2 nút `[✅ Xác nhận sửa]` và `[❌ Huỷ]` với bộ đếm TTL 120s
  4. Người dùng bấm `[✅ Xác nhận sửa]`, đơn hàng được cập nhật nguyên tử vào DB với khóa lạc quan (optimistic locking chống xung đột); nếu bấm huỷ hoặc quá 120s thì giữ nguyên trạng thái cũ
  5. Khi câu chat chưa nói rõ trạng thái đích, hệ thống hiển thị danh sách nút bấm trạng thái gợi ý để người dùng bấm chọn 1-chạm

**Plans**: TBD
**UI hint**: yes

### Phase 8: Containerization & Kubernetes Deployment

**Goal**: Ứng dụng bot được đóng gói thành container Docker chuẩn hóa, cấu hình persistent volume cho SQLite WAL và sẵn sàng triển khai trên Docker Compose hoặc Kubernetes với cam kết single-replica an toàn
**Depends on**: Phase 5, Phase 6, Phase 7
**Requirements**: DEP-01, DEP-02, DEP-03, DEP-04, DEP-05
**Success Criteria** (what must be TRUE):

  1. Container Docker build thành công qua multi-stage build trên nền `python:3.12-slim`, chạy với non-root user (UID 10001) và cấu hình múi giờ `TZ=Asia/Ho_Chi_Minh`
  2. Dữ liệu SQLite (`.db`, `-wal`, `-shm`) được lưu trữ tại thư mục volume mount `/app/data` bảo toàn nguyên vẹn sau khi container restart
  3. Hệ thống triển khai chạy ổn định bằng `docker-compose up -d` với đầy đủ biến môi trường, health check và auto-restart policy
  4. Bộ manifest Kubernetes (`Deployment`, `PVC` RWO, `ConfigMap`, `Secret`) triển khai chính xác với `replicas: 1` và `strategy.type: Recreate`, ngăn chặn hoàn toàn tình trạng multi-pod làm hỏng SQLite
  5. Khi nhận tín hiệu `SIGTERM`/`SIGINT`, tiến trình container thực hiện graceful shutdown, gọi `PRAGMA wal_checkpoint(TRUNCATE)` và đóng kết nối DB sạch sẽ trước khi thoát

**Plans**: TBD

## Progress Table

| Phase | Milestone | Plans Complete | Status | Completed |
|-------|-----------|----------------|--------|-----------|
| 1. Foundation, Persistence & Security Whitelist | v1.0 | 3/3 | Completed | 2026-10-24 |
| 2. LLM Ingestion & Interactive Confirmation | v1.0 | 2/2 | Completed | 2026-10-24 |
| 3. Ergonomic Order Management & Low-Tech Actions | v1.0 | 3/3 | Completed | 2026-10-24 |
| 4. Natural Language Order Search | v1.0 | 3/3 | Completed | 2026-10-25 |
| 5. Role-Based Access Control & Telegram Admin Suite | v1.1 | 2/2 | Complete   | 2026-10-25 |
| 6. Telegram Database Backup Engine & Scheduled Tasks | v1.1 | 0/TBD | Not started | - |
| 7. Natural Language Order Mutation Pipeline | v1.1 | 0/TBD | Not started | - |
| 8. Containerization & Kubernetes Deployment | v1.1 | 0/TBD | Not started | - |
