# Phase 3: Ergonomic Order Management & Low-Tech Actions - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-10-24
**Phase:** 3-Ergonomic Order Management & Low-Tech Actions
**Areas discussed:** Menu & Danh sách đơn, Thẻ chi tiết & Đổi trạng thái, Mã vận đơn & Quản lý ảnh

---

## Menu & Danh sách đơn

### 1. Bố cục Reply Keyboard cố định dưới khung chat
| Option | Description | Selected |
|--------|-------------|----------|
| Lưới 2x2 nút to | Hàng 1: [📦 Đơn hôm nay] [📋 Xem theo ngày] \| Hàng 2: [📝 Nhập đơn mới] [❓ Trợ giúp]. Nút to, rõ nghĩa, không phải gõ lệnh slash. | ✓ |
| Cột dọc 4 nút | 4 nút dọc từ trên xuống dưới, chiếm nhiều không gian bàn phím hơn. | |
| Hàng 3 nút + 1 nút | 3 nút hàng đầu, 1 nút hàng dưới. | |

**User's choice:** Lưới 2x2 nút to (Recommended)

### 2. Chọn ngày khi bấm 'Xem theo ngày'
| Option | Description | Selected |
|--------|-------------|----------|
| Nút chọn nhanh 3-5 ngày gần nhất | Hiển thị nút Inline: [Hôm nay] [Hôm qua] [Chọn ngày khác]. Bấm 'Chọn ngày khác' bot hiện các ngày gần nhất (3-5 ngày gần đây) dạng nút để chạm chọn luôn. | ✓ |
| Yêu cầu gõ text DD/MM/YYYY | Bấm 'Chọn ngày khác' rồi yêu cầu người dùng gõ text ngày theo định dạng DD/MM/YYYY. | |
| Inline Calendar tháng | Gửi lịch tương tác dạng Inline Calendar (phức tạp hơn cho người lớn tuổi). | |

**User's choice:** Nút chọn nhanh 3-5 ngày gần nhất (Recommended)

### 3. Phân trang danh sách đơn theo ngày
| Option | Description | Selected |
|--------|-------------|----------|
| 5 đơn/trang kèm nút xem chi tiết | Mỗi trang 5 đơn. Mỗi đơn 2-3 dòng (Mã, tên khách, tổng tiền, trạng thái) kèm 1 nút Inline [Xem đơn #ID] ngay dưới để chạm mở chi tiết. Cuối danh sách có nút [⬅️ Trước] [Trang X/Y] [Sau ➡️]. | ✓ |
| Hiển thị hết vào 1 tin nhắn | Liệt kê tất cả đơn trong 1 tin nhắn dài (không phân trang), nếu nhiều đơn người già cuộn màn hình sẽ mỏi tay. | |
| 10 đơn/trang danh sách tóm tắt | Mỗi trang 10 đơn gọn gàng chỉ có mã và tên khách, ít chi tiết hơn. | |

**User's choice:** 5 đơn/trang kèm nút xem chi tiết (Recommended)

### 4. Xử lý khi ngày không có đơn hàng
| Option | Description | Selected |
|--------|-------------|----------|
| Báo trống + Nút nhập đơn mới | Gửi tin nhắn thông báo nhẹ nhàng: 'Ngày này chưa có đơn hàng nào bác nhé!' kèm nút bấm nhanh [📝 Nhập đơn mới]. | ✓ |
| Chỉ gửi text thông báo | Chỉ gửi tin nhắn thông báo 'Chưa có đơn hàng nào.' không kèm nút bấm. | |

**User's choice:** Báo trống + Nút nhập đơn mới (Recommended)

---

## Thẻ chi tiết & Đổi trạng thái

### 1. Cơ chế 1-chạm sao chép SĐT, Địa chỉ, Mã vận đơn
| Option | Description | Selected |
|--------|-------------|----------|
| Kết hợp code mono + CopyTextButton | Trong text dùng thẻ HTML <code> (chạm vào copy ngay trên Telegram điện thoại) KÈM nút Inline CopyTextButton ở dưới cho người dùng thích bấm nút. | ✓ |
| Chỉ dùng nút Inline CopyTextButton | Chỉ dùng nút Inline CopyTextButton dưới thẻ đơn hàng. | |
| Chỉ dùng code mono trong text | Chỉ bọc trong thẻ <code>, không thêm nút Inline copy riêng. | |

**User's choice:** Kết hợp code mono + CopyTextButton (Recommended)

### 2. Giao diện các nút bấm đổi trạng thái đơn
| Option | Description | Selected |
|--------|-------------|----------|
| Nút bước tiếp theo + Nút mở rộng | Hiển thị 1 nút to gợi ý bước tiếp theo (VD: đang 'Chờ làm' -> nút [▶️ Bắt đầu làm]), KÈM 1 nút [🔄 Đổi trạng thái khác] mở ra danh sách đầy đủ. | ✓ |
| Hiển thị tất cả 8 nút cùng lúc | Hiển thị luôn tất cả 7-8 nút trạng thái dưới thẻ chi tiết. | |
| Chỉ chuyển tiếp tuần tự 1 bước | Chỉ cho phép chuyển tiếp tuần tự từng bước một, không cho nhảy cóc trạng thái. | |

**User's choice:** Nút bước tiếp theo + Nút mở rộng (Recommended)

### 3. Xác nhận khi đổi sang trạng thái nhạy cảm (Huỷ đơn / Bom hàng)
| Option | Description | Selected |
|--------|-------------|----------|
| Chỉ confirm khi Huỷ/Bom | Chỉ hỏi xác nhận khi bấm vào trạng thái nhạy cảm (Huỷ đơn, Bom hàng) kèm 2 nút [Đồng ý] / [Quay lại]. Các trạng thái thông thường thì đổi ngay 1 chạm không cần hỏi lại. | ✓ |
| Luôn hỏi xác nhận mọi trạng thái | Bất kỳ trạng thái nào cũng hiện popup hỏi xác nhận trước khi đổi. | |
| Đổi ngay không hỏi lại | Không hỏi lại bước nào, bấm là đổi ngay lập tức. | |

**User's choice:** Chỉ confirm khi Huỷ/Bom (Recommended)

### 4. Phản hồi khi đổi trạng thái thành công
| Option | Description | Selected |
|--------|-------------|----------|
| Edit tin nhắn cũ + Popup alert | Cập nhật trực tiếp tin nhắn thẻ hiện tại (edit_message_text) kèm popup Telegram alert nhỏ '✅ Đã đổi sang [Trạng thái]', tránh gửi thêm tin nhắn mới làm rác màn hình. | ✓ |
| Gửi tin nhắn mới riêng biệt | Gửi một tin nhắn thông báo mới dưới khung chat. | |
| Chỉ edit tin nhắn cũ | Chỉ edit tin nhắn cũ, không hiện popup thông báo gì thêm. | |

**User's choice:** Edit tin nhắn cũ + Popup alert (Recommended)

---

## Mã vận đơn & Quản lý ảnh

### 1. Quy trình nhập mã vận đơn cho đơn hàng
| Option | Description | Selected |
|--------|-------------|----------|
| Nút bấm kích hoạt nhập text/ảnh | Trên thẻ chi tiết có nút [🚚 Nhập/Đổi mã vận đơn] -> Bot hiển thị tin nhắn hướng dẫn kèm nút [❌ Huỷ] -> Người dùng gửi tin nhắn text mã vận đơn hoặc dán ảnh hoá đơn ship -> Bot lưu và cập nhật thẻ. | ✓ |
| Dùng lệnh slash /mvd | Dùng cú pháp gõ lệnh chat (VD: /mvd 12 GHTK123456). | |
| Tự động đoán mã vận đơn từ chat tự do | Tự động bóc tách mã vận đơn nếu người dùng chat mã bất kỳ vào nhóm. | |

**User's choice:** Nút bấm kích hoạt nhập text/ảnh (Recommended)

### 2. Xem lại ảnh đính kèm của đơn hàng
| Option | Description | Selected |
|--------|-------------|----------|
| Nút xem Album ảnh send_media_group | Thẻ chi tiết hiển thị dòng: '📷 Ảnh đính kèm: 3 ảnh' kèm nút Inline [🖼️ Xem 3 ảnh]. Bấm nút, bot gửi Album ảnh (send_media_group) bằng file_id đã lưu kèm nút [Quay lại thẻ đơn]. | ✓ |
| Gửi từng ảnh riêng lẻ | Gửi từng ảnh một thành nhiều tin nhắn riêng lẻ dưới khung chat. | |
| Luôn hiện sẵn ảnh kèm thẻ chi tiết | Luôn gửi ảnh đính kèm cùng với thẻ chi tiết. | |

**User's choice:** Nút xem Album ảnh send_media_group (Recommended)

### 3. Bổ sung thêm ảnh cho đơn hàng đã lưu
| Option | Description | Selected |
|--------|-------------|----------|
| Nút kích hoạt gửi thêm ảnh | Bấm nút [➕ Gửi thêm ảnh] trên thẻ đơn -> Bot nhắc 'Bác gửi ảnh chụp cho đơn này nhé' -> Người dùng gửi 1 hoặc nhiều ảnh -> Bot lưu thêm file_id vào DB và báo thành công. | ✓ |
| Không cho thêm ảnh sau khi tạo đơn | Chỉ cho phép thêm ảnh lúc tạo đơn ban đầu, không cho bổ sung sau khi đơn đã lưu. | |

**User's choice:** Nút kích hoạt gửi thêm ảnh (Recommended)

### 4. Tránh kẹt bot khi đang ở trạng thái chờ nhập mã hoặc gửi ảnh
| Option | Description | Selected |
|--------|-------------|----------|
| Nút Huỷ + Tự hết hạn sau 2 phút | Luôn có nút Inline [❌ Huỷ bỏ thao tác] trong tin nhắn chờ để người dùng bấm huỷ quay lại bất cứ lúc nào, đồng thời tự động hết hạn sau 2 phút nếu không có thao tác. | ✓ |
| Gõ text để huỷ | Chỉ cho huỷ khi gõ chữ 'huy' hoặc lệnh /cancel. | |
| Chờ vĩnh viễn không timeout | Không có timeout, chờ vĩnh viễn cho đến khi người dùng gửi tin nhắn mới. | |

**User's choice:** Nút Huỷ + Tự hết hạn sau 2 phút (Recommended)

---

## Claude's Discretion
- Định dạng thẻ chi tiết đơn hàng trực quan với các emoji rõ ràng, thoáng mắt.
- Mapping 8 trạng thái `OrderStatus` sang các nhãn tiếng Việt gần gũi.

## Deferred Ideas
- Tìm kiếm/tra cứu đơn hàng và điều hướng bằng câu chat tự nhiên tiếng Việt (VD: *"xem chi tiết đơn của anh Tuấn ở Hà Nội"* hoặc *"thêm ảnh cho đơn anh Tuấn"*): Chuyển sang **Phase 4: Natural Language Order Search** theo đúng phạm vi roadmap.
