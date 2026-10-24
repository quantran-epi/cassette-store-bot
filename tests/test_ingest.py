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
    assert "Khách quen: 1 đơn" in reply_text
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
