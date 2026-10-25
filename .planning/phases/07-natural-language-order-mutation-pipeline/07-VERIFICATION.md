---
phase: 07-natural-language-order-mutation-pipeline
verified: 2026-10-25T18:20:00Z
status: human_needed
score: 13/13 must-haves verified
overrides_applied: 0
re_verification:
  previous_status: human_needed
  previous_score: 10/10
  gaps_closed:
    - "find_orders_for_mutation strips conversational honorifics/prefixes ('khach', 'bac', 'anh', 'chi', 'don', 'cua') so 'khách Bác Ba' matches DB record 'Bác Ba'"
    - "_clean_json_markdown reliably isolates JSON object {...} via regex even when 9router outputs trailing markdown notes or explanations"
    - "mutate_order_with_lock normalizes updated_at timestamp comparison (truncating microseconds/parsing datetime) to prevent false-positive optimistic lock conflicts on consecutive mutations"
  gaps_remaining: []
  regressions: []
human_verification:
  - test: "Tạo 2 đơn có cùng tên khách 'Bác Ba', nhắn tin 'đổi sđt khách Bác Ba thành 0988776655' (UAT Test 2 Re-check)"
    expected: "Bot nhận diện từ khoá 'Bác Ba' (bỏ qua từ đệm 'khách'), hiển thị danh sách các nút bấm inline 1-chạm [📦 Đơn #X - Bác Ba - ... - ...]. Bấm 1 nút lập tức chuyển sang Thẻ Diff với số điện thoại mới mà không phải gõ lại"
    why_human: "Cần xác nhận trên Telegram thực tế rằng thuật ngữ xưng hô tiếng Việt không còn làm nghẽn việc tìm kiếm đơn hàng"
  - test: "Nhắn tin 'chuyển trạng thái đơn 1' mà không nêu rõ trạng thái đích, sau đó bấm chọn trạng thái gợi ý và bấm [✅ Xác nhận sửa] (UAT Test 3 Re-check)"
    expected: "Bot hiển thị các nút trạng thái hợp lý theo vòng đời. Khi bấm chọn và xác nhận, đơn được cập nhật thành công, KHÔNG bị cảnh báo xung đột giả do lệch timestamp microsecond vs millisecond"
    why_human: "Cần xác minh luồng 1-chạm và loại trừ triệt để lỗi xung đột giả trên client Telegram thực tế"
  - test: "Dùng 2 tài khoản Telegram cùng mở thẻ sửa đơn #1. Tài khoản A bấm xác nhận sửa địa chỉ, sau đó tài khoản B mới bấm xác nhận sửa số điện thoại (UAT Test 5 Re-check)"
    expected: "Tài khoản B nhận thông báo cảnh báo xung đột nêu rõ người sửa, thời điểm và nội dung thay đổi của tài khoản A, hiển thị thẻ đơn mới nhất và không bị ghi đè dữ liệu cũ"
    why_human: "Xác minh trải nghiệm thông báo xung đột đồng thời trong môi trường nhiều quản trị viên thực tế"
  - test: "Gửi tin nhắn 'sửa địa chỉ đơn 1 thành 456 Hai Bà Trưng, P. Tân Định, Q.1' trên ứng dụng Telegram di động"
    expected: "Thẻ Visual Diff hiển thị tiêu đề [Mã đơn #1 - Khách: ...], đường kẻ divider 14 ký tự (──────────────) gọn gàng không vỡ dòng trên màn hình điện thoại nhỏ/cỡ chữ to, chỉ in trường địa chỉ thay đổi dạng [Cũ] ➡️ [Mới], kèm 2 nút inline [✅ Xác nhận sửa] và [❌ Huỷ]"
    why_human: "Cần kiểm tra độ vừa vặn trực quan và bố cục thẻ diff trên kích thước màn hình và cỡ chữ thực tế của người dùng lớn tuổi"
  - test: "Gửi yêu cầu sửa đơn để hiện Thẻ Diff, đợi quá 120 giây rồi mới bấm [✅ Xác nhận sửa]"
    expected: "Bot cập nhật tin nhắn thành thông báo hết hạn 120s, gỡ bỏ toàn bộ nút bấm inline, dữ liệu trong cơ sở dữ liệu giữ nguyên không đổi"
    why_human: "Kiểm tra cơ chế dọn dẹp bàn phím và bộ đếm thời gian thực trên client Telegram"
---

# Phase 07: Natural Language Order Mutation Pipeline Verification Report

**Phase Goal:** Người dùng có thể chỉnh sửa các thông tin đơn hàng bằng tin nhắn chat tự nhiên tiếng Việt và xác nhận 1-chạm qua thẻ so sánh Trước ➡️ Sau an toàn
**Verified:** 2026-10-25T18:20:00Z
**Status:** human_needed
**Re-verification:** Yes — sau khi hoàn thành kế hoạch đóng gap 07-03

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | 3-Way Intent Router phân loại chính xác tin nhắn tự do sang MUTATE (thay vì CREATE/SEARCH) qua regex, reply context hoặc LLM fallback (MUT-01) | ✓ VERIFIED | `classify_intent` trong `src/services/intent_router.py`, tích hợp vào `ingest.py`; 6 unit tests passing trong `tests/test_intent_router.py` |
| 2 | Tìm đúng đơn hàng cần sửa dựa trên từ khoá; ưu tiên các đơn active (CHO_LAM tới SHIPPER_DA_LAY); nếu khớp 2-5 đơn hiển thị bàn phím inline 1-chạm để chọn (MUT-02) | ✓ VERIFIED | `find_orders_for_mutation` trong `src/db/orders.py`, `build_mutation_disambiguation_keyboard` trong `src/bot/keyboards.py`, xử lý tại `src/bot/handlers/mutation.py` |
| 3 | LLM 2-tier bóc tách delta thay đổi 5 nhóm trường (trạng thái, mã vận đơn, ghi chú, tiền COD/tổng đơn, SĐT/địa chỉ nhận hàng/băng) với json_object fallback (MUT-03) | ✓ VERIFIED | `OrderMutationDelta` trong `src/models/mutation.py`, `extract_mutation_delta` trong `src/services/mutation_extractor.py`, fallback chuẩn hóa markdown JSON |
| 4 | Fast-path status regex chuyển đổi lệnh trạng thái ngắn ('huỷ đơn 12', 'đơn 12 đã giao') thành delta trong 0ms không tốn token LLM | ✓ VERIFIED | `parse_fast_path_status` trong `src/services/intent_router.py`, kiểm thử trực tiếp qua `test_mutation_flow_fast_path_status` |
| 5 | Bảng `order_history` lưu vết lịch sử sửa đơn chi tiết (action, changes_json, user attribution) và bảng `orders` lưu thông tin người tạo | ✓ VERIFIED | `init_db` trong `src/db/schema.py`, `record_order_history` và `mutate_order_with_lock` trong `src/db/orders.py`, `Order` model có `created_by_user_id` và `notes` |
| 6 | Thẻ so sánh Trước ➡️ Sau (Visual Diff) chỉ in các trường thay đổi với divider 14 ký tự ('──────────────') và 2 nút [✅ Xác nhận sửa] / [❌ Huỷ] (MUT-04) | ✓ VERIFIED | `render_mutation_diff_card` và `build_mutation_confirm_keyboard` trong `src/bot/keyboards.py`, divider độ dài chuẩn 14 ký tự |
| 7 | Bộ đếm TTL 120s trong user_data tự động hết hạn, huỷ bỏ thao tác và gỡ sạch nút inline để chống bấm nhầm | ✓ VERIFIED | Kiểm tra `time.time() > draft['expires_at']` trong `handle_mutation_callback` (`src/bot/handlers/callbacks.py`), edit tin nhắn và dọn dẹp inline keyboard |
| 8 | Khóa lạc quan (Optimistic Concurrency) UPDATE WHERE id=? AND updated_at=? cập nhật nguyên tử, phát hiện xung đột và báo rõ người vừa sửa kèm chi tiết | ✓ VERIFIED | `mutate_order_with_lock` trong `src/db/orders.py`, sử dụng millisecond timestamp và đối soát `order_history` khi rowcount=0 |
| 9 | Gợi ý trạng thái đích chưa rõ (MUT-05) hiển thị các nút bấm chuyển đổi vòng đời hợp lý theo trạng thái hiện tại | ✓ VERIFIED | `get_suggested_next_statuses` và `build_mutation_status_keyboard` trong `src/bot/keyboards.py`, kiểm thử `tests/test_status_suggestions.py` |
| 10 | Tích hợp toàn diện vào Telegram ingest pipeline, xử lý mượt mà ngữ cảnh Reply, cập nhật thẻ đơn in-place sau xác nhận thành công | ✓ VERIFIED | `handle_text_order` trong `src/bot/handlers/ingest.py`, `handle_mutation_callback` trong `src/bot/handlers/callbacks.py`, pattern `^ord_mut_` trong `src/bot/app.py` |
| 11 | (Gap 07-03) `find_orders_for_mutation` bóc tách từ xưng hô/từ đệm ('khách', 'bác', 'anh', 'chị', 'đơn', 'của') và tìm kiếm đa token để 'khách Bác Ba' khớp bản ghi 'Bác Ba' | ✓ VERIFIED | `PREFIX_FILLERS` và `HONORIFIC_FILLERS` trong `src/db/orders.py:find_orders_for_mutation`, test `test_find_orders_for_mutation_strips_honorifics_and_fillers` passing |
| 12 | (Gap 07-03) `_clean_json_markdown` bóc tách khối JSON `{...}` qua regex an toàn khi 9router trả về ghi chú hoặc văn bản thừa ngoài code block | ✓ VERIFIED | `re.search(r"\{[\s\S]*\}", cleaned)` trong `src/services/mutation_extractor.py`, test `test_clean_json_markdown_with_trailing_chatter` passing |
| 13 | (Gap 07-03) `mutate_order_with_lock` chuẩn hóa timestamp so sánh `updated_at` (về millisecond 3 chữ số) chống xung đột giả trên các lần sửa liên tiếp | ✓ VERIFIED | `_normalize_ts` trong `src/db/orders.py`, test `test_mutate_order_with_lock_consecutive_mutations` và `test_mutate_order_with_lock_microsecond_vs_millisecond_normalization` passing |

**Score:** 13/13 truths verified

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `src/models/mutation.py` | OrderMutationDelta & IntentType Pydantic schemas (min 40 lines) | ✓ VERIFIED | 72 lines; đầy đủ 5 nhóm trường, regex SĐT VN, Pydantic v2 validator |
| `src/services/intent_router.py` | 3-Way Intent Router and fast-path status regex parser | ✓ VERIFIED | 118 lines; exports `classify_intent`, `extract_order_id_from_reply`, `parse_fast_path_status` |
| `src/services/mutation_extractor.py` | 2-tier LLM mutation delta extractor kèm regex chatter stripper | ✓ VERIFIED | 117 lines; exports `extract_mutation_delta`, `_clean_json_markdown` cô lập `{...}` an toàn |
| `src/db/orders.py` | Active-first order finder với prefix peeling, optimistic concurrency update chuẩn hóa timestamp, và audit trail logger | ✓ VERIFIED | 450 lines; exports `find_orders_for_mutation`, `record_order_history`, `mutate_order_with_lock`, `_normalize_ts` |
| `src/bot/keyboards.py` | Visual diff card, 14-char divider, confirmation & disambiguation keyboards | ✓ VERIFIED | 972 lines; exports `render_mutation_diff_card`, `build_mutation_confirm_keyboard`, `build_mutation_disambiguation_keyboard`, `build_mutation_status_keyboard`, `get_suggested_next_statuses`, `DIVIDER` |
| `src/bot/handlers/mutation.py` | Mutation flow controller, disambiguation, and suggestion selection | ✓ VERIFIED | 297 lines; exports `handle_mutation_flow`, `handle_mutation_selection`, `handle_status_suggestion_selection` |
| `src/bot/handlers/ingest.py` | 3-Way Intent Router integration in handle_text_order | ✓ VERIFIED | 266 lines; Dispatch tới `handle_mutation_flow` khi intent là `MUTATE` |
| `src/bot/handlers/callbacks.py` | Callback handler for `ord_mut_` actions | ✓ VERIFIED | 329 lines; Handles `cf`, `ca`, `sel`, `st` với TTL check và optimistic concurrency conflict handling |
| `src/bot/app.py` | Telegram callback handler registration | ✓ VERIFIED | `CallbackQueryHandler(handle_mutation_callback, pattern=r"^ord_mut_")` registered at group 0 |
| `tests/test_order_audit_trail.py` | Unit tests for DB schema, creator fields, order_history (min 40 lines) | ✓ VERIFIED | 243 lines, 7 unit tests passing |
| `tests/test_intent_router.py` | Unit tests for 3-way router, fast-path, reply context (min 50 lines) | ✓ VERIFIED | 91 lines, 6 unit tests passing |
| `tests/test_mutation_extractor.py` | Unit tests for 5-group delta extraction, regex chatter cleaning (min 50 lines) | ✓ VERIFIED | 150 lines, 6 unit tests passing |
| `tests/test_mutation_card_and_lock.py` | Unit tests for diff card, divider, concurrency lock, timestamp normalization (min 60 lines) | ✓ VERIFIED | 425 lines, 12 unit tests passing |
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
| `src/bot/handlers/mutation.py` | `matches` | `find_orders_for_mutation(db, ...)` | Có, truy vấn SQLite bảng `orders` theo trạng thái active và keyword đã tách prefix | ✓ FLOWING |
| `src/bot/handlers/mutation.py` | `delta` | `extract_mutation_delta(client, model, text)` | Có, gọi OpenAI client structured outputs với fallback regex JSON | ✓ FLOWING |
| `src/bot/keyboards.py` | `diff_text` | `delta_dict` so khớp với thuộc tính thực của `Order` | Có, tạo thẻ Trước ➡️ Sau cho các trường khác biệt | ✓ FLOWING |
| `src/bot/handlers/callbacks.py` | `fresh_order` | `mutate_order_with_lock(db, ...)` | Có, thực thi atomic UPDATE và trả về `Order` mới nhất từ DB | ✓ FLOWING |
| `src/db/orders.py` | `changes_json` | Dynamic diff dict giữa bản ghi hiện tại và delta mới | Có, lưu đầy đủ `{field: {"old": ..., "new": ...}}` vào `order_history` | ✓ FLOWING |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| Fast-path status parser nhận diện cú pháp ngắn | `parse_fast_path_status("huỷ đơn 12")` | `(12, OrderStatus.HUY_DON)` | ✓ PASS |
| Thẻ Visual Diff dùng divider 14 ký tự | `len(DIVIDER) == 14` | `True` (`──────────────`) | ✓ PASS |
| Thẻ Visual Diff hiển thị đúng thay đổi Before ➡️ After | `render_mutation_diff_card(order, delta.model_dump())` | Chứa `#1`, `0988776655`, `0912345678`, divider | ✓ PASS |
| Chuẩn hóa timestamp timestamp millisecond vs microsecond | `_normalize_ts("2026-10-25 10:00:00.024") == _normalize_ts("2026-10-25T10:00:00.024000")` | `True` | ✓ PASS |
| Lọc bỏ markdown code fences và text thừa khỏi JSON | `_clean_json_markdown("```json\n{\"target_order_id\": 12}\n```\n\nNote: test")` | `'{"target_order_id": 12}'` | ✓ PASS |
| Toàn bộ test suite dự án | `./.venv/bin/pytest -q` | `223 passed in 1.03s` | ✓ PASS |
| Test suite riêng cho Phase 07 (bao gồm test gap closure 07-03) | `./.venv/bin/pytest tests/test_*mutation* tests/test_intent_router.py tests/test_order_audit_trail.py tests/test_status_suggestions.py` | `46 passed in 0.43s` | ✓ PASS |

### Probe Execution

Không có kịch bản probe dạng shell script trong dự án (Phase 07 không yêu cầu probe scripts). Toàn bộ 46 test cases kiểm thử tự động của Phase 07 và 223 test cases toàn hệ thống đều pass.

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|------------|-------------|--------|----------|
| **MUT-01** | 07-01-PLAN | 3-Way Intent Router tách biệt chính xác với Tạo đơn và Tìm kiếm | ✓ SATISFIED | `classify_intent` trong `src/services/intent_router.py`, `tests/test_intent_router.py` |
| **MUT-02** | 07-01-PLAN, 07-03-PLAN | Tìm đúng đơn hàng cần sửa dựa trên từ khoá; khớp nhiều đơn hiển thị nút chọn 1-chạm; hỗ trợ từ xưng hô | ✓ SATISFIED | `find_orders_for_mutation` trong `src/db/orders.py`, `build_mutation_disambiguation_keyboard` trong `src/bot/keyboards.py` |
| **MUT-03** | 07-01-PLAN, 07-03-PLAN | LLM trích xuất delta thay đổi cho 5 nhóm trường: Trạng thái, Vận đơn, Ghi chú, Tiền COD/tổng, SĐT/Địa chỉ; cô lập JSON an toàn | ✓ SATISFIED | `OrderMutationDelta` trong `src/models/mutation.py`, `extract_mutation_delta` trong `src/services/mutation_extractor.py` |
| **MUT-04** | 07-02-PLAN, 07-03-PLAN | Thẻ so sánh Trước ➡️ Sau kèm nút Inline `[✅ Xác nhận sửa]` và `[❌ Huỷ]` (TTL 120s); chuẩn hóa timestamp khóa lạc quan | ✓ SATISFIED | `render_mutation_diff_card` trong `src/bot/keyboards.py`, `mutate_order_with_lock` trong `src/db/orders.py` |
| **MUT-05** | 07-02-PLAN, 07-03-PLAN | Hiển thị danh sách nút bấm trạng thái gợi ý 1-chạm khi câu chat chưa rõ trạng thái đích | ✓ SATISFIED | `get_suggested_next_statuses` và `build_mutation_status_keyboard` trong `src/bot/keyboards.py`, `handle_status_suggestion_selection` trong `src/bot/handlers/mutation.py` |

Không có yêu cầu mồ côi (orphaned requirements). Toàn bộ 5 mã yêu cầu MUT-01 đến MUT-05 đều được triển khai, kiểm thử tự động, và bổ sung khắc phục qua kế hoạch 07-03.

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| - | - | Không phát hiện TBD, FIXME, XXX | Clean | Không có nợ kỹ thuật tồn đọng |
| - | - | Không phát hiện TODO, HACK, PLACEHOLDER | Clean | Mã nguồn hoàn thiện, không chứa stub |
| - | - | Không phát hiện chuỗi văn bản tạm thời ("coming soon") | Clean | Không có chức năng bỏ dở |

### Human Verification Required

### 1. Phân định nhiều đơn khớp tên có từ đệm (UAT Test 2 Re-check)

**Test:** Tạo 2 đơn có cùng tên khách "Bác Ba", sau đó gửi tin nhắn `"đổi sđt khách Bác Ba thành 0988776655"`.
**Expected:** Bot bóc tách từ khoá "Bác Ba", loại bỏ từ đệm "khách", tìm thấy cả 2 đơn và hiển thị danh sách nút bấm inline 1-chạm dạng `[📦 Đơn #X - Bác Ba - ... - ...]`. Bấm 1 nút lập tức chuyển sang Thẻ Visual Diff với số điện thoại mới.
**Why human:** Xác nhận người dùng thực tế không bị lỗi "Không tìm thấy đơn" khi chat kèm từ xưng hô thông dụng.

### 2. Gợi ý trạng thái và xác nhận không bị xung đột giả (UAT Test 3 Re-check)

**Test:** Nhắn tin `"chuyển trạng thái đơn 1"` (không nêu rõ trạng thái đích). Bot hiện danh sách nút trạng thái gợi ý. Bấm chọn 1 trạng thái rồi bấm `[✅ Xác nhận sửa]`.
**Expected:** Đơn hàng được cập nhật thành công sang trạng thái mới. Không bị cảnh báo xung đột giả do lệch timestamp SQLite millisecond và Python microsecond.
**Why human:** Xác nhận tính ổn định của luồng cập nhật trạng thái 1-chạm trên Telegram.

### 3. Cảnh báo xung đột đồng thời thực tế (UAT Test 5 Re-check)

**Test:** Dùng 2 tài khoản Telegram cùng mở thẻ sửa đơn #1. Tài khoản A bấm xác nhận sửa địa chỉ, sau đó tài khoản B mới bấm xác nhận sửa số điện thoại.
**Expected:** Tài khoản B nhận thông báo cảnh báo xung đột nêu rõ người sửa, thời điểm và nội dung thay đổi của tài khoản A, hiển thị thẻ đơn mới nhất và không bị ghi đè dữ liệu cũ.
**Why human:** Xác minh trải nghiệm thông báo xung đột đồng thời trong môi trường nhiều quản trị viên thực tế.

### 4. Hiển thị Thẻ Visual Diff Trước ➡️ Sau trên Telegram Mobile

**Test:** Gửi tin nhắn `"sửa địa chỉ đơn 1 thành 456 Hai Bà Trưng, P. Tân Định, Q.1"` trên ứng dụng Telegram di động.
**Expected:** Thẻ Visual Diff hiển thị tiêu đề `[Mã đơn #1 - Khách: ...]`, đường kẻ divider 14 ký tự (`──────────────`) không bị ngắt/vỡ dòng trên màn hình điện thoại; chỉ in trường địa chỉ thay đổi dạng `📍 Địa chỉ: [Cũ] ➡️ [Mới]`; bên dưới có 2 nút inline `[✅ Xác nhận sửa]` và `[❌ Huỷ]`.
**Why human:** Đánh giá độ vừa vặn trực quan, chống vỡ dòng và thẩm mỹ thực tế trên client Telegram điện thoại cho đối tượng người lớn tuổi.

### 5. Hết hạn TTL 120s và chống bấm nhầm

**Test:** Gửi yêu cầu sửa đơn để hiển thị Thẻ Diff, đợi quá 2 phút (120s) rồi mới bấm `[✅ Xác nhận sửa]`.
**Expected:** Bot thông báo hết hạn 120s, gỡ bỏ toàn bộ bàn phím inline; cơ sở dữ liệu giữ nguyên không đổi.
**Why human:** Kiểm tra thời gian thực tế và trải nghiệm gỡ phím inline trên Telegram client.

### Gaps Summary

Tất cả 13 must-haves kỹ thuật (bao gồm 3 must-haves bổ sung từ kế hoạch đóng gap 07-03) đã được kiểm thử tự động đạt 100% (46/46 tests Phase 7, 223/223 tests toàn dự án). Kế hoạch đóng gap 07-03 đã giải quyết triệt để 3 root causes phát hiện từ đợt UAT trước:
1. `find_orders_for_mutation` đã bóc tách từ xưng hô/từ đệm ('khách', 'bác', 'anh', 'chị'...).
2. `_clean_json_markdown` cô lập regex `{...}` chống vỡ parse khi có trailing commentary text từ 9router.
3. `mutate_order_with_lock` chuẩn hóa timestamp so sánh về precision millisecond chống xung đột giả.

Hệ thống đã sẵn sàng cho bước kiểm thử người dùng (UAT) lần 2 trên Telegram để xác nhận trực quan các bản vá này.

---

_Verified: 2026-10-25T18:20:00Z_
_Verifier: Claude (gsd-verifier)_
