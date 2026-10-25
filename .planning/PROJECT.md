# Cassette Store Telegram Chatbot

## What This Is

Chatbot Telegram phục vụ quản lý đơn hàng và khách hàng cho shop bán băng cassette. Hệ thống được thiết kế đặc thù cho người dùng lớn tuổi, low-tech, thao tác chủ yếu qua Inline Keyboard Buttons một chạm và nhập liệu dạng free-text chat tự nhiên được bóc tách bằng LLM.

## Core Value

Người lớn tuổi nhập tự do một đoạn tin nhắn đặt hàng bất kỳ qua Telegram, bot dùng LLM tự bóc tách chính xác thông tin (khách, hàng hoá, tiền COD, hình thức), hiển thị nút bấm xác nhận trực quan và lưu trữ an toàn vào DB mà không cần thao tác biểu mẫu phức tạp.

## Current Milestone: v1.1 NL Order Mutation, Console Admin, Phân quyền & GitHub Backup

**Goal:** Mở rộng bot với khả năng chỉnh sửa đơn hàng bằng ngôn ngữ tự nhiên (NL mutation), cung cấp console quản trị tại server, phân quyền Admin đa tầng trên Telegram và backup dữ liệu tự động lên GitHub.

**Target features:**
- Natural language order mutation: Đổi trạng thái, gán mã vận đơn, sửa ghi chú, sửa COD/giá tiền, đổi sđt/địa chỉ bằng tin nhắn chat tự nhiên kèm thẻ xác nhận 2-phase.
- Interactive Console App tại server: CLI menu tương tác quản lý bot, xem trạng thái, quản lý whitelist và chạy backup thủ công.
- Phân quyền Admin đa tầng (Super Admin vs Admin): Cấu hình Super Admin toàn quyền, Admin vận hành (không có quyền phân quyền), bộ lệnh Telegram cho Admin tương đương console.
- Backup dữ liệu lên GitHub: Tự động sao lưu định kỳ file SQLite DB lên GitHub repo và hỗ trợ kích hoạt thủ công từ Console/Telegram.

## Current State

Tất cả 4/4 phases trong Milestone v1.0 hoàn thành:
- Phase 01: Nền tảng, SQLite WAL persistence & Bảo mật Whitelist
- Phase 02: Bóc tách đơn hàng bằng LLM & Xác nhận tương tác
- Phase 03: Quản trị đơn hàng công thái học, nút sao chép 1-chạm & Cập nhật mã vận đơn
- Phase 04: Tra cứu và tìm kiếm đơn hàng bằng ngôn ngữ tự nhiên (Natural language order search, thống kê doanh thu, phân trang, unaccent tiếng Việt)

## Requirements

### Validated

- [x] Cấu hình model LLM và environment linh hoạt trong settings/config local qua Pydantic-Settings v2 (CFG-01). *Validated in Phase 01: foundation-persistence-security-whitelist*
- [x] Giới hạn quyền truy cập bot qua Telegram User ID whitelist ở Handler Group -1 chặn triệt để người lạ (SEC-01). *Validated in Phase 01: foundation-persistence-security-whitelist*
- [x] Lưu trữ và quản lý thông tin khách hàng: tên, nhiều số điện thoại, nhiều địa chỉ, ghi chú (DATA-01). *Validated in Phase 01: foundation-persistence-security-whitelist*
- [x] Lưu trữ thông tin đơn hàng với customer snapshot (tên, sđt, địa chỉ tại thời điểm đặt hàng) (DATA-02). *Validated in Phase 01: foundation-persistence-security-whitelist*
- [x] Quản lý trạng thái đơn hàng vòng đời 8 trạng thái (DRAFT -> COMPLETED) qua database CHECK constraints (DATA-03). *Validated in Phase 01: foundation-persistence-security-whitelist*
- [x] Lưu trữ danh sách Telegram photo file_ids dạng JSON array trong đơn hàng (DATA-04). *Validated in Phase 01: foundation-persistence-security-whitelist*
- [x] Bóc tách tin nhắn đơn hàng bằng LLM (qua 9router / OpenAI-compatible API): nhận free-text tiếng Việt, extract thông tin có cấu trúc, trả về kèm Inline Keyboard "Xác nhận / Huỷ", lưu DB và thông báo sau xác nhận. *Validated in Phase 02: llm-ingestion-interactive-confirmation*
- [x] Tập lệnh quản trị nhanh thân thiện với người lớn tuổi: đổi trạng thái đơn, đánh dấu đã giao, xem danh sách đơn theo ngày (hôm nay, hôm qua, ngày cụ thể). *Validated in Phase 03: ergonomic-order-management-low-tech-actions*
- [x] Cập nhật mã vận đơn cho đơn hàng cụ thể kèm xác nhận. *Validated in Phase 03: ergonomic-order-management-low-tech-actions*
- [x] Xem chi tiết đơn hàng kèm các inline button sao chép nhanh 1 chạm (sao chép mã vận đơn, số điện thoại, địa chỉ nhận hàng). *Validated in Phase 03: ergonomic-order-management-low-tech-actions*
- [x] Tra cứu/tìm kiếm đơn hàng bằng ngôn ngữ tự nhiên: người dùng chat free-text mô tả đơn cần xem, bot dùng LLM tìm trong DB, hỏi xác nhận trước khi hiển thị chi tiết hoặc thao tác. *Validated in Phase 04: natural-language-order-search*

### Active

- [ ] Bóc tách intent chỉnh sửa đơn hàng bằng ngôn ngữ tự nhiên: tìm đơn, hiển thị thẻ so sánh Trước/Sau và yêu cầu xác nhận 1-chạm trước khi thực thi
- [ ] Chỉnh sửa trạng thái đơn hàng qua chat tự nhiên (tự suy luận trạng thái đích hoặc hiển thị nút trạng thái gợi ý)
- [ ] Cập nhật mã vận đơn, ghi chú, tiền COD/tổng giá, và địa chỉ/sđt nhận hàng qua chat tự nhiên
- [ ] Interactive Console App trên terminal server cho phép quản lý cấu hình, whitelist và vận hành bot trực tiếp
- [ ] Phân quyền đa tầng Super Admin (toàn quyền) và Admin (quản trị vận hành, không can thiệp phân quyền)
- [ ] Bộ lệnh quản trị Telegram dành riêng cho Admin tương đương tính năng Console
- [ ] Sao lưu cơ sở dữ liệu SQLite định kỳ tự động lên GitHub repository
- [ ] Kích hoạt sao lưu dữ liệu thủ công tức thì qua Console và Telegram Admin*

### Out of Scope

- Đồng bộ API trực tiếp hai chiều với các đơn vị vận chuyển (GHTK, GHN, ViettelPost) — Người dùng tự tạo đơn trên app ngoài và dán mã vận đơn vào bot để giữ quy trình đơn giản.
- Quản lý kho, tồn kho chi tiết theo từng mã vạch băng cassette — Chỉ lưu tên hàng hoá tự do trong đơn, tránh phức tạp hoá việc kiểm kho.
- Giao diện web dashboard — Chỉ tập trung 100% trải nghiệm Telegram bot cho người low-tech.
- Cổng thanh toán trực tuyến tự động — Chỉ ghi nhận chuyển khoản trước hoặc COD thủ công.

## Context

- Shipped v1.0 MVP with 7,134 LOC Python across 4 phases and 11 plans. 110 automated tests passing. Zero external dashboard, 100% in Telegram via async python-telegram-bot, aiosqlite (WAL), and 9router LLM gateway.
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
| Python + SQLite | Nhẹ, chạy local hoặc VPS nhỏ không cần cài đặt DB phức tạp, dễ backup file .db | Validated in Phase 01 |
| Hàng hoá dạng free-text trong đơn | Đúng nhu cầu thực tế của shop cassette, không bắt tạo mã sản phẩm rườm rà | Validated in Phase 01 |
| 9router làm gateway LLM | Tương thích chuẩn OpenAI API, dễ dàng chuyển đổi linh hoạt giữa các model qua settings | Validated in Phase 01 |
| Whitelist Telegram User ID | Bot nội bộ cho người nhà/chủ shop, ngăn chặn người lạ truy cập dữ liệu khách hàng | Validated in Phase 01 |
| 2-tier LLM parsing (parse + json_object) | Chống crash 400 trên 9router khi đổi model | Validated in Phase 02 |
| In-memory draft orders trước khi lưu DB | Tránh ghi rác vào SQLite khi người dùng bấm huỷ | Validated in Phase 02 |
| Cảnh báo khách bom hàng & gợi ý đổi địa chỉ | Giúp chủ shop lớn tuổi nhận diện rủi ro và chọn địa chỉ nhanh | Validated in Phase 02 |
| Phím tắt 2x2 Reply Keyboard & CopyTextButton | Tối đa thao tác một chạm trên điện thoại cho người già | Validated in Phase 03 |
| Unaccent function SQLite & Conversation 2-phase | Tìm kiếm linh hoạt tiếng Việt không dấu, xác nhận trước khi thao tác đơn hàng | Validated in Phase 04 |

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
*Last updated: 2026-10-25 after milestone v1.1 initialization*
