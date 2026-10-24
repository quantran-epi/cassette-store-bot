# Phase 3: Ergonomic Order Management & Low-Tech Actions - Context

**Gathered:** 2026-10-24
**Status:** Ready for planning

<domain>
## Phase Boundary

Xây dựng toàn bộ giao diện quản trị đơn hàng hàng ngày tối ưu cho người lớn tuổi / low-tech 100% trên Telegram: Reply Keyboard cố định dưới khung chat, danh sách đơn hàng theo ngày với phân trang gọn gàng, thẻ chi tiết đơn hàng tích hợp sao chép 1 chạm (HTML code + CopyTextButton), đổi trạng thái đơn hàng vòng đời kèm bảo vệ chống bấm nhầm (confirm với trạng thái nhạy cảm), quy trình nhập mã vận đơn đối tác ship và xem lại/bổ sung ảnh đính kèm.

</domain>

<decisions>
## Implementation Decisions

### 1. Menu chính (Reply Keyboard) & Danh sách đơn theo ngày
- **D-01:** Reply Keyboard cố định dưới màn hình bố trí dạng lưới 2x2 nút to, dễ bấm cho người già:
  - Hàng 1: `[📦 Đơn hôm nay]` `[📋 Xem theo ngày]`
  - Hàng 2: `[📝 Nhập đơn mới]` `[❓ Trợ giúp]`
  - Người dùng bấm nút là kích hoạt ngay, không bắt buộc nhớ hay gõ các lệnh slash `/`.
- **D-02:** Xem đơn theo ngày:
  - Khi bấm `[📋 Xem theo ngày]`, bot phản hồi bằng tin nhắn kèm các nút Inline bấm nhanh: `[Hôm nay]`, `[Hôm qua]`, và danh sách 3-5 ngày gần nhất để chạm chọn ngày xem ngay mà không phải gõ cú pháp ngày tháng phức tạp.
- **D-03:** Phân trang danh sách đơn hàng:
  - Hiển thị gọn 5 đơn/trang. Mỗi đơn tóm tắt 2-3 dòng (Mã đơn `#ID`, Tên khách, Tổng tiền, Trạng thái đơn) kèm nút Inline `[Xem đơn #ID]` ngay dưới để mở thẻ chi tiết.
  - Hàng nút điều hướng phân trang ở cuối tin nhắn: `[⬅️ Trước]` `[Trang X/Y]` `[Sau ➡️]`.
- **D-04:** Xử lý danh sách đơn trống:
  - Khi ngày được chọn không có đơn hàng nào, bot thông báo thân thiện: *"Ngày này chưa có đơn hàng nào bác nhé!"* kèm nút bấm nhanh `[📝 Nhập đơn mới]`.

### 2. Thẻ chi tiết đơn hàng & Cơ chế sao chép 1 chạm (Copy UX)
- **D-05:** Cơ chế sao chép 1 chạm thông tin khách để dán vào app ship (GHTK/GHN/ViettelPost):
  - Kết hợp 2 tầng:
    1. Bọc Số điện thoại, Địa chỉ nhận hàng, Mã vận đơn trong thẻ HTML `<code>...</code>` (người dùng chạm tay vào chữ trên điện thoại là copy ngay vào clipboard).
    2. Cung cấp các nút Inline chuyên dụng sử dụng `CopyTextButton` của Telegram Bot API 7.3+ (ví dụ: `[📋 Copy SĐT]`, `[📍 Copy Địa chỉ]`, `[🚚 Copy Mã vận đơn]`) để người già dễ bấm.
- **D-06:** Bố cục đổi trạng thái vòng đời đơn:
  - Dưới thẻ chi tiết hiển thị 1 nút to nổi bật gợi ý bước kế tiếp tự nhiên theo luồng (ví dụ: đang ở `CHO_LAM` -> gợi ý nút `[▶️ Bắt đầu làm]`).
  - Kèm 1 nút phụ `[🔄 Đổi trạng thái khác]` để mở rộng menu chọn bất kỳ trạng thái nào trong 8 trạng thái.
- **D-07:** Xác nhận với trạng thái nhạy cảm:
  - Các trạng thái thông thường (`DANG_LAM`, `DA_DONG_GOI`, `DA_TAO_DON`, `SHIPPER_DA_LAY`, `DA_GIAO`) đổi ngay tức thì 1 chạm.
  - Riêng 2 trạng thái nhạy cảm/kết thúc đơn có tổn thất (`BOM_HANG`, `HUY_DON`): Bot hiển thị bước hỏi xác nhận kèm 2 nút `[⚠️ Xác nhận]` và `[Quay lại]` để tránh người già chạm nhầm.
- **D-08:** Phản hồi khi đổi trạng thái:
  - Chỉnh sửa trực tiếp tin nhắn thẻ hiện tại (`edit_message_text`), không gửi tin nhắn mới làm trôi màn hình.
  - Hiển thị popup toast alert ngắn gọn trên Telegram (`query.answer(text="✅ Đã chuyển sang: ...")`) và bọc try/catch chống lỗi `telegram.error.BadRequest: Message is not modified`.

### 3. Nhập mã vận đơn & Quản lý ảnh đính kèm
- **D-09:** Quy trình nhập mã vận đơn đối tác ship:
  - Trên thẻ chi tiết có nút `[🚚 Nhập/Đổi mã vận đơn]`. Khi bấm, bot gửi tin nhắn hướng dẫn: *"Bác gửi mã vận đơn (hoặc dán ảnh biên lai ship) cho đơn này nhé:"* kèm nút Inline `[❌ Huỷ bỏ]`.
  - Bot chờ tin nhắn text từ người dùng, cập nhật `tracking_code` vào DB cho đơn hàng đó và cập nhật lại thẻ chi tiết.
- **D-10:** Xem lại ảnh đính kèm:
  - Thẻ chi tiết hiển thị dòng: `📷 Ảnh đính kèm: N ảnh`.
  - Nếu có ảnh, hiển thị nút Inline `[🖼️ Xem N ảnh]`. Khi bấm, bot gửi Album ảnh bằng `send_media_group` (sử dụng các `file_id` Telegram đã lưu trong DB) kèm nút `[Quay lại thẻ đơn]`.
- **D-11:** Bổ sung ảnh cho đơn đã lưu:
  - Trên thẻ chi tiết có nút `[➕ Gửi thêm ảnh]`. Khi bấm, bot kích hoạt trạng thái chờ ảnh. Người dùng gửi 1 hoặc nhiều ảnh, bot tự động lấy `photo.file_id` append vào `photo_file_ids` của đơn trong DB via `append_order_photos()`.
- **D-12:** Thoát trạng thái chờ (Cancel & Timeout):
  - Mọi trạng thái chờ nhập (chờ mã vận đơn, chờ gửi ảnh) luôn đi kèm nút Inline `[❌ Huỷ bỏ thao tác]` trong tin nhắn hướng dẫn và tự động hủy sau 2 phút nếu không có thao tác để tránh kẹt bot.

### Claude's Discretion
- Tạo helper format chuỗi HTML cho thẻ chi tiết đơn hàng rõ ràng, font chữ to, ngắt dòng thoáng mắt, emoji trực quan.
- Mapping trạng thái đơn hàng sang tiếng Việt thân thiện:
  - `CHO_LAM`: ⏳ Chờ làm
  - `DANG_LAM`: 🛠️ Đang làm
  - `DA_DONG_GOI`: 📦 Đã đóng gói
  - `DA_TAO_DON`: 📑 Đã tạo đơn ship
  - `SHIPPER_DA_LAY`: 🚚 Shipper đã lấy
  - `DA_GIAO`: ✅ Đã giao thành công
  - `BOM_HANG`: 🚫 Bom hàng
  - `HUY_DON`: ❌ Đã huỷ đơn

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Architecture & Tech Stack Guidelines
- `CLAUDE.md` §1 — Access Control Whitelist, Telegram Bot (PTB v20+ Async), Elderly Low-Tech UX Patterns, Stateless Callback Handlers, CopyTextButton
- `CLAUDE.md` §2 — SQLite Database & Schema Design (aiosqlite WAL mode, JSON arrays, snapshot orders)
- `CLAUDE.md` §3 — Settings Management (Pydantic-Settings v2)

### Project Requirements & Roadmaps
- `.planning/PROJECT.md` — Project definition, core values, constraints, and architecture decisions
- `.planning/REQUIREMENTS.md` — Requirements DATA-05, UI-01, UI-02, UI-03, UI-04, UI-05, UI-06
- `.planning/ROADMAP.md` — Phase 3 Goal & Success criteria (Ergonomic Order Management & Low-Tech Actions)
- `.planning/phases/02-llm-ingestion-interactive-confirmation/02-CONTEXT.md` — Phase 2 decisions and data contracts

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `src/db/orders.py`:
  - `get_order_by_id(db, order_id)`: Đã có sẵn để lấy chi tiết đơn hàng.
  - `update_order_status(db, order_id, new_status)`: Đã có sẵn để cập nhật trạng thái đơn.
  - `update_order_tracking(db, order_id, tracking_code)`: Đã có sẵn để lưu mã vận đơn.
  - `append_order_photos(db, order_id, new_photo_ids)`: Đã có sẵn để thêm ảnh bổ sung.
  - `list_orders_by_status(db, status, limit, offset)`: Đã có sẵn.
  - Cần thêm query hàm tìm kiếm/liệt kê đơn theo ngày: `list_orders_by_date(db, date_str, limit, offset)` và đếm tổng đơn theo ngày `count_orders_by_date(db, date_str)`.
- `src/models/order.py`:
  - `OrderStatus` enum đầy đủ 8 trạng thái.
  - `Order` model với đầy đủ trường `tracking_code`, `photo_file_ids`, `shipping_address`, `customer_phone`.
- `src/bot/handlers/base.py`:
  - Có thể cập nhật `start_command()` để gửi kèm Reply Keyboard cố định ngay khi khởi động bot.
- `src/bot/app.py`:
  - Đăng ký các handler mới: Reply Keyboard handler, Callback query handler cho quản lý đơn, và conversation/state handler cho nhập tracking code & thêm ảnh.

### Established Patterns
- python-telegram-bot v20+ async handler architecture.
- Inline CallbackQuery handling với `query.answer()` ngay lập tức để chống spinner.
- Format tiền tệ VNĐ: `{amount:,} đ`.replace(",", ".").

### Integration Points
- `src/bot/keyboards.py`: Tạo mới module quản lý các bàn phím Reply Keyboard cố định và Inline Keyboard cho danh sách đơn, thẻ chi tiết, chọn trạng thái, nút copy.
- `src/bot/handlers/orders.py`: Tạo mới module xử lý xem đơn hôm nay, chọn ngày, phân trang, và hiển thị thẻ chi tiết đơn.
- `src/bot/handlers/order_actions.py`: Tạo mới module xử lý đổi trạng thái, nhập mã vận đơn, xem/gửi thêm ảnh.
- `src/db/orders.py`: Bổ sung hàm truy vấn đơn theo ngày (`list_orders_by_date`, `count_orders_by_date`).

</code_context>

<specifics>
## Specific Ideas
- Định dạng thẻ chi tiết đơn hàng thoáng mắt:
  ```text
  📦 CHI TIẾT ĐƠN HÀNG #12
  Trạng thái: ⏳ Chờ làm
  -----------------------------
  👤 Khách: Bác Hùng
  📞 SĐT: 0912345678 (chạm để copy)
  📍 Địa chỉ: 123 Lê Lợi, P. Bến Thành, Q.1, TP.HCM
  📼 Băng: 2 cuốn Tuấn Vũ 3, 1 cuốn Chế Linh
  💰 Tổng tiền: 350.000 đ
  💵 Tiền COD: 300.000 đ
  🚚 Mã vận đơn: [Chưa có]
  📷 Ảnh đính kèm: 2 ảnh
  -----------------------------
  [▶️ Bắt đầu làm]
  [📋 Copy SĐT] [📍 Copy Địa chỉ]
  [🚚 Nhập mã vận đơn] [🖼️ Xem 2 ảnh]
  [🔄 Đổi trạng thái khác] [➕ Thêm ảnh]
  [⬅️ Quay lại danh sách]
  ```

</specifics>

<deferred>
## Deferred Ideas
- Tra cứu đơn hàng bằng câu chat tự nhiên tiếng Việt (VD: *"tìm đơn của anh Tuấn ở Hà Nội"*, *"thêm ảnh cho đơn anh Tuấn"*): Thuộc phạm vi của **Phase 4: Natural Language Order Search** (Yêu cầu SEARCH-01, SEARCH-02).
- Tự động đồng bộ trạng thái đơn từ webhook/API của hãng ship GHTK/GHN: Out of scope (v2).

</deferred>

---

*Phase: 3-Ergonomic Order Management & Low-Tech Actions*
*Context gathered: 2026-10-24*
