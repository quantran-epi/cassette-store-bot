import pytest

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



