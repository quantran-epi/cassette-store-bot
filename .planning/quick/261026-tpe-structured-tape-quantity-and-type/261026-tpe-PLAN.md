---
phase: quick
plan: 261026-tpe
type: execute
wave: 1
depends_on: []
files_modified:
  - src/services/tape_parser.py
  - src/db/schema.py
  - src/db/connection.py
  - src/db/orders.py
  - src/models/order.py
  - src/models/extractor.py
  - src/models/mutation.py
  - src/services/extractor.py
  - src/services/mutation_extractor.py
  - src/services/order_search.py
  - src/bot/handlers/ingest.py
  - src/bot/handlers/callbacks.py
  - src/bot/keyboards.py
  - tests/test_tape_parser.py
  - tests/test_db_orders.py
  - tests/test_extractor.py
  - tests/test_mutation_extractor.py
  - tests/test_ingest.py
  - tests/test_orders_ui.py
  - tests/test_mutation_card_and_lock.py
  - tests/test_order_search.py
autonomous: true
requirements: [QUICK-TPE]
must_haves:
  truths:
    - "tape_quantity luôn bằng sum(qty của từng phần tử trong tapes_json); LLM trả tape_quantity=99 lệch với danh sách 6 cuốn thì DB lưu 6."
    - "Cụm trong ngoặc '(6 sony 90p)' / '(1 băng)' là phôi của các băng đã liệt kê, không cộng thêm: đơn #4 tính 6, không phải 11."
    - "Chỉ có một cài đặt heuristic: db.connection.tape_count() uỷ quyền cho services.tape_parser, không còn regex thứ hai."
    - "Khi mutation đổi items_text, cả 3 cột được tính lại trong cùng transaction; khi không đổi items_text thì 3 cột giữ nguyên."
    - "Đơn cũ giữ NULL; card hiển thị '—' chứ không phải '0'; tổng hợp chỉ cộng dữ liệu cấu trúc bằng COALESCE(tape_quantity, 0) và báo số đơn NULL, không fallback tape_count."
    - "Card xem trước, card chi tiết đơn, card diff mutation hiển thị breakdown phôi; prompt Text-to-SQL có 3 cột mới + quy tắc NULL."
  artifacts:
    - path: "src/services/tape_parser.py"
      provides: "parse_tapes_deterministic, build_tape_columns, format_tape_summary"
    - path: "src/db/schema.py"
      provides: "3 cột tape_quantity/tapes_json/tape_genre_json + ALTER TABLE"
    - path: "src/db/orders.py"
      provides: "Ghi 3 cột qua helper, đọc lại qua _row_to_order, recompute trong mutate_order_with_lock"
    - path: "src/models/order.py"
      provides: "TapeItem + 3 field domain"
    - path: "src/models/extractor.py"
      provides: "ExtractedOrder.tapes / .tape_genres (không có tape_quantity)"
    - path: "src/models/mutation.py"
      provides: "OrderMutationDelta.new_tapes / .new_tape_genres"
    - path: "src/services/order_search.py"
      provides: "Prompt 3 cột mới + NULL semantics + ví dụ đếm băng"
    - path: "src/bot/keyboards.py"
      provides: "Card chi tiết + diff hiển thị phôi/số băng"
    - path: "src/bot/handlers/ingest.py"
      provides: "Draft mang 3 giá trị helper + preview card phôi"
  key_links:
    - from: "src/db/connection.py"
      to: "src/services/tape_parser.py"
      via: "tape_count delegate"
      pattern: "parse_tapes_deterministic"
    - from: "src/db/orders.py"
      to: "src/services/tape_parser.py"
      via: "build_tape_columns trong create_order và mutate_order_with_lock"
      pattern: "build_tape_columns"
    - from: "src/bot/handlers/callbacks.py"
      to: "src/bot/handlers/ingest.py"
      via: "draft tapes/tape_genres/tape_quantity"
      pattern: "tape_quantity"
    - from: "src/services/order_search.py"
      to: "src/db/schema.py"
      via: "prompt tài liệu hoá cột"
      pattern: "tape_quantity"
---

<objective>
Thêm dữ liệu băng có cấu trúc vào đơn hàng: `tape_quantity` (tổng), `tapes_json` (breakdown phôi: label + qty), `tape_genre_json` (thể loại nội dung). Bóc tách khi tạo đơn và tính lại khi mutation đổi `items_text`. Đơn cũ giữ NULL, không backfill.

Purpose: `tape_count(items_text)` hiện là heuristic free-text và đếm sai đơn trộn danh sách đánh số với cụm ngoặc (đơn #4 thật: 11 thay vì 6). Cột có cấu trúc + một helper duy nhất loại bỏ khả năng lệch dữ liệu, và trả lời đúng "bao nhiêu băng / bao nhiêu băng Sony".
Output: module parser mới, 3 cột DB, schema LLM + prompt tạo/sửa đơn, draft → persist, card hiển thị, prompt Text-to-SQL. Không thêm dependency.
</objective>

<execution_context>
@$HOME/.claude/gsd-core/workflows/execute-plan.md
@$HOME/.claude/gsd-core/templates/summary.md
</execution_context>

<context>
@.planning/quick/261026-tpe-structured-tape-quantity-and-type/261026-tpe-DESIGN.md
@.planning/quick/261026-hnn-fix-photo-album-bug-on-order-creation-se/261026-hnn-SUMMARY.md
@.planning/STATE.md
@./CLAUDE.md
@src/db/schema.py
@src/db/connection.py
@src/db/orders.py
@src/models/order.py
@src/models/extractor.py
@src/models/mutation.py
@src/services/extractor.py
@src/services/mutation_extractor.py
@src/services/order_search.py
@src/bot/handlers/ingest.py
@src/bot/handlers/callbacks.py
@src/bot/keyboards.py
@tests/conftest.py
</context>

<tasks>

<task type="auto" tdd="true">
  <name>Task 1: Parser duy nhất + 3 cột schema + ghi/đọc DB (nền tảng, không LLM)</name>
  <files>src/services/tape_parser.py, src/db/schema.py, src/db/connection.py, src/db/orders.py, src/models/order.py, src/services/order_search.py, tests/test_tape_parser.py, tests/test_db_orders.py, tests/test_order_search.py</files>
  <behavior>
    - 6 chuỗi items_text thật trong cassette_store.db cho đúng số băng: (1) 6, (2) 3, (3) 1, (4) 6 — ngoặc thắng, (5) 6, (6) 1.
    - `parse_tapes_deterministic("")` → quantity 0, tapes []; chuỗi không có số ("Tuấn Vũ, Chế Linh") → 2; danh sách đánh số "1 Chế Linh, 2 Tuấn Vũ, 3 Duy Khánh" → 3.
    - Bất biến: mọi TapeBreakdown có `sum(t.qty for t in tapes) == quantity`.
    - `build_tape_columns` bỏ qua mọi con số `tape_quantity` do LLM trả (không có tham số/field này); tapes do LLM trả thắng fallback; tapes rỗng → fallback deterministic.
    - `create_order` ghi 3 cột; `get_order_by_id` đọc lại đúng tapes/tape_quantity/tape_genres; hàng cũ (NULL) đọc ra `tape_quantity is None`, `tapes == []`.
    - `tape_count()` vẫn là SQLite function nhưng uỷ quyền cho parser (một cài đặt duy nhất).
  </behavior>
  <action>
    Tạo `src/services/tape_parser.py`:
    1. Hằng `TAPE_UNITS = ("bang","cuon","phoi","dia","ud","ur","hf","sony","maxell","tdk","cd")`, regex unit-number dựng từ hằng này (không hardcode lặp), regex ngoặc `\(([^)]*)\)`. Comment `ponytail:` ghi rõ giới hạn: heuristic free-text, nâng cấp khi shop nhập form có cấu trúc.
    2. `@dataclass(frozen=True) class TapeBreakdown: quantity: int; tapes: list[TapeItem]`.
    3. `parse_tapes_deterministic(items_text: str | None) -> TapeBreakdown` theo đúng DESIGN:
       - Rỗng/toàn khoảng trắng → `TapeBreakdown(0, [])`.
       - Làm việc trên bản unaccent + lowercase (`remove_accents` từ `src.db.connection`; import trong hàm để tránh vòng lặp import — connection sẽ import parser).
       - Quy tắc 1 (ngoặc thắng): quét các cụm `(...)`; cụm CUỐI có chứa `<số> <unit>` quyết định. quantity = số đó; một TapeItem label = phần trong ngoặc bỏ số đếm và khoảng trắng/punctuation (vd "sony 90p", "bang"). Không cộng gì thêm.
       - Quy tắc 2: nếu không có ngoặc thoả, tách theo dấu phẩy; trong từng entry tìm `<số> <unit>`, label = phần từ chữ unit tới hết entry (bỏ số đếm, strip dấu câu/ngoặc), lowercase/unaccent. Cộng dồn qty theo label; quantity = tổng.
       - Quy tắc 3: nếu quy tắc 2 không khớp gì và mọi entry khớp `^\d+\s+\S` → mỗi entry 1 TapeItem qty 1 (label = entry bỏ số đầu), quantity = số entry.
       - Quy tắc 4: còn lại (text không rỗng) → mỗi entry phẩy 1 TapeItem qty 1; tối thiểu 1 item cho text không rỗng. quantity = tổng qty.
    4. `build_tape_columns(items_text: str | None, llm_tapes: list | None, llm_genres: list[str] | None) -> tuple[int, str, str]`:
       - Chuẩn hoá llm_tapes qua `TapeItem.model_validate` (chấp nhận dict hoặc model), bỏ item label rỗng/qty < 1; nếu còn item → tapes = chúng, quantity = sum(qty). Không nhận, không đọc trường tape_quantity nào từ LLM.
       - Nếu không có item hợp lệ → dùng `parse_tapes_deterministic(items_text)`.
       - genres = danh sách string strip/lowercase, bỏ rỗng.
       - Trả `(quantity, json.dumps([t.model_dump() for t in tapes], ensure_ascii=False), json.dumps(genres, ensure_ascii=False))`.
       - Bảo đảm bất biến bằng assert nội bộ: `assert quantity == sum(t.qty for t in tapes)`.
    5. `format_tape_summary(tape_quantity: int | None, tapes: list[TapeItem]) -> str`: `None` → `"—"`; ngược lại `f"{q} cuốn"` + ` (sony 90p ×6, ...)` khi có tapes. Hàm thuần text, dùng chung cho mọi card.
    Trong `src/models/order.py`: thêm `TapeItem(BaseModel)` (label: str, qty: int = Field(ge=1)) và 3 field `Order`: `tape_quantity: int | None = None`, `tapes: list[TapeItem] = Field(default_factory=list)`, `tape_genres: list[str] = Field(default_factory=list)`. TapeItem đặt ở đây (domain dùng trước) và `src/models/extractor.py` import lại — tránh 2 class trùng và tránh vòng lặp import.
    Trong `src/db/schema.py`: thêm 3 cột vào CREATE TABLE (`tape_quantity INTEGER`, `tapes_json TEXT`, `tape_genre_json TEXT`) và 3 nhánh `ALTER TABLE ... ADD COLUMN` trong block `PRAGMA table_info(orders)` hiện có.
    Trong `src/db/connection.py`: xoá `_TAPE_UNIT_RE` và thân heuristic; `tape_count(items_text)` chỉ còn `return parse_tapes_deterministic(items_text).quantity` (import từ `src.services.tape_parser`). Giữ `create_function("tape_count", 1, tape_count)`.
    Trong `src/db/orders.py`:
    - `_row_to_order`: đọc `tape_quantity` (None nếu cột vắng/NULL), parse `tapes_json` → `list[TapeItem]`, `tape_genre_json` → `list[str]`; dùng kiểm tra `"col" in row.keys()` như pattern `created_by_name` hiện có, try/except json → [].
    - `create_order`: gọi `qty, tapes_json, genres_json = build_tape_columns(order.items_text, order.tapes, order.tape_genres)` và thêm 3 cột vào INSERT (3 placeholder). Không dùng `order.tape_quantity` khi ghi — đây là điểm duy nhất bảo vệ bất biến.
    Trong `src/services/order_search.py` `_dict_to_order`: parse thêm `tape_quantity`, `tapes_json`, `tape_genre_json` từ row dict (guard key vắng) để card tìm kiếm đọc được breakdown.
    Trong tests/test_order_search.py: sửa `test_tape_count_heuristic` — kỳ vọng `tape_count("1 Ngọc Sơn vol1, 5 Băng ca sĩ khác (6 sony 90p)") == 11` thành `== 6` kèm comment "quy tắc ngoặc thắng — DESIGN 261026-tpe".
    Tạo `tests/test_tape_parser.py` (không cần DB): 6 chuỗi thật + empty + no-digit + track-numbering; assert bất biến sum(qty)==quantity cho mọi kết quả; test `build_tape_columns` với `ExtractedOrder.model_validate_json` chứa `"tape_quantity": 99` + tapes tổng 6 → trả 6; test LLM không có tapes → fallback khác 0 cho text không rỗng; test `format_tape_summary(None, []) == "—"`.
    Thêm vào `tests/test_db_orders.py`: round-trip `create_order` với `tapes=[TapeItem(label="sony 90p", qty=6)]` → `get_order_by_id` trả `tape_quantity == 6`, `tapes[0].label == "sony 90p"`; insert thẳng SQL không có 3 cột (mô phỏng đơn cũ) → đọc ra `tape_quantity is None`, `tapes == []`.
  </action>
  <verify>
    <automated>python -m pytest tests/test_tape_parser.py tests/test_db_orders.py tests/test_order_search.py -q</automated>
  </verify>
  <done>
    Parser trả đúng 6 chuỗi thật (đơn #4 = 6), bất biến sum==quantity luôn đúng, tape_count chỉ còn một cài đặt, create/read round-trip 3 cột, đơn cũ NULL, test cũ pass sau khi sửa kỳ vọng đơn #4.
  </done>
</task>

<task type="auto" tdd="true">
  <name>Task 2: Bóc tách LLM (tạo + sửa đơn), draft → persist, recompute khi items_text đổi</name>
  <files>src/models/extractor.py, src/services/extractor.py, src/models/mutation.py, src/services/mutation_extractor.py, src/bot/handlers/ingest.py, src/bot/handlers/callbacks.py, src/db/orders.py, tests/test_extractor.py, tests/test_mutation_extractor.py, tests/test_ingest.py, tests/test_mutation_card_and_lock.py</files>
  <behavior>
    - `ExtractedOrder` có `tapes: list[TapeItem]` và `tape_genres: list[str]`, KHÔNG có field `tape_quantity`; JSON LLM có `tape_quantity: 99` bị bỏ và DB lưu số do helper tính (6).
    - LLM không trả tapes → tạo đơn vẫn có tape_quantity > 0 cho items_text không rỗng (fallback deterministic).
    - Draft trong `process_extracted_order` mang `tape_quantity` (do helper tính), `tapes`, `tape_genres`; xác nhận lưu ghi đủ 3 cột.
    - Mutation đổi `items_text`: 3 cột được tính lại từ text mới + `new_tapes`/`new_tape_genres` trong cùng UPDATE/transaction, không trộn tapes cũ.
    - Mutation đổi field khác (status, địa chỉ, tiền): 3 cột không đổi.
    - Prompt mutation yêu cầu điền `new_tapes`/`new_tape_genres` khi có `new_items_text`.
  </behavior>
  <action>
    Trong `src/models/extractor.py`: thêm `tapes: list[TapeItem] = Field(default_factory=list, description=...)` (phôi: hãng/độ dài, mỗi item label + qty) và `tape_genres: list[str] = Field(default_factory=list, description=...)` (thể loại nội dung, [] khi không rõ). Import `TapeItem` từ `src.models.order`. Thêm `@field_validator("tapes", mode="before")` chuẩn hoá: bỏ item rỗng, qty < 1 → bỏ, label strip; `@field_validator("tape_genres", mode="before")` strip + bỏ rỗng. Không thêm field `tape_quantity` (pydantic mặc định bỏ extra → con số LLM tự động bị loại).
    Trong `src/services/extractor.py` `SYSTEM_PROMPT`: thêm mục hướng dẫn sau `items_text` (giữ nguyên các mục đánh số hiện có, có thể thành 4b):
    - `tapes`: breakdown PHÔI băng shop phải lấy từ kho — mỗi item `{label, qty}`; label là cụm hãng/loại + độ dài giữ nguyên văn ("sony 90p", "ud xám 90p", "maxell 90p"), không bịa, không gộp nhầm ca sĩ vào phôi.
    - `tape_genres`: thể loại nội dung best effort ("nhạc vàng", "hải ngoại", "tình ca"); không rõ thì [].
    - Quy tắc ngoặc: "(6 sony 90p)", "(1 băng)" là phôi cho các băng đã liệt kê — qty của phôi đó là số trong ngoặc, KHÔNG cộng dồn với số khác.
    - Tuyệt đối KHÔNG trả `tape_quantity`; hệ thống tự tính tổng.
    Thêm `"tapes"` và `"tape_genres"` vào ít nhất 2 ví dụ few-shot (Ví dụ 1: `[{"label":"ud xám 90p","qty":3}]`, `["nhạc vàng"]`; Ví dụ 2: `[{"label":"chế linh","qty":2}]` hoặc phôi tương ứng, `[]`).
    Trong `src/models/mutation.py`: thêm `new_tapes: list[TapeItem] | None = None` và `new_tape_genres: list[str] | None = None`, mô tả "chỉ điền khi new_items_text thay đổi". Import TapeItem từ `src.models.order`.
    Trong `src/services/mutation_extractor.py` prompt: thêm rule ở nhóm 5 — khi trích `new_items_text`, đồng thời điền `new_tapes` (breakdown phôi label+qty) và `new_tape_genres`; nếu chỉ sửa field khác thì để null. Nhắc lại quy tắc ngoặc như prompt tạo đơn.
    Trong `src/bot/handlers/ingest.py` `process_extracted_order`: trước khi dựng draft, gọi `qty, tapes_json, genres_json = build_tape_columns(extracted.items_text, extracted.tapes, extracted.tape_genres)` (import từ `src.services.tape_parser`), lưu draft các key `"tape_quantity": qty`, `"tapes": json.loads(tapes_json)`, `"tape_genres": json.loads(genres_json)` (import json).
    Trong `src/bot/handlers/callbacks.py` nhánh `cf`: khi dựng `Order`, truyền `tapes=[TapeItem(**t) for t in draft.get("tapes") or []]` (hoặc để model validate), `tape_genres=draft.get("tape_genres") or []`, `tape_quantity=draft.get("tape_quantity")`. `create_order` vẫn tự tính lại qua helper — draft chỉ là nguồn LLM, không phải nguồn chân lý.
    Trong `src/db/orders.py` `mutate_order_with_lock`, sau vòng lặp build `fields/params/changes` và ngay TRƯỚC khi append `updated_at`: nếu `"items_text" in changes` thì lấy `new_text = changes["items_text"]["new"]`, `new_tapes = delta_dict.get("new_tapes") or delta_dict.get("tapes")`, `new_genres = delta_dict.get("new_tape_genres") or delta_dict.get("tape_genres")`, gọi `build_tape_columns(new_text, new_tapes, new_genres)` và append 3 cặp `tape_quantity = ?`, `tapes_json = ?`, `tape_genre_json = ?` vào cùng UPDATE (cùng transaction với audit insert). Không đổi gì khi items_text không có trong `changes`; các key `new_tapes`/`new_tape_genres` tự động bị bỏ qua trong vòng lặp cột vì không phải cột trong `row_keys`.
    Tests:
    - `tests/test_extractor.py`: thêm test tier-2 JSON có `"tape_quantity": 99` + `"tapes":[{"label":"sony 90p","qty":6}]` → `ExtractedOrder` không có attr `tape_quantity`, `res.tapes[0].qty == 6`; test tapes rỗng → `build_tape_columns` fallback khác 0.
    - `tests/test_mutation_extractor.py`: assert prompt chứa "new_tapes" và "new_tape_genres".
    - `tests/test_ingest.py`: test `process_extracted_order` lưu draft có `tape_quantity > 0` và `tapes`; test confirm `ord:cf` persist 3 cột (đọc lại `list_orders_by_status` thấy `tape_quantity == 6` cho items "6 sony 90p").
    - `tests/test_mutation_card_and_lock.py`: test đổi chỉ `items_text` (vd "1 cuốn" → "6 sony 90p") → `tape_quantity == 6`, `tapes_json` chứa "sony 90p", giá trị cũ không còn; test đổi `shipping_address` → 3 cột giữ nguyên giá trị trước đó.
  </action>
  <verify>
    <automated>python -m pytest tests/test_extractor.py tests/test_mutation_extractor.py tests/test_ingest.py tests/test_mutation_handler_flow.py tests/test_mutation_card_and_lock.py -q</automated>
  </verify>
  <done>
    LLM bóc tapes/genres, không thể gửi tape_quantity; draft mang 3 giá trị helper; tạo đơn ghi 3 cột; mutation đổi items_text tính lại cả 3 trong cùng transaction, field khác không đụng; test mocked-LLM pass.
  </done>
</task>

<task type="auto" tdd="true">
  <name>Task 3: Hiển thị card (preview, chi tiết, diff) + prompt Text-to-SQL với NULL semantics</name>
  <files>src/bot/handlers/ingest.py, src/bot/keyboards.py, src/services/order_search.py, tests/test_ingest.py, tests/test_orders_ui.py, tests/test_mutation_card_and_lock.py, tests/test_order_search.py</files>
  <behavior>
    - Preview card có dòng PHÔI BĂNG với số cuốn + breakdown từ draft.
    - Card chi tiết đơn hiển thị phôi + số băng; đơn cũ (`tape_quantity is None`) hiển thị "—", không phải "0".
    - Card diff mutation khi items_text đổi hiển thị số băng cũ ➡️ mới (cũ là "—" nếu NULL).
    - Prompt Text-to-SQL có `tape_quantity`, `tapes_json`, `tape_genre_json`, quy tắc NULL = "đơn cũ chưa có dữ liệu số lượng", `COALESCE`, và 2 ví dụ "bao nhiêu băng" / "bao nhiêu băng Sony".
    - Toàn bộ test cũ pass (không phá layout/escape).
  </behavior>
  <action>
    Trong `src/bot/handlers/ingest.py` `render_preview_card`: sau dòng `📼 <b>BĂNG CASSETTE:</b>` thêm dòng `📼 <b>PHÔI BĂNG:</b> ...` dùng `format_tape_summary(draft.get("tape_quantity"), [TapeItem(**t) for t in draft.get("tapes") or []])`, html.escape phần text; chỉ thêm khi draft có `tape_quantity` khác None hoặc tapes không rỗng.
    Trong `src/bot/keyboards.py` `render_order_detail_card`: thêm dòng `📼 <b>PHÔI BĂNG:</b> {html.escape(format_tape_summary(order.tape_quantity, order.tapes))}` ngay sau dòng BĂNG CASSETTE — luôn hiển thị để đơn cũ hiện "—" (đúng NULL semantics). Import `format_tape_summary` từ `src.services.tape_parser`, `TapeItem` nếu cần.
    Trong `render_mutation_diff_card`, nhánh items (mục 7): sau dòng BĂNG CASSETTE cũ ➡️ mới, tính `qty, _, _ = build_tape_columns(str(new_items), delta_dict.get("new_tapes") or delta_dict.get("tapes"), delta_dict.get("new_tape_genres") or delta_dict.get("tape_genres"))`, render `old_display = order.tape_quantity if order.tape_quantity is not None else "—"`, thêm dòng `📼 <b>SỐ BĂNG:</b> {old_display} ➡️ <b>{qty}</b>`. Không thêm gì khi items_text không đổi (giữ test "BĂNG" not in card).
    Trong `src/services/order_search.py` `SYSTEM_PROMPT_TEXT_TO_SQL_TEMPLATE`: cập nhật schema `Table orders` thêm 3 cột kèm comment:
    `tape_quantity INTEGER  -- tổng số băng; NULL = đơn cũ chưa có dữ liệu số lượng`,
    `tapes_json TEXT        -- JSON breakdown phôi: [{"label":"sony 90p","qty":6}]`,
    `tape_genre_json TEXT   -- JSON thể loại nội dung: ["nhạc vàng"]`.
    Thay rule 7 hiện tại bằng:
    - Câu hỏi SỐ LƯỢNG BĂNG dùng `tape_quantity`; đơn cũ NULL KHÔNG fallback `tape_count(items_text)` vì user chọn để trống. Tổng dùng `COALESCE(tape_quantity, 0)`.
    - NULL nghĩa là "đơn cũ chưa có dữ liệu số lượng". Cùng query phải trả thêm `COUNT(*) FILTER (WHERE tape_quantity IS NULL) AS orders_without_tape_data`; summary phải nói rõ có bao nhiêu đơn cũ chưa được tính.
    - Ví dụ "có bao nhiêu băng" → `SELECT SUM(COALESCE(tape_quantity, 0)) AS total_tapes, COUNT(*) FILTER (WHERE tape_quantity IS NULL) AS orders_without_tape_data FROM orders`.
    - Ví dụ "bao nhiêu băng Sony" → `SELECT SUM(COALESCE(tape_quantity, 0)) AS total_sony_tapes, COUNT(*) FILTER (WHERE tape_quantity IS NULL) AS orders_without_tape_data FROM orders WHERE tapes_json LIKE '%sony%' OR tape_quantity IS NULL`.
    - Hỏi thể loại → lọc `tape_genre_json LIKE '%nhạc vàng%'`.
    Tests:
    - `tests/test_ingest.py` `test_render_preview_card_layout_and_buttons`: thêm tapes vào draft và assert dòng "PHÔI BĂNG" + breakdown xuất hiện.
    - `tests/test_orders_ui.py`: test card chi tiết với `Order(tape_quantity=None)` → chứa "—"; với `tape_quantity=6, tapes=[TapeItem(label="sony 90p", qty=6)]` → chứa "6 cuốn" và "sony 90p".
    - `tests/test_mutation_card_and_lock.py`: diff card khi đổi items_text → chứa "SỐ BĂNG:" và "➡️"; khi không đổi items_text → không có "SỐ BĂNG:".
    - `tests/test_order_search.py`: mở rộng/ thêm test prompt: sys_prompt chứa "tape_quantity", "tapes_json", "tape_genre_json", "COALESCE", "đơn cũ chưa có dữ liệu số lượng", "total_sony_tapes"; user prompt "<query>" giữ nguyên.
  </action>
  <verify>
    <automated>python -m pytest tests/test_ingest.py tests/test_orders_ui.py tests/test_mutation_card_and_lock.py tests/test_order_search.py -q</automated>
  </verify>
  <done>
    Preview/chi tiết/diff hiển thị phôi và số băng với "—" cho NULL; prompt Text-to-SQL tài liệu hoá 3 cột, COALESCE và NULL rule với 2 ví dụ; test cũ + mới pass.
  </done>
</task>

</tasks>

<threat_model>
## Trust Boundaries

| Boundary | Description |
|----------|-------------|
| Tin nhắn chat -> LLM extraction | Model có thể trả qty/label/tổng sai hoặc bịa |
| LLM output -> DB write | tapes/genres đi vào cột JSON và số tổng |
| User mutation -> DB UPDATE | `new_items_text`/`new_tapes` do LLM sinh, ghi đè dữ liệu cũ |
| DB rows -> card HTML | label/tên phôi do khách nhập, render vào Telegram HTML |
| Câu hỏi chat -> Text-to-SQL | SQL do LLM sinh từ câu hỏi |

## STRIDE Threat Register

| Threat ID | Category | Component | Disposition | Mitigation Plan |
|-----------|----------|-----------|-------------|-----------------|
| T-TPE-01 | Tampering | build_tape_columns / create_order | mitigate | Tổng luôn tính bằng sum(qty) trong helper, assert bất biến; schema LLM không có field tape_quantity nên số model trả bị pydantic loại |
| T-TPE-02 | Tampering | mutate_order_with_lock | mitigate | Recompute trong cùng UPDATE + transaction khi items_text đổi; không merge tapes cũ |
| T-TPE-03 | Information Disclosure | JSON columns đọc ra card | mitigate | `html.escape` mọi label/genre trước khi render; không render JSON thô |
| T-TPE-04 | Injection | build_tape_columns JSON | mitigate | `json.dumps(ensure_ascii=False)` với object đã validate qua TapeItem; không nối chuỗi SQL, chỉ bind tham số |
| T-TPE-05 | Denial of Service | parser regex | accept | Regex tuyến tính trên `items_text` ngắn (< vài KB), không eval; ponytail ghi giới hạn heuristic |
| T-TPE-06 | Tampering | Text-to-SQL prompt | mitigate | Prompt chỉ thêm cột; sanitize/validate read-only SELECT hiện có vẫn chạy trước khi execute |
</threat_model>

<verification>
1. `python -m pytest tests/test_tape_parser.py tests/test_db_orders.py -q`
2. `python -m pytest tests/test_extractor.py tests/test_mutation_extractor.py tests/test_ingest.py tests/test_mutation_handler_flow.py tests/test_mutation_card_and_lock.py -q`
3. `python -m pytest tests/test_orders_ui.py tests/test_order_search.py -q`
4. `python -m pytest tests/ -q` (toàn bộ phải pass; 2 warning PTB JobQueue là pre-existing)
</verification>

<success_criteria>
- `tape_quantity == sum(qty trong tapes_json)` ở mọi write path; LLM trả số lệch bị bỏ.
- Đơn #4 thật ("1 Ngọc Sơn vol1, 5 Băng ca sĩ khác (6 sony 90p)") tính 6.
- Chỉ một cài đặt heuristic: `tape_count` uỷ quyền parser.
- Mutation đổi items_text → 3 cột recompute; đổi field khác → không đụng.
- Đơn cũ NULL, card hiện "—", tổng hợp COALESCE, prompt có NULL rule.
- Không thêm dependency; toàn bộ `python -m pytest tests/ -q` pass.
</success_criteria>

<output>
Implement trực tiếp trong working tree. Không commit. Không revert các thay đổi chưa commit của quick task 261026-hnn. Báo lại file đã sửa, kết quả pytest từng bước, và ghi chú nếu phải điều chỉnh kỳ vọng test cũ (đơn #4 11 → 6).
</output>
