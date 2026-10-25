# Phase 7: Natural Language Order Mutation Pipeline - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-10-25
**Phase:** 07-Natural Language Order Mutation Pipeline
**Areas discussed:** Routing ý định 3 chiều, Phạm vi & Chọn đơn khớp, Giao diện Thẻ Diff Trước/Sau, Xung đột khóa lạc quan

---

## Routing ý định 3 chiều

| Option | Description | Selected |
|--------|-------------|----------|
| Regex trước + LLM fallback (Recommended) | Dùng regex bắt từ khoá sửa ("sửa", "đổi", "huỷ", "cập nhật", "thay địa chỉ"...) trước. Nếu không khớp regex mới gọi LLM phân loại. Nhanh 0ms, tiết kiệm token. | ✓ |
| LLM phân loại toàn bộ | Mọi tin nhắn không phải lệnh / đều qua LLM phân loại 3 nhãn: CREATE_ORDER, SEARCH_ORDER, MUTATE_ORDER. | |
| Bác quyết định giúp tôi | Claude tự cân đối phương án tối ưu dựa trên độ trễ và độ an toàn. | |

**User's choice:** Regex trước + LLM fallback (Recommended)
**Notes:** Giữ độ trễ 0ms cho đa số tin nhắn rõ ràng, chỉ fallback LLM khi tin nhắn mập mờ.

| Option | Description | Selected |
|--------|-------------|----------|
| Ưu tiên sửa nếu tìm thấy đơn (Recommended) | Nếu câu có dấu hiệu sửa đơn nhưng cũng có đủ thông tin như một đơn mới: ưu tiên tìm đơn cũ để sửa trước; nếu không tìm thấy đơn cũ mới hỏi bác muốn tạo mới hay sửa. | ✓ |
| Hỏi người dùng bằng nút bấm | Hiện 2 nút bấm Inline ngay lập tức: [📦 Tạo đơn mới] hoặc [✏️ Sửa đơn có sẵn]. | |
| Bác quyết định giúp tôi | Claude tự quyết định luồng hợp lý nhất để người già không bị rối. | |

**User's choice:** Ưu tiên sửa nếu tìm thấy đơn (Recommended)
**Notes:** Tối giản nút bấm và thao tác của người dùng.

| Option | Description | Selected |
|--------|-------------|----------|
| Router hàm hợp nhất (Recommended) | Gộp kiểm tra thành 1 router thống nhất: classify_intent(text) -> CREATE \| SEARCH \| MUTATE. Code gọn gàng, tránh if-else chồng chéo trong ingest.py. | ✓ |
| Check tuần tự từng bước | Giữ nguyên check action_state -> check search_state -> check mutation_intent -> check search_intent -> tạo đơn. | |
| Bác quyết định giúp tôi | Claude tự tổ chức code kiến trúc chuẩn nhất. | |

**User's choice:** Router hàm hợp nhất (Recommended)
**Notes:** Cấu trúc module sạch, dễ mở rộng và kiểm thử độc lập.

| Option | Description | Selected |
|--------|-------------|----------|
| Prompt phân loại nhẹ (Recommended) | Gọi prompt phân loại siêu ngắn (10-20 token output, trả về nhãn intent). Nhanh, chuẩn xác khi câu chat ngắn hoặc dùng tiếng lóng. | ✓ |
| Chỉ regex, không gọi LLM router | Chỉ dựa vào regex từ khoá; nếu không khớp sửa hay tìm kiếm thì mặc định coi như tạo đơn mới. | |
| Bác quyết định giúp tôi | Claude tự cân đối độ trễ và chi phí token. | |

**User's choice:** Prompt phân loại nhẹ (Recommended)

| Option | Description | Selected |
|--------|-------------|----------|
| Tự bắt ID đơn khi Reply (Recommended) | Nếu người dùng Reply (trả lời) vào tin nhắn hiển thị đơn của bot: router tự động nhận diện là sửa chính đơn hàng đó mà không cần tìm kiếm lại theo từ khoá. | ✓ |
| Bỏ qua ngữ cảnh Reply | Vẫn chạy quy trình tìm kiếm đơn bình thường dựa vào nội dung tin nhắn, bỏ qua thông tin Reply. | |
| Bác quyết định giúp tôi | Claude tự quyết định phương án tiện nhất. | |

**User's choice:** Tự bắt ID đơn khi Reply (Recommended)
**Notes:** Cực kỳ tiện cho người dùng Telegram trên điện thoại.

| Option | Description | Selected |
|--------|-------------|----------|
| Fast-path không cần LLM (Recommended) | Nếu câu chat ngắn có cú pháp rõ ràng như 'huỷ đơn #12' hoặc 'đơn 12 đã giao': Router chuyển thẳng thành delta trạng thái không cần gọi LLM bóc tách, vẫn hiện thẻ xác nhận 1-chạm. | ✓ |
| Luôn qua LLM trích xuất | Mọi câu sửa đơn đều phải qua LLM trích xuất delta chuẩn hoá JSON, bất kể câu ngắn hay dài. | |
| Bác quyết định giúp tôi | Claude tự quyết định phương án tối ưu. | |

**User's choice:** Fast-path không cần LLM (Recommended)

---

## Phạm vi & Chọn đơn khớp

| Option | Description | Selected |
|--------|-------------|----------|
| Ưu tiên đơn đang active (Recommended) | Ưu tiên tìm các đơn đang active (CHO_LAM, DANG_LAM, DA_DONG_GOI, DA_TAO_DON, SHIPPER_DA_LAY). Nếu không thấy mới tìm trong đơn đã hoàn tất. | ✓ |
| Tìm trong tất cả trạng thái | Tìm trong toàn bộ đơn hàng bất kể trạng thái nào. | |
| Chặn sửa đơn đã hoàn tất | Chỉ cho phép tìm và sửa đơn đang active; cấm tuyệt đối sửa đơn đã giao hoặc đã huỷ. | |

**User's choice:** Ưu tiên đơn đang active (Recommended)

| Option | Description | Selected |
|--------|-------------|----------|
| Nút Inline 3-5 đơn gần nhất (Recommended) | Hiển thị tối đa 3-5 đơn gần nhất dưới dạng nút Inline 1-chạm: [Đơn #12 - Nam - 250k - Chờ làm]. | ✓ |
| In chi tiết từng đơn kèm nút | In chi tiết nội dung từng đơn thành tin nhắn dài kèm nút bấm số 1, 2, 3 bên dưới để chọn. | |
| Bác quyết định giúp tôi | Claude tự quyết định định dạng tối ưu cho người lớn tuổi. | |

**User's choice:** Nút Inline 3-5 đơn gần nhất (Recommended)

| Option | Description | Selected |
|--------|-------------|----------|
| Báo không thấy + gợi ý gửi SĐT (Recommended) | Thông báo nhẹ nhàng 'Không tìm thấy đơn hàng nào của [từ khoá]'. Kèm 1 nút [🔍 Tìm kiếm nâng cao] hoặc gợi ý gửi SĐT/mã đơn để bot tìm lại. Không tự động tạo đơn rác. | ✓ |
| Hỏi chuyển sang tạo đơn mới | Tự động hỏi: 'Bác có muốn tạo đơn mới cho thông tin này không?' kèm 2 nút [Tạo đơn mới] / [Bỏ qua]. | |
| Bác quyết định giúp tôi | Claude tự quyết định câu thoại thân thiện. | |

**User's choice:** Báo không thấy + gợi ý gửi SĐT (Recommended)

| Option | Description | Selected |
|--------|-------------|----------|
| Áp ngay delta đã bóc tách (Recommended) | Lưu sẵn delta đã trích xuất từ câu chat ban đầu vào user_data. Khi bấm chọn đơn, bot lập tức áp delta vào đơn đã chọn và hiện thẻ Diff Trước ➡️ Sau để xác nhận luôn. | ✓ |
| Gọi LLM bóc tách lại sau khi chọn | Khi bấm chọn đơn xong mới gọi LLM so khớp và bóc tách lại. | |
| Bác quyết định giúp tôi | Claude tự chọn luồng mượt nhất. | |

**User's choice:** Áp ngay delta đã bóc tách (Recommended)

---

## Giao diện Thẻ Diff Trước/Sau

| Option | Description | Selected |
|--------|-------------|----------|
| Chỉ hiện các trường thay đổi (Recommended) | Tiêu đề hiển thị [Mã đơn #12 - Khách: Nam], bên dưới chỉ liệt kê các trường có thay đổi dạng: '📍 Địa chỉ: [Cũ] ➡️ [Mới]'. Gọn gàng, tập trung đúng thông tin thay đổi. | ✓ |
| In toàn bộ đơn kèm highlight | In toàn bộ thẻ đơn hàng đầy đủ trong đó các trường thay đổi được bôi đậm kèm mũi tên ➡️. | |
| Bác quyết định giúp tôi | Claude tự thiết kế format thẻ trực quan nhất. | |

**User's choice:** Chỉ hiện các trường thay đổi (Recommended)

| Option | Description | Selected |
|--------|-------------|----------|
| Edit tin nhắn + gỡ nút (Recommended) | Khi bấm [❌ Huỷ] hoặc quá 120s: edit tin nhắn thành '❌ Đã huỷ yêu cầu sửa đơn' / '⏰ Đã hết hạn 120s' và gỡ bỏ toàn bộ nút bấm inline để tránh bấm nhầm lần 2. | ✓ |
| Xoá luôn tin nhắn thẻ | Xoá hẳn tin nhắn thẻ so sánh khỏi màn hình chat Telegram. | |
| Giữ nút + hiện Alert popup | Giữ nguyên tin nhắn và nút, khi bấm vào quá hạn thì hiện popup Alert báo 'Hết hạn'. | |

**User's choice:** Edit tin nhắn + gỡ nút (Recommended)

| Option | Description | Selected |
|--------|-------------|----------|
| Gợi ý theo vòng đời hợp lý (Recommended) | Dựa vào trạng thái hiện tại của đơn, chỉ gợi ý các bước kế tiếp hợp lý (ví dụ: đang DANG_LAM thì gợi ý DA_DONG_GOI, DA_TAO_DON, HUY_DON). Ít nút hơn (3-4 nút). | ✓ |
| Hiển thị đầy đủ tất cả trạng thái | Hiển thị bàn phím đầy đủ cả 7 trạng thái còn lại (chia 2 cột) để người dùng chọn bất kỳ trạng thái nào. | |
| Bác quyết định giúp tôi | Claude tự thiết kế bàn phím chuyển trạng thái hợp lý. | |

**User's choice:** Gợi ý theo vòng đời hợp lý (Recommended)

| Option | Description | Selected |
|--------|-------------|----------|
| Edit tin nhắn thành đơn mới (Recommended) | Sửa trực tiếp tin nhắn thẻ Diff thành thẻ đơn hàng hoàn tất đã cập nhật kèm thông báo '✅ Đã cập nhật thành công đơn #12!'. Kèm các nút hành động quen thuộc. | ✓ |
| Gửi tin nhắn mới tách biệt | Gửi tin nhắn mới tinh thông báo thành công + in thẻ đơn hàng mới, giữ nguyên tin nhắn diff phía trên làm lịch sử. | |
| Bác quyết định giúp tôi | Claude tự quyết định luồng giao diện gọn gàng nhất. | |

**User's choice:** Edit tin nhắn thành đơn mới (Recommended)

---

## Xung đột khóa lạc quan

| Option | Description | Selected |
|--------|-------------|----------|
| WHERE id + updated_at (Recommended) | Dùng WHERE id = ? AND updated_at = ?. Tận dụng cột updated_at sẵn có, không cần sửa schema DB hay migration, kiểm tra khớp mili-giây thời điểm đọc. | ✓ |
| Thêm cột version INT | Thêm cột version INT tăng dần (version = version + 1). | |
| Bác quyết định giúp tôi | Claude tự chọn giải pháp đơn giản và an toàn nhất. | |

**User's choice:** WHERE id + updated_at (Recommended) ("cách nào tối ưu thì chọn")
**Notes:** Tối ưu hiệu năng, không cần thêm cột, chuẩn atomic SQL.

| Option | Description | Selected |
|--------|-------------|----------|
| Bảng order_history riêng (Recommended) | Tạo bảng order_history (order_id, user_id, user_name, changes_json, created_at) và cột created_by_user_id trong orders. Khi xung đột: đọc bản ghi mới nhất để báo '⚠️ [Tên] vừa sửa [Nội dung] lúc [Giờ]!'. | ✓ |
| Lưu text vào cột notes | Lưu dạng chuỗi text tóm tắt lịch sử vào cột notes hoặc audit_log của bảng orders. | |
| Bác quyết định giúp tôi | Claude tự tối ưu cấu trúc dữ liệu theo chuẩn SQL. | |

**User's choice:** Bảng order_history riêng (Recommended)
**Notes:** User yêu cầu: "lưu người tạo đơn và lịch sử sửa đơn, khi có xung đột, báo rõ ai vừa sửa, và sửa nội dung gì".

| Option | Description | Selected |
|--------|-------------|----------|
| Hiện đơn mới + dừng thao tác cũ (Recommended) | Hiện thông báo xung đột kèm thẻ chi tiết đơn mới nhất (kèm các nút thao tác). Bác xem xong nếu vẫn muốn sửa thì nhắn tiếp hoặc bấm nút. Tránh áp nhầm dữ liệu đè lên thay đổi của người khác. | ✓ |
| Tự tạo thẻ Diff mới ngay | Tự động tạo thẻ Diff mới áp đè các trường bác muốn sửa lên đơn vừa đổi để bác bấm xác nhận lại luôn. | |
| Bác quyết định giúp tôi | Claude tự cân nhắc độ an toàn. | |

**User's choice:** Hiện đơn mới + dừng thao tác cũ (Recommended)

---

## Claude's Discretion

- Format chi tiết của thông báo xung đột và thẻ thông tin lỗi.
- Pydantic schema validation cho payload trích xuất delta từ LLM.
- Tên và cú pháp của câu lệnh SQL migration cho `order_history`.

## Deferred Ideas

None — discussion stayed within phase scope.
