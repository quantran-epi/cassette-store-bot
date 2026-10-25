# Project Retrospective

*A living document updated after each milestone. Lessons feed forward into future planning.*

## Milestone: v1.0 — MVP

**Shipped:** 2026-10-25
**Phases:** 4 | **Plans:** 11 | **Tasks:** 0 | **Commits:** 128

### What Was Built
- Nền tảng SQLite async (aiosqlite) với WAL mode, cấu hình Pydantic-Settings v2 và Telegram User ID whitelist security gate tại Group -1.
- Ingestion pipeline bóc tách tin nhắn tiếng Việt tự do qua 9router gateway (OpenAI-compatible) với 2-tier fallback, chuẩn hoá tiền tệ VNĐ, thẻ xem trước trực quan và xác nhận 2 pha.
- Customer intelligence: lưu trữ lịch sử khách hàng, mảng SĐT/địa chỉ JSON, phát hiện bom hàng, và xử lý ảnh độ phân giải cao kèm album debounce buffer (500ms).
- UI/UX công thái học cho người lớn tuổi: bàn phím Reply Keyboard 2x2 cố định, lọc đơn theo ngày UTC+7, nút Copy 1 chạm (`CopyTextButton`), chuyển trạng thái đơn 1 chạm có chống bấm nhầm.
- Công cụ tra cứu đơn hàng bằng ngôn ngữ tự nhiên: Text-to-SQL an toàn (read-only, unaccent tiếng Việt, 1-shot retry) và luồng hỏi xác nhận bảo toàn ngữ cảnh điều hướng.

### What Worked
- Tiếp cận 2-phase confirmation cho cả tạo đơn và tìm kiếm giúp tránh hoàn toàn ghi rác vào DB hoặc hiển thị sai đơn hàng.
- SQLite WAL mode kết hợp busy timeout 5000ms vận hành trơn tru, không gặp bất kỳ lỗi database locked nào trong suốt quá trình chạy async.
- Phím bấm Copy 1 chạm (`CopyTextButton`) giải quyết dứt điểm vấn đề người lớn tuổi gặp khó khăn khi bôi đen copy SĐT/địa chỉ sang app giao hàng.
- 110 automated unit & integration tests phủ trọn vẹn toàn bộ 19 yêu cầu chức năng, giúp phát hiện sớm các lỗi tích hợp qua từng phase.

### What Was Inefficient
- Việc các phase sau (Phase 3 & Phase 4) chỉnh sửa code chung trong `src/bot/handlers/` và `src/bot/app.py` làm báo cáo verification của Phase 2 & Phase 3 bị đánh dấu "stale", đòi hỏi bước giải trình khi đóng milestone.
- Một số biểu thức regex tiếng Việt trong nhận diện câu hỏi tìm kiếm ban đầu thiếu cờ `re.DOTALL`, cần debug fix ở Phase 4 (WR-03).

### Patterns Established
- Handler Group -1 cho Whitelist Gate chặn đứng truy cập trái phép trước mọi handler nghiệp vụ.
- `_get_active_db_context` helper chuẩn hoá cách truy cập kết nối DB an toàn trên mọi handler callback và message.
- Custom unaccent function tích hợp sẵn vào SQLite connection cho phép tìm kiếm tiếng Việt không dấu tự nhiên mà không cần extension bên ngoài.

### Key Lessons
1. Luôn dùng 2-tier fallback (`parse` → `json_object`) khi tích hợp với các LLM gateway đa dạng nhà cung cấp để tránh lỗi HTTP 400.
2. Với người dùng lớn tuổi, bàn phím Reply Keyboard cố định dưới khung chat kết hợp Inline Buttons một chạm mang lại trải nghiệm vượt trội so với lệnh gõ slash `/`.

### Cost Observations
- Model: cc-high[1m]
- Test coverage: 110 passing automated tests
- Python LOC: 7,134 lines of clean async Python

---

## Cross-Milestone Trends

### Process Evolution

| Milestone | Commits | Phases | Plans | Key Change |
|-----------|---------|--------|-------|------------|
| v1.0 | 128 | 4 | 11 | Initial MVP release with GSD SDD workflows and full test-driven verification |

### Cumulative Quality

| Milestone | Tests | Requirements Met | Tech Debt Items |
|-----------|-------|------------------|-----------------|
| v1.0 | 110 | 19/19 (100%) | 2 minor (photo race condition under concurrency, phone normalization edge-case) |

### Top Lessons (Verified Across Milestones)

1. Two-phase confirmation with in-memory draft staging guarantees data hygiene in chat-based workflows.
2. Direct 1-tap UX (`CopyTextButton`, fixed 2x2 Reply Keyboards) is essential for non-tech-savvy users.
