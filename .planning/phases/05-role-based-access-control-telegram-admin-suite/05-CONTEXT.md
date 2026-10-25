# Phase 5: Role-Based Access Control & Telegram Admin Suite - Context

**Gathered:** 2026-10-25
**Status:** Ready for planning

<domain>
## Phase Boundary

Xây dựng hệ thống phân quyền 2 cấp độ (SUPER_ADMIN vs ADMIN) cho Telegram bot, bộ menu quản trị `/admin` trực quan bằng Inline Keyboard (xem dashboard trạng thái hệ thống, chuyển đổi model LLM 9router kèm kiểm tra reachability tức thì, quản trị whitelist CRUD cho người dùng/nhân viên) và lệnh xem nhật ký hệ thống trực tiếp `/logs` qua thẻ HTML `<pre>`.

</domain>

<decisions>
## Implementation Decisions

### 1. Bố cục Menu Admin (Admin Suite Layout & UX)
- **D-01:** Truy cập menu quản trị thông qua lệnh gõ `/admin`, giữ nguyên bàn phím Reply Keyboard 2x2 cố định cho việc bán hàng gọn gàng và tránh thao tác nhầm lẫn.
- **D-02:** Tin nhắn phản hồi `/admin` hiển thị ngay Dashboard tổng quan trạng thái hệ thống (Uptime bot, trạng thái SQLite DB & WAL size, kết nối 9router & model_id đang dùng, số đơn hôm nay) kèm các nút Inline chức năng bên dưới.
- **D-03:** Bố trí nút Inline menu admin dạng lưới 2 cột trực quan:
  - Hàng 1: `[👥 Quản lý Whitelist]` `[🤖 Đổi Model LLM]`
  - Hàng 2: `[📜 Xem Logs]` `[💾 Sao lưu DB]`
  - Hàng 3: `[🔄 Làm mới]` `[❌ Đóng menu]`
- **D-04:** Điều hướng trong menu admin sử dụng cơ chế `edit_message_text` trực tiếp trên tin nhắn hiện tại kèm nút `[⬅️ Quay lại]` để giữ khung chat sạch sẽ, không tạo tin nhắn rác.

### 2. Quản trị Whitelist (Whitelist CRUD UX & Sync)
- **D-05:** Giao diện danh sách Whitelist hiển thị chi tiết: Telegram User ID, Tên gợi nhớ/ghi chú, Vai trò (`👑 SUPER_ADMIN` / `🛡️ ADMIN` / `👤 STAFF`), kèm nút chọn xem/thao tác từng ID và nút `[➕ Thêm ID]`.
- **D-06:** Quy trình thêm người dùng mới: Chờ admin gửi tin nhắn chứa Telegram User ID (và tuỳ chọn Tên) với timeout 60 giây và nút `[❌ Huỷ]`, sau đó hiển thị nút chọn role `[🛡️ Admin]` hoặc `[👤 Nhân viên]`.
- **D-07:** Xoá hoặc hạ quyền người dùng khỏi Whitelist bắt buộc qua thẻ xác nhận 2 bước với 2 nút `[⚠️ Xác nhận xoá]` và `[Quay lại]` để chống bấm nhầm.
- **D-08:** Quản lý danh sách trong bảng SQLite `admin_users`. Khi khởi động bot, tự động đồng bộ `TELEGRAM_SUPER_ADMIN_ID` và `TELEGRAM_WHITELIST_USER_IDS` từ `.env` vào DB nếu chưa tồn tại. Khi thêm/xoá trên Telegram, cập nhật đồng thời cả DB và `context.bot_data["whitelist_user_ids"]` để có hiệu lực tức thì.

### 3. Đổi Model LLM & Reachability Testing (Model Switcher)
- **D-09:** Menu đổi model hỗ trợ lưu danh sách model phổ biến khả dụng (vd: `gpt-4o-mini`, `gpt-4o`, `claude-3-5-haiku`, `gemini-1.5-flash`), chọn nhanh 1-chạm (đánh dấu `[✓]` ở model đang active) kèm nút `[✏️ Nhập tên khác]` cho phép nhập tự do tên model_id từ 9router.
- **D-10:** Cơ chế Reachability Probe: Trước khi lưu và áp dụng model mới, bot tự động gửi một test call siêu nhẹ (completion prompt 1 token) đến 9router. Nếu nhận phản hồi HTTP 200 OK mới lưu và áp dụng; nếu gặp lỗi (401/404/500/timeout) giữ nguyên model cũ và thông báo lỗi chi tiết cho admin.
- **D-11:** Cấu hình bền vững: Lưu model active và danh sách model khả dụng vào bảng `system_settings` trong SQLite. Khởi động bot ưu tiên nạp từ DB, nếu chưa có mới fallback sang `.env` (`NINE_ROUTER_MODEL_ID`).
- **D-12:** Khi admin nhập một model mới qua text và probe thành công, hệ thống tự động lưu model đó vào danh sách chọn nhanh trong DB để tái sử dụng; trong menu có nút `[🗑️ Xoá khỏi danh sách]` để dọn bớt model không dùng.

### 4. Phân cấp Quyền hạn & Bảo vệ Root (Role Hierarchy & Root Protection)
- **D-13:** Phân định 2 vai trò quản trị:
  - `SUPER_ADMIN`: Toàn quyền hệ thống (xem dashboard, quản lý admin khác, đổi model LLM, xem logs `/logs`, kích hoạt sao lưu `/backup`).
  - `ADMIN`: Quản lý nghiệp vụ (xem dashboard, quản lý nhân viên bán hàng Staff trong whitelist, đổi model LLM). Không có quyền quản lý Admin khác, không xem được `/logs`, không được kích hoạt sao lưu `/backup`.
- **D-14:** Decorator phân quyền `@require_role(role)` bảo vệ mọi lệnh slash và callback queries. Khi vi phạm quyền hạn: với CallbackQuery hiển thị Telegram Alert pop-up (`show_alert=True`), với lệnh gõ gửi tin nhắn từ chối lịch sự, nêu rõ thẩm quyền yêu cầu.
- **D-15:** Chống tự khoá Root Super Admin: Nhận diện `TELEGRAM_SUPER_ADMIN_ID` cấu hình trong `.env`; ẩn hoàn toàn nút xoá/hạ quyền trên UI và chặn cứng ở tầng DB/Service (ném ngoại lệ bảo vệ nếu có request can thiệp).
- **D-16:** Lệnh xem nhật ký `/logs` cho Super Admin: Đọc ring buffer (25-50 dòng log gần nhất trong bộ nhớ) định dạng HTML `<pre><code>...</code></pre>`, kèm các nút Inline tiện ích: `[25 dòng]`, `[50 dòng]`, `[⚠️ Chỉ Lỗi]`, `[🔄 Làm mới]`.

### Claude's Discretion
- Định dạng chuỗi tin nhắn HTML cho Dashboard trạng thái hệ thống.
- Cấu trúc chi tiết bảng SQLite `admin_users` và `system_settings`.
- Cấu hình Logging Ring Buffer handler (sử dụng `logging.Handler` chuẩn Python kết hợp `collections.deque` thread-safe).

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
- `.planning/REQUIREMENTS.md` — Requirements RBAC-01, RBAC-02, RBAC-03, RBAC-04, RBAC-05
- `.planning/ROADMAP.md` — Phase 5 Goal, dependencies, and success criteria

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `src/bot/security.py`: `whitelist_gate` đang chạy ở group -1, kiểm tra `context.bot_data["whitelist_user_ids"]`.
- `src/config.py`: `Settings` quản lý nạp `.env` với `telegram_whitelist_user_ids`.
- `src/bot/keyboards.py`: Cung cấp hàm tạo InlineKeyboardMarkup và CopyTextButton chuẩn cho Telegram.
- `src/bot/app.py`: Khởi tạo `Application`, `AppContext`, nạp `bot_data` dùng chung.
- `src/db/connection.py`: Kết nối SQLite bất đồng bộ qua `aiosqlite` ở chế độ WAL.

### Established Patterns
- python-telegram-bot v20+ async handler architecture.
- Quản lý dữ liệu nhạy cảm hoặc cấu hình nóng trong `context.bot_data` kết hợp đồng bộ SQLite.
- Giao diện 2 bước xác nhận (confirmation cards) đối với hành động nguy hiểm/nhạy cảm (tương tự đổi trạng thái đơn BOM_HANG/HUY_DON ở Phase 3).

### Integration Points
- `src/config.py`: Bổ sung `telegram_super_admin_id: int | None = None`.
- `src/db/schema.py`: Bổ sung DDL cho bảng `admin_users` và `system_settings`.
- `src/bot/security.py`: Thêm decorator `@require_role` và các hàm tiện ích kiểm tra vai trò (`get_user_role`, `is_super_admin`, `is_admin`).
- `src/bot/handlers/admin.py`: Module mới chứa các handler cho `/admin`, `/logs` và các callback điều hướng menu admin.
- `src/bot/app.py`: Đăng ký các admin handlers và khởi tạo ring buffer logging handler.

</code_context>

<specifics>
## Specific Ideas
- Người dùng yêu cầu đặc thù cho Đổi Model: Phải có tính năng kiểm tra model có reachable hay không (ping probe 1 token) trước khi đổi; cho phép lưu các model phổ biến để chọn nhanh và vẫn hỗ trợ nhập text tuỳ ý.
- Root Super Admin ID trong `.env` luôn là bất khả xâm phạm, không bao giờ bị xoá hay hạ quyền kể cả khi database bị chỉnh sửa.

</specifics>

<deferred>
## Deferred Ideas
None — discussion stayed within phase scope.

</deferred>

---

*Phase: 05-Role-Based Access Control & Telegram Admin Suite*
*Context gathered: 2026-10-25*
