# Requirements: Cassette Store Telegram Chatbot

**Defined:** 2026-10-24
**Core Value:** Người lớn tuổi nhập tự do một đoạn tin nhắn đặt hàng bất kỳ qua Telegram (kèm ảnh hoặc text), bot dùng LLM tự bóc tách chính xác thông tin, hiển thị nút bấm xác nhận trực quan và lưu trữ an toàn vào DB mà không cần thao tác biểu mẫu phức tạp.

## v1 Requirements

Requirements for initial release. Each maps to roadmap phases.

### Core Data & Persistence (DATA)

- [x] **DATA-01**: Khách hàng được lưu trữ với tên, hỗ trợ nhiều số điện thoại, nhiều địa chỉ nhận hàng, và ghi chú đi kèm.
- [x] **DATA-02**: Đơn hàng lưu chi tiết hàng hoá dạng text tự do (tên băng cassette, số lượng, giá), tổng tiền thu khách, tiền COD, hình thức (chuyển khoản trước hay COD), và mã vận đơn đối tác ship.
- [x] **DATA-03**: Quản lý vòng đời đơn hàng qua 7 trạng thái rõ ràng: `Chờ làm` -> `Đang làm` -> `Đã đóng gói` -> `Đã tạo đơn trên app vận chuyển` -> `Shipper đã lấy hàng` -> `Đã giao thành công` / `Bom hàng` / `Huỷ đơn`.
- [x] **DATA-04**: Đơn hàng hỗ trợ đính kèm 1 hoặc nhiều ảnh (lưu trữ mã `file_id` Telegram vào DB, hỗ trợ gửi kèm lúc tạo đơn hoặc thêm ảnh bổ sung sau khi có đơn).
- [x] **DATA-05**: Nhập và cập nhật mã vận đơn cho đơn hàng cụ thể.

### Smart Ingestion with LLM (INGEST)

- [x] **INGEST-01**: Nhận tin nhắn free-text bất kỳ từ Zalo/Facebook chuyển sang; LLM (qua 9router gateway) tự động bóc tách: Tên khách, SĐT, Địa chỉ, Danh sách băng cassette, Tiền thu khách, Tiền COD, Hình thức thanh toán.
- [x] **INGEST-02**: Tự động chuẩn hoá đơn vị tiền tệ tiếng Việt ("250k", "1tr2", "50 ngàn", "cọc 50k thu 200k") thành số nguyên VNĐ chuẩn xác.
- [x] **INGEST-03**: Hiển thị thẻ thông tin đơn xem trước (preview card) kèm 2 nút bấm Inline: `✅ Xác nhận lưu` và `❌ Huỷ bỏ`.
- [x] **INGEST-04**: Đơn hàng chỉ được ghi vào DB và gửi thông báo hoàn tất sau khi người dùng bấm nút xác nhận.

### Ergonomic Admin & Low-tech UX (UI)

- [x] **UI-01**: 100% tính năng vận hành trên giao diện chat Telegram thông qua Inline Buttons và Reply Keyboard (không làm web/app riêng cho thao tác hàng ngày).
- [x] **UI-02**: Menu phím bấm to, cố định dưới khung chat (Reply Keyboard) cho các thao tác chính: Đơn hôm nay, Nhập đơn mới, Tra cứu đơn, Trợ giúp.
- [x] **UI-03**: Liệt kê danh sách đơn theo ngày: Hôm nay, Hôm qua, hoặc ngày cụ thể tuỳ chọn bằng nút bấm.
- [x] **UI-04**: Thẻ chi tiết đơn hàng cung cấp các nút bấm Inline "Sao chép nhanh" 1 chạm (`CopyTextButton` / định dạng code mono) để copy SĐT, Địa chỉ nhận hàng, Mã vận đơn dán trực tiếp vào app ship (GHTK/GHN) mà không phải bôi đen chọn chữ.
- [x] **UI-05**: Đổi trạng thái đơn hàng trực tiếp bằng 1 chạm thông qua danh sách nút bấm Inline trạng thái tương ứng.
- [x] **UI-06**: Xem lại danh sách ảnh đã đính kèm của đơn hàng trong Telegram chat (dưới dạng media group hoặc từng ảnh) và nút thêm ảnh mới cho đơn.

### Natural Language Search & Security / Config (SEARCH & SEC)

- [x] **SEARCH-01**: Tra cứu/tìm kiếm đơn hàng bằng ngôn ngữ tự nhiên thông qua tin nhắn chat tự do (VD: *"tìm đơn anh Tuấn hôm qua mua 2 cuốn Tuấn Vũ"*).
- [ ] **SEARCH-02**: LLM truy vấn tìm kiếm đơn hàng phù hợp trong DB; gửi lại thẻ xác nhận *"Có phải bạn muốn xem đơn này không?"* kèm nút xác nhận trước khi hiển thị chi tiết hoặc thao tác.
- [x] **SEC-01**: Whitelist Telegram User ID bảo mật — chỉ các Telegram User ID được cấu hình mới có quyền sử dụng bot; chặn và từ chối toàn bộ tương tác từ người lạ.
- [x] **CFG-01**: Cấu hình hệ thống local (`.env` / file settings): quản lý Bot Token, danh sách Whitelist User IDs, URL 9router, API Key và Model ID (cho phép linh hoạt chọn/đổi model LLM trong setting).

## v2 Requirements

Deferred to future release. Tracked but not in current roadmap.

### Enhancements

- **ENH-01**: Tải ảnh backup tự động về máy tính local song song với lưu `file_id`.
- **ENH-02**: Xuất báo cáo doanh thu, tiền COD theo tuần/tháng ra file Excel (.xlsx).
- **ENH-03**: Gửi tin nhắn thông báo tự động cho khách hàng qua Telegram nếu khách có dùng Telegram.

## Out of Scope

Explicitly excluded. Documented to prevent scope creep.

| Feature | Reason |
|---------|--------|
| Kết nối API trực tiếp hai chiều với hãng ship (GHTK, GHN, ViettelPost) | Tránh phức tạp hoá cấu hình token/webhook của hãng ship; người dùng tự tạo đơn trên app ship ngoài rồi dán mã vận đơn vào bot |
| Quản lý tồn kho theo mã vạch / SKU băng cassette chi tiết | Shop bán băng đĩa nhạc vintage đa dạng, lưu text tự do tên cuốn băng giúp thao tác nhanh và không bị gò bó |
| Giao diện Web Admin Dashboard | Người dùng lớn tuổi chỉ quen dùng Telegram trên điện thoại; tập trung 100% trải nghiệm Telegram bot |
| Cổng thanh toán trực tuyến tự động (VNPAY, MoMo API) | Chỉ ghi nhận hình thức chuyển khoản trước hoặc COD thủ công |

## Traceability

Which phases cover which requirements. Updated during roadmap creation.

| Requirement | Phase | Status |
|-------------|-------|--------|
| CFG-01 | Phase 1 | Complete |
| SEC-01 | Phase 1 | Complete |
| DATA-01 | Phase 1 | Complete |
| DATA-02 | Phase 1 | Complete |
| DATA-03 | Phase 1 | Complete |
| DATA-04 | Phase 1 | Complete |
| INGEST-01 | Phase 2 | Complete |
| INGEST-02 | Phase 2 | Complete |
| INGEST-03 | Phase 2 | Complete |
| INGEST-04 | Phase 2 | Complete |
| DATA-05 | Phase 3 | Complete |
| UI-01 | Phase 3 | Complete |
| UI-02 | Phase 3 | Complete |
| UI-03 | Phase 3 | Complete |
| UI-04 | Phase 3 | Complete |
| UI-05 | Phase 3 | Complete |
| UI-06 | Phase 3 | Complete |
| SEARCH-01 | Phase 4 | Complete |
| SEARCH-02 | Phase 4 | Pending |

**Coverage:**
- v1 requirements: 19 total
- Mapped to phases: 19
- Unmapped: 0

---
*Requirements defined: 2026-10-24*
*Last updated: 2026-10-24 after roadmap creation*
