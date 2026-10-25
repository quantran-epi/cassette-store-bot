# Phase 5: Role-Based Access Control & Telegram Admin Suite - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-10-25
**Phase:** 5-Role-Based Access Control & Telegram Admin Suite
**Areas discussed:** Bố cục Menu Admin, Quản trị Whitelist, Đổi Model LLM, Phân cấp Quyền hạn

---

## Bố cục Menu Admin

| Option | Description | Selected |
|--------|-------------|----------|
| Chỉ dùng lệnh /admin (Khuyên dùng) | Giữ nguyên bàn phím 2x2 cho thao tác bán hàng, chỉ mở admin khi gõ lệnh /admin | ✓ |
| Hiện nút [⚙️ Quản trị] | Thêm nút vào Reply Keyboard cho tài khoản Admin | |
| Hỗ trợ cả hai | Admin có thể bấm nút trên bàn phím hoặc gõ /admin | |

**User's choice:** Chỉ dùng lệnh /admin (Khuyên dùng)
**Notes:** Giữ giao diện bán hàng đơn giản, không làm rối màn hình nhân viên.

---

## Giao diện Dashboard Menu Admin

| Option | Description | Selected |
|--------|-------------|----------|
| Dashboard tổng quan ngay (Khuyên dùng) | Hiển thị ngay thẻ thông tin: Trạng thái Bot, Database (WAL size), 9router (Model hiện tại), Uptime + các nút Inline chức năng | ✓ |
| Menu nút bấm tối giản | Tin nhắn ngắn gọn chào admin kèm danh sách các nút chức năng | |
| Bạn tự quyết định | Claude tự thiết kế hiển thị tối ưu | |

**User's choice:** Dashboard tổng quan ngay (Khuyên dùng)
**Notes:** Admin nắm bắt ngay tình trạng hệ thống khi vừa mở menu.

---

## Bố trí nút chức năng Menu Admin

| Option | Description | Selected |
|--------|-------------|----------|
| Lưới 2 cột trực quan (Khuyên dùng) | [👥 Whitelist] [🤖 Đổi Model] / [📜 Xem Log] [💾 Sao lưu] / [🔄 Làm mới] [❌ Đóng] | ✓ |
| Hàng đơn 1 cột to rõ | Mỗi hàng 1 nút to rõ ràng, có chú thích chi tiết | |
| Bạn tự quyết định | Bố trí cân đối theo chuẩn UX | |

**User's choice:** Lưới 2 cột trực quan (Khuyên dùng)
**Notes:** Tiết kiệm chiều dọc màn hình điện thoại.

---

## Điều hướng Menu Con

| Option | Description | Selected |
|--------|-------------|----------|
| Chỉnh sửa tin nhắn hiện tại (Khuyên dùng) | Sửa trực tiếp tin nhắn menu hiện tại (edit_message_text) kèm nút [⬅️ Quay lại] | ✓ |
| Gửi tin nhắn mới riêng | Mỗi lần chọn chức năng sẽ gửi một tin nhắn mới riêng biệt | |
| Bạn tự quyết định | Dùng edit_message_text theo chuẩn | |

**User's choice:** Chỉnh sửa tin nhắn hiện tại (Khuyên dùng)
**Notes:** Tránh gây rác khung chat Telegram.

---

## Giao diện danh sách Whitelist

| Option | Description | Selected |
|--------|-------------|----------|
| Danh sách chi tiết kèm role (Khuyên dùng) | Mỗi dòng hiển thị: ID, Tên/Ghi chú, Vai trò kèm nút chọn và nút [➕ Thêm ID] | ✓ |
| Văn bản text + nút thao tác chung | Liệt kê danh sách ID dạng <code>12345678</code> để copy | |
| Bạn tự quyết định | Trình bày theo format tối ưu | |

**User's choice:** Danh sách chi tiết kèm role (Khuyên dùng)
**Notes:** Hiển thị rõ cấp độ quyền của từng người.

---

## Quy trình thêm người dùng Whitelist

| Option | Description | Selected |
|--------|-------------|----------|
| Gửi tin nhắn ID + chọn role (Khuyên dùng) | Bot chờ gửi tin nhắn ID (+ Tên) trong 60s, sau đó chọn role qua nút Inline [Admin] hay [Nhân viên] | ✓ |
| Dùng lệnh /whitelist_add | Gõ lệnh cú pháp nhanh: /whitelist_add <user_id> [admin/staff] | |
| Bạn tự quyết định | Thiết kế flow nhập liệu an toàn | |

**User's choice:** Gửi tin nhắn ID + chọn role (Khuyên dùng)
**Notes:** Thao tác trực quan, có nút [❌ Huỷ] và timeout.

---

## Cơ chế xoá Whitelist

| Option | Description | Selected |
|--------|-------------|----------|
| Bắt buộc xác nhận 2 bước (Khuyên dùng) | Thẻ cảnh báo xác nhận 2 nút [⚠️ Xác nhận xoá] và [Quay lại] | ✓ |
| Xoá tức thì 1 chạm | Bấm nút xoá là xoá ngay | |
| Bạn tự quyết định | Theo chuẩn bảo vệ an toàn | |

**User's choice:** Bắt buộc xác nhận 2 bước (Khuyên dùng)
**Notes:** Chống chạm nhầm làm mất quyền nhân viên/admin.

---

## Lưu trữ và đồng bộ Whitelist

| Option | Description | Selected |
|--------|-------------|----------|
| SQLite DB + sync từ .env (Khuyên dùng) | Quản lý trong bảng SQLite admin_users, nạp từ .env lúc boot, cập nhật DB và bot_data tức thì | ✓ |
| Ghi trực tiếp vào .env | Chỉ dùng file .env, bot tự ghi đè file trên server | |
| Bạn tự quyết định | Lưu DB và đồng bộ in-memory | |

**User's choice:** SQLite DB + sync từ .env (Khuyên dùng)
**Notes:** Dữ liệu chuẩn hoá trong DB, phản hồi ngay lập tức qua in-memory cache bot_data.

---

## Giao diện & Cơ chế Đổi Model LLM

| Option | Description | Selected |
|--------|-------------|----------|
| Nút chọn nhanh + nhập tuỳ biến (Khuyên dùng) | Nút chọn nhanh model phổ biến + nút nhập tên khác | |
| Chỉ nhập text tên model | Chỉ hiển thị ô yêu cầu gõ tên model_id | |
| Custom (Yêu cầu từ người dùng) | Cho phép lưu các model phổ biến, chọn nhanh qua list đã lưu, cho cả nhập text, và CẦN có tính năng kiểm tra model có reachable hay không | ✓ |

**User's choice:** Cho phép lưu các model phổ biến, chọn nhanh qua list đã lưu đó, và cho cả nhập text, cần có tính năng kiểm tra model có reachable hay không
**Notes:** Yêu cầu người dùng đặc biệt nhấn mạnh việc ping probe kiểm tra kết nối với 9router trước khi chấp nhận chuyển đổi.

---

## Cơ chế kiểm tra Model Reachable

| Option | Description | Selected |
|--------|-------------|----------|
| Tự động probe trước khi lưu (Khuyên dùng) | Gửi test prompt 1 token đến 9router, 200 OK mới lưu; lỗi giữ nguyên model cũ | ✓ |
| Nút kiểm tra thủ công | Lưu ngay và hiển thị nút [🩺 Kiểm tra kết nối] thủ công | |
| Bạn tự quyết định | Thiết kế probe siêu nhẹ | |

**User's choice:** Tự động probe trước khi lưu (Khuyên dùng)
**Notes:** Bảo đảm bot không bao giờ bị rơi vào trạng thái dùng model chết hoặc sai tên.

---

## Lưu trữ cấu hình Model bền vững

| Option | Description | Selected |
|--------|-------------|----------|
| Bảng SQLite system_settings (Khuyên dùng) | Lưu active model và preset list vào DB, khởi động lại bot vẫn bảo lưu | ✓ |
| Chỉ lưu tạm in-memory | Chỉ lưu trong bộ nhớ RAM bot_data | |
| Bạn tự quyết định | Lưu SQLite kèm fallback .env | |

**User's choice:** Bảng SQLite system_settings (Khuyên dùng)
**Notes:** Không mất cấu hình khi reboot bot/container.

---

## Xử lý model mới nhập qua text

| Option | Description | Selected |
|--------|-------------|----------|
| Tự động lưu vào danh sách (Khuyên dùng) | Tự động thêm model mới vào danh sách chọn nhanh trong DB; có nút xoá khỏi danh sách | ✓ |
| Hỏi xác nhận trước khi lưu | Hỏi xác nhận trước khi lưu vào danh sách | |
| Không lưu vào danh sách | Chỉ đổi active model | |

**User's choice:** Tự động lưu vào danh sách (Khuyên dùng)
**Notes:** Tiết kiệm thao tác cho những lần đổi model tiếp theo.

---

## Phân định thẩm quyền vai trò

| Option | Description | Selected |
|--------|-------------|----------|
| Admin nghiệp vụ + Super Admin hệ thống (Khuyên dùng) | Admin thường: Xem dashboard, quản lý Staff, đổi model. Super Admin: Toàn quyền, quản lý Admin, xem logs, sao lưu | ✓ |
| Admin chỉ xem (Read-only) | Admin thường chỉ xem dashboard, mọi thao tác đổi do Super Admin làm | |
| Admin đồng quyền hạn | Admin thường ngang Super Admin, chỉ không xoá được Root ID | |

**User's choice:** Admin nghiệp vụ + Super Admin hệ thống (Khuyên dùng)
**Notes:** Phân quyền rõ ràng giữa nghiệp vụ quản trị hàng ngày và an ninh hệ thống.

---

## Phản hồi khi vi phạm phân quyền

| Option | Description | Selected |
|--------|-------------|----------|
| Cảnh báo pop-up & tin nhắn rõ ràng (Khuyên dùng) | Nút bấm: pop-up Telegram (show_alert=True). Lệnh gõ: tin nhắn từ chối rõ ràng | ✓ |
| Im lặng không phản hồi (Silent drop) | Bỏ qua không phản hồi | |
| Bạn tự quyết định | Theo chuẩn bảo mật | |

**User's choice:** Cảnh báo pop-up & tin nhắn rõ ràng (Khuyên dùng)
**Notes:** Người dùng nội bộ cần biết lý do không thao tác được.

---

## Bảo vệ tài khoản Root Super Admin

| Option | Description | Selected |
|--------|-------------|----------|
| Ẩn nút + Chặn cứng backend (Khuyên dùng) | Ẩn nút [Xoá] trên UI; chặn cứng ở tầng DB/Service (không thể xoá hoặc hạ quyền) | ✓ |
| Hiện nút kèm thông báo từ chối | Vẫn hiện nút nhưng bấm thì báo lỗi | |
| Bạn tự quyết định | Tự động nhận diện root ID từ .env | |

**User's choice:** Ẩn nút + Chặn cứng backend (Khuyên dùng)
**Notes:** Chống tuyệt đối nguy cơ tự khoá (self-lockout) tài khoản quản trị cao nhất.

---

## Giao diện nhật ký hệ thống /logs

| Option | Description | Selected |
|--------|-------------|----------|
| Định dạng <pre> + nút lọc & làm mới (Khuyên dùng) | Hiển thị 30 dòng gần nhất trong thẻ <pre> code kèm các nút: [25 dòng] [50 dòng] [⚠️ Chỉ Lỗi] [🔄 Làm mới] | ✓ |
| Text cố định 30 dòng đơn giản | Chỉ xuất ra tin nhắn text cố định 30 dòng | |
| Bạn tự quyết định | Tuân thủ giới hạn Telegram 4096 ký tự | |

**User's choice:** Định dạng <pre> + nút lọc & làm mới (Khuyên dùng)
**Notes:** Hỗ trợ Super Admin chẩn đoán lỗi nhanh trực tiếp trên điện thoại.

---

## Claude's Discretion
- Định dạng chuỗi tin nhắn HTML cho Dashboard trạng thái hệ thống.
- Cấu trúc chi tiết bảng SQLite `admin_users` và `system_settings`.
- Cấu hình Logging Ring Buffer handler (sử dụng `logging.Handler` chuẩn Python kết hợp `collections.deque` thread-safe).

## Deferred Ideas
None — discussion stayed within phase scope.
