---
phase: 261027-htn
plan: 01
type: execute
wave: 1
depends_on: []
files_modified:
  - src/services/order_search.py
  - tests/test_search_mixed_pagination.py
  - tests/test_order_search.py
autonomous: true
requirements: ["QUICK-261027-HTN-MIXED-SUMMARY"]
user_setup: []

must_haves:
  truths:
    - "Câu hỏi MIXED 'nay bán tổng bao tiền, có bán được Chế Linh không' với list khớp 1 đơn: summarizer nhận được matched_order_count=1 và không nói 'không bán được Chế Linh nào'"
    - "Danh sách đơn vẫn render bình thường, summary thống kê vẫn giữ nguyên nội dung doanh thu"
    - "AGGREGATE-only (1 câu SQL thống kê) không gửi matched_order_count, hành vi không đổi"
    - "Mọi test cũ của summarize_aggregate_result vẫn xanh (tham số mới keyword-only, mặc định None)"
  artifacts:
    - path: "src/services/order_search.py"
      provides: "SYSTEM_PROMPT_SUMMARY rule matched_order_count; summarize_aggregate_result(*, list_total); _run_aggregate(*, list_total); MIXED chạy list trước aggregate"
    - path: "tests/test_search_mixed_pagination.py"
      provides: "Regression MIXED: summary call thấy matched_order_count; AGGREGATE-only không thấy"
    - path: "tests/test_order_search.py"
      provides: "Unit test inject list_total + prompt chứa matched_order_count"
  key_links:
    - from: "src/services/order_search.py:_execute_search_statements"
      to: "src/services/order_search.py:_run_aggregate"
      via: "_run_list trước, truyền list_total=total_count khi rows_are_orders"
      pattern: "list_total="
    - from: "src/services/order_search.py:_run_aggregate"
      to: "src/services/order_search.py:summarize_aggregate_result"
      via: "keyword list_total"
      pattern: "summarize_aggregate_result"
---

<objective>
Sửa lỗi summary MIXED tự bịa "không bán được <X> nào" dù danh sách đơn có dòng khớp: đưa số đơn khớp của câu list (`total_count`) vào prompt summarizer dưới dạng fact deterministic `matched_order_count`, kèm luật prompt cấm khẳng định vắng mặt khi con số > 0.

Purpose: người dùng lớn tuổi đọc một câu trả lời mâu thuẫn với danh sách ngay bên dưới sẽ mất tin bot.
Output: prompt rule + tham số `list_total` xuyên `_execute_search_statements` → `_run_aggregate` → `summarize_aggregate_result`, cùng test hồi quy.
</objective>

<context>
@.planning/STATE.md
@CLAUDE.md
@src/services/order_search.py
@tests/test_search_mixed_pagination.py
@tests/test_order_search.py
</context>

<tasks>

<task type="auto">
  <name>Task 1: Truyền số đơn khớp vào summarizer cho MIXED</name>
  <files>src/services/order_search.py</files>
  <action>
    1. `SYSTEM_PROMPT_SUMMARY`: thêm một đoạn sau dòng LƯU Ý hiện có (giữ nguyên toàn bộ nội dung cũ), đúng các cụm ổn định để test bám:
       `QUY TẮC SỐ ĐƠN KHỚP: Nếu dữ liệu có dòng matched_order_count với giá trị lớn hơn 0, nghĩa là có đơn khớp câu hỏi và bot đang hiển thị danh sách các đơn đó ngay bên dưới câu trả lời. Khi đó TUYỆT ĐỐI KHÔNG được nói shop không có, chưa bán được, không tìm thấy, hay không bán được đơn/băng nào khớp câu hỏi.`
       Không đổi các ví dụ/rule cũ (test hiện có assert nội dung prompt khác).

    2. `summarize_aggregate_result`: thêm tham số keyword-only `list_total: int | None = None` sau `raw_rows` (giữ nguyên các tham số vị trí cũ để call shape cũ không vỡ). Tách user content thành biến `user_content` như hiện tại, rồi CHỈ khi `list_total is not None and list_total > 0` nối thêm dòng:
       `\nmatched_order_count: {list_total} (số đơn khớp câu hỏi; bot hiển thị danh sách các đơn này bên dưới câu trả lời)`
       Không mutate `raw_rows` (không thêm key vào dict, tránh rò rỉ vào `SearchResult.raw_rows`).
       Giữ nguyên chuỗi hậu kỳ `_append_missing_tape_note(_strip_missing_list_claims(raw), raw_rows)`. Không thêm post-filter mới: fact + prompt rule là đủ cho phạm vi này.

    3. `_run_aggregate`: thêm keyword-only `list_total: int | None = None`, truyền `list_total=list_total` xuống `summarize_aggregate_result`.

    4. `_execute_search_statements`, nhánh MIXED (2 statement): đảo thứ tự — chạy `_run_list` TRƯỚC để có `total_count`, rồi gọi `_run_aggregate(..., list_total=total_count if rows_are_orders else None)`. Khi `rows_are_orders` False thì bot không render list nên không được bơm fact. Giữ nguyên nhánh `if total_count and not rows_are_orders: return aggregate_result` và toàn bộ phần tạo `SearchResult(MIXED, ...)`.
       Nhánh 1-statement (ORDERS/AGGREGATE, kể cả fallback `total_count and not rows_are_orders`) KHÔNG truyền `list_total` — `total_count` của pure aggregate không phải số đơn khớp.

    Ràng buộc: minimum diff, không đổi tên hàm, không đổi `SYSTEM_PROMPT_TEXT_TO_SQL_TEMPLATE`, không đổi hành vi AGGREGATE-only.
  </action>
  <verify>
    <automated>python -m pytest tests/test_order_search.py tests/test_search_mixed_pagination.py -q</automated>
  </verify>
  <done>
    `summarize_aggregate_result` nhận list_total keyword-only (mặc định None); MIXED gửi `matched_order_count: N` khi list khớp > 0; AGGREGATE-only không gửi; prompt có cụm `matched_order_count`; test cũ vẫn xanh.
  </done>
</task>

<task type="auto">
  <name>Task 2: Test hồi quy summary MIXED + chạy full suite</name>
  <files>tests/test_order_search.py, tests/test_search_mixed_pagination.py</files>
  <action>
    tests/test_order_search.py:
    1. `test_summary_prompt_forbids_absent_claim_when_list_matches`: import `SYSTEM_PROMPT_SUMMARY` (thêm vào import tại chỗ dùng), assert `"matched_order_count"` và `"TUYỆT ĐỐI KHÔNG"` nằm trong prompt.
    2. `test_summarize_aggregate_result_injects_list_total`: AsyncMock trả về summary cố định `"Dạ hôm nay shop có 7 đơn, tổng 1.000.000 đ bác nhé!"`. Gọi `summarize_aggregate_result(..., raw_rows=[{"total_orders": 7}], list_total=3)`; assert `"matched_order_count: 3"` trong `mock_client.chat.completions.create.call_args.kwargs["messages"][1]["content"]`. Gọi lại không truyền `list_total`; assert `"matched_order_count"` KHÔNG có trong user content (dùng `reset_mock` hoặc đọc `call_args_list[-1]`). Assert `raw_rows` gốc không bị thêm key.

    tests/test_search_mixed_pagination.py:
    3. `test_mixed_summary_sees_list_match_count`: seed 1 đơn `items_text="1 cuốn Chế Linh"` + 2 đơn `"1 cuốn Tuấn Vũ"` qua `create_order`. Mock LLM side_effect 2 lần: (a) SQL `SELECT COUNT(*) AS total_orders, SUM(total_amount) AS total_revenue FROM orders; SELECT o.* FROM orders o WHERE o.items_text LIKE '%Chế Linh%' ORDER BY o.created_at DESC, o.id DESC`, (b) summary bất kỳ. `run_order_search(...)`. Assert `result.result_type == SearchResultType.MIXED`, `result.total_count == 1`, `len(result.orders) == 1`, và user content của call summarize (`call_args_list[1].kwargs["messages"][1]["content"]`) chứa `"matched_order_count: 1"`.
    4. `test_aggregate_only_summary_has_no_list_total`: mock trả 1 câu aggregate `SELECT COUNT(*) AS total_orders FROM orders` rồi summary; sau `run_order_search` assert user content của call summarize KHÔNG chứa `"matched_order_count"`.

    Chạy full suite: nếu test khác vỡ do thay đổi prompt/call shape, sửa đúng theo hành vi mới (không nới assertion thành vô nghĩa).
  </action>
  <verify>
    <automated>python -m pytest -q</automated>
  </verify>
  <done>
    4 test mới xanh; full suite xanh; test MIXED chứng minh summarizer thấy `matched_order_count: 1` trong khi render list vẫn đúng.
  </done>
</task>

</tasks>

<threat_model>
## Trust Boundaries

| Boundary | Description |
|----------|-------------|
| DB → LLM summary prompt | Số đơn khớp là integer nội bộ, chèn vào user message |
| LLM summary → Telegram HTML | Summary được `html.escape` ở `src/bot/handlers/search.py` trước khi ghép vào card |

## STRIDE Threat Register

| Threat ID | Category | Component | Disposition | Mitigation Plan |
|-----------|----------|-----------|-------------|-----------------|
| T-261027-htn-01 | Tampering | summarize_aggregate_result user content | accept | Fact chèn là `int` từ `COUNT(*)` do bot tự tính, không phải text người dùng; query vẫn nằm trong thẻ nội dung như thiết kế hiện có |
| T-261027-htn-02 | Information Disclosure | summary text | accept | Bot chỉ phục vụ whitelist; nội dung summary vốn hiển thị cho user whitelist |
| T-261027-htn-SC | Tampering | package installs | accept | Không thêm dependency nào |
</threat_model>

<verification>
- `python -m pytest tests/test_order_search.py tests/test_search_mixed_pagination.py -q` xanh.
- `python -m pytest -q` toàn bộ xanh.
</verification>

<success_criteria>
- MIXED: user content gửi summarizer có `matched_order_count: N` khi list khớp > 0, không có khi list rỗng hoặc AGGREGATE-only.
- Summary prompt cấm khẳng định "không có/chưa bán được" khi matched_order_count > 0.
- Không đổi chữ ký vị trí của `summarize_aggregate_result`; test cũ không phải sửa.
</success_criteria>

<output>
Create `.planning/quick/261027-htn-fix-mixed-search-summary-claiming-no-mat/261027-htn-SUMMARY.md` when done
</output>
