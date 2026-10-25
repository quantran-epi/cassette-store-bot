# Phase 6: Telegram Database Backup Engine & Scheduled Tasks - Context

**Gathered:** 2026-10-25
**Status:** Ready for planning

<domain>
## Phase Boundary

Xây dựng động cơ sao lưu cơ sở dữ liệu SQLite định kỳ và thủ công cho Telegram Bot:
1. Tạo snapshot SQLite an toàn bằng `VACUUM INTO` từ live DB (đang bật WAL mode), nén `gzip` giảm 75-85% dung lượng thành file `.sqlite3.gz`.
2. Tự động sao lưu định kỳ hàng ngày (mặc định 02:00 AM UTC+7) thông qua PTB `JobQueue` (APScheduler) và cho phép Super Admin kích hoạt thủ công tức thì qua `/backup` hoặc nút bấm trên menu `/admin`.
3. Gửi file nén trực tiếp vào Telegram chat của Super Admin (`TELEGRAM_SUPER_ADMIN_ID`), kiểm tra ngưỡng an toàn 50MB (cảnh báo khi >= 48MB), cơ chế retry và cô lập lỗi an toàn tuyệt đối không làm gián đoạn bot phục vụ khách.
4. Cho phép Super Admin cấu hình thời gian chạy sao lưu định kỳ trực tiếp trên giao diện Telegram menu `/admin`.
5. Tiếp thu và hoàn thiện 2 tính năng công thái học cho Admin Suite từ Phase 5: danh sách chọn nhanh model mặc định rỗng (thêm qua nhập text kèm probe, hỗ trợ xoá model khỏi danh sách) và tính năng đổi tên (rename) user trong Whitelist.

</domain>

<decisions>
## Implementation Decisions

### 1. Lưu trữ tạm & Retention local trên máy chủ (Storage & Retention)
- **D-01:** File snapshot `VACUUM INTO` và nén gzip được tạo trong thư mục `backups/` nội bộ (nằm cùng cấp với file SQLite chính `data/` hoặc project root), giúp dễ debug, kiểm tra và dễ dàng mount volume trong Docker/Kubernetes.
- **D-02:** Quy ước đặt tên file backup: `cassette_store_backup_YYYYMMDD_HHMMSS.sqlite3.gz` (chuẩn thời gian ISO, sắp xếp theo thứ tự bảng chữ cái tự nhiên, không bao giờ trùng tên khi chạy nhiều lần trong ngày).
- **D-03:** File snapshot `.sqlite3` thô sau `VACUUM INTO` được xoá ngay lập tức trong khối `try...finally` ngay sau khi nén thành `.gz` thành công để tiết kiệm dung lượng đĩa.
- **D-04:** Chính sách Retention local: Giữ tối đa 7 bản backup gần nhất (khoảng 7 ngày) trong thư mục `backups/` để làm phương án dự phòng offline khi Telegram lỗi mạng, tự động quét và dọn dẹp các file cũ hơn khi chạy job mới.

### 2. Trải nghiệm sao lưu thủ công (Manual Backup UX & Caption)
- **D-05:** Khi Super Admin kích hoạt sao lưu thủ công (qua gõ lệnh `/backup` hoặc bấm nút `[💾 Sao lưu DB]` trên menu `/admin`):
  - Hệ thống lập tức phản hồi thông báo tiến trình: `"⏳ Đang tạo snapshot và nén dữ liệu cơ sở dữ liệu..."` (hoặc cập nhật tin nhắn hiện tại nếu gọi từ callback query) để tránh cảm giác bot bị đơ.
  - Sau khi nén xong, gửi file Document `.sqlite3.gz` kèm caption chi tiết và cập nhật thông báo hoàn tất.
- **D-06:** Nội dung Caption đính kèm file Document hiển thị đầy đủ thông số kỹ thuật và nghiệp vụ:
  - ⏱️ Thời gian snapshot (định dạng `YYYY-MM-DD HH:MM:SS` theo giờ Việt Nam UTC+7).
  - 💾 Dung lượng file gốc (uncompressed MB) vs Dung lượng nén (.gz MB) kèm tỷ lệ nén tiết kiệm (ví dụ: `Giảm 82.4%`).
  - 📊 Thống kê nhanh dữ liệu: Tổng số đơn hàng & Tổng số khách hàng đang lưu trong DB.
- **D-07:** Tin nhắn gửi file backup là file Document thuần túy, không đính kèm bàn phím Inline bên dưới để giữ giao diện tin nhắn sạch sẽ, giúp người dùng dễ dàng chạm 1-chạm tải về máy hoặc chuyển tiếp (forward/save) vào Saved Messages.
- **D-08:** Đích đến của file backup khi chạy thủ công: Gửi trực tiếp vào chat của Super Admin đang thao tác gọi lệnh (đã được kiểm tra vai trò `SUPER_ADMIN` qua decorator `@require_role`).

### 3. Xử lý giới hạn dung lượng & Lỗi mạng (Size Limits & Error Handling)
- **D-09:** Telegram Bot API giới hạn dung lượng gửi file Document là 50MB. Hệ thống đặt ngưỡng an toàn là 48MB:
  - Nếu file `.sqlite3.gz` sau khi nén có dung lượng `>= 48MB`: Hệ thống KHÔNG thực hiện gửi file qua Telegram, ghi log `ERROR`, đồng thời gửi tin nhắn cảnh báo đỏ cho Super Admin nêu rõ dung lượng thực tế và cung cấp đường dẫn file lưu trữ trên máy chủ để sysadmin tải về thủ công qua SCP/SFTP.
- **D-10:** Xử lý lỗi mạng Telegram khi gửi Document:
  - Tự động thử lại (retry) tối đa 3 lần với cơ chế exponential backoff (2s, 5s, 10s).
  - Nếu sau 3 lần vẫn thất bại: Gửi tin nhắn text báo lỗi khẩn cho Super Admin, giữ nguyên file backup `.gz` trên ổ cứng local để không bị mất dữ liệu phiên sao lưu.
- **D-11:** Mức độ cô lập tiến trình: Toàn bộ tác vụ backup (snapshot, nén, retention, gửi Telegram) được bao bọc trong khối `try...except Exception`, ghi đầy đủ stacktrace vào `RingBufferLogHandler` và file log hệ thống. Lỗi sao lưu KHÔNG BAO GIỜ làm crash bot hay gián đoạn luồng chat bán hàng của khách.
- **D-12:** Khi job sao lưu tự động định kỳ ban đêm (02:00 AM) gặp bất kỳ lỗi nào, bot luôn gửi tin nhắn thông báo sự cố trực tiếp vào chat riêng của Super Admin để được xử lý kịp thời vào sáng hôm sau.

### 4. Cơ chế Lập lịch Scheduler & Cấu hình giờ qua Menu Admin (Scheduler & Admin Config)
- **D-13:** Sử dụng PTB `JobQueue` (APScheduler) tích hợp sẵn trong `Application` của `python-telegram-bot` (`python-telegram-bot[job-queue]`) để quản lý lifecycle đồng bộ với bot, hỗ trợ múi giờ `Asia/Ho_Chi_Minh` (UTC+7).
- **D-14:** Hành vi khi bot khởi động (Startup Behavior): Chỉ đăng ký lịch chạy tiếp theo vào đúng giờ hẹn kế tiếp (mặc định 02:00 AM). KHÔNG tự động kích hoạt sao lưu lúc vừa boot để tránh tình trạng spam file rác vào chat Telegram khi redeploy hoặc restart tiến trình.
- **D-15:** Cấu hình thời gian sao lưu định kỳ qua Telegram:
  - Cho phép Super Admin xem và thay đổi giờ/phút sao lưu định kỳ trực tiếp trong menu `/admin` trên Telegram (nút `[⏰ Đặt giờ sao lưu]`).
  - Giá trị giờ/phút được lưu trữ bền vững vào bảng `system_settings` trong SQLite (key `backup_schedule_time`, mặc định `"02:00"`).
  - Khi Super Admin đổi giờ trên menu: Bot lập tức huỷ job cũ trong `JobQueue` và lên lịch lại theo giờ mới tức thì mà không cần khởi động lại bot.
- **D-16:** Phân quyền: Chỉ duy nhất tài khoản vai trò `SUPER_ADMIN` mới có quyền kích hoạt `/backup`, bấm nút `[💾 Sao lưu DB]` và thay đổi giờ sao lưu định kỳ. Người dùng `ADMIN` thường hoặc `STAFF` nếu cố tình truy cập sẽ nhận cảnh báo thiếu thẩm quyền (`show_alert=True` hoặc tin nhắn từ chối).

### 5. Hoàn thiện & Tinh chỉnh Admin Suite (Phase 5 Carryover)
- **D-17:** Tinh chỉnh Model Switcher:
  - Mặc định danh sách chọn nhanh model ban đầu là rỗng (không nạp cứng 4 model mẫu như trước). Chỉ hiển thị model active hiện tại lấy từ DB / `.env`.
  - Admin thêm model mới bằng cách bấm `[✏️ Nhập model khác]` / `[➕ Thêm model]`, gửi tên model qua chat text.
  - Bot thực hiện ping probe 1 token qua 9router. Nếu probe HTTP 200 thành công: lưu model vào `system_settings` làm active model và đồng thời thêm vào danh sách model chọn nhanh.
  - Bổ sung nút `[🗑️ Xoá model]` trong menu chọn nhanh để admin có thể gỡ bỏ các model không dùng ra khỏi danh sách chọn nhanh (chặn không cho xoá model đang active).
- **D-18:** Bổ sung tính năng Đổi tên / Ghi chú User trong Whitelist:
  - Trong màn hình chi tiết người dùng Whitelist (`adm:wl:view:<id>`), bổ sung nút `[✏️ Đổi tên]`.
  - Khi bấm, bot chuyển sang chế độ chờ admin gửi tin nhắn text tên mới (timeout 60s, kèm nút `[❌ Huỷ]`).
  - Khi nhận tên mới: cập nhật trường `name` của user trong bảng `admin_users` của SQLite và cập nhật giao diện chi tiết tức thì.

### Claude's Discretion
- Định dạng chuỗi caption HTML chi tiết cho file backup.
- Cấu trúc module backup engine (`src/services/backup.py` hoặc tương đương).
- Tùy biến mức độ nén gzip (mặc định level 6 hoặc 9 cân bằng tốc độ và dung lượng).

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Architecture & Tech Stack Guidelines
- `CLAUDE.md` §1 — Access Control Whitelist & PTB v20+ Async Handler Architecture
- `CLAUDE.md` §2 — SQLite Database & Schema Design (aiosqlite WAL mode, VACUUM INTO compatibility)
- `CLAUDE.md` §4 — Settings Management (Pydantic-Settings v2)

### Project Requirements & Roadmaps
- `.planning/PROJECT.md` — Project definition, core values, constraints, and architecture decisions
- `.planning/REQUIREMENTS.md` — Requirements BKP-01, BKP-02, BKP-03, BKP-04
- `.planning/ROADMAP.md` — Phase 6 Goal, dependencies, and success criteria
- `.planning/phases/05-role-based-access-control-telegram-admin-suite/05-CONTEXT.md` — Admin Suite layout, `@require_role`, và cơ sở hạ tầng Phase 5

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `src/bot/handlers/admin.py`: Đã có sẵn callback stub `adm:bkp:trigger` và giao diện menu admin 2x2.
- `src/bot/keyboards.py`: Các hàm xây dựng bàn phím Inline, hỗ trợ mở rộng thêm nút đặt giờ backup và đổi tên user.
- `src/bot/security.py`: Decorator `@require_role(UserRole.SUPER_ADMIN)` dùng để bảo vệ lệnh `/backup` và các callback sao lưu.
- `src/db/connection.py`: `get_db_connection` kết nối `aiosqlite` ở chế độ WAL.
- `src/db/settings.py`: `get_setting`, `set_setting`, `get_json_setting`, `set_json_setting` sẵn sàng để lưu giờ backup và danh sách model.
- `src/db/admin.py`: `list_admin_users`, `get_admin_user`, `create_or_update_admin_user` sẵn sàng để bổ sung đổi tên user.

### Established Patterns
- Thao tác SQLite bất đồng bộ qua `aiosqlite`.
- Lệnh snapshot `VACUUM INTO ?` có thể thực thi an toàn trực tiếp trên live connection SQLite WAL mà không gây lock hay block ghi đơn hàng.
- Lưu trữ cấu hình động trong bảng `system_settings` và đồng bộ trong `context.bot_data`.

### Integration Points
- `src/services/backup.py`: Service mới chịu trách nhiệm tạo snapshot `VACUUM INTO`, nén `gzip`, tính dung lượng, dọn dẹp retention 7 ngày và gửi file qua Telegram.
- `src/bot/handlers/backup.py` hoặc tích hợp vào `src/bot/handlers/admin.py`: Xử lý lệnh `/backup`, callback `adm:bkp:trigger`, và callback cấu hình giờ `adm:bkp:time`.
- `src/bot/app.py`: Đăng ký `JobQueue` cho tác vụ chạy ngầm định kỳ hàng ngày, nạp cấu hình lịch sao lưu từ DB lúc khởi động.
- `pyproject.toml`: Bổ sung `python-telegram-bot[job-queue]` nếu môi trường chưa kích hoạt APScheduler.

</code_context>

<specifics>
## Specific Ideas
- Lệnh `VACUUM INTO` của SQLite là lệnh native cực kỳ mạnh mẽ, copy nguyên tử một file snapshot độc lập mà không cần tắt kết nối WAL, sau đó dùng module stdlib `gzip` nén lại.
- Tinh chỉnh Phase 5 từ yêu cầu của người dùng: List model chọn nhanh không hardcode sẵn mà bắt đầu rỗng, thêm/xoá theo nhu cầu thực tế; cho phép admin đổi tên gợi nhớ của user trong whitelist để phân biệt người dùng dễ dàng.

</specifics>

<deferred>
## Deferred Ideas
- **RESTORE-01**: Wizard khôi phục dữ liệu từ file backup gửi ngược lại vào Telegram chat (thuộc milestone v2 tương lai).
- **ANALYTICS-01**: Báo cáo doanh thu biểu đồ nâng cao qua tin nhắn hình ảnh Telegram (thuộc milestone v2).

</deferred>

---

*Phase: 06-Telegram Database Backup Engine & Scheduled Tasks*
*Context gathered: 2026-10-25*
