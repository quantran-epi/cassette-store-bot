# Phase 2: LLM Ingestion & Interactive Confirmation - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-10-24
**Phase:** 2-LLM Ingestion & Interactive Confirmation
**Areas discussed:** Xử lý thiếu thông tin & tin nhắn rác, Định dạng thẻ xem trước (Preview Card), Trạng thái lưu tạm & Quản lý tương tác, Khớp khách hàng cũ & Multi-address, Xử lý ảnh đính kèm & lỗi kết nối LLM

---

## Xử lý thiếu thông tin & Tin nhắn rác

| Option | Description | Selected |
|--------|-------------|----------|
| Linh hoạt: Chỉ cần SĐT | Chỉ cần có SĐT và hàng hoá (hoặc giá tiền) là hiện preview card, trường nào thiếu bot đánh dấu [Chưa có] và vẫn cho xác nhận lưu | ✓ (Custom feedback) |
| Nghiêm ngặt: Đủ 4 trường | Bắt buộc phải bóc tách đủ 4 trường: Tên, SĐT, Địa chỉ, Danh sách hàng | |
| Tuỳ bạn quyết định | Claude tự quyết định | |

**User's choice:** sđt là key, chỉ cần sđt, vì khách quen đã có thông tin khác rồi, nếu là khách quen, phải báo cho người dùng biết khi tạo đơn, kèm tóm tắt thông tin lịch sử mua hàng của khách, bao nhiêu đơn, bao nhiêu tiền, có bom hàng hay không.
**Notes:** SĐT là trường bắt buộc duy nhất để tạo đơn. Nếu là khách quen thì phải hiển thị tóm tắt lịch sử đơn hàng và cảnh báo bom hàng nếu có.

---

## Phản hồi tin nhắn không phải đơn hàng

| Option | Description | Selected |
|--------|-------------|----------|
| Nhắc nhẹ nhàng | Báo nhẹ nhàng: "Em không nhận diện được đơn hàng từ tin nhắn này. Bác vui lòng gửi lại tin nhắn có số điện thoại khách nhé!" | ✓ |
| Im lặng bỏ qua | Không phản hồi gì cả | |
| Tuỳ bạn quyết định | Claude tự quyết định | |

**User's choice:** Nhắc nhẹ nhàng (Recommended)
**Notes:** Giúp người lớn tuổi hiểu cách thao tác nếu bot không nhận diện được.

---

## Định dạng thẻ xem trước (Preview Card)

| Option | Description | Selected |
|--------|-------------|----------|
| Phân tách Tổng & COD | Hiển thị rõ ràng cả 2 dòng: "Tổng đơn: 250.000đ" và "Tiền COD thu khách: 200.000đ (đã cọc 50.000đ)" | ✓ |
| Gọn 1 dòng COD | Chỉ hiển thị dòng "Tiền thu (COD): 250.000đ" | |

**User's choice:** Phân tách Tổng & COD (Recommended)
**Notes:** Tránh nhầm lẫn giữa tổng đơn và tiền COD thực tế cần thu sau khi đã cọc.

---

## Bộ nút bấm Inline Keyboard dưới thẻ xem trước

| Option | Description | Selected |
|--------|-------------|----------|
| 2 nút: Xác nhận & Huỷ | [✅ Xác nhận lưu] và [❌ Huỷ bỏ] trên 1 hàng | ✓ |
| 3 nút: Xác nhận, Sửa, Huỷ | Thêm nút [✏️ Sửa nhanh] | |

**User's choice:** 2 nút: Xác nhận & Huỷ (Recommended)
**Notes:** Tối giản cho người lớn tuổi; nếu sai người dùng gửi lại tin nhắn sửa.

---

## Cơ chế lưu trữ đơn tạm thời

| Option | Description | Selected |
|--------|-------------|----------|
| In-memory user_data | Lưu trong context.user_data với draft_id, callback ord:confirm:<draft_id> | ✓ |
| Lưu DB bảng orders (DRAFT) | Lưu DB trực tiếp với status DRAFT | |

**User's choice:** In-memory user_data (Recommended)
**Notes:** Tránh rác DB khi người dùng huỷ hoặc thử nghiệm.

---

## Quản lý tin nhắn dồn liên tục

| Option | Description | Selected |
|--------|-------------|----------|
| Đa đơn độc lập | Mỗi tin nhắn sinh draft_id riêng, xác nhận độc lập | ✓ |
| Chỉ giữ 1 đơn mới nhất | Đơn mới ghi đè đơn cũ | |

**User's choice:** Đa đơn độc lập (Recommended)
**Notes:** Cho phép paste nhiều đơn liên tiếp từ Zalo/Facebook và bấm duyệt từng đơn.

---

## Xử lý địa chỉ mới của khách quen

| Option | Description | Selected |
|--------|-------------|----------|
| Thêm vào danh sách | Tự động thêm vào addresses của khách và snapshot vào đơn | ✓ |
| Hỏi xác nhận cập nhật | Hỏi người dùng có lưu không | |
| Chỉ lưu vào đơn | Chỉ snapshot vào đơn | |

**User's choice:** Thêm vào danh sách (Recommended)
**Notes:** Tiện lợi, không bắt người dùng bấm thêm nút xác nhận lưu địa chỉ.

---

## Khách quen không nhắn địa chỉ

| Option | Description | Selected |
|--------|-------------|----------|
| Tự điền địa chỉ gần nhất | Tự động lấy địa chỉ gần nhất điền vào đơn | ✓ (Custom feedback) |
| Để trống | Để trống [Chưa có địa chỉ] | |

**User's choice:** chọn recommended, nhưng nếu khách có 2 địa chỉ, phải prompt hỏi người dùng chọn.
**Notes:** Nếu chỉ có 1 địa chỉ cũ thì tự điền. Nếu có từ 2 địa chỉ trở lên thì prompt nút bấm để người dùng chọn địa chỉ nào sẽ dùng cho đơn này.

---

## Xử lý ảnh đính kèm (Photo Ingestion)

| Option | Description | Selected |
|--------|-------------|----------|
| Bóc tách caption + gắn ảnh | Bóc tách caption như text thường, lưu telegram photo file_id vào đơn nháp | ✓ |
| Để Phase 3 xử lý ảnh | Chỉ làm text ở Phase 2 | |

**User's choice:** Bóc tách caption + gắn ảnh (Recommended)
**Notes:** Hỗ trợ trực tiếp ảnh bìa cassette gửi kèm thông tin đơn hàng.

---

## Xử lý lỗi Gateway LLM (9router)

| Option | Description | Selected |
|--------|-------------|----------|
| Báo bận & thử lại | Báo nhẹ nhàng: "⚠️ Hệ thống bóc tách đang bận... Bác thử lại sau nhé!" | ✓ |
| Im lặng | Không phản hồi | |

**User's choice:** Báo bận & thử lại (Recommended)
**Notes:** Luôn phản hồi lịch sự để người lớn tuổi biết trạng thái.

---

## Claude's Discretion

- Thiết kế prompt tiếng Việt trích xuất và chuẩn hoá đơn vị tiền tệ VNĐ.
- 2-tier fallback cho OpenAI structured outputs (parse fallback to json_object).
- Chi tiết format và emoji thẻ preview card.

## Deferred Ideas

- Đổi trạng thái vòng đời đơn hàng và nút copy 1 chạm: Phase 3.
- Tra cứu đơn hàng bằng câu hỏi tự nhiên: Phase 4.
