import pytest
from unittest.mock import AsyncMock, MagicMock
from telegram import Update
from telegram.ext import CallbackContext

from src.bot.handlers.ingest import render_preview_card, handle_text_order
from src.bot.handlers.callbacks import handle_order_callback
from src.db.orders import list_orders_by_status
from src.models.order import OrderStatus
from src.models.extractor import ExtractedOrder


def test_render_preview_card_layout_and_buttons():
    """Verify preview card text formatting, HTML escaping, and 2-button layout."""
    draft = {
        "draft_id": "a1b2c3d4",
        "customer_name": "Bác & Hùng <VIP>",
        "customer_phone": "0912345678",
        "shipping_address": "123 Lê Lợi, Q.1",
        "items_text": "2 Băng Chế Linh & Tuấn Vũ",
        "total_amount": 350000,
        "cod_amount": 300000,
        "deposit_amount": 50000,
    }
    stats = {"total_orders": 3, "total_spent": 1200000, "bom_count": 0}

    text, reply_markup = render_preview_card(draft, stats)

    # HTML escapes check
    assert "&amp;" in text
    assert "&lt;VIP&gt;" in text
    assert "0912345678" in text
    assert "350.000 đ" in text
    assert "300.000 đ" in text
    assert "đã cọc 50.000 đ" in text
    assert "Khách quen: 3 đơn - 1.200.000 đ" in text

    # Keyboard checks: 1 row, 2 buttons with compact callbacks <= 64 bytes
    keyboard = reply_markup.inline_keyboard
    assert len(keyboard) == 1
    assert len(keyboard[0]) == 2

    btn_confirm = keyboard[0][0]
    btn_cancel = keyboard[0][1]

    assert "Xác nhận lưu" in btn_confirm.text
    assert btn_confirm.callback_data == "ord:cf:a1b2c3d4"
    assert len(btn_confirm.callback_data.encode("utf-8")) <= 64

    assert "Huỷ bỏ" in btn_cancel.text
    assert btn_cancel.callback_data == "ord:ca:a1b2c3d4"
    assert len(btn_cancel.callback_data.encode("utf-8")) <= 64


def test_render_preview_card_with_bom_hang_warning():
    """If customer has bom_count > 0, preview card displays explicit warning."""
    draft = {
        "draft_id": "bom12345",
        "customer_name": "Anh Bom",
        "customer_phone": "0909999999",
        "shipping_address": "Địa chỉ X",
        "items_text": "1 Băng",
        "total_amount": 150000,
        "cod_amount": 150000,
        "deposit_amount": 0,
    }
    stats = {"total_orders": 2, "total_spent": 150000, "bom_count": 1}

    text, _ = render_preview_card(draft, stats)
    assert "CẢNH BÁO: Khách từng có 1 đơn BOM HÀNG!" in text


@pytest.mark.asyncio
async def test_order_callback_cancel_discards_draft_no_db(test_db):
    """Callback ord:ca:<id> deletes draft from pending_orders and makes 0 DB writes."""
    draft_id = "feedcafe"
    draft_data = {
        "draft_id": draft_id,
        "customer_name": "Khách Test",
        "customer_phone": "0987654321",
        "shipping_address": "Hà Nội",
        "items_text": "1 Băng",
        "total_amount": 200000,
        "cod_amount": 200000,
        "deposit_amount": 0,
        "payment_method": "COD",
        "notes": "",
        "photo_file_ids": [],
    }

    # Mock Update and CallbackQuery
    update = MagicMock(spec=Update)
    query = MagicMock()
    query.data = f"ord:ca:{draft_id}"
    query.answer = AsyncMock()
    query.edit_message_text = AsyncMock()
    update.callback_query = query

    # Mock context with in-memory pending_orders
    context = MagicMock(spec=CallbackContext)
    context.user_data = {"pending_orders": {draft_id: draft_data}}
    app_context = MagicMock()
    app_context.db = test_db
    context.application.bot_data = {"app_context": app_context}

    await handle_order_callback(update, context)

    query.answer.assert_awaited_once()
    assert draft_id not in context.user_data["pending_orders"]
    query.edit_message_text.assert_awaited_once()
    assert "ĐÃ HUỶ ĐƠN HÀNG" in query.edit_message_text.call_args[0][0]

    # Verify 0 records in DB
    orders = await list_orders_by_status(test_db, OrderStatus.CHO_LAM)
    assert len(orders) == 0


@pytest.mark.asyncio
async def test_order_callback_confirm_saves_to_db(test_db):
    """Callback ord:cf:<id> creates customer and order in DB with status CHO_LAM."""
    draft_id = "feedface"
    draft_data = {
        "draft_id": draft_id,
        "customer_name": "Bác Bình",
        "customer_phone": "0901239876",
        "shipping_address": "321 Trần Hưng Đạo, Q5",
        "items_text": "3 Băng Cẩm Ly",
        "total_amount": 450000,
        "cod_amount": 400000,
        "deposit_amount": 50000,
        "payment_method": "COD",
        "notes": "Giao giờ hành chính",
        "photo_file_ids": ["photo_id_test"],
    }

    update = MagicMock(spec=Update)
    query = MagicMock()
    query.data = f"ord:cf:{draft_id}"
    query.answer = AsyncMock()
    query.edit_message_text = AsyncMock()
    update.callback_query = query

    context = MagicMock(spec=CallbackContext)
    context.user_data = {"pending_orders": {draft_id: draft_data}}
    app_context = MagicMock()
    app_context.db = test_db
    context.application.bot_data = {"app_context": app_context}

    await handle_order_callback(update, context)

    query.answer.assert_awaited_once()
    assert draft_id not in context.user_data["pending_orders"]
    query.edit_message_text.assert_awaited_once()
    success_msg = query.edit_message_text.call_args[0][0]
    assert "ĐÃ LƯU ĐƠN HÀNG THÀNH CÔNG" in success_msg
    assert "Mã đơn:" in success_msg

    # Verify created in SQLite with CHO_LAM status
    orders = await list_orders_by_status(test_db, OrderStatus.CHO_LAM)
    assert len(orders) == 1
    saved_order = orders[0]
    assert saved_order.customer_name == "Bác Bình"
    assert saved_order.customer_phone == "0901239876"
    assert saved_order.shipping_address == "321 Trần Hưng Đạo, Q5"
    assert saved_order.total_amount == 450000
    assert saved_order.cod_amount == 400000
    assert saved_order.photo_file_ids == ["photo_id_test"]


@pytest.mark.asyncio
async def test_order_callback_expired_draft(test_db):
    """When draft_id not found in memory, responds with expiry message."""
    update = MagicMock(spec=Update)
    query = MagicMock()
    query.data = "ord:cf:12345678"
    query.answer = AsyncMock()
    query.edit_message_text = AsyncMock()
    update.callback_query = query

    context = MagicMock(spec=CallbackContext)
    context.user_data = {"pending_orders": {}}
    app_context = MagicMock()
    app_context.db = test_db
    context.application.bot_data = {"app_context": app_context}

    await handle_order_callback(update, context)

    query.answer.assert_awaited_once()
    query.edit_message_text.assert_awaited_once()
    assert "hết hạn" in query.edit_message_text.call_args[0][0]


@pytest.mark.asyncio
async def test_handle_text_order_flow(test_db):
    """handle_text_order calls LLM, saves draft to pending_orders, replies with preview card."""
    update = MagicMock(spec=Update)
    message = MagicMock()
    message.text = "Bác Hùng 0912345678 123 Lê Lợi 2 băng Tuấn Vũ 250k"
    message.chat.send_action = AsyncMock()
    message.reply_text = AsyncMock()
    update.message = message

    extracted_mock = ExtractedOrder(
        customer_name="Bác Hùng",
        customer_phone="0912345678",
        shipping_address="123 Lê Lợi",
        items_text="2 băng Tuấn Vũ",
        total_amount=250000,
        cod_amount=250000,
        deposit_amount=0,
    )

    context = MagicMock(spec=CallbackContext)
    context.user_data = {}
    app_context = MagicMock()
    app_context.db = test_db
    app_context.settings.nine_router_model_id = "gpt-4o-mini"
    app_context.openai_client = MagicMock()
    context.application.bot_data = {"app_context": app_context}

    monkeypatch = pytest.MonkeyPatch()
    monkeypatch.setattr(
        "src.bot.handlers.ingest.extract_order_from_text",
        AsyncMock(return_value=extracted_mock),
    )
    try:
        await handle_text_order(update, context)
    finally:
        monkeypatch.undo()

    message.reply_text.assert_awaited_once()
    kwargs = message.reply_text.call_args[1]
    assert kwargs["parse_mode"] == "HTML"
    assert "250.000 đ" in kwargs["text"]

    pending = context.user_data.get("pending_orders", {})
    assert len(pending) == 1
    draft = list(pending.values())[0]
    assert draft["customer_phone"] == "0912345678"
    assert draft["total_amount"] == 250000


@pytest.mark.asyncio
async def test_handle_text_order_missing_phone(test_db):
    """handle_text_order asks politely if no phone number extracted."""
    update = MagicMock(spec=Update)
    message = MagicMock()
    message.text = "Alo shop ơi cho hỏi giá băng"
    message.chat.send_action = AsyncMock()
    message.reply_text = AsyncMock()
    update.message = message

    extracted_mock = ExtractedOrder(
        customer_name=None,
        customer_phone=None,
    )

    context = MagicMock(spec=CallbackContext)
    context.user_data = {}
    app_context = MagicMock()
    app_context.db = test_db
    app_context.settings.nine_router_model_id = "gpt-4o-mini"
    app_context.openai_client = MagicMock()
    context.application.bot_data = {"app_context": app_context}

    monkeypatch = pytest.MonkeyPatch()
    monkeypatch.setattr(
        "src.bot.handlers.ingest.extract_order_from_text",
        AsyncMock(return_value=extracted_mock),
    )
    try:
        await handle_text_order(update, context)
    finally:
        monkeypatch.undo()

    message.reply_text.assert_awaited_once()
    assert "số điện thoại" in message.reply_text.call_args[0][0]
    assert len(context.user_data.get("pending_orders", {})) == 0
