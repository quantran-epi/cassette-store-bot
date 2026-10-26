from unittest.mock import AsyncMock, MagicMock

import pytest

from src.bot.handlers.ingest import handle_text_order
from src.bot.handlers.order_actions import handle_order_action_callback
from src.bot.keyboards import (
    build_order_detail_keyboard,
    build_shipping_helper_card,
    build_shipping_helper_keyboard,
)
from src.db.orders import create_order, delete_order, get_order_by_id, update_order_tracking
from src.models.mutation import OrderMutationDelta
from src.models.order import Order, OrderStatus


@pytest.mark.asyncio
async def test_db_delete_order(test_db):
    """Verify delete_order removes order and cascade-deletes related records."""
    order = Order(
        customer_name="Khách Test Xoá",
        customer_phone="0911223344",
        shipping_address="123 Phố Huế, Hai Bà Trưng, Hà Nội",
        items_text="1 Băng Tuấn Vũ",
        total_amount=150000,
        cod_amount=150000,
    )
    order_id = await create_order(test_db, order)
    assert order_id > 0

    fetched = await get_order_by_id(test_db, order_id)
    assert fetched is not None

    deleted = await delete_order(test_db, order_id)
    assert deleted is True

    fetched_after = await get_order_by_id(test_db, order_id)
    assert fetched_after is None

    # Deleting again returns False
    assert await delete_order(test_db, order_id) is False


@pytest.mark.asyncio
async def test_update_order_tracking_auto_advances_status(test_db):
    """Verify adding tracking code automatically advances status to DA_TAO_DON."""
    order = Order(
        customer_name="Khách Test Vận Đơn",
        customer_phone="0933445566",
        shipping_address="456 Lê Lợi, Quận 1, TP. Hồ Chí Minh",
        items_text="2 Băng Chế Linh",
        total_amount=200000,
        cod_amount=200000,
        status=OrderStatus.CHO_LAM,
    )
    order_id = await create_order(test_db, order)

    success = await update_order_tracking(test_db, order_id, "VTP123456789")
    assert success is True

    updated = await get_order_by_id(test_db, order_id)
    assert updated is not None
    assert updated.tracking_code == "VTP123456789"
    assert updated.status == OrderStatus.DA_TAO_DON


def test_order_detail_keyboard_has_shipping_and_delete_buttons():
    """Verify order detail keyboard includes Tạo đơn vận chuyển and Xoá đơn."""
    order = Order(
        id=99,
        customer_name="Bác Ba",
        customer_phone="0901234567",
        shipping_address="Hà Nội",
        items_text="1 Băng",
        status=OrderStatus.CHO_LAM,
    )
    kb = build_order_detail_keyboard(order, date_str="2026-10-27", page=1)
    callbacks = [btn.callback_data for row in kb.inline_keyboard for btn in row if btn.callback_data]
    assert "ord_act:ship_helper:99" in callbacks
    assert "ord_act:del_prompt:99" in callbacks


def test_shipping_helper_card_and_keyboard_cod():
    """Verify shipping helper card & keyboard formatting for COD orders."""
    order = Order(
        id=88,
        customer_name="Nguyễn Văn A",
        customer_phone="0988776655",
        shipping_address="12 Hàng Bài, Hoàn Kiếm, Hà Nội",
        items_text="3 Băng Nhạc Vàng",
        total_amount=300000,
        cod_amount=300000,
        payment_method="COD",
    )
    card = build_shipping_helper_card(order)
    assert "HỖ TRỢ TẠO ĐƠN VẬN CHUYỂN #88" in card
    assert "Nguyễn Văn A" in card
    assert "0988776655" in card
    assert "Cho xem hàng, KHÔNG DÙNG THỬ" in card
    assert "băng cát sét" in card
    assert "300.000 đ" in card

    kb = build_shipping_helper_keyboard(order)
    copy_texts = [
        btn.copy_text.text
        for row in kb.inline_keyboard
        for btn in row
        if btn.copy_text
    ]
    assert "Nguyễn Văn A" in copy_texts
    assert "0988776655" in copy_texts
    assert "12 Hàng Bài, Hoàn Kiếm, Hà Nội" in copy_texts
    assert "băng cát sét" in copy_texts
    assert "300000" in copy_texts
    assert "Cho xem hàng, KHÔNG DÙNG THỬ" in copy_texts

    # Check action buttons
    callbacks = [btn.callback_data for row in kb.inline_keyboard for btn in row if btn.callback_data]
    assert "ord_act:track:88" in callbacks
    assert "ord_v_cur:88" in callbacks


def test_shipping_helper_note_non_cod():
    """Verify static note is 'Cho xem hàng' when non-COD."""
    order = Order(
        id=77,
        customer_name="Trần Thị B",
        customer_phone="0977665544",
        shipping_address="Hải Phòng",
        items_text="1 Băng",
        total_amount=100000,
        cod_amount=0,
        payment_method="CHUYEN_KHOAN",
    )
    card = build_shipping_helper_card(order)
    assert "Cho xem hàng" in card
    assert "KHÔNG DÙNG THỬ" not in card

    kb = build_shipping_helper_keyboard(order)
    copy_texts = [
        btn.copy_text.text
        for row in kb.inline_keyboard
        for btn in row
        if btn.copy_text
    ]
    assert "Cho xem hàng" in copy_texts
    assert "Cho xem hàng, KHÔNG DÙNG THỬ" not in copy_texts


@pytest.mark.asyncio
async def test_handle_order_action_ship_helper_and_delete(test_db):
    """Verify ship_helper, del_prompt, and del_confirm callback actions."""
    order = Order(
        customer_name="Khách Test Action",
        customer_phone="0944556677",
        shipping_address="Đà Nẵng",
        items_text="1 Băng",
        total_amount=120000,
        cod_amount=120000,
    )
    order_id = await create_order(test_db, order)

    # 1. Test ship_helper callback
    query_ship = AsyncMock()
    query_ship.data = f"ord_act:ship_helper:{order_id}"
    update_ship = MagicMock()
    update_ship.callback_query = query_ship
    context = MagicMock()
    context.bot_data = {"db": test_db}

    await handle_order_action_callback(update_ship, context)
    query_ship.answer.assert_called_once()
    query_ship.edit_message_text.assert_called_once()
    call_args = query_ship.edit_message_text.call_args[1]
    assert "HỖ TRỢ TẠO ĐƠN VẬN CHUYỂN" in call_args["text"]

    # 2. Test del_prompt callback (confirmation dialog)
    query_prompt = AsyncMock()
    query_prompt.data = f"ord_act:del_prompt:{order_id}"
    update_prompt = MagicMock()
    update_prompt.callback_query = query_prompt

    await handle_order_action_callback(update_prompt, context)
    query_prompt.answer.assert_called_once()
    query_prompt.edit_message_text.assert_called_once()
    prompt_args = query_prompt.edit_message_text.call_args[1]
    assert "XÁC NHẬN XOÁ ĐƠN HÀNG" in prompt_args["text"]
    assert f"ord_act:del_confirm:{order_id}" in [
        btn.callback_data
        for row in prompt_args["reply_markup"].inline_keyboard
        for btn in row
    ]

    # 3. Test del_confirm callback (actual delete)
    query_confirm = AsyncMock()
    query_confirm.data = f"ord_act:del_confirm:{order_id}"
    update_confirm = MagicMock()
    update_confirm.callback_query = query_confirm

    await handle_order_action_callback(update_confirm, context)
    query_confirm.answer.assert_called_with("✅ Đã xoá đơn hàng thành công!", show_alert=False)
    confirm_args = query_confirm.edit_message_text.call_args[1]
    assert "ĐÃ XOÁ ĐƠN HÀNG" in confirm_args["text"]

    # Check DB
    assert await get_order_by_id(test_db, order_id) is None


@pytest.mark.asyncio
async def test_preview_nl_chat_editing():
    """Verify natural language chat modifies active preview draft and re-renders card."""
    update = MagicMock()
    update.message.text = "sửa sđt thành 0999888777 và đổi địa chỉ sang 55 Hai Bà Trưng, Hoàn Kiếm, Hà Nội"
    update.message.chat.send_action = AsyncMock()
    update.message.reply_text = AsyncMock()

    context = MagicMock()
    draft = {
        "draft_id": "test1234",
        "customer_name": "Anh Hưng",
        "customer_phone": "0912345678",
        "shipping_address": "Cũ",
        "items_text": "2 Băng",
        "total_amount": 200000,
        "cod_amount": 200000,
        "deposit_amount": 0,
        "tape_quantity": 2,
        "tapes": [],
        "tape_genres": [],
        "tape_artists": [],
        "notes": "",
    }
    context.user_data = {
        "pending_orders": {"test1234": draft},
        "active_draft_id": "test1234",
    }
    mock_openai = AsyncMock()
    context.application.bot_data = {
        "openai_client": mock_openai,
        "settings": MagicMock(nine_router_model_id="test-model"),
    }

    # Mock extract_order_mutation
    from unittest.mock import patch
    delta = OrderMutationDelta(
        new_customer_phone="0999888777",
        new_shipping_address="55 Hai Bà Trưng, Hoàn Kiếm, Hà Nội",
    )
    with patch("src.services.mutation_extractor.extract_mutation_delta", AsyncMock(return_value=delta)):
        await handle_text_order(update, context)

    assert draft["customer_phone"] == "0999888777"
    assert draft["shipping_address"] == "55 Hai Bà Trưng, Hoàn Kiếm, Hà Nội"
    assert context.user_data["active_draft_id"] == "test1234"
    update.message.reply_text.assert_called_once()
    reply_text = update.message.reply_text.call_args[1]["text"]
    assert "ĐÃ CẬP NHẬT THEO YÊU CẦU CỦA BÁC" in reply_text
    assert "0999888777" in reply_text


@pytest.mark.asyncio
async def test_preview_nl_chat_cancel():
    """Verify user can cancel active preview draft by typing 'huỷ'."""
    update = MagicMock()
    update.message.text = "huỷ"
    update.message.reply_text = AsyncMock()

    context = MagicMock()
    context.user_data = {
        "pending_orders": {"test1234": {"draft_id": "test1234"}},
        "active_draft_id": "test1234",
    }

    await handle_text_order(update, context)
    assert "active_draft_id" not in context.user_data
    assert "test1234" not in context.user_data["pending_orders"]
    update.message.reply_text.assert_called_once()
    assert "ĐÃ HUỶ ĐƠN HÀNG" in update.message.reply_text.call_args[1]["text"]
