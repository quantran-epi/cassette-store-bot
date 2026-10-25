# Phase 2 Plan 1: LLM Ingestion & Interactive Confirmation Summary

**Vertical slice E2E:** Bóc tách đơn hàng tiếng Việt tự do qua 9router LLM gateway (OpenAI-compatible) với 2-tier fallback, chuẩn hoá tiền tệ và SĐT, hiển thị thẻ xem trước HTML với nút bấm xác nhận 1 chạm, lưu trữ an toàn hai pha vào SQLite.

## Accomplishments

1. **Extraction Schema & Normalization (`src/models/extractor.py`):**
   - Định nghĩa model Pydantic `ExtractedOrder` bao gồm các trường: `customer_name`, `customer_phone`, `shipping_address`, `items_text`, `total_amount`, `cod_amount`, `deposit_amount`, `payment_method`, `notes`.
   - Chuẩn hoá số điện thoại Việt Nam 10 chữ số đầu 03, 05, 07, 08, 09 (xử lý `+84`, khoảng trắng, dấu chấm, dấu gạch nối).
2. **2-Tier LLM Gateway Service (`src/services/extractor.py`):**
   - Tích hợp `AsyncOpenAI` kết nối tới 9router gateway.
   - Chiến lược fallback 2 tầng: Tier 1 gọi `beta.chat.completions.parse` với Pydantic schema; nếu gặp `BadRequestError` hoặc lỗi không hỗ trợ `json_schema` thì tự động chuyển sang Tier 2 `response_format={"type": "json_object"}` và `ExtractedOrder.model_validate_json`.
   - Phòng chống Prompt Injection (T-02-01) bằng cách bọc dữ liệu người dùng trong boundary tag `<message>...</message>` cùng chỉ thị bảo mật trong System Prompt.
3. **Interactive Telegram Ingestion & Preview Card (`src/bot/handlers/ingest.py`):**
   - Handler `handle_text_order` nhận tin nhắn text từ người dùng trong whitelist, gọi LLM bóc tách.
   - Nếu thiếu SĐT: gửi thông báo nhẹ nhàng hướng dẫn gửi lại tin nhắn kèm SĐT (D-02).
   - Nếu có SĐT: đối chiếu khách cũ trong SQLite để lấy thống kê đơn hàng, tổng chi tiêu, và hiển thị cảnh báo nếu từng có đơn bom hàng `BOM_HANG` (D-05).
   - Render Preview Card dạng HTML chuẩn hoá, escape chống lỗi layout, phân tách rõ Tổng tiền và Tiền COD (D-03).
   - Bàn phím Inline Keyboard gồm 2 nút: `[✅ Xác nhận lưu]` (`ord:cf:<id>`) và `[❌ Huỷ bỏ]` (`ord:ca:<id>`), kích thước token callback <= 15 bytes (tuân thủ giới hạn 64 bytes của Telegram).
4. **Two-Phase Confirmation Callback (`src/bot/handlers/callbacks.py`):**
   - Gọi ngay `query.answer()` đầu handler để triệt tiêu spinner 30s của Telegram.
   - Quản lý trạng thái lưu tạm in-memory theo `draft_id` độc lập (D-07, D-08).
   - Nút Huỷ (`ord:ca:`): xoá draft, cập nhật thẻ đã huỷ, 0 ghi nhận vào DB (D-04).
   - Nút Xác nhận (`ord:cf:`): tìm hoặc tạo khách hàng mới, lưu đơn hàng với trạng thái `CHO_LAM`, cập nhật mã đơn trên thẻ xem trước (D-04).
5. **Customer Aggregates & App Wiring (`src/db/orders.py`, `src/bot/app.py`):**
   - Hàm `get_customer_order_stats` truy vấn tổng hợp đơn hàng, doanh thu và số đơn bom hàng theo `customer_id`.
   - Wiring hoàn chỉnh `AppContext` chứa `AsyncOpenAI`, `Settings`, và `aiosqlite.Connection` trong `ApplicationBuilder`.

## Test Suite Results

- `tests/test_extractor.py`: 6 passed
- `tests/test_ingest.py`: 7 passed
- Full suite (`pytest`): 48 passed in 0.40s

## Commits

- `a5f6ad5`: test(02-01): add test scaffold for LLM extraction and interactive confirmation
- `32dc13f`: feat(02-01): implement ExtractedOrder schema and 2-tier 9router LLM service
- `d4abb59`: feat(02-01): implement text order ingestion, preview card, and interactive confirmation callbacks

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Regex match check in test_order_callback_expired_draft**
- **Found during:** Task 3 verification
- **Issue:** Test case mock callback query data `ord:cf:nonexist` didn't match the strict 8-hex regex pattern `^ord:(cf|ca):([a-f0-9]{8})$`.
- **Fix:** Changed dummy draft ID to 8 hex characters (`12345678`) to test true expiration handling.
- **Files modified:** `tests/test_ingest.py`
- **Commit:** `d4abb59`

## Self-Check: PASSED
- `src/models/extractor.py`: FOUND
- `src/services/extractor.py`: FOUND
- `src/bot/handlers/ingest.py`: FOUND
- `src/bot/handlers/callbacks.py`: FOUND
- Commits `a5f6ad5`, `32dc13f`, `d4abb59`: FOUND in git log
