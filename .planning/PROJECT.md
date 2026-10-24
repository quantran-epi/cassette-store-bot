# Cassette Store Telegram Chatbot

## What This Is

Chatbot Telegram phục vụ quản lý đơn hàng và khách hàng cho shop bán băng cassette. Hệ thống được thiết kế đặc thù cho người dùng lớn tuổi, low-tech, thao tác chủ yếu qua Inline Keyboard Buttons một chạm và nhập liệu dạng free-text chat tự nhiên được bóc tách bằng LLM.

## Core Value

Người lớn tuổi nhập tự do một đoạn tin nhắn đặt hàng bất kỳ qua Telegram, bot dùng LLM tự bóc tách chính xác thông tin (khách, hàng hoá, tiền COD, hình thức), hiển thị nút bấm xác nhận trực quan và lưu trữ an toàn vào DB mà không cần thao tác biểu mẫu phức tạp.

## Requirements

### Validated

(None yet — ship to validate)

### Active

- [ ] Lưu trữ và quản lý thông tin khách hàng: tên, nhiều số điện thoại, nhiều địa chỉ, ghi chú.
- [ ] Lưu trữ và quản lý đơn hàng: tham chiếu khách hàng, chi tiết hàng hoá (dạng text tự do ghi tên các cuốn cassette, số lượng, giá), tổng tiền thu khách, tiền COD, hình thức (chuyển khoản trước / COD), mã vận đơn đơn vị vận chuyển.
- [ ] Lưu trữ và hiển thị ảnh đơn hàng (1 hoặc nhiều ảnh, lưu trữ qua mã file_id Telegram).
- [ ] Quản lý trạng thái đơn hàng vòng đời đầy đủ: Chờ làm -> Đang làm -> Đã đóng gói -> Đã tạo đơn trên app vận chuyển -> Shipper đã lấy hàng -> Đã giao thành công / Bom hàng / Huỷ đơn.
- [ ] Bóc tách tin nhắn đơn hàng bằng LLM (qua 9router / OpenAI-compatible API): nhận free-text tiếng Việt, extract thông tin có cấu trúc, trả về kèm Inline Keyboard "Xác nhận / Huỷ", lưu DB và thông báo sau xác nhận.
- [ ] Tập lệnh quản trị nhanh thân thiện với người lớn tuổi: đổi trạng thái đơn, đánh dấu đã giao, xem danh sách đơn theo ngày (hôm nay, hôm qua, ngày cụ thể).
- [ ] Cập nhật mã vận đơn cho đơn hàng cụ thể kèm xác nhận.
- [ ] Xem chi tiết đơn hàng kèm các inline button sao chép nhanh 1 chạm (sao chép mã vận đơn, số điện thoại, địa chỉ nhận hàng).
- [ ] Tra cứu/tìm kiếm đơn hàng bằng ngôn ngữ tự nhiên: người dùng chat free-text mô tả đơn cần xem, bot dùng LLM tìm trong DB, hỏi xác nhận trước khi hiển thị chi tiết hoặc thao tác.
- [ ] Cấu hình model LLM linh hoạt trong settings/config local (hỗ trợ đổi model trên 9router endpoint).
- [ ] Giới hạn quyền truy cập bot qua Telegram User ID whitelist (bảo mật riêng tư cho chủ shop).

### Out of Scope

- Đồng bộ API trực tiếp hai chiều với các đơn vị vận chuyển (GHTK, GHN, ViettelPost) — Người dùng tự tạo đơn trên app ngoài và dán mã vận đơn vào bot để giữ quy trình đơn giản.
- Quản lý kho, tồn kho chi tiết theo từng mã vạch băng cassette — Chỉ lưu tên hàng hoá tự do trong đơn, tránh phức tạp hoá việc kiểm kho.
- Giao diện web dashboard — Chỉ tập trung 100% trải nghiệm Telegram bot cho người low-tech.
- Cổng thanh toán trực tuyến tự động — Chỉ ghi nhận chuyển khoản trước hoặc COD thủ công.

## Context

- Khách hàng mua cassette thường chốt đơn qua inbox/Zalo/Facebook bằng tin nhắn văn bản không theo khuôn mẫu chuẩn.
- Người vận hành shop là người lớn tuổi, ngại dùng các app bán hàng phức tạp nhiều bước, quen dùng Telegram.
- Inline keyboard buttons với emoji rõ ràng, chữ to, văn phong tiếng Việt dễ hiểu là cốt lõi của UX.

## Constraints

- **Tech stack**: Python + SQLite (sqlite3) + python-telegram-bot (v20+ async).
- **LLM Gateway**: 9router (OpenAI-compatible protocol), cho phép cấu hình URL, API Key và Model ID trong local settings.
- **Bảo mật**: Whitelist Telegram User IDs — từ chối tương tác từ người lạ.
- **UX**: Tối đa nút bấm Inline, tối thiểu việc gõ phím cấu trúc/lệnh dài dòng; mọi hành động nhạy cảm đều phải có bước hỏi lại để confirm.

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| Python + SQLite | Nhẹ, chạy local hoặc VPS nhỏ không cần cài đặt DB phức tạp, dễ backup file .db | — Pending |
| Hàng hoá dạng free-text trong đơn | Đúng nhu cầu thực tế của shop cassette, không bắt tạo mã sản phẩm rườm rà | — Pending |
| 9router làm gateway LLM | Tương thích chuẩn OpenAI API, dễ dàng chuyển đổi linh hoạt giữa các model qua settings | — Pending |
| Whitelist Telegram User ID | Bot nội bộ cho người nhà/chủ shop, ngăn chặn người lạ truy cập dữ liệu khách hàng | — Pending |

## Evolution

This document evolves at phase transitions and milestone boundaries.

**After each phase transition** (via `/gsd-transition`):
1. Requirements invalidated? → Move to Out of Scope with reason
2. Requirements validated? → Move to Validated with phase reference
3. New requirements emerged? → Add to Active
4. Decisions to log? → Add to Key Decisions
5. "What This Is" still accurate? → Update if drifted

**After each milestone** (via `/gsd-complete-milestone`):
1. Full review of all sections
2. Core Value check — still the right priority?
3. Audit Out of Scope — reasons still valid?
4. Update Context with current state

---
*Last updated: 2026-10-24 after initialization*
