# Roadmap: Cassette Store Telegram Chatbot

## Overview

Telegram chatbot phục vụ quản lý đơn hàng cho shop bán băng cassette, tối ưu cho người lớn tuổi / low-tech. Hệ thống vận hành theo chu trình: nhận tin nhắn đặt hàng tự do từ Zalo/Facebook, bóc tách bằng LLM (qua 9router gateway), hiển thị thẻ xác nhận trực quan, lưu trữ an toàn vào SQLite cục bộ và hỗ trợ thao tác một chạm (đổi trạng thái, copy số điện thoại/địa chỉ/mã vận đơn vào app ship, tra cứu bằng ngôn ngữ tự nhiên).

## Phases

**Phase Numbering:**

- Integer phases (1, 2, 3): Planned milestone work
- Decimal phases (2.1, 2.2): Urgent insertions (marked with INSERTED)

- [x] **Phase 1: Foundation, Persistence & Security Whitelist** - Thiết lập cấu hình local, cơ sở dữ liệu SQLite WAL, thực thể khách hàng / đơn hàng / ảnh và middleware chặn người lạ bằng Telegram User ID whitelist. (completed 2026-10-24)
- [x] **Phase 2: LLM Ingestion & Interactive Confirmation** - Tích hợp gateway 9router bóc tách tin nhắn tiếng Việt tự do thành cấu trúc chuẩn hoá tiền tệ VNĐ và luồng xác nhận hai pha qua thẻ preview trước khi lưu DB. (completed 2026-10-24)
- [x] **Phase 3: Ergonomic Order Management & Low-Tech Actions** - Xây dựng giao diện chat Telegram với Reply Keyboard cố định, danh sách đơn theo ngày, thẻ chi tiết kèm nút sao chép 1 chạm, đổi trạng thái vòng đời và quản lý ảnh/mã vận đơn. (completed 2026-10-24)
- [ ] **Phase 4: Natural Language Order Search** - Tra cứu đơn hàng bằng ngôn ngữ tự nhiên tiếng Việt qua LLM kết hợp thẻ hỏi xác nhận trước khi hiển thị chi tiết.

## Phase Details

### Phase 1: Foundation, Persistence & Security Whitelist

**Goal**: Nền tảng dữ liệu SQLite và bảo mật truy cập bot sẵn sàng, lưu trữ đầy đủ thông tin khách hàng, đơn hàng, ảnh và chặn toàn bộ người dùng ngoài whitelist.
**Mode:** mvp
**Depends on**: Nothing (first phase)
**Requirements**: CFG-01, SEC-01, DATA-01, DATA-02, DATA-03, DATA-04
**Success Criteria** (what must be TRUE):

  1. Người lạ (User ID không có trong whitelist cấu hình) gửi tin nhắn đến bot bị từ chối/bỏ qua hoàn toàn, bot không phản hồi dữ liệu nhạy cảm.
  2. Người trong whitelist gửi lệnh kiểm tra bot khởi động thành công với cấu hình nạp từ `.env` (bot token, whitelist IDs, 9router URL, API Key, Model ID).
  3. Hệ thống tạo và lưu trữ thành công bản ghi khách hàng (hỗ trợ nhiều SĐT, nhiều địa chỉ, ghi chú) và đơn hàng (text hàng hoá tự do, tổng tiền, COD, hình thức thanh toán, mảng `file_id` ảnh, 7 trạng thái vòng đời từ `Chờ làm` đến `Đã giao thành công` / `Bom hàng` / `Huỷ đơn`) vào SQLite ở chế độ WAL mà không bị lỗi lock.

**Plans**: 3 plans

Plans:

- [x] 01-01-PLAN.md — Setup project environment, Pydantic-Settings v2 configuration, and Telegram bot application with Whitelist security gate.
- [x] 01-02-PLAN.md — Build async SQLite database connection manager with WAL mode and Customer domain persistence.
- [x] 01-03-PLAN.md — Implement Order domain persistence with customer snapshot, photo attachments, 8-state status lifecycle, and runnable entrypoint.

### Phase 2: LLM Ingestion & Interactive Confirmation

**Goal**: Người dùng gửi một đoạn chat đặt hàng tự do tiếng Việt bất kỳ, bot dùng LLM bóc tách chính xác và hiển thị thẻ xem trước kèm nút bấm xác nhận trước khi ghi dữ liệu.
**Mode:** mvp
**Depends on**: Phase 1
**Requirements**: INGEST-01, INGEST-02, INGEST-03, INGEST-04
**Success Criteria** (what must be TRUE):

  1. Người dùng dán tin nhắn đặt hàng không cấu trúc từ Zalo/Facebook (kèm tiếng lóng như "250k", "1tr2", "cọc 50k thu 200k"), bot trích xuất đúng tên khách, SĐT, địa chỉ, danh sách cassette, tiền thu và tiền COD thành số nguyên VNĐ chuẩn.
  2. Bot phản hồi ngay bằng thẻ xem trước (preview card) hiển thị đầy đủ thông tin bóc tách kèm 2 nút bấm Inline `✅ Xác nhận lưu` và `❌ Huỷ bỏ` (không bị timeout spinner 30s của Telegram).
  3. Khi bấm `❌ Huỷ bỏ`, đơn bị huỷ ngay, không có bản ghi nào được ghi vào DB.
  4. Khi bấm `✅ Xác nhận lưu`, thông tin đơn và khách hàng mới được lưu vĩnh viễn vào DB và bot cập nhật tin nhắn thông báo thành công.

**Plans**: 2/2 plans complete
**UI hint**: yes
Plans:
**Wave 1**

- [x] 02-01-PLAN.md — End-to-end order ingestion vertical slice: LLM 2-tier fallback extraction, Vietnamese currency normalization, interactive preview card & 2-phase confirmation.

**Wave 2** *(blocked on Wave 1 completion)*

- [x] 02-02-PLAN.md — Customer history intelligence (order stats & BOM_HANG alert), multi-address resolution, photo caption ingestion, and resilient error recovery.

### Phase 3: Ergonomic Order Management & Low-Tech Actions

**Goal**: Người lớn tuổi vận hành đơn hàng hàng ngày 100% bằng phím bấm to một chạm trên Telegram: xem đơn theo ngày, đổi trạng thái, gắn mã vận đơn, copy thông tin sang app ship và quản lý ảnh.
**Mode:** mvp
**Depends on**: Phase 2
**Requirements**: DATA-05, UI-01, UI-02, UI-03, UI-04, UI-05, UI-06
**Success Criteria** (what must be TRUE):

  1. Dưới khung chat luôn có Reply Keyboard cố định với các nút to rõ: "Đơn hôm nay", "Nhập đơn mới", "Tra cứu đơn", "Trợ giúp" giúp thao tác không cần gõ lệnh slash `/`.
  2. Bấm "Đơn hôm nay" hoặc chọn "Hôm qua" / ngày cụ thể, bot trả về danh sách đơn gọn gàng kèm badge trạng thái rõ ràng.
  3. Mở thẻ chi tiết một đơn hàng, người dùng chạm 1 lần vào nút Inline Copy (hoặc chạm khối code mono) để copy SĐT, địa chỉ hoặc mã vận đơn trực tiếp vào bộ nhớ tạm để dán vào app GHTK/GHN/ViettelPost.
  4. Người dùng chuyển trạng thái đơn (sang `Đang làm`, `Đã đóng gói`, `Đã tạo đơn`, `Shipper đã lấy`, `Đã giao`, `Bom hàng`, `Huỷ`) chỉ bằng 1 chạm nút Inline và nhận phản hồi tức thì không bị lỗi `Message is not modified`.
  5. Người dùng có thể nhập/cập nhật mã vận đơn cho đơn hàng và xem lại hoặc gửi thêm ảnh đính kèm (qua `file_id` Telegram) trực tiếp trong chat.

**Plans**: 3/3 plans complete
**UI hint**: yes

Plans:
**Wave 1**
- [x] 03-01-PLAN.md — Nền tảng dữ liệu đơn theo ngày UTC+7, Reply Keyboard 2x2, Inline Date Picker & thẻ chi tiết với CopyTextButton.

**Wave 2** *(blocked on Wave 1 completion)*
- [x] 03-02-PLAN.md — Điều hướng danh sách đơn phân trang, đổi trạng thái vòng đời 1 chạm kèm xác nhận chống bấm nhầm, nhập mã vận đơn & quản lý album ảnh.

**Wave 3 (Gap Closure)** *(blocked on Wave 2 completion)*
- [x] 03-03-PLAN.md — Xử lý debounce buffer gom toàn bộ ảnh khi gửi media group album tạo đơn mới (Gap G-03-8).

### Phase 4: Natural Language Order Search

**Goal**: Người dùng tìm lại đơn hàng cũ bằng cách chat tự nhiên bằng tiếng Việt; bot tự hiểu ngữ cảnh, tìm trong DB và hỏi xác nhận trước khi hiển thị chi tiết.
**Mode:** mvp
**Depends on**: Phase 3
**Requirements**: SEARCH-01, SEARCH-02
**Success Criteria** (what must be TRUE):

  1. Người dùng gửi câu chat tìm kiếm tự do (VD: "tìm đơn anh Tuấn hôm qua mua 2 cuốn Tuấn Vũ" hoặc "đơn gửi về Hải Phòng tuần này"), bot dùng LLM diễn giải đúng tiêu chí tìm kiếm (tên, địa chỉ, tên băng, thời gian).
  2. Bot trả về thẻ xác nhận gợi ý: *"Có phải bạn muốn xem đơn này không?"* hiển thị tóm tắt đơn tìm thấy kèm nút xác nhận mở chi tiết, tránh hiển thị nhầm đơn khi có nhiều kết quả tương tự.
  3. Bấm xác nhận trên thẻ gợi ý, bot mở trực tiếp thẻ chi tiết đơn hàng đầy đủ chức năng (sao chép 1 chạm, đổi trạng thái) như trong Phase 3.

**Plans**: 2 plans
**UI hint**: yes

Plans:
**Wave 1**
- [ ] 04-01-PLAN.md — Nền tảng Text-to-SQL an toàn (read-only sanitizer, SQLite unaccent, 1-shot retry) & phân loại tóm tắt kết quả qua LLM.

**Wave 2** *(blocked on Wave 1 completion)*
- [ ] 04-02-PLAN.md — Giao diện tra cứu đơn hàng (menu 2x2, dual-trigger routing), thẻ xác nhận 2-phase confirmation & điều hướng bảo toàn ngữ cảnh.

## Progress

**Execution Order:**
Phases execute in numeric order: 1 → 2 → 3 → 4

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 1. Foundation, Persistence & Security Whitelist | 3/3 | Complete    | 2026-10-24 |
| 2. LLM Ingestion & Interactive Confirmation | 2/2 | Complete    | 2026-10-24 |
| 3. Ergonomic Order Management & Low-Tech Actions | 3/3 | Complete    | 2026-10-24 |
| 4. Natural Language Order Search | 0/TBD | Not started | - |
