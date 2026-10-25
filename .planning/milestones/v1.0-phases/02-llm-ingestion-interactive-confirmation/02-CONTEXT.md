# Phase 2: LLM Ingestion & Interactive Confirmation - Context

**Gathered:** 2026-10-24
**Status:** Ready for planning

<domain>
## Phase Boundary

Tích hợp gateway 9router (OpenAI-compatible protocol) bóc tách tin nhắn tự do tiếng Việt (kèm ảnh hoặc caption) thành cấu trúc chuẩn hoá tiền tệ VNĐ, đối chiếu lịch sử khách hàng (khách quen, nhiều địa chỉ, cảnh báo bom hàng), và quản lý luồng xác nhận hai pha qua thẻ xem trước (preview card) với Inline Keyboard trước khi lưu vĩnh viễn vào SQLite.
</domain>

<decisions>
## Implementation Decisions

### 1. Tiêu chí bóc tách & Nhận diện thông tin tối thiểu
- **D-01:** Số điện thoại (SĐT) là khoá nhận diện duy nhất và bắt buộc (`sđt là key`). Chỉ cần có SĐT hợp lệ là bot tiến hành tạo đơn nháp và hiển thị thẻ xem trước. Các trường thông tin khác (tên khách, địa chỉ, danh sách băng cassette, giá tiền) nếu thiếu trong tin nhắn thì hiển thị dạng placeholder `[Chưa có]` và vẫn cho phép lưu đơn.
- **D-02:** Tin nhắn không phải đơn hàng (không tìm thấy SĐT hợp lệ hoặc tin nhắn chat thông thường): Bot nhắc nhẹ nhàng, lịch sự: *"Em không nhận diện được đơn hàng từ tin nhắn này. Bác vui lòng gửi lại tin nhắn có số điện thoại khách nhé!"* để hướng dẫn người lớn tuổi cách thao tác.

### 2. Định dạng thẻ xem trước (Preview Card) & Nút bấm xác nhận
- **D-03:** Hiển thị tài chính phân tách rõ ràng 2 dòng: `Tổng tiền: ... đ` và `Tiền COD thu khách: ... đ` (kèm thông tin tiền đã cọc nếu có) để người lớn tuổi nhìn một cái hiểu ngay, tránh nhầm lẫn giữa tiền hàng và tiền thu hộ COD.
- **D-04:** Bộ nút bấm Inline Keyboard dưới thẻ xem trước gồm 2 nút to trên cùng 1 hàng: `[✅ Xác nhận lưu]` và `[❌ Huỷ bỏ]`. Khi bấm `❌ Huỷ bỏ`, tin nhắn thẻ được cập nhật thông báo huỷ, không ghi gì vào DB. Khi bấm `✅ Xác nhận lưu`, ghi dữ liệu vào DB và cập nhật tin nhắn thẻ thành thông báo thành công.

### 3. Nhận diện khách quen, Lịch sử mua hàng & Cảnh báo bom hàng
- **D-05:** Khi trích xuất được SĐT, bot tự động truy vấn DB để kiểm tra khách cũ:
  - Nếu là khách quen: Hiển thị ngay phần tóm tắt lịch sử mua hàng trong thẻ xem trước: Số lượng đơn đã đặt, tổng tiền đã mua, và đặc biệt là **Cảnh báo bom hàng** (nếu khách có đơn ở trạng thái `BOM_HANG`).
- **D-06:** Tự động điền địa chỉ cho khách quen:
  - Nếu khách quen KHÔNG nhắn lại địa chỉ trong tin nhắn mới:
    - Nếu khách chỉ có **1 địa chỉ** trong DB: Tự động điền địa chỉ đó vào đơn và ghi chú rõ trong preview card `📍 Địa chỉ (tự lấy từ đơn trước): ...`.
    - Nếu khách có **từ 2 địa chỉ trở lên** đã lưu: Bot hiển thị các nút Inline bấm nhanh cho từng địa chỉ để người dùng chạm chọn 1 trong các địa chỉ cũ, hoặc chọn nhập địa chỉ mới.
  - Nếu khách quen nhắn **địa chỉ mới** khác các địa chỉ cũ đã lưu: Tự động bổ sung địa chỉ mới vào danh sách `addresses` của khách hàng trong DB và snapshot vào đơn hàng hiện tại.

### 4. Quản lý trạng thái lưu tạm (Draft State) & Tương tác đồng thời
- **D-07:** Cơ chế lưu tạm sử dụng in-memory `context.user_data["pending_orders"][draft_id]`. Mỗi thẻ preview gắn 1 `draft_id` ngẫu nhiên (UUID hoặc chuỗi ngắn), nút bấm Inline mang `callback_data` có cấu trúc: `ord:confirm:<draft_id>` và `ord:cancel:<draft_id>`. Nếu bot bị restart khiến mất dữ liệu tạm trong memory, khi bấm nút bot phản hồi thông báo: *"Thao tác hết hạn, bác vui lòng gửi lại tin nhắn nhé!"*.
- **D-08:** Hỗ trợ gửi dồn nhiều tin nhắn cùng lúc (đa đơn độc lập): Mỗi tin nhắn gửi đến sinh một thẻ xem trước với `draft_id` độc lập. Người dùng có thể paste liên tục 2-3 tin nhắn đơn và bấm xác nhận từng thẻ riêng biệt mà không bị ghi đè.

### 5. Xử lý ảnh đính kèm (Photo Ingestion) & Xử lý lỗi Gateway LLM
- **D-09:** Khi người dùng gửi 1 bức ảnh kèm caption (chú thích ảnh): Bot lấy caption gửi cho LLM bóc tách như tin nhắn text thông thường, đồng thời trích xuất `photo.file_id` (lấy độ phân giải cao nhất) đưa vào danh sách `photo_file_ids` của đơn nháp để lưu vào DB khi xác nhận.
- **D-10:** Xử lý lỗi kết nối hoặc phản hồi từ 9router LLM (timeout, hết quota, format lỗi): Báo nhẹ nhàng: *"⚠️ Hệ thống bóc tách đang bận hoặc gián đoạn kết nối. Bác vui lòng thử gửi lại tin nhắn sau giây lát nhé!"* và ghi log chi tiết lỗi cho kỹ thuật viên.

### Claude's Discretion
- Định dạng prompt gửi cho LLM (bao gồm hướng dẫn tiếng Việt, ví dụ tiếng lóng "250k", "1tr2", "cọc 50k thu 200k").
- Cơ chế 2-tier fallback khi gọi LLM: thử dùng `beta.chat.completions.parse()` với Pydantic schema, nếu gateway 9router không hỗ trợ `json_schema` thì fallback sang `response_format={"type": "json_object"}` kết hợp `Pydantic.model_validate_json()`.
- Cấu trúc layout chi tiết và emoji trong Preview Card sao cho thoáng mắt, dễ đọc nhất trên màn hình điện thoại.
</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Architecture & Tech Stack Guidelines
- `CLAUDE.md` §1 — Access Control Whitelist, Telegram Bot (PTB v20+ Async), Elderly Low-Tech UX Patterns, Stateless Callback Handlers
- `CLAUDE.md` §2 — SQLite Database & Schema Design (aiosqlite WAL mode, JSON arrays, snapshot orders)
- `CLAUDE.md` §3 — OpenAI Client, 9router Gateway & Structured Outputs (Pydantic schema, Dual-Mode LLM Client with Fallback)
- `CLAUDE.md` §4 — Settings Management (Pydantic-Settings v2)

### Project Requirements & Roadmaps
- `.planning/PROJECT.md` — Project definition, core values, constraints, and architecture decisions
- `.planning/REQUIREMENTS.md` — Requirements INGEST-01, INGEST-02, INGEST-03, INGEST-04
- `.planning/ROADMAP.md` — Phase 2 Goal & Success criteria
</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `src/config.py`: Đã cấu hình đầy đủ `nine_router_api_key`, `nine_router_base_url`, `nine_router_model_id`, `telegram_whitelist_user_ids`.
- `src/models/customer.py` & `src/db/customers.py`: Các hàm `get_customer_by_phone()`, `create_customer()`, `add_phone_number()`, `add_address()` đã sẵn sàng sử dụng để tra cứu và cập nhật khách hàng.
- `src/models/order.py` & `src/db/orders.py`: Hàm `create_order()` và enum `OrderStatus` (với `OrderStatus.CHO_LAM`, `OrderStatus.BOM_HANG`, ...) và `list_orders_by_customer_id()`.
- `src/bot/security.py`: Decorator whitelist kiểm soát quyền truy cập ở Handler Group -1.
- `src/bot/app.py`: `create_application()` đã đăng ký security gate và các handler cơ bản.

### Established Patterns
- Asynchronous python-telegram-bot v20+ handlers.
- SQLite WAL mode qua `aiosqlite` không bị khoá file.
- Pydantic models cho domain data.

### Integration Points
- Module `src/services/llm.py` hoặc `src/services/extractor.py`: Khởi tạo `AsyncOpenAI` kết nối tới 9router, gọi structured output bóc tách đơn.
- Module `src/bot/handlers/ingest.py`: `MessageHandler` lắng nghe text/photo (caption) từ người dùng whitelist.
- Module `src/bot/handlers/callbacks.py`: `CallbackQueryHandler` bắt pattern `ord:confirm:<draft_id>` và `ord:cancel:<draft_id>`.
</code_context>

<specifics>
## Specific Ideas
- Khi phát hiện khách từng bom hàng (`BOM_HANG`), hiển thị biểu tượng cảnh báo rõ rệt trên thẻ xem trước:
  `⚠️ CẢNH BÁO: Khách từng có 1 đơn BOM HÀNG!`
- Bố cục thẻ xem trước trực quan cho người già:
  ```text
  📦 ĐƠN HÀNG MỚI (Xem trước)
  👤 Khách: Bác Hùng [Khách quen: 3 đơn - 850.000đ]
  📞 SĐT: 0912345678
  📍 Địa chỉ: 123 Lê Lợi, P. Bến Thành, Q.1, TP.HCM
  📼 Băng cassette: 2 cuốn Tuấn Vũ 3, 1 cuốn Chế Linh
  💰 Tổng tiền: 350.000đ
  💵 Tiền COD thu: 300.000đ (đã cọc 50.000đ)
  --------------------------
  Bác bấm nút bên dưới để xác nhận nhé:
  [✅ Xác nhận lưu]  [❌ Huỷ bỏ]
  ```
</specifics>

<deferred>
## Deferred Ideas
- Đổi trạng thái đơn hàng (sang `Đang làm`, `Đã đóng gói`, ...) và các nút bấm sao chép 1 chạm thông tin giao hàng: thuộc Phase 3 (Ergonomic Order Management & Low-Tech Actions).
- Tìm kiếm đơn hàng bằng chat tự nhiên: thuộc Phase 4 (Natural Language Order Search).
</deferred>

---

*Phase: 2-LLM Ingestion & Interactive Confirmation*
*Context gathered: 2026-10-24*
