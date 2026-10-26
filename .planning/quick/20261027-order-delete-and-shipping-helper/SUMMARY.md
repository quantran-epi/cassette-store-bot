---
status: complete
date: 2026-10-27
slug: 20261027-order-delete-and-shipping-helper
---

# Quick Task Summary: Order Delete Confirmation, Shipping Dispatch Helper, and Tracking Auto-Advance

## Implemented Features
1. **Order Deletion with 2-Step Confirmation**:
   - Added `delete_order` in `src/db/orders.py` (cascading delete on order_history and reminders).
   - Added `🗑️ Xoá đơn` button to order detail keyboard (`build_order_detail_keyboard`).
   - Added two-step confirmation dialog with `del_prompt` and `del_confirm` callbacks in `src/bot/handlers/order_actions.py`.

2. **Shipping Dispatch Helper (App Carrier Copy Helper)**:
   - Added `🚚 Tạo đơn vận chuyển` button to order detail view and post-creation success card.
   - Built `build_shipping_helper_card` and `build_shipping_helper_keyboard` in `src/bot/keyboards.py`.
   - Native 1-tap `CopyTextButton` for customer name, phone, address, fixed item text "băng cát sét", raw COD amount, and conditional static note ("Cho xem hàng, KHÔNG DÙNG THỬ" for COD, "Cho xem hàng" for non-COD).

3. **Tracking Entry & Auto-Transition to DA_TAO_DON**:
   - Added `🚚 Nhập mã vận đơn` button on order creation success card and inside shipping helper.
   - `update_order_tracking` automatically updates order status to `OrderStatus.DA_TAO_DON` and records audit trail.

4. **Address Normalization via LLM**:
   - Enhanced `SYSTEM_PROMPT` in `src/services/extractor.py` and `src/services/mutation_extractor.py` to normalize shipping addresses with at least 3 administrative levels (Xã/Phường, Quận/Huyện, Tỉnh/Thành phố).

5. **Conversational Preview Draft Editing (No Timeout)**:
   - Set `context.user_data["active_draft_id"]` on order preview.
   - Allowed editing draft via natural language without timeout until explicit user confirmation or cancellation.

## Verification
- Added 8 tests in `tests/test_quick_order_delete_and_shipping.py`.
- Ran full test suite: 329 passed in 1.90s.
- Ruff lint check: All checks passed.
