import json
from unittest.mock import AsyncMock, MagicMock

import pytest
from telegram import CallbackQuery, Update

from src.db.orders import create_order
from src.models.order import Order
from src.services.order_search import (
    SearchResult,
    SearchResultType,
    count_search_results,
    execute_natural_language_search,
    fetch_search_page,
    parse_search_plan,
    prepare_aggregate_sql,
    prepare_list_sql,
    run_order_search,
    split_and_validate_statements,
)

AGGREGATE_SQL = "SELECT COUNT(*) AS total_orders, SUM(total_amount) AS total_revenue FROM orders"
LIST_SQL = "SELECT o.* FROM orders o ORDER BY o.created_at DESC, o.id DESC"
MIXED_SQL = f"{AGGREGATE_SQL}; {LIST_SQL}"

PURPOSE_AGG = "Tổng số đơn và doanh thu"
PURPOSE_LIST = "Danh sách đơn hàng"


def _plan_json(
    *,
    list_sql: str | None = None,
    list_purpose: str = PURPOSE_LIST,
    aggregates: list[tuple[str, str]] | None = None,
) -> str:
    data = {
        "list": (
            {"purpose": list_purpose, "sql": list_sql} if list_sql is not None else None
        ),
        "aggregates": [
            {"purpose": purpose, "sql": sql} for purpose, sql in (aggregates or [])
        ],
    }
    return json.dumps(data, ensure_ascii=False)


def _mock_client(*contents) -> AsyncMock:
    client = AsyncMock()
    client.chat.completions.create.side_effect = [
        content
        if isinstance(content, BaseException)
        else MagicMock(choices=[MagicMock(message=MagicMock(content=content))])
        for content in contents
    ]
    return client


async def _seed_orders(db, count: int) -> list[int]:
    ids: list[int] = []
    for i in range(count):
        ids.append(
            await create_order(
                db,
                Order(
                    customer_name=f"Khách {i}",
                    customer_phone=f"09000000{i:02d}",
                    shipping_address="Hà Nội",
                    items_text="1 cuốn",
                    total_amount=100000,
                ),
            )
        )
    return ids


def test_split_statements_valid_mixed():
    assert split_and_validate_statements(MIXED_SQL) == [AGGREGATE_SQL, LIST_SQL]


@pytest.mark.parametrize(
    "raw",
    [
        f"{AGGREGATE_SQL}; {LIST_SQL}; {LIST_SQL}",
        f"{AGGREGATE_SQL}; INSERT INTO orders (customer_name) VALUES ('x')",
        f"{AGGREGATE_SQL}; {LIST_SQL}; DROP TABLE orders",
        "SELECT * FROM orders; DROP TABLE orders; SELECT 1",
        "SELECT * FROM orders;; SELECT 1",
    ],
)
def test_split_statements_rejects_unsafe(raw):
    with pytest.raises(ValueError):
        split_and_validate_statements(raw)


def test_ddl_inside_string_literal_is_not_treated_as_a_statement():
    literal = "SELECT o.* FROM orders o WHERE o.items_text LIKE '%DELETE FROM orders%'"
    assert split_and_validate_statements(literal) == [literal]


def test_prepare_list_sql_keeps_user_limits_and_stabilizes_order():
    # The legacy safety cap is never appended on the search path, so any LIMIT is user intent.
    prepared = prepare_list_sql(f"{LIST_SQL} LIMIT 20")
    assert prepared.upper().endswith("LIMIT 20")
    assert "o.created_at DESC, o.id DESC" in prepared

    no_order = prepare_list_sql("SELECT * FROM orders")
    assert no_order.endswith("ORDER BY created_at DESC, id DESC")
    assert "LIMIT" not in no_order.upper()

    # Already ordered by created_at only -> id DESC tiebreaker appended
    with_tiebreak = prepare_list_sql(
        "SELECT o.* FROM orders o ORDER BY o.created_at DESC"
    )
    assert "o.created_at DESC, o.id DESC" in with_tiebreak

    # Already has id -> no duplicate tiebreaker
    already_stable = prepare_list_sql(
        "SELECT o.* FROM orders o ORDER BY o.created_at DESC, o.id DESC LIMIT 20"
    )
    assert already_stable.count("o.id DESC") == 1

    # User-requested top-n must be preserved.
    top_n = prepare_list_sql("SELECT o.* FROM orders o ORDER BY o.created_at DESC LIMIT 3")
    assert top_n.upper().endswith("LIMIT 3")

    # Aggregates already run over the full set; an explicit limit is the user's top-n.
    assert prepare_aggregate_sql(f"{AGGREGATE_SQL} LIMIT 20") == f"{AGGREGATE_SQL} LIMIT 20"
    assert prepare_aggregate_sql(f"{AGGREGATE_SQL} LIMIT 3").endswith("LIMIT 3")

    # Comma / negative LIMIT forms must stay behind any injected ORDER BY.
    comma_limit = prepare_list_sql("SELECT * FROM orders LIMIT 10, 5")
    assert "ORDER BY created_at DESC, id DESC LIMIT 10, 5" in comma_limit

    negative_limit = prepare_list_sql("SELECT * FROM orders LIMIT -1")
    assert negative_limit.endswith("id DESC LIMIT -1")


def test_prepare_list_sql_handles_join_window_and_trailing_comment():
    # A window function's ORDER BY is not a top-level ORDER BY -> no stray tiebreaker.
    windowed = prepare_list_sql(
        "SELECT o.*, ROW_NUMBER() OVER (PARTITION BY o.customer_id ORDER BY o.created_at DESC) AS rn "
        "FROM orders o"
    )
    assert windowed.endswith("ORDER BY o.created_at DESC, o.id DESC")

    # Aliased join is fine: columns stay qualified.
    aliased_join = prepare_list_sql(
        "SELECT o.* FROM customers c JOIN orders o ON o.customer_id = c.id"
    )
    assert aliased_join.endswith("ORDER BY o.created_at DESC, o.id DESC")

    # Unaliased orders table: the table name is itself an unambiguous qualifier.
    unaliased_join = prepare_list_sql(
        "SELECT orders.* FROM customers c JOIN orders ON orders.customer_id = c.id"
    )
    assert unaliased_join.endswith("ORDER BY orders.created_at DESC, orders.id DESC")

    # Nested `FROM orders` inside EXISTS must not leak an alias to the outer query.
    exists_sql = prepare_list_sql(
        "SELECT c.* FROM customers c "
        "WHERE EXISTS (SELECT 1 FROM orders o WHERE o.customer_id = c.id)"
    )
    assert "o.created_at" not in exists_sql

    # Compound selects: order by the shared projected column only, not by table columns.
    compound = prepare_list_sql(
        "SELECT id, customer_name FROM orders WHERE total_amount > 10 "
        "UNION SELECT id, customer_name FROM orders WHERE total_amount > 0"
    )
    assert compound.endswith("ORDER BY id DESC")

    # A trailing comment is stripped by the splitter, so a raw prepare keeps it intact.
    commented = prepare_list_sql("SELECT o.* FROM orders o LIMIT 20 -- 20 đơn")
    assert "--" in commented


def test_is_aggregate_ignores_aggregate_subqueries_in_order_queries():
    from src.services.order_search import _is_aggregate_statement

    order_query = (
        "SELECT o.id, o.customer_name, o.customer_phone, o.items_text, o.total_amount "
        "FROM orders o WHERE o.total_amount > (SELECT AVG(total_amount) FROM orders)"
    )
    assert _is_aggregate_statement(order_query) is False

    scalar_query = "SELECT COUNT(*) AS total, MAX(o.created_at) AS last_seen FROM orders o"
    assert _is_aggregate_statement(scalar_query) is True


def test_split_statements_ignores_semicolons_inside_literals_and_comments():
    with_literal = "SELECT o.* FROM orders o WHERE o.items_text LIKE '%abc; xyz%'"
    assert split_and_validate_statements(with_literal) == [with_literal]

    with_comment = f"{AGGREGATE_SQL} -- ghi chú; tạm\n; {LIST_SQL}"
    assert len(split_and_validate_statements(with_comment)) == 2


def test_parse_search_plan_accepts_list_and_aggregates():
    plan = parse_search_plan(
        _plan_json(list_sql=LIST_SQL, aggregates=[(PURPOSE_AGG, AGGREGATE_SQL)])
    )
    assert plan.list_query is not None
    assert plan.list_query.purpose == PURPOSE_LIST
    assert plan.list_query.sql == LIST_SQL
    assert [(a.purpose, a.sql) for a in plan.aggregates] == [(PURPOSE_AGG, AGGREGATE_SQL)]


def test_parse_search_plan_trims_and_caps_purpose():
    long_purpose = "  Đơn   có   Chế   Linh  " + "x" * 300
    plan = parse_search_plan(_plan_json(list_sql=LIST_SQL, list_purpose=long_purpose))
    assert plan.list_query is not None
    assert len(plan.list_query.purpose) <= 120
    assert "  " not in plan.list_query.purpose
    assert plan.list_query.purpose.startswith("Đơn có Chế Linh")


@pytest.mark.parametrize(
    "raw",
    [
        json.dumps({"list": {"purpose": "", "sql": LIST_SQL}, "aggregates": []}),
        json.dumps({"list": {"purpose": 5, "sql": LIST_SQL}, "aggregates": []}),
        json.dumps(
            {
                "list": None,
                "aggregates": [
                    {"purpose": f"a{i}", "sql": "SELECT COUNT(*) FROM orders"}
                    for i in range(4)
                ],
            }
        ),
        json.dumps({"list": None, "aggregates": []}),
        json.dumps({"list": "oops", "aggregates": []}),
        "not json",
    ],
)
def test_parse_search_plan_rejects_invalid(raw):
    with pytest.raises(ValueError):
        parse_search_plan(raw)


@pytest.mark.parametrize(
    "sql",
    [
        "SELECT * FROM orders; DROP TABLE orders",
        "DELETE FROM orders",
        "PRAGMA table_info(orders)",
        "SELECT * FROM orders; SELECT 1",
    ],
)
def test_parse_search_plan_rejects_unsafe_sql(sql):
    with pytest.raises(ValueError):
        parse_search_plan(json.dumps({"list": {"purpose": "x", "sql": sql}, "aggregates": []}))


@pytest.mark.asyncio
async def test_run_order_search_mixed_full_aggregate_and_first_page(test_db):
    await _seed_orders(test_db, 7)
    plan = _plan_json(list_sql=LIST_SQL, aggregates=[(PURPOSE_AGG, AGGREGATE_SQL)])
    client = _mock_client(plan, "Dạ hôm nay shop có 7 đơn hàng tổng 700.000 đ bác nhé!")

    result = await run_order_search(
        client=client,
        model_id="mock-model",
        db=test_db,
        query="hôm nay bán bao nhiêu đơn, liệt kê các đơn",
    )

    assert result.result_type == SearchResultType.MIXED
    assert result.total_count == 7
    assert len(result.orders) == 5
    assert result.page_size == 5
    assert result.list_purpose == PURPOSE_LIST
    assert "LIMIT" not in (result.list_sql or "").upper()
    assert result.raw_rows[0]["total_orders"] == 7
    assert result.summary_text == "Dạ hôm nay shop có 7 đơn hàng tổng 700.000 đ bác nhé!"
    assert ";" in result.sql_executed

    system_prompt = client.chat.completions.create.call_args_list[0].kwargs["messages"][0]["content"]
    assert "aggregates" in system_prompt
    assert "KHÔNG thêm LIMIT" in system_prompt


@pytest.mark.asyncio
async def test_run_order_search_list_not_capped_at_20(test_db):
    await _seed_orders(test_db, 25)
    client = _mock_client(_plan_json(list_sql=LIST_SQL))

    result = await run_order_search(
        client=client, model_id="mock-model", db=test_db, query="liệt kê đơn"
    )

    assert result.result_type == SearchResultType.ORDERS
    assert result.total_count == 25
    assert len(result.orders) == 5
    assert result.list_purpose == PURPOSE_LIST
    assert "LIMIT" not in (result.list_sql or "").upper()
    assert client.chat.completions.create.call_count == 1


def test_multi_keyboard_uses_xem_them_label():
    from src.bot.keyboards import build_search_multi_keyboard

    orders = [
        Order(id=i, customer_name=f"Khách {i}", customer_phone="0901",
              shipping_address="HN", items_text="Băng", total_amount=100000)
        for i in range(1, 6)
    ]
    kb = build_search_multi_keyboard(orders=orders, search_id="sid", page=1, total_pages=2)
    flat = [btn for row in kb.inline_keyboard for btn in row]

    assert any(btn.text == "Xem thêm ➡️" and btn.callback_data == "sch_pg:sid:2" for btn in flat)


@pytest.mark.asyncio
async def test_mixed_summary_sees_only_list_purpose_and_count(test_db):
    await create_order(
        test_db,
        Order(
            customer_name="Khách A",
            customer_phone="0900000001",
            shipping_address="Hà Nội",
            items_text="1 cuốn Chế Linh",
            total_amount=100000,
        ),
    )
    for i in range(2):
        await create_order(
            test_db,
            Order(
                customer_name=f"Khách B{i}",
                customer_phone=f"09000000{i + 10}",
                shipping_address="Hà Nội",
                items_text="1 cuốn Tuấn Vũ",
                total_amount=100000,
            ),
        )

    list_sql = (
        "SELECT o.* FROM orders o WHERE o.items_text LIKE '%Chế Linh%' "
        "ORDER BY o.created_at DESC, o.id DESC"
    )
    plan = _plan_json(
        list_sql=list_sql,
        list_purpose="Đơn có Chế Linh",
        aggregates=[(PURPOSE_AGG, AGGREGATE_SQL)],
    )
    client = _mock_client(plan, "Dạ shop có 1 đơn Chế Linh bác nhé!")

    result = await run_order_search(
        client=client,
        model_id="mock-model",
        db=test_db,
        query="nay bán tổng bao tiền, có bán được Chế Linh không",
    )

    assert result.result_type == SearchResultType.MIXED
    assert result.total_count == 1
    assert len(result.orders) == 1
    user_content = client.chat.completions.create.call_args_list[1].kwargs["messages"][1]["content"]
    assert "Đơn có Chế Linh" in user_content
    assert '"count": 1' in user_content
    assert "items_text" not in user_content
    assert "Khách A" not in user_content


@pytest.mark.asyncio
async def test_aggregate_only_summary_has_no_list_section(test_db):
    await _seed_orders(test_db, 3)
    plan = _plan_json(aggregates=[(PURPOSE_AGG, "SELECT COUNT(*) AS total_orders FROM orders")])
    client = _mock_client(plan, "Dạ shop có 3 đơn bác nhé!")

    result = await run_order_search(
        client=client, model_id="mock-model", db=test_db, query="hôm nay bán được bao nhiêu đơn"
    )

    assert result.result_type == SearchResultType.AGGREGATE
    assert result.orders == []
    user_content = client.chat.completions.create.call_args_list[1].kwargs["messages"][1]["content"]
    assert "Danh sách đơn" not in user_content
    assert '"count"' not in user_content


@pytest.mark.asyncio
async def test_multi_aggregate_all_executed_and_labeled(test_db):
    await _seed_orders(test_db, 3)
    revenue_sql = "SELECT SUM(total_amount) AS total_revenue FROM orders"
    top_customer_sql = (
        "SELECT customer_name, COUNT(*) AS order_count FROM orders "
        "GROUP BY customer_name ORDER BY order_count DESC LIMIT 1"
    )
    plan = _plan_json(
        list_sql=LIST_SQL,
        aggregates=[
            ("Tổng doanh thu", revenue_sql),
            ("Khách mua nhiều nhất", top_customer_sql),
        ],
    )
    client = _mock_client(plan, "Dạ shop có 3 đơn bác nhé!")

    result = await run_order_search(
        client=client, model_id="mock-model", db=test_db, query="doanh thu và khách top"
    )

    assert result.result_type == SearchResultType.MIXED
    user_content = client.chat.completions.create.call_args_list[1].kwargs["messages"][1]["content"]
    assert "Tổng doanh thu" in user_content
    assert "Khách mua nhiều nhất" in user_content
    assert "total_revenue" in user_content
    assert "order_count" in user_content
    assert len(result.raw_rows) == 2
    assert client.chat.completions.create.call_count == 2


@pytest.mark.asyncio
async def test_malformed_plan_regenerates_once(test_db):
    aggregate_plan = _plan_json(
        aggregates=[(PURPOSE_AGG, "SELECT COUNT(*) AS total_orders FROM orders")]
    )
    client = _mock_client("not json", aggregate_plan, "Dạ shop có 0 đơn bác nhé!")

    result = await run_order_search(
        client=client, model_id="mock-model", db=test_db, query="bao nhiêu đơn"
    )

    assert result.result_type == SearchResultType.AGGREGATE
    assert client.chat.completions.create.call_count == 3
    retry_messages = client.chat.completions.create.call_args_list[1].kwargs["messages"]
    retry_content = " ".join(m["content"] for m in retry_messages)
    assert "Plan JSON" in retry_content
    assert "not json" in retry_content


@pytest.mark.asyncio
async def test_aggregate_role_mismatch_retries(test_db):
    await _seed_orders(test_db, 2)
    bad_plan = _plan_json(aggregates=[("Đơn hàng", LIST_SQL)])
    good_plan = _plan_json(
        aggregates=[(PURPOSE_AGG, "SELECT COUNT(*) AS total_orders FROM orders")]
    )
    client = _mock_client(bad_plan, good_plan, "Dạ shop có 2 đơn bác nhé!")

    result = await run_order_search(
        client=client, model_id="mock-model", db=test_db, query="bao nhiêu đơn"
    )

    assert result.result_type == SearchResultType.AGGREGATE
    assert result.orders == []
    assert client.chat.completions.create.call_count == 3


@pytest.mark.asyncio
async def test_list_role_mismatch_retries(test_db):
    await _seed_orders(test_db, 4)
    bad_plan = _plan_json(list_sql="SELECT COUNT(*) AS n FROM orders")
    good_plan = _plan_json(list_sql=LIST_SQL)
    client = _mock_client(bad_plan, good_plan)

    result = await run_order_search(
        client=client, model_id="mock-model", db=test_db, query="liệt kê đơn"
    )

    assert result.result_type == SearchResultType.ORDERS
    assert result.total_count == 4
    assert len(result.orders) == 4
    assert client.chat.completions.create.call_count == 2


@pytest.mark.asyncio
async def test_json_object_fallback_without_response_format(test_db):
    await _seed_orders(test_db, 1)
    client = _mock_client(Exception("gateway rejects json_schema"), _plan_json(list_sql=LIST_SQL))

    result = await run_order_search(
        client=client, model_id="mock-model", db=test_db, query="liệt kê đơn"
    )

    assert result.result_type == SearchResultType.ORDERS
    assert client.chat.completions.create.call_count == 2
    first_call = client.chat.completions.create.call_args_list[0].kwargs
    second_call = client.chat.completions.create.call_args_list[1].kwargs
    assert first_call["response_format"] == {"type": "json_object"}
    assert "response_format" not in second_call


def _sample_orders(count: int) -> list[Order]:
    return [
        Order(id=i, customer_name=f"Khách {i}", customer_phone="0901",
              shipping_address="HN", items_text="Băng", total_amount=100000)
        for i in range(1, count + 1)
    ]


def test_render_purpose_heading_escaped_on_all_cards():
    from src.bot.keyboards import (
        render_search_empty_card,
        render_search_multi_card,
        render_search_single_order_card,
    )

    purpose = "Đơn <Chế Linh>"
    multi = render_search_multi_card(
        orders=_sample_orders(2),
        query="q",
        page=1,
        total_pages=1,
        total_orders=2,
        purpose=purpose,
    )
    assert "&lt;Chế Linh&gt;" in multi
    assert "<Chế Linh>" not in multi
    assert "Tìm theo" not in multi

    empty = render_search_empty_card("q", purpose=purpose)
    assert "&lt;Chế Linh&gt;" in empty
    assert "<Chế Linh>" not in empty
    assert "Mẹo tìm kiếm" not in empty

    single = render_search_single_order_card(_sample_orders(1)[0], "q", purpose=purpose)
    assert "&lt;Chế Linh&gt;" in single
    assert "<Chế Linh>" not in single
    assert "Tìm theo" not in single


def test_render_without_purpose_keeps_legacy_heading():
    from src.bot.keyboards import (
        render_search_empty_card,
        render_search_multi_card,
        render_search_single_order_card,
    )

    assert "KẾT QUẢ TÌM KIẾM ĐƠN HÀNG" in render_search_multi_card(
        orders=_sample_orders(2), query="băng", page=1, total_pages=1, total_orders=2
    )
    assert "Tìm theo" in render_search_multi_card(
        orders=_sample_orders(2), query="băng", page=1, total_pages=1, total_orders=2
    )
    assert "Mẹo tìm kiếm" in render_search_empty_card("q")
    assert "KẾT QUẢ TÌM KIẾM ĐƠN HÀNG" in render_search_single_order_card(
        _sample_orders(1)[0], "q"
    )


@pytest.mark.asyncio
async def test_fetch_search_page_stable_across_pages(test_db):
    await _seed_orders(test_db, 7)
    prepared = prepare_list_sql("SELECT * FROM orders")

    assert await count_search_results(test_db, prepared) == 7

    page1 = await fetch_search_page(test_db, prepared, 1, 5)
    page2 = await fetch_search_page(test_db, prepared, 2, 5)

    ids1 = [o.id for o in page1]
    ids2 = [o.id for o in page2]

    assert len(ids1) == 5
    assert len(ids2) == 2
    assert set(ids1).isdisjoint(ids2)
    assert len(set(ids1) | set(ids2)) == 7
    assert ids1 == sorted(ids1, reverse=True)
    assert ids2 == sorted(ids2, reverse=True)


@pytest.mark.asyncio
async def test_search_callback_more_fetches_db_page(test_db):
    from src.bot.handlers.search import handle_search_callback

    ids = await _seed_orders(test_db, 7)
    prepared = prepare_list_sql("SELECT * FROM orders")
    page1 = await fetch_search_page(test_db, prepared, 1, 5)

    search_res = SearchResult(
        result_type=SearchResultType.MIXED,
        sql_executed="agg; list",
        summary_text="Dạ shop có 7 đơn",
        orders=page1,
        list_sql=prepared,
        list_purpose="Đơn có Chế Linh hôm nay",
        total_count=7,
        page_size=5,
    )

    query = MagicMock(spec=CallbackQuery)
    query.answer = AsyncMock()
    query.edit_message_text = AsyncMock()
    query.data = "sch_pg:sid:2"
    update = MagicMock(spec=Update)
    update.callback_query = query

    context = MagicMock()
    context.application.bot_data = {"db": test_db}
    context.user_data = {
        "searches": {
            "sid": {"query": "hôm nay bán bao nhiêu đơn", "result": search_res, "page": 1}
        }
    }

    await handle_search_callback(update, context)

    text = query.edit_message_text.call_args[1]["text"]
    kb = query.edit_message_text.call_args[1]["reply_markup"]
    flat_texts = [btn.text for row in kb.inline_keyboard for btn in row]

    assert "Đơn có Chế Linh hôm nay" in text
    assert "Trang 2/2" in text
    assert f"Đơn #{ids[1]}" in text or f"Đơn #{ids[0]}" in text
    assert "Dạ shop có 7 đơn" in text
    assert not any("Xem thêm" in t for t in flat_texts)
    assert context.user_data["searches"]["sid"]["page"] == 2


@pytest.mark.asyncio
async def test_legacy_snapshot_pagination_unchanged():
    from src.bot.handlers.search import handle_search_callback

    orders = [
        Order(id=i, customer_name=f"Khách {i}", customer_phone="0901",
              shipping_address="HN", items_text="Băng", total_amount=100000)
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

    context = MagicMock()
    context.application.bot_data = {}
    context.user_data = {
        "searches": {"snap1": {"query": "tìm băng", "result": search_res, "page": 1}}
    }

    await handle_search_callback(update, context)

    text = query.edit_message_text.call_args[1]["text"]
    assert "Trang 2/2" in text
    assert "Đơn #6" in text
    assert "Đơn #7" in text
    assert "Tìm theo" in text


@pytest.mark.asyncio
async def test_legacy_snapshot_with_purpose_keeps_purpose_heading():
    from src.bot.handlers.search import handle_search_callback

    orders = [
        Order(id=i, customer_name=f"Khách {i}", customer_phone="0901",
              shipping_address="HN", items_text="Băng", total_amount=100000)
        for i in range(1, 4)
    ]
    search_res = SearchResult(
        result_type=SearchResultType.ORDERS,
        sql_executed="SELECT * FROM orders",
        orders=orders,
        list_sql=None,
        list_purpose="Đơn băng nhạc",
    )

    query = MagicMock(spec=CallbackQuery)
    query.answer = AsyncMock()
    query.edit_message_text = AsyncMock()
    query.data = "sch_bk:snap1"
    update = MagicMock(spec=Update)
    update.callback_query = query

    context = MagicMock()
    context.application.bot_data = {}
    context.user_data = {
        "searches": {"snap1": {"query": "tìm băng", "result": search_res, "page": 1}}
    }

    await handle_search_callback(update, context)

    text = query.edit_message_text.call_args[1]["text"]
    assert "Đơn băng nhạc" in text
    assert "Tìm theo" not in text


@pytest.mark.asyncio
async def test_mutation_legacy_search_still_capped(test_db):
    client = _mock_client("SELECT * FROM orders")

    sql, rows = await execute_natural_language_search(
        client=client, model_id="mock-model", db=test_db, query="tìm đơn"
    )

    assert sql.endswith("LIMIT 20")
    assert isinstance(rows, list)
