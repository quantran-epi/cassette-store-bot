import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest
from telegram import Update
from telegram.ext import CallbackContext

from src.bot.handlers.callbacks import handle_order_callback
from src.bot.handlers.ingest import handle_photo_order, handle_text_order, render_preview_card
from src.db.customers import create_customer, get_customer_by_phone
from src.db.orders import create_order, list_orders_by_status
from src.models.customer import Customer
from src.models.extractor import ExtractedOrder
from src.models.order import Order, OrderStatus


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
        "tape_quantity": 2,
        "tapes": [{"label": "sony 90p", "qty": 2}],
    }
    stats = {"total_orders": 3, "total_spent": 1200000, "bom_count": 0}

    text, reply_markup = render_preview_card(draft, stats)
    # Task 261026-tpe: preview card shows the tape breakdown line.
    assert "PHÔI BĂNG:" in text
    assert "sony 90p" in text

    # HTML escapes check
    assert "&amp;" in text
    assert "&lt;VIP&gt;" in text
    assert "0912345678" in text
    assert "350.000 đ" in text
    assert "300.000 đ" in text
    assert "đã cọc 50.000 đ" in text
    assert "TẦN SUẤT:</b> <b>KHÁCH QUEN</b> (3 đơn hoàn thành)" in text
    assert "🥉 <b>CHI TIÊU:</b> <b>1.200.000 đ</b>" in text
    assert "Khách quen:" not in text

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
    stats = {"total_orders": 0, "total_spent": 0, "bom_count": 1}

    text, _ = render_preview_card(draft, stats)
    assert "TẦN SUẤT:</b> <b>KHÁCH VÃNG LAI</b> (0 đơn hoàn thành)" in text
    assert "🪙 <b>CHI TIÊU:</b> <b>0 đ</b>" in text
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
    assert "MÃ ĐƠN:" in success_msg or "Mã đơn:" in success_msg

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
    # Task 261026-tpe: confirm persists derived tape columns.
    assert saved_order.tape_quantity == 3
    assert saved_order.tapes[0].qty == 3


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
    # Task 261026-tpe: draft must carry derived tape columns.
    assert draft["tape_quantity"] == 2
    assert draft["tapes"][0]["qty"] == 2


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


@pytest.mark.asyncio
async def test_photo_order_caption_extraction(test_db):
    """handle_photo_order extracts caption with LLM and stores highest-res photo_file_id in draft."""
    update = MagicMock(spec=Update)
    message = MagicMock()
    message.caption = "Khách Lan 0903334444 123 Hai Bà Trưng 1 băng Tuấn Vũ 150k"

    # Telegram provides photos in ascending resolutions
    photo_thumb = MagicMock()
    photo_thumb.file_id = "thumb_id"
    photo_hi_res = MagicMock()
    photo_hi_res.file_id = "hi_res_photo_id"
    message.photo = [photo_thumb, photo_hi_res]
    message.chat.send_action = AsyncMock()
    message.reply_text = AsyncMock()
    update.message = message

    extracted_mock = ExtractedOrder(
        customer_name="Khách Lan",
        customer_phone="0903334444",
        shipping_address="123 Hai Bà Trưng",
        items_text="1 băng Tuấn Vũ",
        total_amount=150000,
        cod_amount=150000,
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
        await handle_photo_order(update, context)
    finally:
        monkeypatch.undo()

    message.reply_text.assert_awaited_once()
    assert "150.000 đ" in message.reply_text.call_args[1]["text"]

    pending = context.user_data.get("pending_orders", {})
    assert len(pending) == 1
    draft = list(pending.values())[0]
    assert draft["photo_file_ids"] == ["hi_res_photo_id"]
    assert draft["customer_name"] == "Khách Lan"


@pytest.mark.asyncio
async def test_photo_order_missing_caption(test_db):
    """handle_photo_order asks politely if photo has no caption."""
    update = MagicMock(spec=Update)
    message = MagicMock()
    message.caption = None
    message.photo = [MagicMock(file_id="photo_1")]
    message.reply_text = AsyncMock()
    update.message = message

    context = MagicMock(spec=CallbackContext)
    context.user_data = {}

    await handle_photo_order(update, context)
    message.reply_text.assert_awaited_once()
    assert "chú thích" in message.reply_text.call_args[0][0].lower()


@pytest.mark.asyncio
async def test_returning_customer_stats_and_bom_warning(test_db):
    """Returning customer displays order count, total spent, and BOM HÀNG warning in preview card."""
    cust_id = await create_customer(
        test_db,
        Customer(name="Khách Bom", phones=["0909998888"], addresses=["Địa chỉ cũ"]),
    )
    # Add a BOM_HANG order for this customer
    await create_order(
        test_db,
        Order(
            customer_id=cust_id,
            customer_name="Khách Bom",
            customer_phone="0909998888",
            shipping_address="Địa chỉ cũ",
            items_text="Băng cũ",
            total_amount=200000,
            status=OrderStatus.BOM_HANG,
        ),
    )

    update = MagicMock(spec=Update)
    message = MagicMock()
    message.text = "Khách Bom 0909998888 1 băng Chế Linh 180k"
    message.chat.send_action = AsyncMock()
    message.reply_text = AsyncMock()
    update.message = message

    extracted_mock = ExtractedOrder(
        customer_name="Khách Bom",
        customer_phone="0909998888",
        shipping_address=None,
        items_text="1 băng Chế Linh",
        total_amount=180000,
        cod_amount=180000,
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
    reply_text = message.reply_text.call_args[1]["text"]
    assert "CẢNH BÁO: Khách từng có 1 đơn BOM HÀNG!" in reply_text
    assert "TẦN SUẤT:</b> <b>KHÁCH VÃNG LAI</b> (0 đơn hoàn thành)" in reply_text
    assert "🪙 <b>CHI TIÊU:</b> <b>0 đ</b>" in reply_text
    # Check auto-filled single address
    assert "tự lấy từ đơn trước" in reply_text
    assert "Địa chỉ cũ" in reply_text


@pytest.mark.asyncio
async def test_address_auto_fill_and_picker_buttons(test_db):
    """Customer with 2+ addresses gets inline address picker buttons ord:ad:<id>:<idx>."""
    await create_customer(
        test_db,
        Customer(
            name="Khách Nhiều Nhà",
            phones=["0912000111"],
            addresses=["123 Lê Lợi, Q1, HCM", "456 Nguyễn Trãi, Q5, HCM"],
        ),
    )

    update = MagicMock(spec=Update)
    message = MagicMock()
    message.text = "0912000111 2 băng 200k"
    message.chat.send_action = AsyncMock()
    message.reply_text = AsyncMock()
    update.message = message

    extracted_mock = ExtractedOrder(
        customer_name="Khách Nhiều Nhà",
        customer_phone="0912000111",
        shipping_address=None,
        items_text="2 băng",
        total_amount=200000,
        cod_amount=200000,
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
    reply_markup = message.reply_text.call_args[1]["reply_markup"]
    keyboard = reply_markup.inline_keyboard
    # Should have address button row(s) plus confirm/cancel row
    assert len(keyboard) >= 2
    address_callbacks = [
        btn.callback_data for row in keyboard for btn in row if "ord:ad:" in btn.callback_data
    ]
    assert len(address_callbacks) == 2
    assert address_callbacks[0].endswith(":0")
    assert address_callbacks[1].endswith(":1")


@pytest.mark.asyncio
async def test_address_selection_callback(test_db):
    """Callback ord:ad:<draft_id>:<index> updates shipping_address and re-renders preview card."""
    draft_id = "abcd1234"
    draft_data = {
        "draft_id": draft_id,
        "customer_name": "Khách Test",
        "customer_phone": "0912000111",
        "shipping_address": "456 Nguyễn Trãi, Q5, HCM",
        "available_addresses": ["123 Lê Lợi, Q1, HCM", "456 Nguyễn Trãi, Q5, HCM"],
        "items_text": "2 băng",
        "total_amount": 200000,
        "cod_amount": 200000,
        "deposit_amount": 0,
        "payment_method": "COD",
        "notes": "",
        "photo_file_ids": [],
    }

    update = MagicMock(spec=Update)
    query = MagicMock()
    # Click on first address (index 0)
    query.data = f"ord:ad:{draft_id}:0"
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
    # Draft should be updated in memory to the selected address
    assert (
        context.user_data["pending_orders"][draft_id]["shipping_address"] == "123 Lê Lợi, Q1, HCM"
    )
    query.edit_message_text.assert_awaited_once()
    kwargs = query.edit_message_text.call_args[1]
    edited_text = kwargs.get("text") or query.edit_message_text.call_args[0][0]
    assert "123 Lê Lợi, Q1, HCM" in edited_text


@pytest.mark.asyncio
async def test_llm_gateway_error_fallback(test_db):
    """When LLM gateway fails with network/timeout exception, bot replies politely."""
    update = MagicMock(spec=Update)
    message = MagicMock()
    message.text = "0912345678 Đặt 2 băng"
    message.chat.send_action = AsyncMock()
    message.reply_text = AsyncMock()
    update.message = message

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
        AsyncMock(side_effect=Exception("Connection timeout to 9router gateway")),
    )
    try:
        await handle_text_order(update, context)
    finally:
        monkeypatch.undo()

    message.reply_text.assert_awaited_once()
    reply_msg = message.reply_text.call_args[0][0]
    assert "gián đoạn kết nối" in reply_msg
    assert len(context.user_data.get("pending_orders", {})) == 0


@pytest.mark.asyncio
async def test_order_confirmation_appends_new_address_for_existing_customer(test_db):
    """When confirming order with new address, it is idempotently added to customer's addresses."""
    await create_customer(
        test_db,
        Customer(
            name="Anh Tuấn",
            phones=["0977112233"],
            addresses=["Địa chỉ cũ 1"],
        ),
    )

    draft_id = "feed1122"
    draft_data = {
        "draft_id": draft_id,
        "customer_name": "Anh Tuấn",
        "customer_phone": "0977112233",
        "shipping_address": "Địa chỉ mới 2",
        "items_text": "1 băng",
        "total_amount": 100000,
        "cod_amount": 100000,
        "deposit_amount": 0,
        "payment_method": "COD",
        "notes": "",
        "photo_file_ids": ["photo_123"],
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

    # Customer should now have both addresses
    customer = await get_customer_by_phone(test_db, "0977112233")
    assert customer is not None
    assert len(customer.addresses) == 2
    assert "Địa chỉ cũ 1" in customer.addresses
    assert "Địa chỉ mới 2" in customer.addresses


@pytest.mark.asyncio
async def test_media_group_album_bundled_single_preview(test_db):
    """Media group album bundles all photo_file_ids into single draft and sends 1 preview card."""
    media_group_id = "album_123"

    # Photo 1 has caption
    update1 = MagicMock(spec=Update)
    msg1 = MagicMock()
    msg1.media_group_id = media_group_id
    msg1.caption = "Khách Mai 0988112233 456 Lê Lợi 2 băng Chế Linh 300k"
    msg1.photo = [MagicMock(file_id="photo_1")]
    msg1.chat.send_action = AsyncMock()
    msg1.reply_text = AsyncMock()
    update1.message = msg1

    # Photo 2 has no caption
    update2 = MagicMock(spec=Update)
    msg2 = MagicMock()
    msg2.media_group_id = media_group_id
    msg2.caption = None
    msg2.photo = [MagicMock(file_id="photo_2")]
    msg2.chat.send_action = AsyncMock()
    msg2.reply_text = AsyncMock()
    update2.message = msg2

    # Photo 3 has no caption
    update3 = MagicMock(spec=Update)
    msg3 = MagicMock()
    msg3.media_group_id = media_group_id
    msg3.caption = None
    msg3.photo = [MagicMock(file_id="photo_3")]
    msg3.chat.send_action = AsyncMock()
    msg3.reply_text = AsyncMock()
    update3.message = msg3

    extracted_mock = ExtractedOrder(
        customer_name="Khách Mai",
        customer_phone="0988112233",
        shipping_address="456 Lê Lợi",
        items_text="2 băng Chế Linh",
        total_amount=300000,
        cod_amount=300000,
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
    monkeypatch.setattr("src.bot.handlers.ingest.MEDIA_GROUP_DEBOUNCE_SECONDS", 0.05)

    try:
        await asyncio.gather(
            handle_photo_order(update1, context),
            handle_photo_order(update2, context),
            handle_photo_order(update3, context),
        )
        # Debounce finalizer now runs as a background task; let it finish before undoing patches.
        await asyncio.sleep(0.2)
    finally:
        monkeypatch.undo()

    # Update 1 should have replied with preview card
    msg1.reply_text.assert_awaited_once()
    # Update 2 and 3 should NOT have replied with any warning
    msg2.reply_text.assert_not_awaited()
    msg3.reply_text.assert_not_awaited()

    # Check preview card content
    preview_text = msg1.reply_text.call_args[1]["text"]
    assert "3 ảnh" in preview_text
    assert "300.000 đ" in preview_text

    # Check pending_orders has exactly 1 draft with all 3 photo IDs
    pending = context.user_data.get("pending_orders", {})
    assert len(pending) == 1
    draft = list(pending.values())[0]
    assert draft["customer_name"] == "Khách Mai"
    assert draft["photo_file_ids"] == ["photo_1", "photo_2", "photo_3"]


@pytest.mark.asyncio
async def test_media_group_sequential_updates_do_not_drop_photos(test_db):
    """Sequential pump (real production order) still collects all 3 album photos into 1 draft."""
    media_group_id = "album_seq_789"

    def _make_update(file_id: str, caption: str | None):
        upd = MagicMock(spec=Update)
        msg = MagicMock()
        msg.media_group_id = media_group_id
        msg.caption = caption
        msg.photo = [MagicMock(file_id=file_id)]
        msg.chat.send_action = AsyncMock()
        msg.reply_text = AsyncMock()
        upd.message = msg
        return upd

    update1 = _make_update("photo_1", "Khách Mai 0988112233 456 Lê Lợi 2 băng Chế Linh 300k")
    update2 = _make_update("photo_2", None)
    update3 = _make_update("photo_3", None)

    extracted_mock = ExtractedOrder(
        customer_name="Khách Mai",
        customer_phone="0988112233",
        shipping_address="456 Lê Lợi",
        items_text="2 băng Chế Linh",
        total_amount=300000,
        cod_amount=300000,
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
    monkeypatch.setattr("src.bot.handlers.ingest.MEDIA_GROUP_DEBOUNCE_SECONDS", 0.05)

    try:
        # Await one at a time: this is how PTB's sequential pump delivers album updates.
        await handle_photo_order(update1, context)
        await handle_photo_order(update2, context)
        await handle_photo_order(update3, context)
        await asyncio.sleep(0.2)
    finally:
        monkeypatch.undo()

    update1.message.reply_text.assert_awaited_once()
    update2.message.reply_text.assert_not_awaited()
    update3.message.reply_text.assert_not_awaited()
    assert "3 ảnh" in update1.message.reply_text.call_args[1]["text"]

    pending = context.user_data.get("pending_orders", {})
    assert len(pending) == 1
    draft = list(pending.values())[0]
    assert draft["photo_file_ids"] == ["photo_1", "photo_2", "photo_3"]


@pytest.mark.asyncio
async def test_media_group_album_missing_all_captions(test_db):
    """When all photos in album lack caption, only 1 warning message is sent."""
    media_group_id = "album_nocap_456"

    update1 = MagicMock(spec=Update)
    msg1 = MagicMock()
    msg1.media_group_id = media_group_id
    msg1.caption = None
    msg1.photo = [MagicMock(file_id="p1")]
    msg1.reply_text = AsyncMock()
    update1.message = msg1

    update2 = MagicMock(spec=Update)
    msg2 = MagicMock()
    msg2.media_group_id = media_group_id
    msg2.caption = ""
    msg2.photo = [MagicMock(file_id="p2")]
    msg2.reply_text = AsyncMock()
    update2.message = msg2

    update3 = MagicMock(spec=Update)
    msg3 = MagicMock()
    msg3.media_group_id = media_group_id
    msg3.caption = None
    msg3.photo = [MagicMock(file_id="p3")]
    msg3.reply_text = AsyncMock()
    update3.message = msg3

    context = MagicMock(spec=CallbackContext)
    context.user_data = {}

    monkeypatch = pytest.MonkeyPatch()
    monkeypatch.setattr("src.bot.handlers.ingest.MEDIA_GROUP_DEBOUNCE_SECONDS", 0.05)
    try:
        await asyncio.gather(
            handle_photo_order(update1, context),
            handle_photo_order(update2, context),
            handle_photo_order(update3, context),
        )
        # Wait for the background finalizer to emit its single warning.
        await asyncio.sleep(0.2)
    finally:
        monkeypatch.undo()

    msg1.reply_text.assert_awaited_once()
    assert "chú thích" in msg1.reply_text.call_args[0][0].lower()
    msg2.reply_text.assert_not_awaited()
    msg3.reply_text.assert_not_awaited()
    assert len(context.user_data.get("pending_orders", {})) == 0


@pytest.mark.asyncio
async def test_single_photo_without_media_group_retains_behavior(test_db):
    """Single photo without media_group_id processes immediately with 1 photo_file_id."""
    update = MagicMock(spec=Update)
    message = MagicMock()
    message.media_group_id = None
    message.caption = "Khách Hùng 0912345678 123 Lê Lợi 1 băng Tuấn Vũ 150k"
    message.photo = [MagicMock(file_id="single_photo_1")]
    message.chat.send_action = AsyncMock()
    message.reply_text = AsyncMock()
    update.message = message

    extracted_mock = ExtractedOrder(
        customer_name="Khách Hùng",
        customer_phone="0912345678",
        shipping_address="123 Lê Lợi",
        items_text="1 băng Tuấn Vũ",
        total_amount=150000,
        cod_amount=150000,
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
        await handle_photo_order(update, context)
    finally:
        monkeypatch.undo()

    message.reply_text.assert_awaited_once()
    pending = context.user_data.get("pending_orders", {})
    assert len(pending) == 1
    draft = list(pending.values())[0]
    assert draft["photo_file_ids"] == ["single_photo_1"]


@pytest.mark.asyncio
async def test_returning_customer_name_autofill_and_preview_card(test_db):
    """When returning customer order has no name in message, name is auto-filled from DB."""
    from src.bot.handlers.ingest import process_extracted_order

    # Pre-create customer in DB
    cust_id = await create_customer(
        test_db,
        Customer(
            name="Bác Ba Phi",
            phones=["0918889999"],
            addresses=["Ấp 4, Cà Mau"],
        ),
    )

    update = MagicMock(spec=Update)
    message = MagicMock()
    message.reply_text = AsyncMock()
    update.message = message

    context = MagicMock(spec=CallbackContext)
    context.user_data = {}
    app_context = MagicMock()
    app_context.db = test_db
    context.application.bot_data = {"app_context": app_context}

    # Order has no customer_name
    extracted = ExtractedOrder(
        customer_name=None,
        customer_phone="0918889999",
        shipping_address=None,
        items_text="3 cuốn Tân cổ",
        total_amount=300000,
        cod_amount=300000,
    )

    await process_extracted_order(update, context, extracted, raw_text="0918889999 3 cuốn Tân cổ")

    message.reply_text.assert_awaited_once()
    call_kwargs = message.reply_text.call_args[1]
    preview_text = call_kwargs["text"]

    # Verify customer name was auto-filled from DB instead of "[Chưa có]"
    assert "Bác Ba Phi" in preview_text
    assert "[Chưa có]" not in preview_text
    assert "Ấp 4, Cà Mau" in preview_text
    assert "0918889999" in preview_text
    assert "3 cuốn Tân cổ" in preview_text
    assert "300.000 đ" in preview_text

    # Check pending order draft data
    pending = context.user_data.get("pending_orders", {})
    assert len(pending) == 1
    draft = list(pending.values())[0]
    assert draft["customer_name"] == "Bác Ba Phi"
    assert draft["customer_id"] == cust_id


@pytest.mark.asyncio
async def test_preview_card_multi_address_radio_and_customer_detail_nav(test_db):
    """Multi-address customer gets radio buttons (🔘 / ⚪), customer detail button, and back button navigation."""
    cust_id = await create_customer(
        test_db,
        Customer(
            name="Nguyễn Văn A",
            phones=["0901234567"],
            addresses=["123 Lê Lợi, Q1", "456 Nguyễn Trãi, Q5"],
        ),
    )
    # Create 6 orders for pagination test (page size = 5 -> 2 pages)
    for i in range(6):
        await create_order(
            test_db,
            Order(
                customer_id=cust_id,
                customer_name="Nguyễn Văn A",
                customer_phone="0901234567",
                shipping_address="123 Lê Lợi, Q1",
                items_text=f"Băng số {i + 1}",
                total_amount=150000,
                cod_amount=150000,
                status=OrderStatus.DA_GIAO,
            ),
        )

    draft_id = "abcd9999"
    draft_data = {
        "draft_id": draft_id,
        "customer_id": cust_id,
        "customer_name": "Nguyễn Văn A",
        "customer_phone": "0901234567",
        "shipping_address": "123 Lê Lợi, Q1",
        "available_addresses": ["123 Lê Lợi, Q1", "456 Nguyễn Trãi, Q5"],
        "items_text": "2 băng mới",
        "total_amount": 200000,
        "cod_amount": 200000,
        "deposit_amount": 0,
        "payment_method": "COD",
        "notes": "",
        "photo_file_ids": [],
        "stats": {"total_orders": 6, "total_spent": 900000, "bom_count": 0},
    }

    # 1. Test preview card rendering with radio buttons and customer detail button
    text, markup = render_preview_card(draft_data, draft_data["stats"])
    assert "Nguyễn Văn A" in text
    assert "0901234567" in text
    assert "123 Lê Lợi, Q1" in text
    assert "2 băng mới" in text
    assert "200.000 đ" in text

    buttons = [btn for row in markup.inline_keyboard for btn in row]
    btn_texts = [b.text for b in buttons]

    # Verify radio buttons
    assert any("🔘" in t and "123 Lê Lợi" in t for t in btn_texts)
    assert any("⚪" in t and "456 Nguyễn Trãi" in t for t in btn_texts)

    # Verify customer detail button
    cust_btn = next((b for b in buttons if b.callback_data.startswith("ord:cs:")), None)
    assert cust_btn is not None
    assert "Chi tiết khách (6 đơn xong)" in cust_btn.text
    assert cust_btn.callback_data == f"ord:cs:{draft_id}:1"

    # 2. Test clicking customer detail button (ord:cs:<draft_id>:1)
    update = MagicMock(spec=Update)
    query = MagicMock()
    query.data = f"ord:cs:{draft_id}:1"
    query.answer = AsyncMock()
    query.edit_message_text = AsyncMock()
    update.callback_query = query

    context = MagicMock(spec=CallbackContext)
    context.user_data = {"pending_orders": {draft_id: draft_data}}
    app_context = MagicMock()
    app_context.db = test_db
    context.application.bot_data = {"app_context": app_context}

    await handle_order_callback(update, context)

    query.edit_message_text.assert_awaited_once()
    cust_view_text = query.edit_message_text.call_args[1]["text"]
    cust_view_markup = query.edit_message_text.call_args[1]["reply_markup"]

    assert "HỒ SƠ KHÁCH HÀNG: NGUYỄN VĂN A" in cust_view_text
    assert "Trang 1/2" in cust_view_text
    assert "TẦN SUẤT:</b> <b>KHÁCH THÂN THIẾT</b> (6 đơn hoàn thành)" in cust_view_text
    assert "🪙 <b>CHI TIÊU:</b> <b>900.000 đ</b>" in cust_view_text

    cust_view_btns = [btn for row in cust_view_markup.inline_keyboard for btn in row]
    # Check pagination: should have Next page button and Back button
    next_btn = next((b for b in cust_view_btns if b.callback_data == f"ord:cs:{draft_id}:2"), None)
    back_btn = next((b for b in cust_view_btns if b.callback_data == f"ord:bk:{draft_id}"), None)
    assert next_btn is not None
    assert back_btn is not None
    assert "Quay lại" in back_btn.text

    # 3. Test clicking back button (ord:bk:<draft_id>)
    query.edit_message_text.reset_mock()
    query.data = f"ord:bk:{draft_id}"
    await handle_order_callback(update, context)

    query.edit_message_text.assert_awaited_once()
    back_text = query.edit_message_text.call_args[1]["text"]
    assert "ĐƠN HÀNG MỚI (Xem trước)" in back_text
    assert "Nguyễn Văn A" in back_text
    assert "2 băng mới" in back_text


@pytest.mark.asyncio
async def test_order_mutation_auto_appends_new_address_to_customer(test_db):
    """When mutating order to change shipping_address, customer profile is automatically updated with new address."""
    from src.db.customers import get_customer_by_id
    from src.db.orders import mutate_order_with_lock

    cust_id = await create_customer(
        test_db,
        Customer(
            name="Chị Lan",
            phones=["0933221100"],
            addresses=["10 Phố Huế, Hà Nội"],
        ),
    )
    order_id = await create_order(
        test_db,
        Order(
            customer_id=cust_id,
            customer_name="Chị Lan",
            customer_phone="0933221100",
            shipping_address="10 Phố Huế, Hà Nội",
            items_text="1 băng Cẩm Ly",
            total_amount=120000,
            cod_amount=120000,
            status=OrderStatus.CHO_LAM,
        ),
    )

    # Fetch initial order to get timestamp
    from src.db.orders import get_order_by_id

    order = await get_order_by_id(test_db, order_id)
    assert order is not None

    # Mutate shipping_address to a new address
    success, changes, fresh = await mutate_order_with_lock(
        db=test_db,
        order_id=order_id,
        expected_updated_at=order.updated_at.isoformat() if order.updated_at else None,
        delta_dict={"shipping_address": "25 Bà Triệu, Hà Nội"},
        user_name="Admin",
    )
    assert success is True
    assert fresh.shipping_address == "25 Bà Triệu, Hà Nội"

    # Customer profile should now contain both addresses
    cust = await get_customer_by_id(test_db, cust_id)
    assert cust is not None
    assert len(cust.addresses) == 2
    assert "10 Phố Huế, Hà Nội" in cust.addresses
    assert "25 Bà Triệu, Hà Nội" in cust.addresses



def _draft_edit_harness(text, draft_overrides=None, delta=None):
    """Build (update, context) for a draft-edit message and patch the extractor."""
    from unittest.mock import patch

    from src.models.mutation import OrderMutationDelta

    update = MagicMock()
    update.message.text = text
    update.message.chat.send_action = AsyncMock()
    update.message.reply_text = AsyncMock()

    draft = {
        "draft_id": "test1234",
        "customer_name": "Anh Hưng",
        "customer_phone": "0912345678",
        "shipping_address": "12 Lý Thường Kiệt, Hoàn Kiếm, Hà Nội",
        "items_text": "2 Băng Chế Linh",
        "total_amount": 200000,
        "cod_amount": 200000,
        "deposit_amount": 0,
        "tape_quantity": 2,
        "tapes": [],
        "tape_genres": [],
        "tape_artists": [],
        "notes": "khách dặn gọi trước",
        "reminder_at": None,
        "reminder_note": None,
    }
    draft.update(draft_overrides or {})

    context = MagicMock()
    context.user_data = {
        "pending_orders": {"test1234": draft},
        "active_draft_id": "test1234",
    }
    context.application.bot_data = {
        "openai_client": AsyncMock(),
        "settings": MagicMock(nine_router_model_id="test-model"),
    }
    return update, context, draft, patch(
        "src.services.mutation_extractor.extract_mutation_delta",
        AsyncMock(return_value=delta or OrderMutationDelta()),
    )


@pytest.mark.asyncio
async def test_draft_edit_reminder_only_does_not_touch_notes():
    """A delivery appointment sets draft reminder fields and leaves notes alone."""
    from src.models.mutation import OrderMutationDelta

    delta = OrderMutationDelta(
        new_reminder_at="2026-10-28 10:00",
        new_reminder_note="Gửi hàng cho khách",
    )
    update, context, draft, patcher = _draft_edit_harness(
        "khách hẹn sáng mai 10h gửi hàng", delta=delta
    )
    with patcher:
        await handle_text_order(update, context)

    assert draft["reminder_at"] == "2026-10-28 10:00"
    assert draft["reminder_note"] == "Gửi hàng cho khách"
    assert draft["notes"] == "khách dặn gọi trước"
    assert "LỊCH NHẮC" in update.message.reply_text.call_args[1]["text"]


@pytest.mark.asyncio
async def test_draft_edit_clear_reminder_wipes_both_fields():
    """clear_reminder drops both reminder fields without touching notes."""
    from src.models.mutation import OrderMutationDelta

    update, context, draft, patcher = _draft_edit_harness(
        "thôi không nhắc nữa",
        draft_overrides={"reminder_at": "2026-10-28 10:00", "reminder_note": "Gửi hàng"},
        delta=OrderMutationDelta(clear_reminder=True),
    )
    with patcher:
        await handle_text_order(update, context)

    assert draft["reminder_at"] is None
    assert draft["reminder_note"] is None
    assert draft["notes"] == "khách dặn gọi trước"


@pytest.mark.asyncio
async def test_draft_edit_notes_replacement_keeps_reminder():
    """A notes edit replaces notes but leaves an existing reminder intact."""
    from src.models.mutation import OrderMutationDelta

    update, context, draft, patcher = _draft_edit_harness(
        "ghi chú hàng dễ vỡ",
        draft_overrides={"reminder_at": "2026-10-28 10:00", "reminder_note": "Gửi hàng"},
        delta=OrderMutationDelta(new_notes="hàng dễ vỡ"),
    )
    with patcher:
        await handle_text_order(update, context)

    assert draft["notes"] == "hàng dễ vỡ"
    assert draft["reminder_at"] == "2026-10-28 10:00"


def test_mutation_prompt_routes_time_to_reminder_and_has_date_hook():
    """Reminder fields are documented and the runtime prompt carries the current date."""
    from datetime import datetime
    from zoneinfo import ZoneInfo

    from src.services.mutation_extractor import (
        MUTATION_SYSTEM_PROMPT,
        build_mutation_system_prompt,
    )

    for field in ("new_reminder_at", "new_reminder_note", "clear_reminder"):
        assert field in MUTATION_SYSTEM_PROMPT
    assert "TUYỆT ĐỐI KHÔNG đưa ngày/giờ hẹn" in MUTATION_SYSTEM_PROMPT

    now = datetime(2026, 10, 27, 15, 30, tzinfo=ZoneInfo("Asia/Ho_Chi_Minh"))
    prompt = build_mutation_system_prompt(now)
    assert "2026-10-27 15:30" in prompt
    assert "2026-10-28" in prompt
    assert "Thứ 3" in prompt
