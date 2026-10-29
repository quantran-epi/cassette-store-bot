---
status: resolved
trigger: "Truy vấn 'Khách nào mua nhiều đơn nhất nhỉ' bị route sang tìm kiếm hồ sơ khách"
created: 2026-10-29T10:00:00Z
updated: 2026-10-29T10:45:00Z
---

## Symptoms

expected: Route sang order search, xếp hạng khách theo số đơn.
actual: Route sang customer profile search và báo không tìm thấy.
reproduction: `is_customer_search('Khách nào mua nhiều đơn nhất nhỉ') -> True`.

## Root Cause

`is_customer_search` coi mọi câu bắt đầu bằng "khách" là tra cứu hồ sơ. `SEARCH_CONVERSATIONAL_PATTERNS` và prompt SQL thiếu trường hợp xếp hạng khách.

## Resolution

- Loại câu hỏi xếp hạng, so sánh, thống kê khỏi customer profile search.
- Nhận diện câu hỏi xếp hạng trong order search.
- Hướng dẫn query plan dùng `GROUP BY`, `COUNT(*)`, `ORDER BY`, `LIMIT`.
- Thêm regression tests cho câu thực tế và biến thể.
