---
task: returning-customer-preview-history
description: Fix returning customer name preview, add customer order history view with back button, inline multi-address selector, and auto-add address on order change
files_modified:
  - src/bot/handlers/ingest.py
  - src/bot/handlers/callbacks.py
  - src/bot/app.py
  - src/db/orders.py
  - tests/test_ingest.py
  - tests/test_mutation_card_and_lock.py
---

## Objective
1. Fix preview card for returning customer: when `extracted.customer_name` is missing, auto-populate from `customer.name` in DB.
2. Preview card displays all required fields: tên khách, sđt, địa chỉ, băng cassette, tổng tiền, tiền COD thu.
3. Add customer order history button on preview card (`📜 Lịch sử mua hàng (N đơn)`) when returning customer has previous orders; viewing history presents summary card with `◀️ Quay lại` button to return to the draft preview.
4. Inline multi-address picker: if customer has multiple addresses, show intuitive radio-style selection buttons (`🔘 [Địa chỉ chọn]` / `⚪ [Địa chỉ khác]`) on preview card.
5. Auto-append new address to customer address list when mutating order's `shipping_address`.
