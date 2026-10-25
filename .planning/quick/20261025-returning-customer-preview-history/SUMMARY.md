---
status: complete
task: returning-customer-preview-history
completed_at: 2026-10-25
---

# Quick Task Summary: Returning Customer Preview & Order History View

## What was done
1. **Fix returning customer name preview (`src/bot/handlers/ingest.py`)**:
   - Auto-fill `customer_name` from existing `customer.name` in DB when `extracted.customer_name` is missing or empty.
   - Store `customer_id` into draft data.
2. **Preview card layout & multi-address selector (`src/bot/handlers/ingest.py`)**:
   - Explicitly displays all 6 key fields: Tên khách, SĐT, Địa chỉ, Băng cassette, Tổng tiền, Tiền COD thu.
   - For customers with $\ge 2$ addresses, renders radio-style inline buttons (`🔘 [Địa chỉ chọn]` / `⚪ [Địa chỉ khác]`) to switch addresses in 1-tap.
   - Added `[👤 Chi tiết khách (N đơn)]` button for existing customers.
3. **Customer detail profile & paginated order history (`src/bot/keyboards.py`, `src/bot/handlers/callbacks.py`, `src/db/orders.py`)**:
   - Added `get_orders_by_customer_id` and `count_orders_by_customer_id` with limit/offset pagination.
   - Added `render_customer_detail_card` displaying customer profile, phone numbers, addresses, stats, and paginated orders (5 orders/page).
   - Handled callback `ord:cs:<draft_id>:<page>` with `[⬅️ Trước]` `[Trang X/Y]` `[Sau ➡️]` buttons and `[◀️ Quay lại đơn đang tạo]` (`ord:bk:<draft_id>`).
4. **Auto-adding new address on order mutation (`src/db/orders.py`)**:
   - When mutating order's `shipping_address`, new address is automatically and idempotently appended to customer's address list via `add_address`.
5. **Testing**:
   - Added unit and integration tests in `tests/test_ingest.py` covering all scenarios.
   - 234/234 tests passing.
