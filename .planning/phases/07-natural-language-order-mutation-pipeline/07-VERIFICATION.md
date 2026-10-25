---
phase: 07-natural-language-order-mutation-pipeline
verified: 2026-10-25T17:35:00Z
status: human_needed
score: 10/10 must-haves verified
overrides_applied: 0
human_verification:
  - test: "Gửi tin nhắn 'sửa địa chỉ đơn 1 thành 456 Hai Bà Trưng, P. Tân Định, Q.1' trên ứng dụng Telegram di động"
    expected: "Thẻ Visual Diff hiển thị tiêu đề [Mã đơn #1 - Khách: ...], đường kẻ divider 14 ký tự (──────────────) gọn gàng không vỡ dòng, chỉ in trường địa chỉ thay đổi dạng [Cũ] ➡️ [Mới], kèm 2 nút inline [✅ Xác nhận sửa] và [❌ Huỷ]"
    why_human: "Cần kiểm tra độ vừa vặn trực quan và bố cục thẻ diff trên kích thước màn hình và cỡ chữ thực tế của người dùng lớn tuổi"
  - test: "Tạo 2 đơn có cùng tên khách 'Bác Ba', nhắn tin 'đổi sđt khách Bác Ba thành 0988776655'"
    expected: "Bot hiển thị danh sách các nút bấm inline 1-chạm [📦 Đơn #X - Bác Ba - ... - ...], bấm 1 nút lập tức chuyển sang Thẻ Diff với số điện thoại mới mà không phải gõ lại"
    why_human: "Cần trải nghiệm độ mượt mà khi chuyển đổi trạng thái tin nhắn và tính dễ thao tác của bàn phím inline phân định đơn"
  - test: "Nhắn tin 'chuyển trạng thái đơn 1' mà không nêu rõ trạng thái đích"
    expected: "Bot hiển thị danh sách các nút bấm gợi ý các bước kế tiếp hợp lý theo vòng đời đơn hàng (ví dụ: đang Chờ làm gợi ý '▶️ Bắt đầu làm' và '❌ Huỷ đơn này') kèm nút '❌ Huỷ bỏ'"
    why_human: "Xác minh trực quan các nhãn nút bấm gợi ý thân thiện và thao tác chuyển trạng thái 1-chạm"
  - test: "Gửi yêu cầu sửa đơn để hiện Thẻ Diff, đợi quá 120 giây rồi mới bấm [✅ Xác nhận sửa]"
    expected: "Bot cập nhật tin nhắn thành thông báo hết hạn 120s, gỡ bỏ toàn bộ nút bấm inline, dữ liệu trong cơ sở dữ liệu giữ nguyên không đổi"
    why_human: "Kiểm tra cơ chế dọn dẹp bàn phím và bộ đếm thời gian thực trên client Telegram"
  - test: "Dùng 2 tài khoản Telegram cùng mở thẻ sửa đơn #1. Tài khoản A bấm xác nhận sửa địa chỉ, sau đó tài khoản B mới bấm xác nhận sửa số điện thoại"
    expected: "Tài khoản B nhận thông báo cảnh báo xung đột nêu rõ người sửa, thời điểm và nội dung thay đổi của tài khoản A, hiển thị thẻ đơn mới nhất và không bị ghi đè dữ liệu cũ"
    why_human: "Xác minh trải nghiệm thông báo xung đột đồng thời trong môi trường nhiều quản trị viên thực tế"
---

# Phase 07: Natural Language Order Mutation Pipeline Verification Report

**Phase Goal:** Người dùng có thể chỉnh sửa các thông tin đơn hàng bằng tin nhắn chat tự nhiên tiếng Việt và xác nhận 1-chạm qua thẻ so sánh Trước ➡️ Sau an toàn
**Verified:** 2026-10-25T17:35:00Z
**Status:** human_needed
**Re-verification:** No — initial verification

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | 3-Way Intent Router phân loại chính xác tin nhắn tự do sang MUTATE (thay vì CREATE/SEARCH) qua regex, reply context hoặc LLM fallback (MUT-01) | ✓ VERIFIED | `classify_intent` trong `src/services/intent_router.py`, tích hợp vào `ingest.py`; 41 tests passing |
| 2 | Tìm đúng đơn hàng cần sửa dựa trên từ khoá; ưu tiên các đơn active (CHO_LAM tới SHIPPER_DA_LAY); nếu khớp 2-5 đơn hiển thị bàn phím inline 1-chạm để chọn (MUT-02) | ✓ VERIFIED | `find_orders_for_mutation` trong `src/db/orders.py`, `build_mutation_disambiguation_keyboard` trong `src/bot/keyboards.py`, xử lý tại `src/bot/handlers/mutation.py` |
| 3 | LLM 2-tier bóc tách delta thay đổi 5 nhóm trường (trạng thái, mã vận đơn, ghi chú, tiền COD/tổng đơn, SĐT/địa chỉ nhận hàng/băng) với json_object fallback (MUT-03) | ✓ VERIFIED | `OrderMutationDelta` trong `src/models/mutation.py`, `extract_mutation_delta` trong `src/services/mutation_extractor.py`, fallback chuẩn hóa markdown JSON |
| 4 | Fast-path status regex chuyển đổi lệnh trạng thái ngắn ('huỷ đơn 12', 'đơn 12 đã giao') thành delta trong 0ms không tốn token LLM | ✓ VERIFIED | `parse_fast_path_status` trong `src/services/intent_router.py`, kiểm thử trực tiếp qua `test_mutation_flow_fast_path_status` |
| 5 | Bảng `order_history` lưu vết lịch sử sửa đơn chi tiết (action, changes_json, user attribution) và bảng `orders` lưu thông tin người tạo | ✓ VERIFIED | `init_db` trong `src/db/schema.py`, `record_order_history` và `mutate_order_with_lock` trong `src/db/orders.py`, `Order` model có `created_by_user_id` và `notes` |
| 6 | Thẻ so sánh Trước ➡️ Sau (Visual Diff) chỉ in các trường thay đổi với divider 14 ký tự ('──────────────') và 2 nút [✅ Xác nhận sửa] / [❌ Huỷ] (MUT-04) | ✓ VERIFIED | `render_mutation_diff_card` và `build_mutation_confirm_keyboard` trong `src/bot/keyboards.py`, divider độ dài chuẩn 14 ký tự |
| 7 | Bộ đếm TTL 120s trong user_data tự động hết hạn, huỷ bỏ thao tác và gỡ sạch nút inline để chống bấm nhầm | ✓ VERIFIED | Kiểm tra `time.time() > draft['expires_at']` trong `handle_mutation_callback` (`src/bot/handlers/callbacks.py`), edit tin nhắn và dọn dẹp inline keyboard |
| 8 | Khóa lạc quan (Optimistic Concurrency) UPDATE WHERE id=? AND updated_at=? cập nhật nguyên tử, phát hiện xung đột và báo rõ người vừa sửa kèm chi tiết | ✓ VERIFIED | `mutate_order_with_lock` trong `src/db/orders.py`, sử dụng millisecond timestamp và đối soát `order_history` khi rowcount=0 |
| 9 | Gợi ý trạng thái đích chưa rõ (MUT-05) hiển thị các nút bấm chuyển đổi vòng đời hợp lý theo trạng thái hiện tại | ✓ VERIFIED | `get_suggested_next_statuses` và `build_mutation_status_keyboard` trong `src/bot/keyboards.py`, kiểm thử `tests/test_status_suggestions.py` |
| 10 | Tích hợp toàn diện vào Telegram ingest pipeline, xử lý mượt mà ngữ cảnh Reply, cập nhật thẻ đơn in-place sau xác nhận thành công | ✓ VERIFIED | `handle_text_order` trong `src/bot/handlers/ingest.py`, `handle_mutation_callback` trong `src/bot/handlers/callbacks.py`, pattern `^ord_mut_` trong `src/bot/app.py` |

**Score:** 10/10 truths verified

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `src/models/mutation.py` | OrderMutationDelta & IntentType Pydantic schemas (min 40 lines) | ✓ VERIFIED | 72 lines; đầy đủ 5 nhóm trường, regex SĐT VN, Pydantic v2 validator |
| `src/services/intent_router.py` | 3-Way Intent Router and fast-path status regex parser | ✓ VERIFIED | 118 lines; exports `classify_intent`, `extract_order_id_from_reply`, `parse_fast_path_status` |
| `src/services/mutation_extractor.py` | 2-tier LLM mutation delta extractor | ✓ VERIFIED | 108 lines; exports `extract_mutation_delta` với structured parse và json_object fallback |
| `src/db/orders.py` | Active-first order finder, optimistic concurrency update, and audit trail logger | ✓ VERIFIED | Exports `find_orders_for_mutation`, `record_order_history`, `mutate_order_with_lock` |
| `src/bot/keyboards.py` | Visual diff card, 14-char divider, confirmation & disambiguation keyboards | ✓ VERIFIED | Exports `render_mutation_diff_card`, `build_mutation_confirm_keyboard`, `build_mutation_disambiguation_keyboard`, `build_mutation_status_keyboard`, `get_suggested_next_statuses`, `DIVIDER` |
| `src/bot/handlers/mutation.py` | Mutation flow controller, disambiguation, and suggestion selection | ✓ VERIFIED | 297 lines; exports `handle_mutation_flow`, `handle_mutation_selection`, `handle_status_suggestion_selection` |
| `src/bot/handlers/ingest.py` | 3-Way Intent Router integration in handle_text_order | ✓ VERIFIED | Dispatch tới `handle_mutation_flow` khi intent là `MUTATE` |
| `src/bot/handlers/callbacks.py` | Callback handler for `ord_mut_` actions | ✓ VERIFIED | Handles `cf`, `ca`, `sel`, `st` with TTL check and optimistic concurrency conflict handling |
| `src/bot/app.py` | Telegram callback handler registration | ✓ VERIFIED | `CallbackQueryHandler(handle_mutation_callback, pattern=r"^ord_mut_")` registered at group 0 |
| `tests/test_order_audit_trail.py` | Unit tests for DB schema, creator fields, order_history (min 40 lines) | ✓ VERIFIED | 243 lines, 7 unit tests passing |
| `tests/test_intent_router.py` | Unit tests for 3-way router, fast-path, reply context (min 50 lines) | ✓ VERIFIED | 91 lines, 6 unit tests passing |
| `tests/test_mutation_extractor.py` | Unit tests for 5-group delta extraction (min 50 lines) | ✓ VERIFIED | 123 lines, 4 unit tests passing |
| `tests/test_mutation_card_and_lock.py` | Unit tests for diff card, divider, concurrency lock (min 60 lines) | ✓ VERIFIED | 338 lines, 9 unit tests passing |
| `tests/test_status_suggestions.py` | Unit tests for lifecycle transitions & keyboards (min 40 lines) | ✓ VERIFIED | 91 lines, 6 unit tests passing |
| `tests/test_mutation_handler_flow.py` | Comprehensive integration tests for Telegram handler flow | ✓ VERIFIED | 357 lines, 9 integration tests passing |

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| `src/services/intent_router.py` | `src/services/order_search.py` | `from src.services.order_search import PHONE_PATTERN, is_search_intent` | ✓ WIRED | Tái sử dụng regex và search intent parser |
| `src/services/mutation_extractor.py` | `src/models/mutation.py` | `response_format=OrderMutationDelta` | ✓ WIRED | Strict structured outputs parsing và Pydantic JSON validation |
| `src/db/schema.py` | `order_history` | `CREATE TABLE IF NOT EXISTS order_history` | ✓ WIRED | Tạo bảng audit trail, foreign key cascade, và index |
| `src/bot/handlers/ingest.py` | `src/services/intent_router.py` | `intent = await classify_intent(...)` | ✓ WIRED | Gọi intent router tại dòng 213 của `ingest.py` |
| `src/bot/handlers/ingest.py` | `src/bot/handlers/mutation.py` | `await handle_mutation_flow(...)` | ✓ WIRED | Chuyển tiếp tin nhắn MUTATE tại dòng 223 của `ingest.py` |
| `src/bot/handlers/callbacks.py` | `src/db/orders.py` | `mutate_order_with_lock(...)` | ✓ WIRED | Thực thi cập nhật lạc quan tại dòng 265 của `callbacks.py` |
| `src/bot/app.py` | `src/bot/handlers/callbacks.py` | `CallbackQueryHandler(handle_mutation_callback, pattern=r"^ord_mut_")` | ✓ WIRED | Đăng ký callback handler tại dòng 296 của `app.py` |

### Data-Flow Trace (Level 4)

| Artifact | Data Variable | Source | Produces Real Data | Status |
|----------|---------------|--------|---------------------|--------|
| `src/bot/handlers/mutation.py` | `matches` | `find_orders_for_mutation(db, ...)` | Có, truy vấn SQLite bảng `orders` theo trạng thái active và keyword | ✓ FLOWING |
| `src/bot/handlers/mutation.py` | `delta` | `extract_mutation_delta(client, model, text)` | Có, gọi OpenAI client structured outputs với fallback | ✓ FLOWING |
| `src/bot/keyboards.py` | `diff_text` | `delta_dict` so khớp với thuộc tính thực của `Order` | Có, tạo thẻ Trước ➡️ Sau cho các trường khác biệt | ✓ FLOWING |
| `src/bot/handlers/callbacks.py` | `fresh_order` | `mutate_order_with_lock(db, ...)` | Có, thực thi atomic UPDATE và trả về `Order` mới nhất từ DB | ✓ FLOWING |
| `src/db/orders.py` | `changes_json` | Dynamic diff dict giữa bản ghi hiện tại và delta mới | Có, lưu đầy đủ `{field: {"old": ..., "new": ...}}` vào `order_history` | ✓ FLOWING |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| Fast-path status parser nhận diện cú pháp ngắn | `parse_fast_path_status("huỷ đơn 12")` | `(12, OrderStatus.HUY_DON)` | ✓ PASS |
| Thẻ Visual Diff dùng divider 14 ký tự | `len(DIVIDER) == 14` | `True` (`──────────────`) | ✓ PASS |
| Thẻ Visual Diff hiển thị đúng thay đổi Before ➡️ After | `render_mutation_diff_card(order, delta)` | Chứa `#12`, `Trạng thái:`, `Tổng tiền:`, divider | ✓ PASS |
| Optimistic locking từ chối bản ghi bị sửa đồng thời | `mutate_order_with_lock(db, oid, stale_updated_at, delta)` | `(False, changes, fresh)` | ✓ PASS |
| Toàn bộ test suite dự án | `./.venv/bin/pytest -q` | `218 passed in 0.95s` | ✓ PASS |
| Test suite riêng cho Phase 07 | `./.venv/bin/pytest tests/test_*mutation* tests/test_intent_router.py tests/test_order_audit_trail.py tests/test_status_suggestions.py` | `41 passed in 0.33s` | ✓ PASS |

### Probe Execution

Không có kịch bản probe dạng shell script trong dự án (Phase 07 không yêu cầu probe scripts). Kiểm thử tự động hóa được thực thi qua bộ test suite pytest (41 test cases cho Phase 07, 218 test cases toàn dự án).

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|------------|-------------|--------|----------|
| **MUT-01** | 07-01-PLAN | 3-Way Intent Router tách biệt chính xác với Tạo đơn và Tìm kiếm | ✓ SATISFIED | `classify_intent` trong `src/services/intent_router.py`, `tests/test_intent_router.py` |
| **MUT-02** | 07-01-PLAN | Tìm đúng đơn hàng cần sửa dựa trên từ khoá; khớp nhiều đơn hiển thị nút chọn 1-chạm | ✓ SATISFIED | `find_orders_for_mutation` trong `src/db/orders.py`, `build_mutation_disambiguation_keyboard` trong `src/bot/keyboards.py` |
| **MUT-03** | 07-01-PLAN | LLM trích xuất delta thay đổi cho 5 nhóm trường: Trạng thái, Vận đơn, Ghi chú, Tiền COD/tổng, SĐT/Địa chỉ | ✓ SATISFIED | `OrderMutationDelta` trong `src/models/mutation.py`, `extract_mutation_delta` trong `src/services/mutation_extractor.py` |
| **MUT-04** | 07-02-PLAN | Thẻ so sánh Trước ➡️ Sau kèm nút Inline `[✅ Xác nhận sửa]` và `[❌ Huỷ]` (TTL 120s) | ✓ SATISFIED | `render_mutation_diff_card` trong `src/bot/keyboards.py`, `mutate_order_with_lock` trong `src/db/orders.py` |
| **MUT-05** | 07-02-PLAN | Hiển thị danh sách nút bấm trạng thái gợi ý 1-chạm khi câu chat chưa rõ trạng thái đích | ✓ SATISFIED | `get_suggested_next_statuses` và `build_mutation_status_keyboard` trong `src/bot/keyboards.py`, `handle_status_suggestion_selection` trong `src/bot/handlers/mutation.py` |

Không có yêu cầu mồ côi (orphaned requirements). Toàn bộ 5 mã yêu cầu MUT-01 đến MUT-05 đều đã được đối chiếu, triển khai và kiểm thử đầy đủ.

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| - | - | Không phát hiện TBD, FIXME, XXX | Clean | Không có nợ kỹ thuật tồn đọng |
| - | - | Không phát hiện TODO, HACK, PLACEHOLDER | Clean | Mã nguồn hoàn thiện, không chứa stub |
| - | - | Không phát hiện chuỗi văn bản tạm thời ("coming soon") | Clean | Không có chức năng bỏ dở |

### Human Verification Required

### 1. Hiển thị Thẻ Visual Diff Trước ➡️ Sau trên Telegram Mobile

**Test:** Gửi tin nhắn `"sửa địa chỉ đơn 1 thành 456 Hai Bà Trưng, P. Tân Định, Q.1"` trên ứng dụng Telegram di động.
**Expected:** Thẻ Visual Diff hiển thị tiêu đề `[Mã đơn #1 - Khách: ...]`, đường kẻ divider 14 ký tự (`──────────────`) không bị ngắt/vỡ dòng trên màn hình điện thoại; chỉ in trường địa chỉ thay đổi dạng `📍 Địa chỉ: [Cũ] ➡️ [Mới]`; bên dưới có 2 nút inline `[✅ Xác nhận sửa]` và `[❌ Huỷ]`.
**Why human:** Đánh giá độ vừa vặn trực quan, chống vỡ dòng và thẩm mỹ thực tế trên client Telegram điện thoại cho đối tượng người lớn tuổi.

### 2. Chọn đơn 1-chạm khi khớp nhiều đơn (Disambiguation)

**Test:** Tạo 2 đơn có cùng tên khách "Bác Ba", sau đó gửi tin nhắn `"đổi sđt khách Bác Ba thành 0988776655"`.
**Expected:** Bot hiển thị danh sách các nút bấm inline 1-chạm dạng `[📦 Đơn #X - Bác Ba - ... - ...]`. Bấm vào 1 đơn mong muốn, bot lập tức chuyển sang Thẻ Visual Diff với số điện thoại mới mà không phải gõ lại tin nhắn.
**Why human:** Cần kiểm tra độ phản hồi và cảm giác mượt mà của thao tác 1-chạm trên ứng dụng Telegram.

### 3. Gợi ý trạng thái tiếp theo 1-chạm (MUT-05)

**Test:** Nhắn tin `"chuyển trạng thái đơn 1"` (không nói rõ trạng thái nào).
**Expected:** Bot hiển thị danh sách các nút bấm gợi ý các bước kế tiếp hợp lý theo vòng đời đơn hàng (ví dụ: đang "Chờ làm" thì gợi ý `"▶️ Bắt đầu làm"` và `"❌ Huỷ đơn này"`) kèm nút `"❌ Huỷ bỏ"`.
**Why human:** Xác nhận nhãn tiếng Việt dễ hiểu và luồng chuyển đổi trạng thái bằng nút bấm một chạm.

### 4. Hết hạn TTL 120s và chống bấm nhầm

**Test:** Gửi yêu cầu sửa đơn để hiển thị Thẻ Diff, đợi quá 2 phút (120s) rồi mới bấm `[✅ Xác nhận sửa]`.
**Expected:** Bot cập nhật tin nhắn thành thông báo hết hạn 120s, gỡ bỏ toàn bộ nút bấm inline, dữ liệu trong DB không bị thay đổi.
**Why human:** Kiểm tra hành vi timeout thực tế theo thời gian thực và việc dọn dẹp bàn phím inline chống bấm nhầm.

### 5. Cảnh báo xung đột (Optimistic Concurrency) khi 2 người cùng sửa

**Test:** Dùng 2 tài khoản Telegram cùng mở giao diện sửa đơn #1. Tài khoản A bấm xác nhận sửa địa chỉ, sau đó tài khoản B mới bấm xác nhận sửa số điện thoại.
**Expected:** Tài khoản B nhận cảnh báo xung đột nêu rõ người sửa, thời điểm và nội dung thay đổi của tài khoản A, hiển thị thẻ đơn mới nhất và không bị ghi đè dữ liệu cũ.
**Why human:** Xác minh trải nghiệm xử lý xung đột trong môi trường thực tế nhiều người cùng quản lý shop.

### Gaps Summary

Không phát hiện khoảng cách kỹ thuật (zero gaps). Toàn bộ 10 must-haves, 5 requirements (MUT-01 đến MUT-05), 41 unit/integration tests cho Phase 07 và 218 tests toàn hệ thống đều đạt 100%. Các phản hồi sau đợt review mã nguồn (CR-01, CR-02, WR-01, WR-02, WR-03) đã được khắc phục triệt để. Chuyển trạng thái sang `human_needed` để tiến hành thẩm định người dùng trên ứng dụng Telegram thực tế.

---

_Verified: 2026-10-25T17:35:00Z_
_Verifier: Claude (gsd-verifier)_
