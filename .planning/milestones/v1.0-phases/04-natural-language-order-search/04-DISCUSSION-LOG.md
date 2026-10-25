# Phase 04: Natural Language Order Search - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-10-25
**Phase:** 04-natural-language-order-search
**Areas discussed:** Query Trigger Mode, LLM Search Translation, Results & Confirmation UX, Action & Navigation Flow

---

## Query Trigger Mode

| Option | Description | Selected |
|--------|-------------|----------|
| Nút bấm riêng biệt | Thêm nút "🔍 Tra cứu đơn" vào Reply Keyboard cố định | ✓ |
| Tự động phân loại intent | Gõ bất kỳ câu chat nào không có SĐT thì coi là câu tìm kiếm | |
| Lệnh slash /tim | Bắt đầu câu bằng /tim hoặc prefix cố định | |

**User's choice:** Nút bấm riêng biệt
**Notes:** Bố trí nút trên Reply Keyboard 2x2 thay thế nút Trợ giúp; đồng thời hỗ trợ nhận diện tự động nếu câu chat bắt đầu bằng từ khoá "tìm...", "tra cứu...". Trạng thái chờ có nút [❌ Huỷ tra cứu] và timeout 2 phút.

---

## LLM Search Translation

| Option | Description | Selected |
|--------|-------------|----------|
| Pydantic Schema + SQL Builder | LLM sinh schema tiêu chí -> Python build SQL | |
| Text-to-SQL (SELECT-only) | Gửi DDL schema cho LLM sinh SQL thuần tuý, app chỉ cho phép SELECT | ✓ |

**User's choice:** Text-to-SQL (SELECT-only)
**Notes:** Người dùng yêu cầu hệ thống phải cực kỳ linh hoạt để trả lời được mọi câu hỏi phức tạp (ví dụ: "lần gần nhất có khách mua băng Tuấn Vũ là khi nào", "khách A đã mua bao nhiêu đơn rồi"). App gửi schema DDL + giờ hiện tại UTC+7, LLM sinh câu SELECT. Code Python kiểm tra cú pháp và chỉ cho phép SELECT. Nếu kết quả là thống kê thì LLM tóm tắt lại thành câu trả lời tự nhiên.

---

## Results & Confirmation UX

| Option | Description | Selected |
|--------|-------------|----------|
| Thẻ tóm tắt hỏi xác nhận | Hiện thẻ tóm tắt hỏi "Có phải bác muốn xem đơn này không?" kèm nút xem chi tiết | ✓ |
| Mở thẳng chi tiết luôn | Mở ngay thẻ chi tiết đầy đủ | |

**User's choice:** Thẻ tóm tắt hỏi xác nhận
**Notes:**
- 1 đơn duy nhất: Hiện thẻ tóm tắt kèm lý do tìm thấy và nút [👁️ Đúng rồi, xem chi tiết].
- Nhiều đơn (từ 2 trở lên): Hiện danh sách chọn đơn phân trang 5 đơn/trang.
- 0 đơn: Báo thân thiện kèm gợi ý từ khoá và nút tìm lại.
- Trạng thái chờ: Gửi ChatAction.TYPING liên tục.

---

## Action & Navigation Flow

| Option | Description | Selected |
|--------|-------------|----------|
| Tái dùng thẻ chi tiết Phase 3 | Mở thẻ chi tiết đầy đủ có nút Copy, đổi trạng thái, xem/thêm ảnh | ✓ |
| Thẻ chỉ xem riêng biệt | Tạo thẻ riêng chỉ để xem | |

**User's choice:** Tái dùng thẻ chi tiết Phase 3
**Notes:** Nút [⬅️ Quay lại] đưa người dùng trở về danh sách/thẻ tìm kiếm trước đó; cho phép đổi trạng thái trực tiếp; luôn có nút [🔍 Tìm câu khác] để tra cứu câu mới.

---

## Claude's Discretion
- Prompt Text-to-SQL chi tiết với quy tắc UTC+7 và mapping bảng `orders`, `customers`.
- Thêm `LIMIT 20` tự động cho các câu lệnh tìm kiếm đơn hàng để bảo vệ bộ nhớ.

## Deferred Ideas
- Không có (tính năng nằm ngoài phạm vi tìm kiếm đã có trong Backlog).
