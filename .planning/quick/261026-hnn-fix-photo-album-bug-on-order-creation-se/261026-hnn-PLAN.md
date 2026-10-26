---
phase: quick
plan: 261026-hnn
type: execute
wave: 1
depends_on: []
files_modified:
  - src/bot/handlers/ingest.py
  - src/bot/handlers/search.py
  - src/bot/keyboards.py
  - src/bot/app.py
  - src/db/customers.py
  - src/db/connection.py
  - src/services/order_search.py
  - tests/test_ingest.py
  - tests/test_customer_search.py
  - tests/test_order_search.py
autonomous: true
requirements: [QUICK-HNN]
must_haves:
  truths:
    - "Gửi album 3 ảnh kèm caption tạo đúng 1 bản nháp với đủ 3 photo_file_ids, preview ghi '3 ảnh'"
    - "Handler ảnh không chặn update pump: debounce chạy nền, update kế tiếp vẫn được xử lý ngay"
    - "Câu 'tìm khách <tên|SĐT|địa chỉ>' trả hồ sơ khách hoặc danh sách chọn, không gọi LLM"
    - "Câu hỏi số lượng băng dùng tape_count(items_text) và SQLite function đăng ký trong connection"
    - "Prompt Text-to-SQL có quy tắc nhóm theo giờ/ngày trong tuần với '+7 hours' và ví dụ khung giờ"
    - "Summary MIXED không bao giờ nói thiếu danh sách chi tiết; bộ lọc hậu kỳ xoá câu đó trước khi gửi"
  artifacts:
    - path: "src/bot/handlers/ingest.py"
      provides: "Debounce album chạy nền, không block update pump"
    - path: "src/db/customers.py"
      provides: "search_customers + is_customer_search deterministic"
    - path: "src/bot/handlers/search.py"
      provides: "Route customer search trước LLM, render hồ sơ/chọn khách, callback cus_pg/cus_v/cus_bk"
    - path: "src/bot/keyboards.py"
      provides: "render_customer_detail_card hỗ trợ callback điều hướng tuỳ biến"
    - path: "src/db/connection.py"
      provides: "SQLite function tape_count(items_text)"
    - path: "src/services/order_search.py"
      provides: "Prompt tape_count + hour/weekday rules, hậu kỳ xoá câu thiếu danh sách"
    - path: "tests/test_ingest.py"
      provides: "Regression: album 3 ảnh, chờ finalizer nền"
    - path: "tests/test_customer_search.py"
      provides: "Regression: tìm khách theo tên/SĐT/địa chỉ"
    - path: "tests/test_order_search.py"
      provides: "Regression: tape_count, prompt rules, summary post-filter"
  key_links:
    - from: "src/bot/handlers/search.py"
      to: "src/db/customers.py"
      via: "search_customers trước run_order_search"
      pattern: "search_customers"
    - from: "src/bot/handlers/search.py"
      to: "src/bot/keyboards.py"
      via: "render_customer_detail_card"
      pattern: "render_customer_detail_card"
    - from: "src/bot/app.py"
      to: "src/bot/handlers/search.py"
      via: "CallbackQueryHandler pattern ^cus_"
      pattern: "\\^cus_"
    - from: "src/db/connection.py"
      to: "src/services/order_search.py"
      via: "tape_count documented in Text-to-SQL prompt"
      pattern: "tape_count"
---

<objective>
Sửa 4 nhóm lỗi tra cứu/đơn hàng: album nhiều ảnh chỉ lưu ảnh đầu, không tra được khách, câu hỏi số lượng băng trả số đơn, câu hỏi khung giờ trả "không có thông tin", và kết quả MIXED tự nói thiếu danh sách chi tiết.

Purpose: Các lỗi này đều làm bác chủ nhận câu trả lời sai hoặc mất dữ liệu ảnh; INVESTIGATION.md đã xác định nguyên nhân gốc, plan này thực thi đúng phần "Required fix" của từng lỗi.
Output: ingest.py, search.py, keyboards.py, app.py, customers.py, connection.py, order_search.py, và test hồi quy tương ứng. Không thêm dependency.
</objective>

<execution_context>
@$HOME/.claude/gsd-core/workflows/execute-plan.md
@$HOME/.claude/gsd-core/templates/summary.md
</execution_context>

<context>
@.planning/STATE.md
@.planning/quick/261026-hnn-fix-photo-album-bug-on-order-creation-se/261026-hnn-INVESTIGATION.md
@./CLAUDE.md
@src/bot/handlers/ingest.py
@src/bot/handlers/search.py
@src/bot/keyboards.py
@src/bot/app.py
@src/db/customers.py
@src/db/connection.py
@src/db/orders.py
@src/services/order_search.py
@tests/test_ingest.py
@tests/test_order_search.py
@tests/conftest.py
</context>

<tasks>

<task type="auto" tdd="true">
  <name>Task 1: Album ảnh — debounce chạy nền, không chặn update pump (Issue 1)</name>
  <files>src/bot/handlers/ingest.py, tests/test_ingest.py</files>
  <behavior>
    - Ba update album gửi tuần tự (không gather) vẫn gom đủ 3 photo_file_ids vào 1 draft và gửi đúng 1 preview "3 ảnh".
    - Handler album trả về ngay sau khi khởi tạo buffer; phần đợi debounce + extract chạy trong task nền.
    - Chỉ schedule finalizer một lần cho mỗi media_group_id: lưu task handle trên buffer, photo sau chỉ append và return.
    - Dedupe `_PROCESSED_MEDIA_GROUPS` (60s prune) giữ nguyên: finalizer chỉ đánh dấu sau khi xử lý xong.
    - Album không caption: đúng 1 tin nhắn nhắc gửi caption, không tạo draft.
    - Ảnh đơn (media_group_id = None) không đổi hành vi.
  </behavior>
  <action>
    Trong src/bot/handlers/ingest.py:
    1. Tách toàn bộ thân khối media-group hiện tại thành coroutine `_finalize_media_group(update, context, media_group_id)` (module level, async). Nội dung: `await asyncio.sleep(MEDIA_GROUP_DEBOUNCE_SECONDS)`; lấy buffer từ `_MEDIA_GROUP_BUFFERS`; chọn `effective_update = buf["caption_update"] or buf["first_update"]`; nếu không có caption thì reply nhắc caption rồi return; ngược lại gọi `_extract_and_process_photo_order(effective_update, context, buf["caption"], list(buf["photos"]))`. Bao toàn bộ trong try/except Exception để log `logger.exception` (task nền không được im lặng nuốt lỗi, và không làm chết task khác); finally: pop buffer, set `_PROCESSED_MEDIA_GROUPS[media_group_id] = time.time()`.
    2. Thêm helper `_spawn_finalizer(context, coro) -> asyncio.Task`: nếu `getattr(context, "application", None)` là instance của `telegram.ext.Application` thì dùng `context.application.create_task(coro)` (PTB xử lý exception qua error handler, tự await khi stop); ngược lại dùng `asyncio.create_task(coro)`. Lý do fallback: test dùng MagicMock context, và PTB có thể không gắn application (xem test hiện có).
    3. Trong `handle_photo_order`, nhánh media group: sau khi khởi tạo buffer (giữ các key photos/caption/caption_update/first_update), gán `buf["task"] = _spawn_finalizer(context, _finalize_media_group(update, context, media_group_id))` và return ngay — xoá hoàn toàn `await asyncio.sleep(...)` khỏi handler. Không đổi thứ tự guard: prune > `_PROCESSED_MEDIA_GROUPS` return > buffer-exists append/return > tạo buffer + schedule.
    4. Không bật `concurrent_updates` trong app.py; giữ update tuần tự để `user_data` an toàn.
    5. Cập nhật tests/test_ingest.py: sau `asyncio.gather(...)` thêm `await asyncio.sleep(0.2)` (debounce đã patch 0.05) TRƯỚC khi `monkeypatch.undo()`, để finalizer nền hoàn tất. Áp dụng cho `test_media_group_album_bundled_single_preview` và `test_media_group_album_missing_all_captions`. Thêm test mới `test_media_group_sequential_updates_do_not_drop_photos`: gọi `await handle_photo_order(update1, context)`, rồi update2, update3 tuần tự (mô phỏng pump thật), `await asyncio.sleep(0.2)`, assert 1 draft với đủ 3 file_id và preview "3 ảnh".
  </action>
  <verify>
    <automated>python -m pytest tests/test_ingest.py -q</automated>
  </verify>
  <done>
    Handler album trả về trước debounce; 3 update tuần tự vẫn cho 1 draft đủ 3 ảnh; album thiếu caption chỉ 1 cảnh báo; test cũ và test mới pass.
  </done>
</task>

<task type="auto" tdd="true">
  <name>Task 2: Tra cứu khách deterministic trước pipeline Text-to-SQL (Issue 2)</name>
  <files>src/db/customers.py, src/bot/handlers/search.py, src/bot/keyboards.py, src/bot/app.py, tests/test_customer_search.py</files>
  <behavior>
    - `tìm khách 0903626566`, `tìm khách anh Tuấn`, `tìm khách Hà Nội`, và tổ hợp tên + SĐT + địa chỉ đều trả hồ sơ/chọn khách, không gọi LLM.
    - Token không dấu, whole-word, accent-insensitive; SĐT khớp một phần (vd '987') vẫn tìm được qua LIKE trên json_each(phones).
    - 1 khách: card hồ sơ + thống kê + lịch sử đơn trang 1 + nút phân trang `cus_pg:{customer_id}:{page}` và quay lại `cus_bk:{search_id}`.
    - Nhiều khách: card chọn gọn, mỗi khách 1 nút `cus_v:{customer_id}:{search_id}`.
    - 0 khách: card rỗng thân thiện gợi ý tìm theo tên/SĐT/địa chỉ.
  </behavior>
  <action>
    Trong src/db/customers.py:
    1. Thêm hằng `_CUSTOMER_FILLERS = {"khach","khách","tim","tìm","tra","cuu","cứu","kiem","kiểm","xem","cua","của","cho","sdt","so","số","dien","điện","thoai","thoại","ten","tên","dia","địa","chi","chỉ","hang","hàng"}` và `_HONORIFICS = {"anh","chi","chị","bac","bác","ong","ông","co","cô","chu","chú","em"}`.
    2. Thêm `async def search_customers(db, query: str, limit: int = 5) -> list[Customer]`: dùng `remove_accents` (import từ src.db.connection) tách token theo khoảng trắng; bỏ filler + honorific; nếu rỗng thì dùng cả câu đã unaccent làm 1 token. Query SQL trên bảng customers với haystack `(name || ' ' || phones || ' ' || addresses || ' ' || notes)`; mỗi token một điều kiện `(word_match(haystack, ?) = 1 OR EXISTS (SELECT 1 FROM json_each(c.phones) p WHERE p.value LIKE ?))` để SĐT khớp một phần; AND toàn bộ token; `ORDER BY id LIMIT ?`. Trả `[_row_to_customer(r) ...]`.
    3. Thêm `def is_customer_search(query: str) -> bool`: unaccent + lowercase; trả True khi câu chứa từ 'khach' VÀ (bắt đầu bằng 'khach' hoặc bắt đầu bằng một trong các tiền tố tìm kiếm 'tim','tra cuu','kiem tra','xem'). Không dùng LLM.
    Trong src/bot/keyboards.py: mở rộng `render_customer_detail_card` bằng 2 tham số keyword-only tuỳ chọn `nav_callback: Callable[[int], str] | None = None` và `back_callback: str | None = None`. Nếu `nav_callback` có thì nút Trước/Sau dùng nó thay cho `ord:cs:{safe_draft_id}:{page}`; nếu `back_callback` có thì thêm nút "🔙 Quay lại kết quả" với callback đó (thay cho nút "Quay lại đơn đang tạo"). Mặc định không truyền = hành vi cũ nguyên vẹn cho callbacks.py.
    Trong src/bot/handlers/search.py:
    4. Import `get_customer_by_id, search_customers, is_customer_search` từ src.db.customers; `count_orders_by_customer_id, get_customer_order_stats, get_orders_by_customer_id` từ src.db.orders; `render_customer_detail_card` từ keyboards.
    5. Thêm helper render: `_render_customer_empty_card(query)` (text gợi ý tên/SĐT/địa chỉ + keyboard `sch_new`); `_render_customer_chooser(customers, search_id)` (mỗi khách 1 dòng: tên + SĐT đầu, callback `cus_v:{id}:{search_id}`, kèm nút Huỷ `sch_cancel`); `async _render_customer_detail(context, customer_id, page, search_id)` mở `_get_active_db_context`, lấy customer, stats, count, orders trang `page` (page_size 5), dựng card qua `render_customer_detail_card(..., draft_id=None, nav_callback=lambda p: f"cus_pg:{customer_id}:{p}", back_callback=f"cus_bk:{search_id}")`.
    6. Trong `process_search_query`, sau khi resolve `active_db` và TRƯỚC phần gọi `run_order_search` (và trước kiểm tra openai_client): nếu `is_customer_search(query_text)` thì gọi `search_customers(active_db, query_text)`; lưu snapshot `context.user_data.setdefault("customer_searches", {})[search_id] = {"query": query_text, "ids": [c.id for c in matches]}` (search_id tạo bằng uuid như nhánh cũ); 1 kết quả → `_render_customer_detail` trang 1, reply HTML; nhiều → chooser; 0 → empty card; return. Không gọi LLM, không gửi typing action.
    7. Thêm `async def handle_customer_callback(update, context)`: `query.answer()`; `cus_v:{cid}:{sid}` → set `context.user_data["customer_search_active"] = sid`, render detail trang 1; `cus_pg:{cid}:{page}` → render detail với page đó, dùng `customer_search_active` cho back_callback; `cus_bk:{sid}` → lấy lại snapshot ids, fetch customers theo id (`get_customer_by_id` từng id), render chooser (nếu snapshot mất thì báo hết hạn như nhánh sch). Dùng `_safe_edit`, parse_mode HTML.
    Trong src/bot/app.py: đăng ký `CallbackQueryHandler(handle_customer_callback, pattern=r"^cus_")` ở group 0, import từ search handler, đặt cạnh handler `^sch_`.
    Tạo tests/test_customer_search.py (dùng fixture `test_db`): test `test_is_customer_search_detects_forms` (các câu đúng/sai); `test_search_customers_by_name_phone_address` seed 3 khách (đủ tên/SĐT/địa chỉ như DB thật) và assert tìm theo từng token, từ không dấu, SĐT một phần, tổ hợp; `test_process_search_query_routes_customer_without_llm` (MagicMock client, assert `openai_client.chat.completions.create` không được gọi, reply chứa tên khách); `test_customer_chooser_and_paging_callbacks` (2 khách cùng địa chỉ → chooser có 2 nút cus_v; gọi cus_v rồi cus_pg trang 2 với 6 đơn → hiển thị "Trang 2/2").
  </action>
  <verify>
    <automated>python -m pytest tests/test_customer_search.py tests/test_order_search.py -q</automated>
  </verify>
  <done>
    Tìm khách theo tên/SĐT/địa chỉ (mọi tổ hợp) trả hồ sơ hoặc chooser, không gọi LLM; callback cus_v/cus_pg/cus_bk hoạt động và đã đăng ký; card hồ sơ cũ trong callbacks.py giữ nguyên hành vi.
  </done>
</task>

<task type="auto" tdd="true">
  <name>Task 3: tape_count + prompt giờ/ngày + chặn summary thiếu danh sách (Issues 3a, 3b, 4)</name>
  <files>src/db/connection.py, src/services/order_search.py, tests/test_order_search.py</files>
  <behavior>
    - `tape_count('6 băng maxell 90p')` = 6; `tape_count('1 băng như ảnh ko dán tem')` = 1; `tape_count('1 Ngọc Sơn vol1, 5 Băng ca sĩ khác (6 sony 90p)')` = 11.
    - Danh sách chỉ toàn `N <title>` (track numbering) mỗi dòng tính 1; danh sách không có unit word vẫn không trả 0.
    - Prompt Text-to-SQL có `tape_count`, `strftime('%H', ..., '+7 hours')`, `strftime('%w', ...)`, quy tắc '+7 hours' cho mọi bucket, và ví dụ "khung giờ nào bán được nhiều đơn nhất".
    - Summary chứa câu "danh sách chi tiết thì chưa có bác nhé" bị xoá trước khi trả; nếu xoá hết thì fallback summary gốc.
  </behavior>
  <action>
    Trong src/db/connection.py:
    1. Thêm `def tape_count(items_text: str | None) -> int` với heuristic: chuẩn hoá unaccent + lowercase; tìm mọi cặp số + đơn vị bằng regex `r"(\d+)\s*(?:bang|cuon|phoi|dia|ud|ur|hf|sony|maxell|tdk|cd)\b"` và cộng dồn (text đã unaccent nên 'băng'→'bang'). Tách items theo dấu phẩy; nếu MỌI mục khớp `^\d+\s+\S` thì coi là đánh số track: cộng 1 cho mỗi mục chưa được cộng bởi unit regex (mục đã khớp unit giữ nguyên số đã cộng). Nếu tổng = 0 và items_text không rỗng: trả số mục phẩy (tối thiểu 1). Thêm comment `ponytail:` ghi rõ đây là ước lượng từ free-text, nâng cấp bằng field số lượng có cấu trúc khi schema đổi.
    2. Đăng ký trong `get_db_connection`: `await db.create_function("tape_count", 1, tape_count)` cạnh unaccent/word_match.
    Trong src/services/order_search.py:
    3. Thêm vào `SYSTEM_PROMPT_TEXT_TO_SQL_TEMPLATE` (giữ đánh số hiện có, chèn trước mục thời gian hoặc thành mục 7-9):
       - Câu hỏi về SỐ LƯỢNG BĂNG/CUỐN/PHÔI (không phải số đơn) phải dùng `SUM(tape_count(o.items_text)) AS total_tapes`, và câu trả lời dùng cột này; ví dụ "có bao nhiêu băng" → `SELECT SUM(tape_count(items_text)) AS total_tapes FROM orders`.
       - Nhóm theo khung giờ: `strftime('%H', o.created_at, '+7 hours')` rồi GROUP BY + ORDER BY count DESC; nhóm theo thứ: `strftime('%w', o.created_at, '+7 hours')`; nhấn mạnh created_at lưu UTC nên MỌI biểu thức bucket phải có '+7 hours'.
       - Ví dụ mẫu đầy đủ: "khung giờ nào bán được nhiều đơn nhất" → `SELECT strftime('%H', created_at, '+7 hours') AS hour, COUNT(*) AS total_orders FROM orders GROUP BY hour ORDER BY total_orders DESC LIMIT 1`.
    4. Thêm rule vào `SYSTEM_PROMPT_SUMMARY`: dữ liệu nhận được chỉ là phần thống kê; danh sách đơn (nếu có) do bot hiển thị riêng bên dưới; tuyệt đối không nói thiếu/không có danh sách chi tiết.
    5. Thêm `_strip_missing_list_claims(text: str) -> str`: tách câu theo `re.split(r"(?<=[.!?])\s+|\n+")`; bỏ câu mà bản unaccent chứa 'danh sach' VÀ ('chua co' hoặc 'khong co' hoặc 'chua'); ghép lại phần còn; nếu rỗng thì trả nguyên text gốc (fallback). Gọi trong `summarize_aggregate_result` ngay trước khi return.
    Trong tests/test_order_search.py thêm: `test_tape_count_heuristic` (các chuỗi items_text thật lấy từ cassette_store.db như liệt kê trong INVESTIGATION + hành vi track numbering + fallback khác 0, chạy trực tiếp hàm Python); `test_tape_count_sqlite_function` (gọi `SELECT tape_count('6 băng maxell 90p')` trên test_db); `test_text_to_sql_prompt_documents_tape_count_and_time_buckets` (assert prompt chứa 'tape_count', `strftime('%H'`, `'+7 hours'`, 'total_tapes'); vẫn giữ assert cũ trong test_generate_sql_from_query_prompt); `test_summary_strips_missing_list_claim` (mock AsyncOpenAI trả câu có "danh sách chi tiết thì chưa có bác nhé", assert kết quả không còn cụm đó và vẫn giữ phần thống kê; trường hợp toàn câu bị xoá thì trả nguyên văn).
  </action>
  <verify>
    <automated>python -m pytest tests/test_order_search.py -q</automated>
  </verify>
  <done>
    tape_count đăng ký và trả số băng hợp lý cho item thật; prompt có quy tắc tape_count + giờ/thứ với '+7 hours' và ví dụ; summary MIXED không còn câu "chưa có danh sách chi tiết"; toàn bộ test order_search pass.
  </done>
</task>

</tasks>

<threat_model>
## Trust Boundaries

| Boundary | Description |
|----------|-------------|
| Telegram update pump -> handler | Update tuần tự dùng chung `context.user_data`; task nền chạm dữ liệu người dùng |
| Câu chat tự do -> tìm khách | Token người dùng nhập đi vào SQL và callback_data |
| LLM -> SQLite | SQL và summary do model sinh từ câu hỏi |
| Telegram callback -> DB | `cus_v`/`cus_pg` chứa customer_id/page do client gửi |

## STRIDE Threat Register

| Threat ID | Category | Component | Disposition | Mitigation Plan |
|-----------|----------|-----------|-------------|-----------------|
| T-HNN-01 | Tampering | customers.search_customers | mitigate | Token truyền qua placeholder `?`; `word_match` dùng `re.escape`; không nối chuỗi token vào SQL |
| T-HNN-02 | Information Disclosure | customer callbacks | mitigate | customer_id lấy từ callback chỉ dùng để SELECT hồ sơ; whitelist gate group -1 vẫn chạy trước mọi handler |
| T-HNN-03 | Denial of Service | album debounce task | mitigate | Mỗi media_group chỉ 1 task nền; buffer pop trong finally; prune `_PROCESSED_MEDIA_GROUPS` 60s |
| T-HNN-04 | Tampering | summary post-filter | accept | Chỉ xoá câu văn bản, không ảnh hưởng SQL/số liệu đã tính từ DB |
| T-HNN-05 | Tampering | tape_count regex | mitigate | Regex biên cố định, không eval, không đọc ngoài `items_text` |
</threat_model>

<verification>
1. `python -m pytest tests/test_ingest.py -q`
2. `python -m pytest tests/test_customer_search.py tests/test_order_search.py -q`
3. `python -m pytest tests/ -q`
4. Smoke tay (nếu có Telegram token): gửi album 3 ảnh, "tìm khách 0903626566", "có bao nhiêu băng", "khung giờ nào bán được nhiều đơn nhất", "hôm nay bán bao nhiêu đơn, liệt kê đơn".
</verification>

<success_criteria>
- Album 3 ảnh lưu đủ 3 ảnh trong 1 draft; handler không block pump.
- Tra khách theo tên/SĐT/địa chỉ hoạt động không tốn LLM; phân trang và quay lại chạy đúng.
- "có bao nhiêu băng" trả tổng số băng qua tape_count; "khung giờ nào..." trả giờ cao điểm.
- MIXED không còn câu nói thiếu danh sách chi tiết.
- `python -m pytest tests/ -q` pass.
</success_criteria>

<output>
Implement trực tiếp trong working tree. Không commit. Báo lại file đã sửa và kết quả pytest từng bước.
</output>
