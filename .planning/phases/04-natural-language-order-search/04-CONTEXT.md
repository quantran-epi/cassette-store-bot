# Phase 4: Natural Language Order Search - Context

**Gathered:** 2026-10-25
**Status:** Ready for planning

<domain>
## Phase Boundary

Tra cứu và tìm kiếm đơn hàng bằng ngôn ngữ tự nhiên tiếng Việt cho người lớn tuổi / low-tech thông qua Telegram bot. Hệ thống hỗ trợ kích hoạt qua nút menu cố định `[🔍 Tra cứu đơn]` hoặc tự động nhận diện câu chat có từ khoá tìm kiếm; sử dụng LLM gateway 9router chuyển đổi câu hỏi tự do thành câu truy vấn Text-to-SQL (SELECT-only) linh hoạt trên cơ sở dữ liệu SQLite; hiển thị thẻ xác nhận trực quan trước khi mở chi tiết đơn hàng hoặc câu trả lời tóm tắt số liệu thống kê tự nhiên, cho phép thao tác đổi trạng thái trực tiếp và quay lại kết quả tìm kiếm mượt mà.

</domain>

<decisions>
## Implementation Decisions

### 1. Kích hoạt tìm kiếm (Query Trigger Mode)
- **D-01:** Bố trí nút `[🔍 Tra cứu đơn]` trên Reply Keyboard cố định dưới khung chat theo lưới 2x2:
  - Hàng 1: `[📦 Đơn hôm nay]` `[📋 Xem theo ngày]`
  - Hàng 2: `[📝 Nhập đơn mới]` `[🔍 Tra cứu đơn]`
  - Thay thế vị trí nút Trợ giúp (chuyển Trợ giúp thành lệnh `/help`).
- **D-02:** Nhận diện tự động: Nếu người dùng không bấm nút `[🔍 Tra cứu đơn]` mà gõ trực tiếp câu chat bắt đầu bằng các từ khoá tìm kiếm ("tìm...", "tra cứu...", "kiểm tra đơn..."), bot tự động nhận diện và kích hoạt luồng tra cứu thay vì báo lỗi thiếu SĐT của luồng nhập đơn.
- **D-03:** Quản lý trạng thái chờ: Khi bấm nút `[🔍 Tra cứu đơn]`, bot phản hồi hướng dẫn kèm nút Inline `[❌ Huỷ tra cứu]`, tự động huỷ sau 2 phút nếu không có thao tác để tránh kẹt trạng thái của bot.

### 2. Chuyển đổi truy vấn qua LLM (LLM Search Translation)
- **D-04:** Kiến trúc Text-to-SQL (Read-only): Để hỗ trợ linh hoạt 100% mọi câu hỏi phức tạp (tìm theo ca sĩ, phôi băng, thời gian, khoảng tiền, trạng thái, câu hỏi thống kê "bao nhiêu đơn", "gần nhất khi nào"):
  - Cung cấp DDL schema của bảng `orders` và `customers` kèm ngày giờ hiện tại theo giờ Việt Nam (UTC+7) trong System Prompt của LLM.
  - LLM sinh câu truy vấn SQL thuần tuý.
- **D-05:** Ràng buộc an toàn: App Python kiểm tra nghiêm ngặt câu lệnh SQL từ LLM sinh ra:
  - Bắt buộc bắt đầu bằng `SELECT`.
  - Nghiêm cấm tuyệt đối các từ khoá thay đổi dữ liệu (`INSERT`, `UPDATE`, `DELETE`, `DROP`, `ALTER`, `CREATE`, `REPLACE`, `ATTACH`, `PRAGMA`).
- **D-06:** Cơ chế gọi LLM & Khôi phục lỗi:
  - Tái sử dụng client OpenAI và gateway 9router đã cấu hình.
  - Nếu câu SQL sinh ra bị lỗi cú pháp SQLite, app tự động gửi lại thông báo lỗi kèm schema cho LLM thử sửa 1 lần (retry 1-shot).
- **D-07:** Phân luồng xử lý kết quả truy vấn:
  - Nếu câu hỏi tìm đơn cụ thể (trả về danh sách các hàng từ bảng `orders`): Chuyển kết quả sang luồng hiển thị thẻ xác nhận đơn hàng (D-08, D-09).
  - Nếu câu hỏi thống kê / tổng hợp (kết quả trả về scalar như `COUNT`, `SUM`, `MAX`, `AVG` hoặc danh sách ngắn thống kê): Gửi kết quả rows về cho LLM tóm tắt thành 1 câu trả lời tiếng Việt tự nhiên, ngắn gọn, ấm áp cho người già.

### 3. Giao diện xác nhận kết quả (Results & Confirmation UX)
- **D-08:** Khớp đúng 1 đơn hàng duy nhất:
  - Hiển thị thẻ tóm tắt hỏi xác nhận: Mã đơn `#ID`, Tên khách, SĐT (dạng che bớt hoặc code), Tên băng, Tổng tiền, Trạng thái đơn.
  - Kèm dòng giải thích ngắn gọn tiêu chí bot đã tìm ra (ví dụ: *"🔍 Em tìm thấy đơn anh Tuấn mua Tuấn Vũ hôm qua:"*).
  - Cung cấp 2 nút bấm Inline: `[👁️ Đúng rồi, xem chi tiết]` và `[🔍 Tìm câu khác]`. Bấm xác nhận mới mở thẻ chi tiết đầy đủ (đáp ứng đúng yêu cầu 2-phase confirmation của SEARCH-02).
- **D-09:** Khớp từ 2 đơn hàng trở lên (Nhiều đơn):
  - Hiển thị thông báo: *"Dạ em tìm thấy N đơn hàng phù hợp:"*, tóm tắt mỗi đơn 2 dòng kèm danh sách nút bấm `[👁️ Xem đơn #ID]` và điều hướng phân trang 5 đơn/trang (tái sử dụng component danh sách đơn của Phase 3).
- **D-10:** Không tìm thấy đơn nào (0 đơn):
  - Thông báo thân thiện: *"Dạ em tìm trong sổ không thấy đơn nào như bác tả rồi!"* kèm gợi ý mẫu câu tìm kiếm và 2 nút bấm Inline: `[🔍 Thử tìm lại]` và `[📝 Nhập đơn mới]`.
- **D-11:** Hiệu ứng chờ: Trong thời gian bot gọi LLM và query SQLite (1-3s), bot gửi liên tục hiệu ứng typing (`ChatAction.TYPING`) để người lớn tuổi an tâm chờ đợi.

### 4. Điều hướng và thao tác (Action & Navigation Flow)
- **D-12:** Tái sử dụng thẻ chi tiết đầy đủ: Khi bấm xem chi tiết đơn tìm được, mở thẻ chi tiết đầy đủ của Phase 3 (`render_order_detail_card` + `build_order_detail_keyboard`) có đầy đủ nút Copy 1 chạm (SĐT, Địa chỉ, Mã vận đơn), xem/thêm ảnh, và cho phép đổi trạng thái trực tiếp.
- **D-13:** Nút quay lại thông minh: Nút `[⬅️ Quay lại]` trên thẻ chi tiết được điều hướng quay trở lại đúng tin nhắn tóm tắt hoặc danh sách kết quả tìm kiếm trước đó, không làm mất ngữ cảnh tìm kiếm.
- **D-14:** Nút tìm kiếm tiếp theo: Dưới kết quả tra cứu luôn có nút `[🔍 Tìm câu khác]` để kích hoạt lại luồng tra cứu ngay lập tức.

### Claude's Discretion
- Định dạng System Prompt Text-to-SQL chi tiết với các quy tắc mapping SQLite: sử dụng `date(created_at, '+7 hours')` cho thời gian UTC+7, so sánh xâu không phân biệt hoa thường, xử lý tiếng Việt.
- Cơ chế sanitize và unaccent đơn giản hỗ trợ SQLite nếu cần cho các trường tên và địa chỉ.
- Tự động giới hạn `LIMIT 20` cho các câu lệnh SELECT tìm đơn để chống tràn bộ nhớ nếu câu truy vấn quá rộng.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Architecture & Tech Stack Guidelines
- `CLAUDE.md` §1 — Telegram Bot (PTB v20+ Async), Elderly Low-Tech UX Patterns, Stateless Callback Handlers, CopyTextButton
- `CLAUDE.md` §2 — SQLite Database & Schema Design (aiosqlite WAL mode, JSON arrays, snapshot orders)
- `CLAUDE.md` §3 — OpenAI Client, 9router Gateway & Structured Outputs
- `CLAUDE.md` §4 — Settings Management (Pydantic-Settings v2)

### Project Requirements & Roadmaps
- `.planning/PROJECT.md` — Core values, constraints, and architecture decisions
- `.planning/REQUIREMENTS.md` — Requirements SEARCH-01, SEARCH-02, UI-02
- `.planning/ROADMAP.md` — Phase 4 Goal & Success criteria
- `.planning/phases/02-llm-ingestion-interactive-confirmation/02-CONTEXT.md` — LLM gateway patterns and 2-tier fallback
- `.planning/phases/03-ergonomic-order-management-low-tech-actions/03-CONTEXT.md` — Menu layout, order list cards, detail cards, and navigation callback patterns

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `src/bot/keyboards.py`:
  - `build_main_menu_reply_keyboard()`: Cần cập nhật nút `[❓ Trợ giúp]` thành `[🔍 Tra cứu đơn]`.
  - `render_order_detail_card(order)`: Thẻ chi tiết HTML mono copy.
  - `build_order_detail_keyboard(order, ...)`: Bộ nút bấm copy 1 chạm, đổi trạng thái, xem/thêm ảnh.
  - `render_order_list_card(...)` & `build_order_list_keyboard(...)`: Component danh sách đơn phân trang tái sử dụng cho trường hợp tìm ra nhiều đơn.
- `src/db/orders.py`:
  - `get_order_by_id(db, order_id)`: Lấy chi tiết đơn.
  - `update_order_status(db, order_id, new_status)`: Đổi trạng thái trực tiếp từ thẻ chi tiết.
- `src/bot/app.py`:
  - Khởi tạo `AppContext` chứa `openai_client`, `settings`, `db`.
  - Đăng ký regex handler cho menu Reply Keyboard.

### Established Patterns
- SQLite WAL mode qua `aiosqlite`.
- Lọc bảo mật whitelist ở Handler Group -1.
- Hiển thị xác nhận 2 pha trước khi thực thi hoặc hiển thị chi tiết nhạy cảm.
- Định dạng ngày tháng chuẩn UTC+7 (`date(created_at, '+7 hours')`).

### Integration Points
- `src/services/order_search.py` (Mới): Service xử lý Text-to-SQL qua OpenAI client (9router), validate câu lệnh SELECT, thực thi SQLite an toàn và tóm tắt kết quả thống kê.
- `src/bot/handlers/search.py` (Mới): Handler bắt sự kiện bấm nút `[🔍 Tra cứu đơn]`, nhận tin nhắn tìm kiếm hoặc câu chat tự động phát hiện prefix "tìm...", gửi ChatAction.TYPING, hiển thị thẻ xác nhận kết quả.
- `src/bot/handlers/orders.py` & `src/bot/keyboards.py`: Tích hợp nút `[🔍 Tra cứu đơn]` vào menu 2x2.

</code_context>

<specifics>
## Specific Ideas
- Prompt cho LLM Text-to-SQL cần có ví dụ mẫu cụ thể:
  - "tìm đơn anh Tuấn hôm qua mua 2 cuốn Tuấn Vũ" -> `SELECT o.* FROM orders o WHERE date(o.created_at, '+7 hours') = date('now', '+7 hours', '-1 day') AND o.customer_name LIKE '%Tuấn%' AND o.items_text LIKE '%Tuấn Vũ%' ORDER BY o.created_at DESC LIMIT 20;`
  - "lần gần nhất có khách mua băng Tuấn Vũ là khi nào" -> `SELECT o.created_at, o.customer_name, o.items_text, o.id FROM orders o WHERE o.items_text LIKE '%Tuấn Vũ%' ORDER BY o.created_at DESC LIMIT 1;`
  - "khách anh Nam đã mua bao nhiêu đơn rồi" -> `SELECT COUNT(*) AS total_orders, SUM(o.total_amount) AS total_spent FROM orders o WHERE o.customer_name LIKE '%Nam%' OR o.customer_phone LIKE '%Nam%';`
- Thẻ xác nhận 1 đơn:
  ```text
  🔍 <b>KẾT QUẢ TÌM KIẾM ĐƠN HÀNG</b>
  <i>(Tìm theo: 'anh Tuấn' - hôm qua)</i>
  ────────────────────
  📦 <b>Đơn #{order.id}</b> - {customer_name}
  📞 SĐT: <code>{customer_phone}</code>
  📼 Băng: {items_text}
  💰 Tổng tiền: {total_amount} | Trạng thái: {status}
  ────────────────────
  Có phải bác muốn xem đơn này không?
  [👁️ Đúng rồi, xem chi tiết]  [🔍 Tìm câu khác]
  ```

</specifics>

<deferred>
## Deferred Ideas

### None — discussion stayed within phase scope
Tất cả các tính năng nâng cao nằm ngoài phạm vi tìm kiếm tự nhiên (như xuất báo cáo Excel, phân tích doanh thu chuyên sâu) đã được đưa vào Backlog / v2 Requirements trong REQUIREMENTS.md.

</deferred>

---

*Phase: 04-natural-language-order-search*
*Context gathered: 2026-10-25*
