# Phase 7: Natural Language Order Mutation Pipeline - Context

**Gathered:** 2026-10-25
**Status:** Ready for planning

<domain>
## Phase Boundary

Người dùng gửi tin nhắn chat tự nhiên chứa ý định chỉnh sửa đơn hàng bằng tiếng Việt. Hệ thống dùng 3-Way Intent Router tách biệt chính xác với luồng Tạo đơn và Tìm kiếm, tìm đúng đơn hàng cần sửa (kèm nút chọn 1-chạm nếu khớp nhiều đơn), dùng LLM (kết hợp fast-path) trích xuất delta thay đổi cho 5 nhóm trường, hiển thị thẻ so sánh Trước ➡️ Sau với TTL 120s, và cập nhật nguyên tử vào DB qua khóa lạc quan (Optimistic Locking) kèm lưu vết lịch sử sửa đơn (Audit Trail).

</domain>

<decisions>
## Implementation Decisions

### Routing ý định 3 chiều (3-Way Intent Router)
- **D-01:** Cơ chế nhận diện ý định Sửa đơn: Dùng regex từ khoá nhanh ("sửa", "đổi", "huỷ", "cập nhật", "thay địa chỉ"...) trước. Nếu không khớp regex mới dùng LLM fallback phân loại. Nhanh 0ms, tiết kiệm token.
- **D-02:** Xử lý câu mơ hồ (vừa có dấu hiệu tạo mới vừa có dấu hiệu sửa): Ưu tiên tìm đơn cũ để sửa trước; nếu không tìm thấy đơn cũ mới hỏi bác muốn tạo mới hay sửa.
- **D-03:** Kiến trúc router: Đóng gói thành 1 router hàm hợp nhất `classify_intent(text) -> CREATE | SEARCH | MUTATE` trong codebase để gom logic điều hướng, tránh if-else chồng chéo trong `ingest.py`.
- **D-04:** LLM fallback phân loại ý định: Khi regex không chắc chắn, gọi prompt phân loại nhẹ (10-20 token output trả về nhãn intent).
- **D-05:** Ngữ cảnh Reply: Khi người dùng Reply trực tiếp vào tin nhắn bot hiển thị đơn hàng trước đó, router tự động trích xuất Order ID từ tin nhắn gốc mà không cần tìm kiếm lại theo từ khoá.
- **D-06:** Fast-path sửa trạng thái: Với câu chat ngắn có cú pháp trạng thái rõ ràng (ví dụ: "huỷ đơn 12", "đơn 12 đã giao"), Router chuyển thẳng thành delta trạng thái mà không cần gọi LLM bóc tách, hiện ngay thẻ xác nhận 1-chạm.

### Phạm vi & Chọn đơn khớp (Scope & Disambiguation)
- **D-07:** Phạm vi tìm kiếm đơn cần sửa: Ưu tiên tìm các đơn đang active (`CHO_LAM`, `DANG_LAM`, `DA_DONG_GOI`, `DA_TAO_DON`, `SHIPPER_DA_LAY`). Nếu không thấy mới tìm trong các đơn đã hoàn tất (`DA_GIAO`, `BOM_HANG`, `HUY_DON`).
- **D-08:** Giao diện khi khớp nhiều đơn: Hiển thị tối đa 3-5 đơn gần nhất dưới dạng danh sách nút Inline 1-chạm: `[Đơn #12 - Nam - 250k - Chờ làm]` để người dùng bấm chọn ngay.
- **D-09:** Phản hồi khi không thấy đơn khớp: Báo "Không tìm thấy đơn hàng nào của [từ khoá]" kèm gợi ý gửi SĐT hoặc mã đơn để bot tìm lại; không tự động tạo đơn rác.
- **D-10:** Xử lý sau khi bấm chọn đơn từ danh sách gợi ý: Áp ngay delta đã bóc tách từ câu chat ban đầu (lưu tạm trong `user_data`) vào đơn đã chọn, lập tức hiển thị thẻ Diff Trước ➡️ Sau để xác nhận luôn.

### Giao diện Thẻ Diff Trước/Sau (Visual Diff Card & UX)
- **D-11:** Định dạng thẻ Visual Diff: Tiêu đề hiển thị `[Mã đơn #12 - Khách: Nam]`, bên dưới chỉ hiển thị các trường có thay đổi dạng `📍 Địa chỉ: [Cũ] ➡️ [Mới]`. Không in lại toàn bộ đơn để giữ màn hình gọn gàng, người già nhìn phát hiểu ngay.
- **D-12:** Xử lý huỷ hoặc hết hạn 120s: Khi bấm `[❌ Huỷ]` hoặc quá 120s TTL, edit tin nhắn thẻ Diff thành `❌ Đã huỷ yêu cầu sửa đơn` / `⏰ Đã hết hạn 120s` và gỡ bỏ toàn bộ nút bấm inline để chống bấm nhầm lần 2.
- **D-13:** Gợi ý trạng thái đích chưa rõ (MUT-05): Dựa vào trạng thái hiện tại của đơn, chỉ gợi ý các bước kế tiếp hợp lý theo vòng đời đơn hàng (ví dụ: `DANG_LAM` gợi ý `DA_DONG_GOI`, `DA_TAO_DON`, `HUY_DON`), hiển thị 3-4 nút bấm trực quan.
- **D-14:** Phản hồi sau khi xác nhận sửa thành công: Sửa trực tiếp (edit) tin nhắn thẻ Diff thành thẻ đơn hàng đã cập nhật kèm thông báo `✅ Đã cập nhật thành công đơn #12!` và các nút hành động (Copy text, Đổi trạng thái). Giữ màn hình chat sạch sẽ.

### Khóa lạc quan & Lịch sử sửa đơn (Optimistic Locking & Audit Trail)
- **D-15:** Cơ chế khóa lạc quan: Sử dụng kiểm tra `WHERE id = ? AND updated_at = ?` khi thực hiện UPDATE. Nếu rowcount == 0 nghĩa là đã có xung đột xảy ra trong 120s chờ xác nhận.
- **D-16:** Lưu người tạo đơn & Lịch sử sửa đơn:
  - Bổ sung 2 cột `created_by_user_id` (INTEGER) và `created_by_name` (TEXT) vào bảng `orders`.
  - Luồng tạo đơn mới (`confirm_order_callback`): lưu `effective_user.id` và `effective_user.full_name` vào bản ghi đơn hàng mới, đồng thời ghi 1 bản ghi vào `order_history` (action `CREATE`).
  - Thẻ chi tiết đơn hàng (`render_order_detail_card`): hiển thị người tạo ngay tại dòng thời gian theo format `🕒 Thời gian: 25/10/2026 14:30 (bởi Quan Tran)`. Với đơn cũ không có dữ liệu người tạo thì không hiện đoạn `(bởi ...)`.
  - Tạo bảng `order_history (id, order_id, user_id, user_name, action, changes_json, created_at)` ghi nhận chi tiết mọi thao tác tạo mới và sửa đổi (ai thực hiện, lúc nào, thay đổi trường gì từ giá trị cũ sang giá trị mới).
- **D-17:** Xử lý và thông báo khi có xung đột: Khi phát hiện optimistic lock mismatch, bot đọc bản ghi mới nhất từ `order_history` và thông báo rõ: "⚠️ Đơn vừa được [Tên/ID] sửa nội dung [Chi tiết thay đổi] lúc [Giờ]!".
- **D-18:** Điều hướng sau xung đột: Hiển thị thông báo xung đột kèm thẻ chi tiết đơn mới nhất (kèm các nút thao tác) và dừng thao tác sửa cũ để tránh ghi đè nhầm lên thay đổi của người khác.

### Claude's Discretion
- Định dạng cụ thể của tin nhắn lỗi hoặc cảnh báo hết hạn TTL.
- Tên chính xác của các regex pattern và cấu trúc Pydantic schema cho OrderMutationDelta.
- Tối ưu hóa câu lệnh SQL migration bổ sung bảng `order_history` và cột `created_by_user_id`.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Requirements & Roadmap
- `.planning/ROADMAP.md` — Phase 7 scope, goals, and success criteria
- `.planning/REQUIREMENTS.md` — MUT-01 to MUT-05 requirement specs

### Ingestion & Search Routing
- `src/bot/handlers/ingest.py` — Existing message ingestion, preview card rendering, action_state and search_intent dispatch
- `src/services/order_search.py` — Search keywords, regex conversational patterns, and keyword resolution logic

### Order Domain & Persistence
- `src/models/order.py` — Order and OrderStatus domain models (8 states)
- `src/db/orders.py` — Order creation, lookup, status/tracking update, and concurrency lock helpers
- `src/db/schema.py` — SQLite schema definitions and migrations

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `src/services/order_search.py::is_search_intent`: Pattern matching logic for search queries, directly extensible for intent routing.
- `src/bot/handlers/ingest.py::render_preview_card`: Elderly-friendly HTML card formatting pattern with InlineKeyboard buttons.
- `src/bot/handlers/order_actions.py`: Existing manual status update and tracking prompt flows with 120s TTL expiry.
- `src/services/extractor.py::extract_order_from_text`: 2-tier OpenAI parse client pattern with json_object fallback.

### Established Patterns
- 120s TTL for interactive Telegram confirmation states stored in `context.user_data`.
- 1-tap inline buttons (`InlineKeyboardButton`, `InlineKeyboardMarkup`) with short prefix callback_data (e.g., `ord:mut:confirm:<draft_id>`).
- Async SQLite with `aiosqlite` and WAL mode.
- Access control enforced via `src/bot/security.py` whitelist and RBAC roles.

### Integration Points
- `src/bot/handlers/ingest.py::handle_text_order`: Main entry point where `classify_intent` will route text to Mutation handler before search/create.
- `src/bot/handlers/callbacks.py`: Dispatching `ord:mut:*` callback queries for confirm, cancel, and state disambiguation.
- `src/db/schema.py`: Adding `order_history` table and `orders.created_by_user_id`.

</code_context>

<specifics>
## Specific Ideas

- Khi phát hiện xung đột khóa lạc quan (ai đó sửa trước trong 120s), đọc bảng `order_history` để báo rõ: "⚠️ Đơn vừa được [Tên/ID] sửa nội dung [Chi tiết thay đổi] lúc [Giờ]!".
- Người dùng Reply tin nhắn đơn cũ của bot để sửa -> tự nhận diện ID đơn, không cần tìm kiếm từ khoá lại.
- Fast-path cho câu ngắn "huỷ đơn 12", "đơn 12 đã giao" không cần qua LLM, tăng tốc độ phản hồi và tiết kiệm token.

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope.

</deferred>

---

*Phase: 07-Natural Language Order Mutation Pipeline*
*Context gathered: 2026-10-25*
