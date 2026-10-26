---
status: complete
date: 2026-10-26
quick_id: 261026-hnn
---

# Quick Task 261026-hnn — Summary

## What changed

| Defect | Fix |
|---|---|
| Album lưu 1 ảnh | `ingest.py`: debounce chuyển sang task nền `_finalize_media_group`; handler trả về ngay, không chặn update pump tuần tự |
| Không tìm được khách | `customers.py::is_customer_search` + `search_customers` (không LLM); `search.py` route trước pipeline SQL, thêm callback `cus_v/cus_pg/cus_bk`; `keyboards.py` cho phép tuỳ biến nav/back callback |
| "bao nhiêu băng" trả số đơn | SQLite function `tape_count(items_text)` + quy tắc prompt `SUM(tape_count(...)) AS total_tapes` |
| "khung giờ nào bán nhiều nhất" báo không có thông tin | Prompt thêm `strftime('%H'/'%w', created_at, '+7 hours')` + ví dụ mẫu |
| MIXED tự nói thiếu danh sách | Rule prompt + `_strip_missing_list_claims`; toàn bộ bị xoá → summary rỗng, bot chỉ hiện danh sách |

## Verification

- `python -m pytest tests/ -q` → **277 passed**, 2 pre-existing PTB JobQueue warnings.
- Live smoke với gateway thật (`cassette_store.db`, 6 đơn):
  - `có bao nhiêu băng` → `total_tapes = 28`, trả lời "28 cuốn băng".
  - `khung giờ nào bán được nhiều đơn nhất` → `hour = 12`, 6 đơn.
  - `tìm khách 0903626566` → hồ sơ Nguyễn Đức Thành (route deterministic, không LLM).
  - `hôm nay bán bao nhiêu đơn và liệt kê chi tiết` → MIXED, summary sạch, không còn câu "danh sách chi tiết thì chưa có".

## Deviations from plan

- `search_customers` thêm fallback substring (unaccent `LIKE`) khi AND whole-word không khớp: DB thật lưu "Hanoi cũ" trong khi người dùng gõ "Hà Nội". Test `test_search_customers_spacing_variant_falls_back_to_substring` khoá lại.
- `_strip_missing_list_claims` trả chuỗi rỗng khi mọi câu đều bị xoá (plan nói fallback về nguyên văn — sai, vì nguyên văn chính là câu cần chặn). `search.py` đã có sẵn fallback riêng cho AGGREGATE.

## Known limits

- `tape_count` là ước lượng từ free-text (`ponytail:` trong code). Đơn trộn danh sách đánh số 1..N với cụm "(6 sony 90p)" có thể lệch ±1. Nâng cấp khi `orders` có cột số lượng có cấu trúc.
- Chưa commit — cây làm việc đang có thay đổi khác chưa xong của task trước.
