from unittest.mock import AsyncMock, MagicMock, patch
import pytest
from telegram import Update
from telegram.ext import ContextTypes

from src.db.connection import remove_accents
from src.services.order_search import (
    is_search_intent,
    sanitize_and_validate_sql,
)


def test_unaccent_remove_accents():
    assert remove_accents("Tuấn Vũ") == "tuan vu"
    assert remove_accents("Đà Nẵng") == "da nang"
    assert remove_accents("Đức Thành") == "duc thanh"
    assert remove_accents(None) == ""
    assert remove_accents("") == ""


@pytest.mark.asyncio
async def test_unaccent_sqlite(test_db):
    cursor = await test_db.execute("SELECT unaccent('Tuấn Vũ') AS unaccented")
    row = await cursor.fetchone()
    assert row["unaccented"] == "tuan vu"

    cursor = await test_db.execute("SELECT unaccent('Đà Nẵng') AS unaccented")
    row = await cursor.fetchone()
    assert row["unaccented"] == "da nang"


def test_sql_sanitizer_valid():
    sql1 = "SELECT * FROM orders"
    assert sanitize_and_validate_sql(sql1) == "SELECT * FROM orders LIMIT 20"

    sql2 = "SELECT * FROM orders WHERE status = 'CHO_LAM' LIMIT 5"
    assert sanitize_and_validate_sql(sql2) == "SELECT * FROM orders WHERE status = 'CHO_LAM' LIMIT 5"

    sql3 = "```sql\nSELECT o.* FROM orders o;\n```"
    assert sanitize_and_validate_sql(sql3) == "SELECT o.* FROM orders o LIMIT 20"

    sql4 = "select count(*) from orders;"
    assert sanitize_and_validate_sql(sql4) == "select count(*) from orders LIMIT 20"


def test_sql_sanitizer_rejections():
    # Multi-statement injection defense
    with pytest.raises(ValueError, match="nhiều câu lệnh SQL"):
        sanitize_and_validate_sql("SELECT * FROM orders; DROP TABLE orders")

    with pytest.raises(ValueError, match="nhiều câu lệnh SQL"):
        sanitize_and_validate_sql("SELECT 1; SELECT 2;")

    # Not starting with SELECT
    with pytest.raises(ValueError, match="bắt đầu bằng SELECT"):
        sanitize_and_validate_sql("DELETE FROM orders")

    with pytest.raises(ValueError, match="bắt đầu bằng SELECT"):
        sanitize_and_validate_sql("INSERT INTO orders (customer_name) VALUES ('x')")

    with pytest.raises(ValueError, match="bắt đầu bằng SELECT"):
        sanitize_and_validate_sql("SHOW TABLES")

    # Forbidden DDL/DML keywords inside SELECT
    with pytest.raises(ValueError, match="từ khoá cấm"):
        sanitize_and_validate_sql("SELECT * FROM orders WHERE id IN (DELETE FROM orders)")

    with pytest.raises(ValueError, match="từ khoá cấm"):
        sanitize_and_validate_sql("SELECT * FROM orders WHERE 1=1 OR PRAGMA schema_version")

    with pytest.raises(ValueError, match="từ khoá cấm"):
        sanitize_and_validate_sql("SELECT * FROM (ALTER TABLE orders ADD COLUMN x TEXT)")


def test_is_search_intent():
    assert is_search_intent("tìm đơn anh Tuấn") is True
    assert is_search_intent("Tìm đơn Tuấn Vũ") is True
    assert is_search_intent("  tra cứu đơn hôm qua ") is True
    assert is_search_intent("kiểm tra đơn 123") is True
    assert is_search_intent("xem lại đơn anh Hải") is True
    assert is_search_intent("hỏi đơn hàng gửi đi Đà Nẵng") is True

    # Negative cases
    assert is_search_intent("Tuấn Vũ 2 cuốn gửi 123 Lê Lợi 0903123456") is False
    assert is_search_intent("Khánh Ly hạ trắng thu 300k") is False
    assert is_search_intent("đơn mới nè") is False


def test_is_search_intent_conversational_questions():
    """Verify natural Vietnamese conversational inquiry questions are detected per G-04-3."""
    # Positive conversational inquiry questions
    assert is_search_intent("a Biên đã mua băng bao giờ chưa nhỉ?") is True
    assert is_search_intent("anh Nam mua mấy đơn rồi?") is True
    assert is_search_intent("chị Mai có mua băng bao giờ chưa?") is True
    assert is_search_intent("hôm nay bán được bao nhiêu đơn?") is True
    assert is_search_intent("anh Nam đã từng mua băng chưa?") is True
    # Multiline query test with re.DOTALL per WR-03
    assert is_search_intent("Anh Tuấn đã từng mua băng\nbao giờ chưa?") is True

    # Negative cases (order ingestion texts should remain False)
    assert is_search_intent("Khách Tuấn 0903123456 2 cuốn Tuấn Vũ 200k") is False
    assert is_search_intent("Bác Ba 0903123456 2 cuốn Chế Linh") is False
    assert is_search_intent("Khách mua 2 cuốn Tuấn Vũ gửi 123 Lê Lợi") is False
    # CR-01 regression cases: orders with conversational phrases but containing phone numbers
    assert is_search_intent("Khách mua 2 cuốn Tuấn Vũ (hỏi xem có chưa nhỉ) gửi 123 Lê Lợi 0903123456") is False
    assert is_search_intent("Đơn anh Tuấn 2 cuốn ship hôm nay được không nhỉ 0912345678") is False
    # Explicit prefix with phone number should still be treated as search
    assert is_search_intent("tìm đơn số 0903123456 xem mua gì chưa nhỉ") is True


def test_generate_sql_from_query_prompt():
    from datetime import datetime
    from zoneinfo import ZoneInfo
    from src.services.order_search import build_text_to_sql_prompt

    fixed_time = datetime(2026, 10, 25, 9, 30, 0, tzinfo=ZoneInfo("Asia/Ho_Chi_Minh"))
    sys_prompt, user_prompt = build_text_to_sql_prompt("tìm đơn Tuấn Vũ hôm nay", current_time=fixed_time)

    assert "CREATE TABLE IF NOT EXISTS orders" in sys_prompt or "Table orders" in sys_prompt
    assert "2026-10-25 09:30:00" in sys_prompt
    assert "2026-10-25" in sys_prompt
    assert "+7 hours" in sys_prompt
    assert "<query>tìm đơn Tuấn Vũ hôm nay</query>" in user_prompt


@pytest.mark.asyncio
async def test_execute_search_query_success(test_db):
    from unittest.mock import AsyncMock, MagicMock
    from src.services.order_search import execute_natural_language_search

    # Seed an order in test_db
    await test_db.execute(
        """
        INSERT INTO orders (customer_name, customer_phone, shipping_address, items_text, total_amount, cod_amount)
        VALUES ('Anh Tuấn', '0903123456', 'Hà Nội', '2 cuốn Tuấn Vũ', 200000, 200000)
        """
    )
    await test_db.commit()

    # Mock OpenAI client
    mock_client = AsyncMock()
    mock_choice = MagicMock()
    mock_choice.message.content = "SELECT * FROM orders WHERE customer_name LIKE '%Tuấn%'"
    mock_resp = MagicMock(choices=[mock_choice])
    mock_client.chat.completions.create.return_value = mock_resp

    sql, rows = await execute_natural_language_search(
        client=mock_client,
        model_id="mock-model",
        db=test_db,
        query="tìm đơn anh Tuấn",
    )

    assert "SELECT * FROM orders" in sql
    assert len(rows) == 1
    assert rows[0]["customer_name"] == "Anh Tuấn"


@pytest.mark.asyncio
async def test_execute_search_query_retry_1shot(test_db):
    from unittest.mock import AsyncMock, MagicMock
    import sqlite3
    from src.services.order_search import execute_natural_language_search

    # Seed an order in test_db
    await test_db.execute(
        """
        INSERT INTO orders (customer_name, customer_phone, shipping_address, items_text, total_amount, cod_amount)
        VALUES ('Chị Lan', '0912345678', 'Đà Nẵng', '1 cuốn Giao Linh', 150000, 150000)
        """
    )
    await test_db.commit()

    mock_client = AsyncMock()
    # First response has syntax error (NONEXISTENT_FUNCTION), second response fixes it
    resp_bad = MagicMock(choices=[MagicMock(message=MagicMock(content="SELECT NONEXISTENT_FN(foo) FROM orders"))])
    resp_good = MagicMock(choices=[MagicMock(message=MagicMock(content="SELECT * FROM orders WHERE customer_name LIKE '%Lan%'"))])
    mock_client.chat.completions.create.side_effect = [resp_bad, resp_good]

    sql, rows = await execute_natural_language_search(
        client=mock_client,
        model_id="mock-model",
        db=test_db,
        query="tìm đơn chị Lan",
    )

    assert mock_client.chat.completions.create.call_count == 2
    # Verify retry call included error message
    retry_call_args = mock_client.chat.completions.create.call_args_list[1]
    messages = retry_call_args.kwargs["messages"]
    retry_content = " ".join(m["content"] for m in messages)
    assert "no such function: NONEXISTENT_FN" in retry_content or "SELECT NONEXISTENT_FN" in retry_content

    assert len(rows) == 1
    assert rows[0]["customer_name"] == "Chị Lan"


def test_classify_search_result_order_records():
    from src.models.order import Order, OrderStatus
    from src.services.order_search import (
        SearchResultType,
        classify_and_hydrate_results,
    )

    rows = [
        {
            "id": 10,
            "customer_id": 1,
            "customer_name": "Anh Tuấn",
            "customer_phone": "0903123456",
            "shipping_address": "Hà Nội",
            "items_text": "2 cuốn Tuấn Vũ",
            "total_amount": 200000,
            "cod_amount": 200000,
            "payment_method": "COD",
            "status": "CHO_LAM",
            "tracking_code": None,
            "photo_file_ids": '["file_1"]',
            "raw_text": "đơn test",
            "created_at": "2026-10-25 10:00:00",
            "updated_at": "2026-10-25 10:00:00",
        }
    ]

    res_type, hydrated = classify_and_hydrate_results(rows, "SELECT o.* FROM orders o")
    assert res_type == SearchResultType.ORDERS
    assert len(hydrated) == 1
    order = hydrated[0]
    assert isinstance(order, Order)
    assert order.id == 10
    assert order.customer_name == "Anh Tuấn"
    assert order.status == OrderStatus.CHO_LAM
    assert order.photo_file_ids == ["file_1"]


def test_classify_search_result_aggregate_scalar():
    from src.services.order_search import (
        SearchResultType,
        classify_and_hydrate_results,
    )

    rows = [{"total_orders": 5, "total_revenue": 1500000}]
    res_type, hydrated = classify_and_hydrate_results(rows, "SELECT COUNT(*) AS total_orders, SUM(total_amount) AS total_revenue FROM orders")
    assert res_type == SearchResultType.AGGREGATE
    assert hydrated == rows

    # Empty result for aggregate query
    res_type_empty, hydrated_empty = classify_and_hydrate_results([], "SELECT COUNT(*) FROM orders WHERE status = 'BOM_HANG'")
    assert res_type_empty == SearchResultType.AGGREGATE
    assert hydrated_empty == []


@pytest.mark.asyncio
async def test_summarize_aggregate_result():
    from unittest.mock import AsyncMock, MagicMock
    from src.services.order_search import summarize_aggregate_result

    mock_client = AsyncMock()
    mock_resp = MagicMock(
        choices=[
            MagicMock(
                message=MagicMock(
                    content="Dạ hôm nay shop mình có 4 đơn hàng, tổng tiền là 1.200.000 đ bác nhé!"
                )
            )
        ]
    )
    mock_client.chat.completions.create.return_value = mock_resp

    summary = await summarize_aggregate_result(
        client=mock_client,
        model_id="mock-model",
        query="hôm nay bán được bao nhiêu đơn",
        raw_rows=[{"total_orders": 4, "total_revenue": 1200000}],
    )

    assert "4 đơn hàng" in summary
    assert "1.200.000 đ" in summary
    assert mock_client.chat.completions.create.call_count == 1
    call_args = mock_client.chat.completions.create.call_args
    assert call_args.kwargs["temperature"] == 0.3


@pytest.mark.asyncio
async def test_run_order_search_end_to_end(test_db):
    from unittest.mock import AsyncMock, MagicMock
    from src.services.order_search import SearchResultType, run_order_search

    # Seed an order
    await test_db.execute(
        """
        INSERT INTO orders (customer_name, customer_phone, shipping_address, items_text, total_amount, cod_amount)
        VALUES ('Anh Hoàng', '0988776655', 'TP HCM', '3 cuốn Chế Linh', 350000, 350000)
        """
    )
    await test_db.commit()

    mock_client = AsyncMock()
    # Mock LLM returning SQL for specific order
    mock_choice = MagicMock()
    mock_choice.message.content = "SELECT o.* FROM orders o WHERE o.customer_name LIKE '%Hoàng%'"
    mock_client.chat.completions.create.return_value = MagicMock(choices=[mock_choice])

    result = await run_order_search(
        client=mock_client,
        model_id="mock-model",
        db=test_db,
        query="tìm đơn anh Hoàng",
    )

    assert result.result_type == SearchResultType.ORDERS
    assert len(result.orders) == 1
    assert result.orders[0].customer_name == "Anh Hoàng"
    assert "SELECT o.* FROM orders" in result.sql_executed


def test_render_search_single_order_card():
    from src.bot.keyboards import render_search_single_order_card
    from src.models.order import Order, OrderStatus

    order = Order(
        id=77,
        customer_name="Bác Tuấn",
        customer_phone="0903123456",
        shipping_address="123 Lê Duẩn, Hà Nội",
        items_text="2 cuốn Tuấn Vũ",
        total_amount=200000,
        cod_amount=200000,
        status=OrderStatus.CHO_LAM,
    )
    card = render_search_single_order_card(order, query="anh Tuấn hôm qua")

    assert "KẾT QUẢ TÌM KIẾM ĐƠN HÀNG" in card
    assert "Tìm theo: &#x27;anh Tuấn hôm qua&#x27;" in card or "Tìm theo: 'anh Tuấn hôm qua'" in card
    assert "Đơn #77" in card
    assert "Bác Tuấn" in card
    assert "<code>0903123456</code>" in card
    assert "2 cuốn Tuấn Vũ" in card
    assert "200.000 đ" in card
    assert "⏳ Chờ làm" in card
    assert "Có phải bác muốn xem đơn này không?" in card


def test_build_search_single_order_keyboard():
    from src.bot.keyboards import build_search_single_order_keyboard

    kb = build_search_single_order_keyboard(order_id=77, search_id="abc12345")
    flat_btns = [btn for row in kb.inline_keyboard for btn in row]
    texts = [btn.text for btn in flat_btns]
    cbs = [btn.callback_data for btn in flat_btns]

    assert "👁️ Đúng rồi, xem chi tiết" in texts
    assert "🔍 Tìm câu khác" in texts
    assert "sch_v:abc12345:77" in cbs
    assert "sch_new" in cbs


def test_render_search_empty_card():
    from src.bot.keyboards import build_search_empty_keyboard, render_search_empty_card

    card = render_search_empty_card(query="đơn ông trời")
    assert "KẾT QUẢ TÌM KIẾM" in card
    assert "không thấy đơn nào như bác tả rồi" in card
    assert "Mẹo tìm kiếm:" in card

    kb = build_search_empty_keyboard()
    flat_btns = [btn for row in kb.inline_keyboard for btn in row]
    cbs = [btn.callback_data for btn in flat_btns]
    assert "sch_new" in cbs
    assert "ord_act:new" in cbs


def test_render_search_multi_card():
    from src.bot.keyboards import build_search_multi_keyboard, render_search_multi_card
    from src.models.order import Order, OrderStatus

    orders = [
        Order(
            id=1,
            customer_name="Khách A",
            customer_phone="0901",
            shipping_address="HN",
            items_text="Băng A",
            total_amount=150000,
            status=OrderStatus.CHO_LAM,
        ),
        Order(
            id=2,
            customer_name="Khách B",
            customer_phone="0902",
            shipping_address="HCM",
            items_text="Băng B",
            total_amount=250000,
            status=OrderStatus.DA_GIAO,
        ),
    ]

    card = render_search_multi_card(
        orders=orders,
        query="băng nhạc",
        page=1,
        total_pages=2,
        total_orders=7,
    )

    assert "KẾT QUẢ TÌM KIẾM ĐƠN HÀNG" in card
    assert "7 đơn hàng" in card
    assert "Trang 1/2" in card
    assert "Đơn #1" in card
    assert "Khách A" in card
    assert "Đơn #2" in card
    assert "Khách B" in card

    kb = build_search_multi_keyboard(orders=orders, search_id="s123", page=1, total_pages=2)
    flat_btns = [btn for row in kb.inline_keyboard for btn in row]
    cbs = [btn.callback_data for btn in flat_btns]
    assert "sch_v:s123:1" in cbs
    assert "sch_v:s123:2" in cbs
    assert "sch_pg:s123:2" in cbs
    assert "sch_new" in cbs


@pytest.mark.asyncio
async def test_handle_search_menu_click():
    import time
    from unittest.mock import AsyncMock, MagicMock
    from telegram import Message, Update
    from telegram.ext import ContextTypes
    from src.bot.handlers.search import handle_search_menu_reply

    message = MagicMock(spec=Message)
    message.reply_text = AsyncMock()
    update = MagicMock(spec=Update)
    update.effective_message = message

    context = MagicMock(spec=ContextTypes.DEFAULT_TYPE)
    context.user_data = {}

    await handle_search_menu_reply(update, context)

    state = context.user_data.get("search_state")
    assert state is not None
    assert state["expires_at"] > time.time() + 100
    message.reply_text.assert_awaited_once()
    assert "TRA CỨU ĐƠN HÀNG TỰ NHIÊN" in message.reply_text.call_args[1]["text"]
    kb = message.reply_text.call_args[1]["reply_markup"]
    assert any(btn.callback_data == "sch_cancel" for row in kb.inline_keyboard for btn in row)


@pytest.mark.asyncio
async def test_handle_search_cancel():
    from unittest.mock import AsyncMock, MagicMock
    from telegram import CallbackQuery, Update
    from telegram.ext import ContextTypes
    from src.bot.handlers.search import handle_search_cancel_callback

    query = MagicMock(spec=CallbackQuery)
    query.answer = AsyncMock()
    query.edit_message_text = AsyncMock()
    update = MagicMock(spec=Update)
    update.callback_query = query

    context = MagicMock(spec=ContextTypes.DEFAULT_TYPE)
    context.user_data = {"search_state": {"expires_at": 9999999999}}

    await handle_search_cancel_callback(update, context)

    assert "search_state" not in context.user_data
    query.answer.assert_awaited_once()
    query.edit_message_text.assert_awaited_once()
    assert "Đã huỷ tìm kiếm" in query.edit_message_text.call_args[1]["text"]


@pytest.mark.asyncio
async def test_search_routing_in_ingest(test_db):
    import time
    from unittest.mock import AsyncMock, MagicMock, patch
    from telegram import Message, Update
    from telegram.ext import ContextTypes
    from src.bot.handlers.ingest import handle_text_order

    message = MagicMock(spec=Message)
    message.text = "tìm đơn anh Tuấn"
    message.reply_text = AsyncMock()
    update = MagicMock(spec=Update)
    update.message = message

    context = MagicMock(spec=ContextTypes.DEFAULT_TYPE)
    context.application.bot_data = {"db": test_db}
    context.user_data = {}

    with patch("src.bot.handlers.search.process_search_query", new_callable=AsyncMock) as mock_search:
        await handle_text_order(update, context)
        mock_search.assert_awaited_once_with(update, context, "tìm đơn anh Tuấn")

    # Routing when search_state is active
    context.user_data = {"search_state": {"expires_at": time.time() + 100}}
    message.text = "Tuấn Vũ"
    with patch("src.bot.handlers.search.process_search_query", new_callable=AsyncMock) as mock_search:
        await handle_text_order(update, context)
        mock_search.assert_awaited_once_with(update, context, "Tuấn Vũ")


@pytest.mark.asyncio
async def test_help_command_registration():
    from unittest.mock import AsyncMock, MagicMock
    from telegram import Message, Update
    from telegram.ext import ContextTypes
    from src.bot.handlers.base import help_command

    message = MagicMock(spec=Message)
    message.reply_text = AsyncMock()
    update = MagicMock(spec=Update)
    update.effective_message = message
    context = MagicMock(spec=ContextTypes.DEFAULT_TYPE)

    await help_command(update, context)

    message.reply_text.assert_awaited_once()
    text = message.reply_text.call_args[0][0]
    assert "HƯỚNG DẪN SỬ DỤNG BOT" in text
    assert "Tra cứu đơn" in text


@pytest.mark.asyncio
async def test_search_callback_pagination():
    from unittest.mock import AsyncMock, MagicMock
    from telegram import CallbackQuery, Update
    from telegram.ext import ContextTypes
    from src.bot.handlers.search import handle_search_callback
    from src.models.order import Order, OrderStatus
    from src.services.order_search import SearchResult, SearchResultType

    orders = [
        Order(id=i, customer_name=f"Khách {i}", customer_phone="0901", shipping_address="HN", items_text="Băng", total_amount=100000)
        for i in range(1, 8)
    ]
    search_res = SearchResult(
        result_type=SearchResultType.ORDERS,
        sql_executed="SELECT * FROM orders",
        orders=orders,
    )

    query = MagicMock(spec=CallbackQuery)
    query.answer = AsyncMock()
    query.edit_message_text = AsyncMock()
    query.data = "sch_pg:snap1:2"
    update = MagicMock(spec=Update)
    update.callback_query = query

    context = MagicMock(spec=ContextTypes.DEFAULT_TYPE)
    context.user_data = {
        "searches": {
            "snap1": {
                "query": "tìm băng",
                "result": search_res,
                "page": 1,
            }
        }
    }

    await handle_search_callback(update, context)

    query.answer.assert_awaited_once()
    query.edit_message_text.assert_awaited_once()
    text = query.edit_message_text.call_args[1]["text"]
    assert "Trang 2/2" in text
    assert "Đơn #6" in text
    assert "Đơn #7" in text


def test_order_detail_keyboard_custom_back():
    from src.bot.keyboards import build_order_detail_keyboard
    from src.models.order import Order, OrderStatus

    order = Order(
        id=99,
        customer_name="Khách Test Back",
        customer_phone="0901234567",
        shipping_address="HCM",
        items_text="Băng Test",
        total_amount=100000,
        status=OrderStatus.CHO_LAM,
    )

    # Default back_callback_data
    kb_def = build_order_detail_keyboard(order, date_str="2026-10-25", page=2)
    flat_def = [btn.callback_data for row in kb_def.inline_keyboard for btn in row if btn.callback_data]
    assert "ord_bk:2026-10-25:2" in flat_def

    # Custom back_callback_data for search preservation per D-13
    kb_custom = build_order_detail_keyboard(order, date_str="search", page=1, back_callback_data="sch_bk:snap999")
    flat_custom = [btn.callback_data for row in kb_custom.inline_keyboard for btn in row if btn.callback_data]
    assert "sch_bk:snap999" in flat_custom
    assert not any("ord_bk:" in cb for cb in flat_custom)


@pytest.mark.asyncio
async def test_search_view_order_detail_and_back_to_results(test_db):
    from unittest.mock import AsyncMock, MagicMock
    from telegram import CallbackQuery, Update
    from telegram.ext import ContextTypes
    from src.bot.handlers.search import handle_search_callback
    from src.db.orders import create_order
    from src.models.order import Order, OrderStatus
    from src.services.order_search import SearchResult, SearchResultType

    # 1. Seed order in test_db
    order = Order(
        customer_name="Bác Khánh",
        customer_phone="0911889900",
        shipping_address="456 Hai Bà Trưng, Đà Nẵng",
        items_text="3 cuốn Khánh Ly",
        total_amount=300000,
        cod_amount=300000,
        status=OrderStatus.CHO_LAM,
    )
    oid = await create_order(test_db, order)
    order.id = oid

    search_res = SearchResult(
        result_type=SearchResultType.ORDERS,
        sql_executed="SELECT * FROM orders",
        orders=[order],
    )

    query = MagicMock(spec=CallbackQuery)
    query.answer = AsyncMock()
    query.edit_message_text = AsyncMock()
    update = MagicMock(spec=Update)
    update.callback_query = query

    context = MagicMock(spec=ContextTypes.DEFAULT_TYPE)
    context.application.bot_data = {"db": test_db}
    context.user_data = {
        "searches": {
            "search_01": {
                "query": "tìm đơn bác Khánh",
                "result": search_res,
                "page": 1,
            }
        }
    }

    # Step 1: Click 'sch_v:search_01:{oid}' to view full detail card
    query.data = f"sch_v:search_01:{oid}"
    await handle_search_callback(update, context)

    query.answer.assert_awaited_once()
    query.edit_message_text.assert_awaited_once()
    detail_text = query.edit_message_text.call_args[1]["text"]
    detail_kb = query.edit_message_text.call_args[1]["reply_markup"]

    assert f"CHI TIẾT ĐƠN HÀNG #{oid}" in detail_text
    assert "Bác Khánh" in detail_text
    assert "456 Hai Bà Trưng" in detail_text

    # Verify back button points to 'sch_bk:search_01'
    flat_cbs = [btn.callback_data for row in detail_kb.inline_keyboard for btn in row if btn.callback_data]
    assert "sch_bk:search_01" in flat_cbs

    # Step 2: Click 'sch_bk:search_01' to return to search result snapshot
    query.answer.reset_mock()
    query.edit_message_text.reset_mock()
    query.data = "sch_bk:search_01"
    await handle_search_callback(update, context)

    query.answer.assert_awaited_once()
    query.edit_message_text.assert_awaited_once()
    back_text = query.edit_message_text.call_args[1]["text"]
    back_kb = query.edit_message_text.call_args[1]["reply_markup"]

    assert "KẾT QUẢ TÌM KIẾM ĐƠN HÀNG" in back_text
    assert "Có phải bác muốn xem đơn này không?" in back_text
    flat_back_cbs = [btn.callback_data for row in back_kb.inline_keyboard for btn in row if btn.callback_data]
    assert f"sch_v:search_01:{oid}" in flat_back_cbs
    assert "sch_new" in flat_back_cbs

    # Step 3: WR-02 regression - verify BadRequest("Message is not modified") is suppressed on repeated back click
    from telegram.error import BadRequest

    query.edit_message_text.side_effect = BadRequest("Message is not modified: specified new message content and reply markup are exactly the same")
    # Should not raise exception
    await handle_search_callback(update, context)


@pytest.mark.asyncio
async def test_process_search_query_without_bot_data_db(tmp_path):
    """Verify process_search_query acquires connection via _get_active_db_context when bot_data['db'] is None per G-04-3."""
    from unittest.mock import AsyncMock, MagicMock
    from telegram import Message, Update
    from telegram.ext import ContextTypes
    from src.bot.handlers.search import process_search_query
    from src.db.connection import get_db_connection
    from src.db.orders import create_order
    from src.db.schema import init_db
    from src.models.order import Order, OrderStatus

    db_path = str(tmp_path / "test_search_dynamic.db")
    async with get_db_connection(db_path) as init_conn:
        await init_db(init_conn)
        order = Order(
            customer_name="Anh Tuấn",
            customer_phone="0903123456",
            shipping_address="Hà Nội",
            items_text="2 cuốn Tuấn Vũ",
            total_amount=200000,
            status=OrderStatus.CHO_LAM,
        )
        await create_order(init_conn, order)

    mock_client = AsyncMock()
    mock_choice = MagicMock()
    mock_choice.message.content = "SELECT * FROM orders WHERE customer_name LIKE '%Tuấn%'"
    mock_resp = MagicMock(choices=[mock_choice])
    mock_client.chat.completions.create.return_value = mock_resp

    mock_settings = MagicMock()
    mock_settings.sqlite_db_path = db_path
    mock_settings.nine_router_model_id = "test-model"

    message = MagicMock(spec=Message)
    message.reply_text = AsyncMock()
    update = MagicMock(spec=Update)
    update.effective_message = message
    update.effective_chat = None

    context = MagicMock(spec=ContextTypes.DEFAULT_TYPE)
    context.application.bot_data = {
        "db": None,
        "settings": mock_settings,
        "openai_client": mock_client,
    }
    context.user_data = {}

    await process_search_query(update, context, "tìm đơn anh Tuấn")

    message.reply_text.assert_awaited_once()
    call_args = message.reply_text.call_args
    reply_text = call_args[1].get("text") if "text" in call_args[1] else call_args[0][0]
    assert "⚠️ Hệ thống tra cứu đang bận" not in reply_text
    assert "KẾT QUẢ TÌM KIẾM ĐƠN HÀNG" in reply_text
    assert "Anh Tuấn" in reply_text


@pytest.mark.asyncio
async def test_process_search_query_uses_active_model_id():
    """Verify process_search_query passes active_model_id from bot_data if present."""
    from src.bot.handlers.search import process_search_query

    mock_client = MagicMock()
    mock_settings = MagicMock()
    mock_settings.nine_router_model_id = "default-model"
    mock_settings.sqlite_db_path = "test.db"

    message = MagicMock()
    message.reply_text = AsyncMock()
    update = MagicMock(spec=Update)
    update.effective_message = message
    update.effective_chat = None

    context = MagicMock(spec=ContextTypes.DEFAULT_TYPE)
    context.application.bot_data = {
        "db": MagicMock(),
        "settings": mock_settings,
        "openai_client": mock_client,
        "active_model_id": "custom-active-model",
    }
    context.user_data = {}

    with patch("src.bot.handlers.search.run_order_search", new_callable=AsyncMock) as mock_search:
        mock_search.return_value = MagicMock(orders=[], interpretation="Không tìm thấy")
        await process_search_query(update, context, "tìm đơn")

    mock_search.assert_awaited_once()
    assert mock_search.call_args[1]["model_id"] == "custom-active-model"


@pytest.mark.asyncio
async def test_handle_search_callback_detail_without_bot_data_db(tmp_path):
    """Verify handle_search_callback sch_v acquires connection dynamically when bot_data['db'] is None per G-04-3."""
    from unittest.mock import AsyncMock, MagicMock
    from telegram import CallbackQuery, Update
    from telegram.ext import ContextTypes
    from src.bot.handlers.search import handle_search_callback
    from src.db.connection import get_db_connection
    from src.db.orders import create_order
    from src.db.schema import init_db
    from src.models.order import Order, OrderStatus
    from src.services.order_search import SearchResult, SearchResultType

    db_path = str(tmp_path / "test_callback_dynamic.db")
    async with get_db_connection(db_path) as init_conn:
        await init_db(init_conn)
        order = Order(
            customer_name="Bác Khánh",
            customer_phone="0911889900",
            shipping_address="456 Hai Bà Trưng, Đà Nẵng",
            items_text="3 cuốn Khánh Ly",
            total_amount=300000,
            status=OrderStatus.CHO_LAM,
        )
        oid = await create_order(init_conn, order)
        order.id = oid

    mock_settings = MagicMock()
    mock_settings.sqlite_db_path = db_path

    search_res = SearchResult(
        result_type=SearchResultType.ORDERS,
        sql_executed="SELECT * FROM orders",
        orders=[order],
    )

    query = MagicMock(spec=CallbackQuery)
    query.answer = AsyncMock()
    query.edit_message_text = AsyncMock()
    query.data = f"sch_v:search_01:{oid}"
    update = MagicMock(spec=Update)
    update.callback_query = query

    context = MagicMock(spec=ContextTypes.DEFAULT_TYPE)
    context.application.bot_data = {
        "db": None,
        "settings": mock_settings,
    }
    context.user_data = {
        "searches": {
            "search_01": {
                "query": "tìm đơn bác Khánh",
                "result": search_res,
                "page": 1,
            }
        }
    }

    await handle_search_callback(update, context)

    query.answer.assert_awaited_once()
    query.edit_message_text.assert_awaited_once()
    call_args = query.edit_message_text.call_args
    detail_text = call_args[1].get("text") if "text" in call_args[1] else call_args[0][0]
    assert "Lỗi cơ sở dữ liệu" not in detail_text
    assert f"CHI TIẾT ĐƠN HÀNG #{oid}" in detail_text
    assert "Bác Khánh" in detail_text







