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
    assert is_customer_search("tìm khách Nhất") is True
    assert is_customer_search("tìm khách Ai") is True

    assert is_customer_search("Khách nào mua nhiều đơn nhất nhỉ") is False
    assert is_customer_search("khách nào chi tiêu nhiều nhất") is False
    assert is_customer_search("top khách mua nhiều đơn") is False
    assert is_customer_search("ai mua nhiều đơn nhất") is False
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
    """When LLM is unavailable (offline), process_search_query falls back to deterministic lookup."""
    await _seed_customers(test_db)

    message = MagicMock(spec=Message)
    message.reply_text = AsyncMock()
    update = MagicMock(spec=Update)
    update.effective_message = message
    update.effective_chat = None

    app_context = MagicMock()
    app_context.db = test_db
    app_context.settings.nine_router_model_id = "gpt-4o-mini"
    app_context.openai_client = None

    context = MagicMock(spec=ContextTypes.DEFAULT_TYPE)
    context.user_data = {}
    context.application.bot_data = {"app_context": app_context}

    await process_search_query(update, context, "tìm khách 0903626566")

    message.reply_text.assert_awaited_once()
    text = message.reply_text.call_args[1]["text"]
    assert "ANH TUẤN" in text
    assert "HỒ SƠ KHÁCH HÀNG" in text


@pytest.mark.asyncio
async def test_process_search_query_routes_customer_with_text_to_sql(test_db):
    """Unified Text-to-SQL search correctly returns customer profile when LLM generates customer query."""
    await _seed_customers(test_db)

    mock_client = AsyncMock()
    mock_choice = MagicMock()
    mock_choice.message.content = (
        '{"list": {"purpose": "Tìm khách tên Tuấn", "sql": "SELECT c.* FROM customers c WHERE unaccent(c.name) LIKE \'%tuan%\' ORDER BY c.id DESC"}, "aggregates": []}'
    )
    mock_client.chat.completions.create.return_value = MagicMock(choices=[mock_choice])

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

    await process_search_query(update, context, "tìm khách tên Tuấn")

    message.reply_text.assert_awaited_once()
    text = message.reply_text.call_args[1]["text"]
    assert "ANH TUẤN" in text
    assert "HỒ SƠ KHÁCH HÀNG" in text


@pytest.mark.asyncio
async def test_search_customer_field_isolation_lam_vs_gia_lam(test_db):
    """User asks 'tìm khách tên lâm ở hà nội'; non-Lâm living at Gia Lâm must NOT match."""
    # Seed customer 1: named Lâm in Hà Nội
    cid1 = await create_customer(
        test_db,
        Customer(
            name="Nguyễn Văn Lâm",
            phones=["0911223344"],
            addresses=["15 Hàng Bông, Hà Nội"],
        ),
    )
    # Seed customer 2: named Tuấn living in Gia Lâm, Hà Nội
    cid2 = await create_customer(
        test_db,
        Customer(
            name="Trần Văn Tuấn",
            phones=["0988776655"],
            addresses=["Thị trấn Trâu Quỳ, Gia Lâm, Hà Nội"],
        ),
    )

    # 1. Deterministic slot-aware fallback test
    results = await search_customers(test_db, "tìm khách tên lâm ở hà nội")
    result_ids = [c.id for c in results]
    assert cid1 in result_ids
    assert cid2 not in result_ids, "Customer living in Gia Lâm must NOT match 'tên lâm'"

    # 2. Text-to-SQL search test
    mock_client = AsyncMock()
    mock_choice = MagicMock()
    mock_choice.message.content = (
        '{"list": {"purpose": "Tìm khách tên Lâm ở Hà Nội", '
        '"sql": "SELECT c.* FROM customers c WHERE unaccent(c.name) LIKE \'%lam%\' AND unaccent(c.addresses) LIKE \'%ha noi%\' ORDER BY c.id DESC"}, '
        '"aggregates": []}'
    )
    mock_client.chat.completions.create.return_value = MagicMock(choices=[mock_choice])

    from src.services.order_search import SearchResultType, run_order_search
    sr = await run_order_search(
        client=mock_client,
        model_id="gpt-4o-mini",
        db=test_db,
        query="tìm khách tên lâm ở hà nội",
    )
    assert sr.result_type == SearchResultType.CUSTOMERS
    assert len(sr.customers) == 1
    assert sr.customers[0].id == cid1


@pytest.mark.asyncio
async def test_customer_chooser_and_paging_callbacks(test_db):
    tuanc, lanc, _ = await _seed_customers(test_db)

    # 6 historical orders across statuses -> 2 pages; only 5 delivered count for classification.
    for i in range(6):
        await create_order(
            test_db,
            Order(
                customer_id=tuanc,
                customer_name="Anh Tuấn",
                customer_phone="0903626566",
                shipping_address="12 Lê Lợi, Hà Nội",
                items_text=f"Băng {i + 1}",
                total_amount=2000000,
                status=OrderStatus.DA_GIAO if i < 5 else OrderStatus.BOM_HANG,
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
    detail_text = query.edit_message_text.call_args[1]["text"]
    assert "Trang 1/2" in detail_text
    assert "TẦN SUẤT:</b> <b>KHÁCH THÂN THIẾT</b> (5 đơn hoàn thành)" in detail_text
    assert "🥇 <b>CHI TIÊU:</b> <b>10.000.000 đ</b>" in detail_text
    assert "CẢNH BÁO: Khách từng có 1 đơn BOM HÀNG!" in detail_text
    assert "🚫 Bom hàng" in detail_text

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


@pytest.mark.asyncio
async def test_customer_search_with_aggregates_classifies_as_customers_and_paginates(test_db):
    """Customer query with count aggregate must classify as CUSTOMERS, render summary, and paginate (not MIXED)."""
    # Seed 7 customers in Quảng Ninh
    qn_ids = []
    for i in range(7):
        cid = await create_customer(
            test_db,
            Customer(
                name=f"Khách QN {i + 1}",
                phones=[f"098100000{i}"],
                addresses=[f"Số {i + 1} Đường Hạ Long, Quảng Ninh"],
            ),
        )
        qn_ids.append(cid)

    # 1. LLM search plan returns BOTH aggregates (COUNT) and list (customers)
    plan_json = (
        '{"list": {"purpose": "Danh sách khách ở Quảng Ninh", '
        '"sql": "SELECT c.* FROM customers c WHERE unaccent(c.addresses) LIKE \'%quang ninh%\' ORDER BY c.id DESC"}, '
        '"aggregates": [{"purpose": "Tổng số khách ở Quảng Ninh", '
        '"sql": "SELECT COUNT(*) AS total_customers FROM customers WHERE unaccent(addresses) LIKE \'%quang ninh%\'"}]}'
    )
    summary_reply = "Dạ shop mình có 7 khách ở Quảng Ninh bác nhé!"

    mock_client = AsyncMock()
    mock_choice1 = MagicMock()
    mock_choice1.message.content = plan_json
    mock_choice2 = MagicMock()
    mock_choice2.message.content = summary_reply

    mock_client.chat.completions.create.side_effect = [
        MagicMock(choices=[mock_choice1]),
        MagicMock(choices=[mock_choice2]),
    ]

    from src.services.order_search import SearchResultType, fetch_search_page, run_order_search
    sr = await run_order_search(
        client=mock_client,
        model_id="gpt-4o-mini",
        db=test_db,
        query="có khách nào ở quảng ninh không?",
    )
    assert sr.result_type == SearchResultType.CUSTOMERS, "Must NOT be classified as MIXED"
    assert sr.total_count == 7
    assert len(sr.customers) == 5
    assert sr.summary_text == summary_reply

    # 2. Process query in bot handler: verify summary prefix and pagination
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

    # Re-mock LLM for process_search_query call
    mock_client.chat.completions.create.side_effect = [
        MagicMock(choices=[mock_choice1]),
        MagicMock(choices=[mock_choice2]),
    ]
    await process_search_query(update, context, "có khách nào ở quảng ninh không?")

    message.reply_text.assert_awaited_once()
    sent_text = message.reply_text.call_args[1]["text"]
    sent_kb = message.reply_text.call_args[1]["reply_markup"]

    # Verify summary prefix is prepended
    assert "Dạ shop mình có 7 khách ở Quảng Ninh bác nhé!" in sent_text
    assert "TÌM THẤY NHIỀU KHÁCH HÀNG" in sent_text
    assert "7 khách" in sent_text
    assert "Trang 1/2" in sent_text

    # Verify buttons include cus_v and pagination cus_ls_pg
    callbacks = [b.callback_data for row in sent_kb.inline_keyboard for b in row]
    cus_v_btns = [c for c in callbacks if c.startswith("cus_v:")]
    assert len(cus_v_btns) == 5
    search_id = cus_v_btns[0].split(":")[2]
    assert f"cus_ls_pg:{search_id}:2" in callbacks

    # 3. Test next page callback (cus_ls_pg:search_id:2)
    query = MagicMock(spec=CallbackQuery)
    query.answer = AsyncMock()
    query.edit_message_text = AsyncMock()
    query.data = f"cus_ls_pg:{search_id}:2"
    update2 = MagicMock(spec=Update)
    update2.callback_query = query

    await handle_customer_callback(update2, context)
    p2_text = query.edit_message_text.call_args[1]["text"]
    p2_kb = query.edit_message_text.call_args[1]["reply_markup"]
    assert "Trang 2/2" in p2_text
    p2_callbacks = [b.callback_data for row in p2_kb.inline_keyboard for b in row]
    p2_cus_v = [c for c in p2_callbacks if c.startswith("cus_v:")]
    assert len(p2_cus_v) == 2
    assert f"cus_ls_pg:{search_id}:1" in p2_callbacks

    # 4. Verify fetch_search_page does not corrupt customer rows into orders
    rejected = await fetch_search_page(test_db, "SELECT * FROM customers", 1, 5)
    assert rejected == [], "fetch_search_page must return empty list for non-order rows"

