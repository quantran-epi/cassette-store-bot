# Roadmap: Cassette Store Telegram Bot

## Milestones

- [x] **v1.0 MVP Core** — Giai đoạn 1 đến 4: Nền tảng bot Telegram, bóc tách đơn tự nhiên bằng LLM, quản lý đơn hàng công thái học và tra cứu thông minh. (Hoàn thành 2026-10-25)
- [ ] **v1.1 Security, Operations & Container Deployment** — Giai đoạn 5 đến 8: Phân quyền RBAC, sao lưu cơ sở dữ liệu lên Telegram, luồng chỉnh sửa đơn bằng ngôn ngữ tự nhiên và đóng gói Kubernetes/Docker. (Đang thực hiện)

## Phases

### Phase 1: Foundation, Persistence & Security Whitelist
**Goal**: Bot khởi chạy an toàn, chỉ chấp nhận người dùng được cấp phép trong Whitelist, lưu trữ dữ liệu đơn hàng và khách hàng bền vững trên SQLite WAL
**Depends on**: Không
**Requirements**: SEC-01, SEC-02, SEC-03, DB-01, DB-02, DB-03
**Success Criteria** (what must be TRUE):
  1. Người lạ nhắn tin vào bot bị từ chối ngay lập tức và ghi log cảnh báo; người trong whitelist tương tác bình thường
  2. Dữ liệu đơn hàng và thông tin khách hàng (hỗ trợ nhiều SĐT, nhiều địa chỉ) được lưu trữ an toàn trong SQLite ở chế độ WAL
  3. Cấu hình hệ thống (bot token, whitelist IDs, 9router URL/key) được nạp và validate chặt chẽ qua Pydantic-Settings khi khởi động
**Plans**: 3 plans
- [x] 01-01-PLAN.md — Cấu hình môi trường và cơ sở dữ liệu SQLite WAL
- [x] 01-02-PLAN.md — Khởi tạo Bot Telegram và Middleware phân quyền Whitelist
- [x] 01-03-PLAN.md — Smoke test tích hợp toàn diện luồng bảo mật và kết nối DB

### Phase 2: LLM Ingestion & Interactive Confirmation
**Goal**: Người dùng gửi tin nhắn đặt hàng tự do bằng tiếng Việt, bot tự bóc tách chính xác thông tin qua LLM và hiển thị thẻ xác nhận trực quan với các nút bấm 1-chạm
**Depends on**: Phase 1
**Requirements**: LLM-01, LLM-02, LLM-03, UX-01, UX-02, UX-03
**Success Criteria** (what must be TRUE):
  1. Tin nhắn đặt hàng tự do chứa nhiều thông tin lộn xộn được bóc tách chuẩn xác qua LLM 9router (hỗ trợ 2 tầng fallback)
  2. Bot phản hồi thẻ xác nhận đơn hàng hiển thị trực quan thông tin khách, hàng hoá, tiền COD và các nút bấm Inline 1-chạm
  3. Người dùng bấm `[✅ Xác nhận]` tạo đơn hàng thành công vào DB; bấm `[❌ Huỷ]` huỷ bỏ thao tác an toàn
**Plans**: 2 plans
- [x] 02-01-PLAN.md — Module bóc tách LLM 2 tầng (Structured Outputs + Fallback) và Pydantic Schema
- [x] 02-02-PLAN.md — Handler tin nhắn tự nhiên, bàn phím Inline và luồng tương tác xác nhận đơn

### Phase 3: Ergonomic Order Management & Low-Tech Actions
**Goal**: Cung cấp giao diện quản lý đơn hàng tối ưu cho người lớn tuổi với bàn phím một chạm (copy text bưu cục, chuyển trạng thái vòng đời) và gắn ảnh đơn
**Depends on**: Phase 2
**Requirements**: MGT-01, MGT-02, MGT-03, MGT-04, MGT-05
**Success Criteria** (what must be TRUE):
  1. Mỗi đơn hàng hiển thị nút `CopyTextButton` cho phép copy nhanh toàn bộ thông tin chuẩn định dạng giao hàng bưu cục chỉ với 1 chạm
  2. Người dùng chuyển đổi trạng thái đơn hàng (Chờ làm ➡️ Đang làm ➡️ Đã đóng gói ➡️ Đã tạo đơn ➡️ Đã giao / Bom / Huỷ) hoàn toàn qua nút bấm Inline
  3. Người dùng gửi ảnh sản phẩm/hoá đơn kèm hoặc sau khi tạo đơn, bot tự động liên kết ảnh vào đơn hàng tương ứng
**Plans**: 3 plans
- [x] 03-01-PLAN.md — Logic CopyText 1-chạm bưu cục và chuyển đổi trạng thái đơn hàng
- [x] 03-02-PLAN.md — Xử lý ảnh đính kèm đơn hàng và lưu trữ photo file IDs
- [x] 03-03-PLAN.md — Menu điều khiển quản lý đơn công thái học và kiểm thử tích hợp

### Phase 4: Natural Language Order Search
**Goal**: Người dùng tra cứu đơn hàng bằng câu hỏi tiếng Việt tự nhiên (hôm nay có bao nhiêu đơn, tìm đơn của anh Nam...), bot dùng LLM dịch thành SQLite query an toàn và phản hồi kết quả
**Depends on**: Phase 3
**Requirements**: SCH-01, SCH-02, SCH-03, SCH-04, SCH-05
**Success Criteria** (what must be TRUE):
  1. Câu hỏi tra cứu tự nhiên được LLM chuyển đổi thành câu lệnh SQL SELECT chính xác (hỗ trợ tìm theo ngày, khách hàng, món hàng, trạng thái)
  2. Hệ thống kiểm soát an toàn tuyệt đối: chỉ cho phép SELECT, chặn mọi từ khoá phá hoại dữ liệu (DROP, DELETE, UPDATE...)
  3. Kết quả tìm kiếm hiển thị danh sách đơn dạng thẻ trực quan hoặc tóm tắt số liệu kinh doanh ngắn gọn, dễ hiểu
**Plans**: 3 plans
- [x] 04-01-PLAN.md — Engine Text-to-SQL an toàn với bộ lọc ngữ pháp SQL và giới hạn SELECT
- [x] 04-02-PLAN.md — Định dạng phản hồi kết quả tra cứu (danh sách thẻ đơn / tóm tắt thống kê)
- [x] 04-03-PLAN.md — Tích hợp câu hỏi tra cứu vào luồng chat tự nhiên và kiểm thử toàn diện

### Phase 5: Role-Based Access Control & Telegram Admin Suite
**Goal**: Phân quyền 2 cấp độ (Super Admin và Admin), cho phép quản lý thành viên Whitelist trực tiếp trên Telegram bằng nút bấm và lệnh bảo mật
**Depends on**: Phase 1, Phase 4
**Requirements**: ADM-01, ADM-02, ADM-03, ADM-04, ADM-05
**Success Criteria** (what must be TRUE):
  1. Hệ thống phân định rõ quyền Super Admin (toàn quyền) và Admin thường (xử lý đơn, không có quyền can thiệp whitelist/hệ thống)
  2. Super Admin có thể thêm, sửa quyền, xoá người dùng khỏi Whitelist trực tiếp qua giao diện nút bấm hoặc lệnh Telegram
  3. Mọi thao tác quản trị được kiểm tra quyền hạn chặt chẽ và ghi log bảo mật đầy đủ
**Plans**: 2 plans
- [x] 05-01-PLAN.md — Schema phân quyền RBAC và phân tầng quyền hạn người dùng (ADM-01, ADM-04)
- [x] 05-02-PLAN.md — Bộ công cụ quản trị Telegram tương tác cho Super Admin (ADM-02, ADM-03, ADM-05)

### Phase 6: Telegram Database Backup Engine & Scheduled Tasks
**Goal**: Sao lưu cơ sở dữ liệu SQLite định kỳ và gửi file backup trực tiếp về Telegram cá nhân của Super Admin với cơ chế mã hoá an toàn
**Depends on**: Phase 1, Phase 5
**Requirements**: BKP-01, BKP-02, BKP-03, BKP-04
**Success Criteria** (what must be TRUE):
  1. Cơ sở dữ liệu SQLite được sao lưu an toàn (sử dụng VACUUM INTO snapshot hoặc online backup API) không gây gián đoạn ghi chép đơn hàng
  2. Hệ thống tự động gửi file backup về chat Telegram của Super Admin theo lịch hẹn định kỳ hàng ngày
  3. Super Admin có thể gõ lệnh `/backup` bất kỳ lúc nào để nhận ngay bản sao lưu tức thời
**Plans**: 2 plans
- [x] 06-01-PLAN.md — Hot SQLite snapshot backup engine via VACUUM INTO with schema migrations (BKP-01, BKP-02)
- [x] 06-02-PLAN.md — PTB JobQueue background scheduling, /backup command, admin UI wiring for backups, schedule configuration, model deletion, and whitelist user renaming (BKP-03, BKP-04)

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

**Plans**: 4 plans
**Wave 1**

- [x] 07-01-PLAN.md — Database audit migration, 3-Way Intent Router, and 2-tier LLM delta extractor (MUT-01, MUT-02, MUT-03)

**Wave 2** *(blocked on Wave 1 completion)*

- [x] 07-02-PLAN.md — Visual Diff Card, 14-char divider, status suggestion disambiguation, optimistic locking update, and Telegram pipeline integration (MUT-04, MUT-05)

**Wave 3 (Gap Closure)** *(blocked on Wave 2 completion)*

- [x] 07-03-PLAN.md — Resilient keyword search, 9router chatter cleanup, and optimistic locking timestamp normalization (MUT-02, MUT-04, MUT-05)
- [x] 07-04-PLAN.md — Generalized multi-field token matching with word boundary and Text-to-SQL search fallback (MUT-02, MUT-03)

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
| 6. Telegram Database Backup Engine & Scheduled Tasks | v1.1 | 2/2 | Completed | 2026-10-25 |
| 7. Natural Language Order Mutation Pipeline | v1.1 | 4/4 | Completed | 2026-10-25 |
| 8. Containerization & Kubernetes Deployment | v1.1 | 0/TBD | Not started | - |
