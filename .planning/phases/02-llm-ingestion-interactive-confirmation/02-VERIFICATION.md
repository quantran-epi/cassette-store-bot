---
phase: 02-llm-ingestion-interactive-confirmation
verified: 2026-10-24T18:40:00Z
status: passed
score: 12/12 must-haves verified
covered_files:
  - .planning/phases/02-llm-ingestion-interactive-confirmation/02-01-PLAN.md
  - .planning/phases/02-llm-ingestion-interactive-confirmation/02-01-SUMMARY.md
  - .planning/phases/02-llm-ingestion-interactive-confirmation/02-02-PLAN.md
  - .planning/phases/02-llm-ingestion-interactive-confirmation/02-02-SUMMARY.md
  - src/bot/app.py
  - src/bot/handlers/callbacks.py
  - src/bot/handlers/ingest.py
  - src/db/customers.py
  - src/db/orders.py
  - src/models/extractor.py
  - src/services/extractor.py
covered_digest: "v2:sha256:499874b32c39386dda9f3a1a3d9e74a69c2178e37895254fb072cab1ab0718c7"
behavior_unverified: 0
overrides_applied: 0
---

# Phase 02: LLM Ingestion & Interactive Confirmation Verification Report

**Phase Goal:** Quản trị viên dán bất kỳ tin nhắn text hoặc gửi ảnh kèm chú thích đặt hàng tự do; bot dùng LLM 9router bóc tách tự động thành công thông tin khách hàng, số điện thoại, sản phẩm, tiền COD, địa chỉ, hiển thị thẻ xem trước trực quan kèm lịch sử khách cũ, và chỉ lưu vào SQLite khi người dùng bấm nút [Xác nhận lưu] một chạm.
**Verified:** 2026-10-24T18:40:00Z
**Status:** passed
**Re-verification:** Yes — UAT completed, status upgraded to passed

## Goal Achievement

### User Flow Coverage (MVP Mode)

| User Step | Expected Outcome | Codebase Evidence | Status |
| --------- | ---------------- | ----------------- | ------ |
| 1. Dán tin nhắn text đặt hàng tự do | LLM bóc tách đúng tên, SĐT, địa chỉ, tiền tệ | `src/services/extractor.py:extract_order_from_text`, `src/models/extractor.py:ExtractedOrder` | ✓ VERIFIED |
| 2. Gửi ảnh kèm caption đặt hàng | Lấy caption bóc tách, lấy ảnh độ phân giải cao nhất | `src/bot/handlers/ingest.py:handle_photo_order` (`photo[-1].file_id`) | ✓ VERIFIED |
| 3. Xem trước đơn hàng (Preview Card) | Hiển thị thẻ HTML phân tách Tổng tiền & COD, tóm tắt khách cũ, cảnh báo BOM_HANG | `src/bot/handlers/ingest.py:render_preview_card`, `src/db/orders.py:get_customer_order_stats` | ✓ VERIFIED |
| 4. Chọn địa chỉ cũ (nếu có nhiều địa chỉ) | Nút Inline bấm nhanh đổi địa chỉ tức thì | `src/bot/handlers/ingest.py:65`, `src/bot/handlers/callbacks.py:42-60` (`ord:ad:`) | ✓ VERIFIED |
| 5. Bấm [❌ Huỷ bỏ] | Huỷ đơn nháp ngay lập tức, 0 bản ghi vào SQLite | `src/bot/handlers/callbacks.py:62-68` (`ord:ca:`) | ✓ VERIFIED |
| 6. Bấm [✅ Xác nhận lưu] | Ghi khách và đơn hàng (Chờ làm) vào SQLite, cập nhật thẻ thông báo thành công | `src/bot/handlers/callbacks.py:71-135` (`ord:cf:`), `create_customer`, `create_order` | ✓ VERIFIED |

### Observable Truths

| #   | Truth | Status | Evidence |
| --- | ----- | ------ | -------- |
| 1   | Người dùng gửi tin nhắn đặt hàng không cấu trúc, bot dùng LLM bóc tách đúng tên, SĐT, địa chỉ, danh sách băng và số tiền VNĐ | ✓ VERIFIED | `src/models/extractor.py:ExtractedOrder`, `src/services/extractor.py:extract_order_from_text`, tested in `test_handle_text_order_flow` |
| 2   | Tiền tệ lóng tiếng Việt (250k, 1tr2, cọc 50k thu 200k) được chuẩn hoá thành số nguyên VNĐ chính xác | ✓ VERIFIED | `src/services/extractor.py:SYSTEM_PROMPT` currency rules, integer validation in `ExtractedOrder`, tested in `test_vietnamese_currency_normalization_model_defaults` |
| 3   | Bot phản hồi bằng thẻ xem trước HTML với phân tách rõ Tổng tiền và Tiền COD thu kèm 2 nút bấm Inline Xác nhận lưu và Huỷ bỏ | ✓ VERIFIED | `src/bot/handlers/ingest.py:render_preview_card` creates separated amounts and `ord:cf:`, `ord:ca:` buttons, tested in `test_render_preview_card_layout_and_buttons` |
| 4   | Bấm Huỷ bỏ cập nhật thông báo huỷ ngay lập tức, không ghi bản ghi nào vào DB | ✓ VERIFIED | `src/bot/handlers/callbacks.py:61-68` pops draft, edits message, 0 DB writes, tested in `test_order_callback_cancel_discards_draft_no_db` |
| 5   | Bấm Xác nhận lưu ghi dữ liệu khách hàng và đơn hàng (trạng thái Chờ làm) vào SQLite và cập nhật thẻ thông báo thành công | ✓ VERIFIED | `src/bot/handlers/callbacks.py:70-135` persists customer and order with `OrderStatus.CHO_LAM`, tested in `test_order_callback_confirm_saves_to_db` |
| 6   | Người dùng gửi ảnh chụp kèm caption đặt hàng, bot trích xuất caption bóc tách thông tin và lưu kèm photo file_id độ phân giải cao nhất | ✓ VERIFIED | `src/bot/handlers/ingest.py:handle_photo_order` extracts `photo[-1].file_id`, invokes LLM extractor, tested in `test_photo_order_caption_extraction` |
| 7   | Khách quen có đơn cũ trong DB hiển thị tóm tắt lịch sử (số đơn, tổng tiền đã mua) trên thẻ xem trước | ✓ VERIFIED | `src/db/orders.py:get_customer_order_stats`, rendered as `[Khách quen: X đơn - Y đ]`, tested in `test_returning_customer_stats_and_bom_warning` |
| 8   | Khách từng có đơn ở trạng thái Bom hàng hiển thị cảnh báo đỏ nổi bật trên thẻ xem trước | ✓ VERIFIED | `src/db/orders.py:get_customer_order_stats` calculates `bom_count`, rendered as `⚠️ CẢNH BÁO: Khách từng có Z đơn BOM HÀNG!`, tested in `test_render_preview_card_with_bom_hang_warning` |
| 9   | Khách quen không gửi địa chỉ: nếu có 1 địa chỉ cũ thì tự động điền, nếu có từ 2 địa chỉ cũ trở lên thì hiển thị nút bấm Inline để chọn nhanh | ✓ VERIFIED | `src/bot/handlers/ingest.py:102-109` auto-fills or generates `ord:ad:` buttons, tested in `test_address_auto_fill_and_picker_buttons` and `test_address_selection_callback` |
| 10  | Khách quen gửi địa chỉ mới khác các địa chỉ cũ thì tự động bổ sung địa chỉ mới vào danh sách địa chỉ của khách trong DB | ✓ VERIFIED | `src/bot/handlers/callbacks.py:105-106` calls `add_address(db, customer.id, address)`, tested in `test_order_confirmation_appends_new_address_for_existing_customer` |
| 11  | Tin nhắn không phải đơn hàng hoặc không có SĐT hợp lệ được phản hồi bằng lời nhắc hướng dẫn nhẹ nhàng, lịch sự | ✓ VERIFIED | `src/bot/handlers/ingest.py:85-89` checks `customer_phone`, sends guidance message, tested in `test_handle_text_order_missing_phone` |
| 12  | Lỗi gateway 9router (timeout, ngắt mạng, lỗi format) được bắt trọn vẹn và thông báo lịch sự, không làm treo bot | ✓ VERIFIED | `try...except Exception` in `handle_text_order` and `handle_photo_order`, tested in `test_llm_gateway_error_fallback` |

**Score:** 12/12 truths verified

### Required Artifacts

| Artifact | Expected | Status | Details |
| -------- | -------- | ------ | ------- |
| `src/models/extractor.py` | Pydantic extraction schema with currency and phone normalization | ✓ VERIFIED | Contains `ExtractedOrder`, `normalize_vietnamese_phone`, integer amounts |
| `src/services/extractor.py` | 2-tier LLM extraction service using AsyncOpenAI with 9router gateway | ✓ VERIFIED | Contains `extract_order_from_text`, 2-tier fallback (parse -> json_object), system prompt |
| `src/bot/handlers/ingest.py` | Text & photo order ingestion handlers, preview card renderer, address picker | ✓ VERIFIED | Contains `render_preview_card`, `handle_text_order`, `handle_photo_order` |
| `src/bot/handlers/callbacks.py` | Two-phase confirmation, cancellation, and address selection callbacks | ✓ VERIFIED | Contains `handle_order_callback`, `ord:cf:`, `ord:ca:`, `ord:ad:` handling |
| `src/db/orders.py` | Customer order stats aggregate query | ✓ VERIFIED | Contains `get_customer_order_stats` calculating `total_orders`, `total_spent`, `bom_count` |
| `src/db/customers.py` | Idempotent customer address append operation | ✓ VERIFIED | Contains `add_address` with normalized deduplication |
| `src/bot/app.py` | App wiring with handlers and dependencies | ✓ VERIFIED | Registers `filters.PHOTO`, `filters.TEXT`, `CallbackQueryHandler(pattern=r"^ord:(cf\|ca\|ad):")` |

### Key Link Verification

| From | To | Via | Status | Details |
| ---- | -- | --- | ------ | ------- |
| `src/bot/handlers/ingest.py` | `src/services/extractor.py` | calls `extract_order_from_text` | ✓ WIRED | Pattern verified in lines 167 & 222 |
| `src/bot/handlers/callbacks.py` | `src/db/orders.py` | calls `create_order` on confirmation | ✓ WIRED | Pattern verified in line 122 |
| `src/bot/handlers/ingest.py` | `src/db/orders.py` | calls `get_customer_order_stats` | ✓ WIRED | Pattern verified in line 101 |
| `src/bot/handlers/callbacks.py` | `src/db/customers.py` | calls `add_address` on confirmation | ✓ WIRED | Pattern verified in line 106 |

### Data-Flow Trace (Level 4)

| Artifact | Data Variable | Source | Produces Real Data | Status |
| -------- | ------------- | ------ | ------------------ | ------ |
| `src/bot/handlers/ingest.py` | `stats` | `get_customer_order_stats` | Yes (SQL `COUNT`, `SUM` from SQLite `orders` table) | ✓ FLOWING |
| `src/bot/handlers/ingest.py` | `customer` | `get_customer_by_phone` | Yes (SQL query on `json_each(phones)`) | ✓ FLOWING |
| `src/bot/handlers/ingest.py` | `preview_card` text & markup | `render_preview_card` | Yes (Dynamic string formatting, real draft data) | ✓ FLOWING |
| `src/bot/handlers/callbacks.py` | `order_id` | `create_order` | Yes (SQLite `INSERT INTO orders` returns rowid) | ✓ FLOWING |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
| -------- | ------- | ------ | ------ |
| Phone & currency normalization | Python script asserting `+84 912.345.678` -> `0912345678` and integers | Output: `PASS` | ✓ PASS |
| DB customer stats & address deduplication | Python script querying in-memory SQLite with orders (BOM_HANG & HUY_DON) | `total_orders=3, total_spent=300000, bom_count=1`, address deduplicated | ✓ PASS |
| Preview card & callback data size | Python script rendering card and asserting inline button bytes <= 64 bytes | `len(callback_data) <= 64` passed, BOM warning included | ✓ PASS |
| Callback pattern regex routing | Python script asserting `ord:(cf\|ca\|ad):[a-f0-9]{8}(:\d+)?` | Regex matches valid callback tokens and rejects invalid | ✓ PASS |
| Full pytest test suite | `./.venv/bin/pytest -v` | 59 passed in 1.90s | ✓ PASS |

### Probe Execution

No probes declared or required for Phase 02.

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
| ----------- | ----------- | ----------- | ------ | -------- |
| **INGEST-01** | 02-01-PLAN, 02-02-PLAN | Nhận tin nhắn free-text bất kỳ từ Zalo/Facebook chuyển sang; LLM (qua 9router gateway) tự động bóc tách: Tên khách, SĐT, Địa chỉ, Danh sách băng cassette, Tiền thu khách, Tiền COD, Hình thức thanh toán | ✓ SATISFIED | `src/models/extractor.py`, `src/services/extractor.py`, `test_handle_text_order_flow` |
| **INGEST-02** | 02-01-PLAN | Tự động chuẩn hoá đơn vị tiền tệ tiếng Việt ("250k", "1tr2", "50 ngàn", "cọc 50k thu 200k") thành số nguyên VNĐ chuẩn xác | ✓ SATISFIED | `src/services/extractor.py:SYSTEM_PROMPT`, `src/models/extractor.py:ExtractedOrder`, `test_vietnamese_currency_normalization_model_defaults` |
| **INGEST-03** | 02-01-PLAN, 02-02-PLAN | Hiển thị thẻ thông tin đơn xem trước (preview card) kèm 2 nút bấm Inline: `✅ Xác nhận lưu` và `❌ Huỷ bỏ` | ✓ SATISFIED | `src/bot/handlers/ingest.py:render_preview_card`, `test_render_preview_card_layout_and_buttons` |
| **INGEST-04** | 02-01-PLAN, 02-02-PLAN | Đơn hàng chỉ được ghi vào DB và gửi thông báo hoàn tất sau khi người dùng bấm nút xác nhận | ✓ SATISFIED | `src/bot/handlers/callbacks.py:handle_order_callback`, `test_order_callback_cancel_discards_draft_no_db`, `test_order_callback_confirm_saves_to_db` |

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
| ---- | ---- | ------- | -------- | ------ |
| None | - | - | - | Zero debt markers (TODO/FIXME/XXX) in `src/`. Clean implementations. |

### Human Verification (UAT Completed)

All 3 human verification checks previously flagged have been tested and verified via `02-UAT.md` (3 passed, 0 issues):

1. **Visual UX on Mobile Telegram**: PASSED — HTML preview card renders clearly with bold labels, mono phone tag, itemized product list, separate Total/COD amounts.
2. **Immediate Button Tap Feedback**: PASSED — Tap `[✅ Xác nhận lưu]` or `[❌ Huỷ bỏ]` acknowledged instantly via `answer_callback_query` with 0 spinner delay.
3. **Photo Caption Ingestion on Real Telegram**: PASSED — Photo caption parsed cleanly, order row stores `photo_file_ids` with highest-resolution file_id.

### Gaps Summary

No technical or functional gaps found in the codebase. All 12 observable truths, 7 required artifacts, and 4 key links are implemented, wired, and verified with 59 automated tests passing. UAT completed with 3 passed tests and 0 issues. Status is `passed`.

---

_Verified: 2026-10-24T18:40:00Z_  
_Verifier: Claude (gsd-verifier)_
