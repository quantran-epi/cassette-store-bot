# Quick Plan: Order Deletion with Confirmation & Shipping Dispatch Helper

## Goal
Implement:
1. Order deletion with two-step confirmation (delete prompt + confirmation + cascaded DB delete).
2. Shipping dispatch helper with 1-tap copy buttons (name, phone, address, static note with COD condition, COD amount, static text "băng cát sét").
3. Tracking code entry action directly accessible after order creation and in shipping helper.

## Proposed Changes
1. `src/db/orders.py`:
   - Add `delete_order(db, order_id: int) -> bool`
2. `src/bot/keyboards.py`:
   - Add `build_shipping_helper_card(order: Order) -> str`
   - Add `build_shipping_helper_keyboard(order: Order) -> InlineKeyboardMarkup`
   - Update `build_order_detail_keyboard` to include `🚚 Tạo đơn vận chuyển` and `🗑️ Xoá đơn`
3. `src/bot/handlers/order_actions.py`:
   - Extend `ACTION_CALLBACK_PATTERN` to support `ship_helper`, `del_prompt`, `del_confirm`
   - Add handler branches for `ship_helper`, `del_prompt`, and `del_confirm`
4. `src/bot/handlers/callbacks.py`:
   - Add `🚚 Nhập mã vận đơn` and `🚚 Tạo đơn vận chuyển` to post-order creation `success_kb`
5. `tests/`:
   - Unit and integration tests for `delete_order`, shipping helper card/keyboard, and callback handlers
