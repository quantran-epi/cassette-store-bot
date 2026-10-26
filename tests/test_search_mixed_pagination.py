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
    prepare_aggregate_sql,
    prepare_list_sql,
    run_order_search,
    split_and_validate_statements,
)

AGGREGATE_SQL = "SELECT COUNT(*) AS total_orders, SUM(total_amount) AS total_revenue FROM orders"
LIST_SQL = "SELECT o.* FROM orders o ORDER BY o.created_at DESC, o.id DESC"
MIXED_SQL = f"{AGGREGATE_SQL}; {LIST_SQL}"


def _mock_client(*contents: str) -> AsyncMock:
    client = AsyncMock()
    client.chat.completions.create.side_effect = [
        MagicMock(choices=[MagicMock(message=MagicMock(content=content))])
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


@pytest.mark.asyncio
async def test_run_order_search_mixed_full_aggregate_and_first_page(test_db):
    await _seed_orders(test_db, 7)
    client = _mock_client(MIXED_SQL, "Dạ hôm nay shop có 7 đơn hàng tổng 700.000 đ bác nhé!")

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
    assert "LIMIT" not in (result.list_sql or "").upper()
    assert result.raw_rows[0]["total_orders"] == 7
    assert result.summary_text == "Dạ hôm nay shop có 7 đơn hàng tổng 700.000 đ bác nhé!"
    assert ";" in result.sql_executed

    system_prompt = client.chat.completions.create.call_args_list[0].kwargs["messages"][0]["content"]
    assert "2 câu SELECT" in system_prompt
    assert "KHÔNG thêm LIMIT" in system_prompt


@pytest.mark.asyncio
async def test_run_order_search_list_not_capped_at_20(test_db):
    await _seed_orders(test_db, 25)
    client = _mock_client(LIST_SQL)

    result = await run_order_search(
        client=client, model_id="mock-model", db=test_db, query="liệt kê đơn"
    )

    assert result.result_type == SearchResultType.ORDERS
    assert result.total_count == 25
    assert len(result.orders) == 5
    assert "LIMIT" not in (result.list_sql or "").upper()


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


@pytest.mark.asyncio
async def test_mutation_legacy_search_still_capped(test_db):
    client = _mock_client("SELECT * FROM orders")

    sql, rows = await execute_natural_language_search(
        client=client, model_id="mock-model", db=test_db, query="tìm đơn"
    )

    assert sql.endswith("LIMIT 20")
    assert isinstance(rows, list)
