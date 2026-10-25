# Phase 1: Foundation, Persistence & Security Whitelist - Context

**Gathered:** 2026-10-24
**Status:** Ready for planning

<domain>
## Phase Boundary

Thiết lập nền tảng cấu hình local (.env via pydantic-settings), cơ sở dữ liệu SQLite ở chế độ WAL qua aiosqlite, thực thể khách hàng và đơn hàng hỗ trợ snapshot, ảnh Telegram file_id, và middleware bảo mật chặn người lạ ngoài Telegram User ID whitelist.
</domain>

<decisions>
## Implementation Decisions

### Whitelist & Security
- **D-01:** Khi người lạ (User ID ngoài whitelist) nhắn tin đến bot, bot phản hồi từ chối lịch sự và hiển thị Telegram User ID của họ (để admin/chủ shop dễ sao chép thêm vào cấu hình whitelist khi cần).
- **D-02:** Whitelist hỗ trợ nạp từ biến môi trường `TELEGRAM_WHITELIST_USER_IDS` dưới dạng chuỗi phân tách bởi dấu phẩy, tự động chuyển đổi thành `list[int]` qua Pydantic-Settings.

### Database & Persistence
- **D-03:** Bảng `customers` sử dụng cột JSON array để lưu danh sách nhiều số điện thoại (`phones`) và nhiều địa chỉ (`addresses`), kèm `notes` và `name`. Giữ thiết kế tinh gọn, tránh phải JOIN 3 bảng.
- **D-04:** Bảng `orders` lưu snapshot thông tin khách tại thời điểm đặt (tên, SĐT, địa chỉ nhận hàng), chi tiết hàng hoá text tự do, tổng tiền, COD, hình thức thanh toán, mã vận đơn và cột `photo_file_ids` (mảng JSON lưu danh sách file_id Telegram).
- **D-05:** Cấu hình SQLite kích hoạt `PRAGMA journal_mode=WAL` và `PRAGMA busy_timeout=5000` thông qua `aiosqlite` để đảm bảo tương thích async không gây lock database.
- **D-06:** Vòng đời đơn hàng quản lý qua enum 7 trạng thái: `CHO_LAM` (Chờ làm), `DANG_LAM` (Đang làm), `DA_DONG_GOI` (Đã đóng gói), `DA_TAO_DON` (Đã tạo đơn trên app vận chuyển), `SHIPPER_DA_LAY` (Shipper đã lấy hàng), `DA_GIAO` (Đã giao thành công), `BOM_HANG` (Bom hàng), `HUY_DON` (Huỷ đơn).

### Code Organization & Settings
- **D-07:** Tổ chức mã nguồn trong thư mục `src/` phân tách rõ ràng:
  - `src/config.py`: Quản lý cấu hình `Settings` với Pydantic-Settings v2.
  - `src/db/`: Quản lý kết nối SQLite `aiosqlite`, tạo schema và các hàm CRUD cơ sở.
  - `src/models/`: Định nghĩa các Pydantic models và domain schemas.
  - `src/bot/`: Khởi tạo Application `python-telegram-bot`, security middleware / filter chặn whitelist, và lệnh cơ bản `/start`, `/ping`.
  - `main.py` ở root: Điểm khởi chạy chính ứng dụng.

### Claude's Discretion
- Định dạng tin nhắn phản hồi `/start` và `/ping` cho admin kiểm tra trạng thái bot khởi động.
- Chi tiết câu lệnh SQL CREATE TABLE và index trên các cột tìm kiếm (`customer_id`, `created_at`, `status`).
</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Architecture & Tech Stack Guidelines
- `CLAUDE.md` §1 — Access Control Whitelist (Security Gate) & Telegram Bot configuration
- `CLAUDE.md` §2 — SQLite Database & Schema Design (aiosqlite WAL mode, JSON arrays)
- `CLAUDE.md` §4 — Settings Management (Pydantic-Settings v2)

### Project Requirements & Roadmaps
- `.planning/PROJECT.md` — Project definition, core values, constraints, and architecture decisions
- `.planning/REQUIREMENTS.md` — Requirements CFG-01, SEC-01, DATA-01, DATA-02, DATA-03, DATA-04
- `.planning/ROADMAP.md` — Phase 1 Goal & Success criteria
</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- Dự án mới khởi tạo, chưa có file mã nguồn. Tất cả nền tảng Phase 1 sẽ là nền tảng dùng chung cho Phase 2, 3, 4.

### Established Patterns
- Async python-telegram-bot v20+ với ApplicationBuilder.
- aiosqlite cho asynchronous local database access.
- Pydantic-settings cho fail-fast environment variable validation.

### Integration Points
- File `.env` chứa cấu hình bot token, whitelist, 9router credentials.
- File cơ sở dữ liệu `cassette_store.db` lưu cục bộ.
</code_context>

<specifics>
## Specific Ideas
- Khi người ngoài whitelist nhắn tin: "⛔ Bạn không có quyền truy cập bot này. Telegram User ID của bạn: `123456789`. Vui lòng liên hệ quản trị viên."
- Chạy lệnh test kiểm tra kết nối DB và cấu hình khởi động trơn tru trước khi sang Phase 2.
</specifics>

<deferred>
## Deferred Ideas
None — discussion stayed within phase scope.
</deferred>

---

*Phase: 1-Foundation, Persistence & Security Whitelist*
*Context gathered: 2026-10-24*
