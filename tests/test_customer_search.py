from unittest.mock import AsyncMock, MagicMock

import pytest
from telegram import CallbackQuery, Message, Update
from telegram.ext import ContextTypes

from src.bot.handlers.search import handle_customer_callback, process_search_query
from src.db.customers import create_customer, is_customer_search, search_customers
from src.db.orders import create_order
from src.models.customer import Customer
from src.models.order import Order, OrderStatus


def test_is_customer_search_detects_forms():
    assert is_customer_search("tìm khách 0903626566") is True
    assert is_customer_search("tìm khách anh Tuấn") is True
    assert is_customer_search("tìm khách Hà Nội") is True
    assert is_customer_search("khách Hà Nội") is True
    assert is_customer_search("tra cứu khách chị Lan") is True

    assert is_customer_search("tìm đơn anh Tuấn") is False
    assert is_customer_search("hôm nay bán bao nhiêu đơn") is False
    assert is_customer_search("không liên quan") is False


async def _seed_customers(db) -> list[int]:
    ids = []
    ids.append(
        await create_customer(
            db,
            Customer(
                name="Anh Tuấn",
                phones=["0903626566"],
                addresses=["12 Lê Lợi, Hà Nội"],
            ),
        )
    )
    ids.append(
        await create_customer(
            db,
            Customer(
                name="Chị Lan",
                phones=["0912349876"],
                addresses=["45 Hai Bà Trưng, Hà Nội"],
            ),
        )
    )
    ids.append(
        await create_customer(
            db,
            Customer(
                name="Bác Hùng",
                phones=["0987776655"],
                addresses=["99 Nguyễn Trãi, TP HCM"],
            ),
        )
    )
    return ids


@pytest.mark.asyncio
async def test_search_customers_by_name_phone_address(test_db):
    tuanc, lanc, hungc = await _seed_customers(test_db)

    by_name = await search_customers(test_db, "tìm khách anh Tuấn")
    assert [c.id for c in by_name] == [tuanc]

    by_accentless = await search_customers(test_db, "tim khach tuan")
    assert [c.id for c in by_accentless] == [tuanc]

    by_phone = await search_customers(test_db, "tìm khách 0903626566")
    assert [c.id for c in by_phone] == [tuanc]

    by_partial_phone = await search_customers(test_db, "tìm khách 349")
    assert [c.id for c in by_partial_phone] == [lanc]

    by_address = await search_customers(test_db, "tìm khách Hà Nội")
    assert {c.id for c in by_address} == {tuanc, lanc}

    combined = await search_customers(test_db, "tìm khách anh Tuấn 0903626566 Hà Nội")
    assert [c.id for c in combined] == [tuanc]

    for c in await search_customers(test_db, "tìm khách Hà Nội"):
        assert c.id != hungc

@pytest.mark.asyncio
async def test_search_customers_spacing_variant_falls_back_to_substring(test_db):
    # Real DB stores "Hanoi cũ" while the user types "Hà Nội" — whole-word AND misses it.
    cid = await create_customer(
        test_db,
        Customer(
            name="Nguyễn Đức Thành",
            phones=["0903626566"],
            addresses=["22 Trần Quốc Vượng, Cầu Giấy (Hanoi cũ)"],
        ),
    )
    assert [c.id for c in await search_customers(test_db, "tìm khách Hà Nội")] == [cid]


@pytest.mark.asyncio
async def test_process_search_query_routes_customer_without_llm(test_db):
    await _seed_customers(test_db)

    mock_client = MagicMock()
    mock_client.chat.completions.create = AsyncMock()

    message = MagicMock(spec=Message)
    message.reply_text = AsyncMock()
    update = MagicMock(spec=Update)
    update.effective_message = message
    update.effective_chat = None

    app_context = MagicMock()
    app_context.db = test_db
    app_context.settings.nine_router_model_id = "gpt-4o-mini"
    app_context.openai_client = mock_client

    context = MagicMock(spec=ContextTypes.DEFAULT_TYPE)
    context.user_data = {}
    context.application.bot_data = {"app_context": app_context}

    await process_search_query(update, context, "tìm khách 0903626566")

    mock_client.chat.completions.create.assert_not_called()
    message.reply_text.assert_awaited_once()
    text = message.reply_text.call_args[1]["text"]
    assert "ANH TUẤN" in text
    assert "HỒ SƠ KHÁCH HÀNG" in text


@pytest.mark.asyncio
async def test_customer_chooser_and_paging_callbacks(test_db):
    tuanc, lanc, _ = await _seed_customers(test_db)

    # 6 orders for Anh Tuấn -> 2 pages at page size 5
    for i in range(6):
        await create_order(
            test_db,
            Order(
                customer_id=tuanc,
                customer_name="Anh Tuấn",
                customer_phone="0903626566",
                shipping_address="12 Lê Lợi, Hà Nội",
                items_text=f"Băng {i + 1}",
                total_amount=100000,
                status=OrderStatus.DA_GIAO,
            ),
        )

    app_context = MagicMock()
    app_context.db = test_db
    app_context.settings.nine_router_model_id = "gpt-4o-mini"
    app_context.openai_client = MagicMock()

    message = MagicMock(spec=Message)
    message.reply_text = AsyncMock()
    update = MagicMock(spec=Update)
    update.effective_message = message
    update.effective_chat = None

    context = MagicMock(spec=ContextTypes.DEFAULT_TYPE)
    context.user_data = {}
    context.application.bot_data = {"app_context": app_context}

    # 2 customers share "Hà Nội" -> chooser with 2 cus_v buttons
    await process_search_query(update, context, "tìm khách Hà Nội")
    chooser_text = message.reply_text.call_args[1]["text"]
    chooser_kb = message.reply_text.call_args[1]["reply_markup"]
    callbacks = [b.callback_data for row in chooser_kb.inline_keyboard for b in row]
    assert len([c for c in callbacks if c.startswith("cus_v:")]) == 2
    assert "TÌM THẤY NHIỀU KHÁCH HÀNG" in chooser_text

    search_id = next(
        c for c in callbacks if c.startswith(f"cus_v:{tuanc}:")
    ).split(":")[2]

    # Tap the customer -> detail page 1
    query = MagicMock(spec=CallbackQuery)
    query.answer = AsyncMock()
    query.edit_message_text = AsyncMock()
    query.data = f"cus_v:{tuanc}:{search_id}"
    update2 = MagicMock(spec=Update)
    update2.callback_query = query
    await handle_customer_callback(update2, context)
    assert "Trang 1/2" in query.edit_message_text.call_args[1]["text"]

    # Page 2 via cus_pg
    query.edit_message_text.reset_mock()
    query.data = f"cus_pg:{tuanc}:2"
    await handle_customer_callback(update2, context)
    assert "Trang 2/2" in query.edit_message_text.call_args[1]["text"]

    # Back to the chooser via cus_bk
    query.edit_message_text.reset_mock()
    query.data = f"cus_bk:{search_id}"
    await handle_customer_callback(update2, context)
    back_kb = query.edit_message_text.call_args[1]["reply_markup"]
    back_callbacks = [b.callback_data for row in back_kb.inline_keyboard for b in row]
    assert any(c.startswith("cus_v:") for c in back_callbacks)
    assert lanc != tuanc
