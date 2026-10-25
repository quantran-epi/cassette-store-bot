import pytest

from src.db.connection import get_db_connection, sqlite_word_match
from src.db.orders import create_order, find_orders_for_mutation
from src.db.schema import init_db
from src.models.order import Order, OrderStatus


def test_sqlite_word_match_boundaries():
    """Verify word_match matches exact unaccented words and rejects partial substrings."""
    # Matches
    assert sqlite_word_match("anh ha", "ha") == 1
    assert sqlite_word_match("Hà Nội", "ha noi") == 1
    assert sqlite_word_match("Chị Hà", "ha") == 1
    assert sqlite_word_match("Tú", "tu") == 1
    assert sqlite_word_match("Bác Ba", "ba") == 1

    # Rejects substring false positives
    assert sqlite_word_match("Thanh", "ha") == 0
    assert sqlite_word_match("Thảo", "ha") == 0
    assert sqlite_word_match("Phạm", "ha") == 0
    assert sqlite_word_match("Hải", "ha") == 0
    assert sqlite_word_match("Tuấn", "tu") == 0
    assert sqlite_word_match(None, "ha") == 0
    assert sqlite_word_match("anh ha", None) == 0
    assert sqlite_word_match("", "") == 0


@pytest.mark.asyncio
async def test_find_orders_for_mutation_short_name_no_false_positives():
    """Verify searching for 'anh hà' matches only 'Hà', not 'Thanh'."""
    async with get_db_connection(":memory:") as db:
        await init_db(db)

        # Order 1: Thanh
        await create_order(
            db,
            Order(
                customer_name="Trần Thị Thanh",
                customer_phone="0911111111",
                shipping_address="Hải Phòng",
                items_text="1 cuốn Tuấn Vũ",
                status=OrderStatus.CHO_LAM,
            ),
        )

        # Order 2: Hà
        oid_ha = await create_order(
            db,
            Order(
                customer_name="Nguyễn Thị Hà",
                customer_phone="0922222222",
                shipping_address="Hà Nội",
                items_text="2 cuốn Chế Linh",
                status=OrderStatus.CHO_LAM,
            ),
        )

        results = await find_orders_for_mutation(db, keyword="anh hà")
        assert len(results) == 1
        assert results[0].id == oid_ha
        assert results[0].customer_name == "Nguyễn Thị Hà"


@pytest.mark.asyncio
async def test_find_orders_for_mutation_composite_name_and_address():
    """Verify multi-token query 'tuấn gia lâm' matches order combining name and address."""
    async with get_db_connection(":memory:") as db:
        await init_db(db)

        # Order 1: Tuấn at Cầu Giấy
        await create_order(
            db,
            Order(
                customer_name="Lê Anh Tuấn",
                customer_phone="0933333333",
                shipping_address="12 Cầu Giấy, Hà Nội",
                items_text="1 cuốn",
                status=OrderStatus.CHO_LAM,
            ),
        )

        # Order 2: Tuấn at Gia Lâm
        oid_tuan_gialam = await create_order(
            db,
            Order(
                customer_name="Nguyễn Văn Tuấn",
                customer_phone="0944444444",
                shipping_address="45 Ngọc Lâm, Gia Lâm, Hà Nội",
                items_text="1 cuốn",
                status=OrderStatus.CHO_LAM,
            ),
        )

        results = await find_orders_for_mutation(db, keyword="tuấn gia lâm")
        assert len(results) == 1
        assert results[0].id == oid_tuan_gialam


@pytest.mark.asyncio
async def test_find_orders_for_mutation_composite_item_and_city():
    """Verify query 'đơn Chế Linh Đà Nẵng' matches across items_text and shipping_address."""
    async with get_db_connection(":memory:") as db:
        await init_db(db)

        oid_match = await create_order(
            db,
            Order(
                customer_name="Bác Ba",
                customer_phone="0955555555",
                shipping_address="10 Hải Phòng, Đà Nẵng",
                items_text="Băng cassette Chế Linh số 2",
                status=OrderStatus.CHO_LAM,
            ),
        )

        await create_order(
            db,
            Order(
                customer_name="Bác Tư",
                customer_phone="0966666666",
                shipping_address="Hà Nội",
                items_text="Băng cassette Chế Linh số 1",
                status=OrderStatus.CHO_LAM,
            ),
        )

        results = await find_orders_for_mutation(db, keyword="đơn Chế Linh Đà Nẵng")
        assert len(results) == 1
        assert results[0].id == oid_match


@pytest.mark.asyncio
async def test_find_orders_for_mutation_active_priority():
    """Verify active orders are prioritized over terminal orders for same customer."""
    async with get_db_connection(":memory:") as db:
        await init_db(db)

        # Terminal order
        await create_order(
            db,
            Order(
                customer_name="Vũ Đức Anh",
                customer_phone="0977777777",
                shipping_address="Hà Nội",
                items_text="1 cuốn",
                status=OrderStatus.DA_GIAO,
            ),
        )

        # Active order
        oid_active = await create_order(
            db,
            Order(
                customer_name="Vũ Đức Anh",
                customer_phone="0977777777",
                shipping_address="Hà Nội",
                items_text="2 cuốn",
                status=OrderStatus.CHO_LAM,
            ),
        )

        results = await find_orders_for_mutation(db, keyword="Vũ Đức Anh", limit=1)
        assert len(results) == 1
        assert results[0].id == oid_active
        assert results[0].status == OrderStatus.CHO_LAM


def test_mutation_system_prompt_captures_composite_keywords():
    """Verify prompt instructs LLM to capture composite identifiers without losing place names."""
    from src.services.mutation_extractor import MUTATION_SYSTEM_PROMPT

    assert "target_customer_keyword" in MUTATION_SYSTEM_PROMPT
    assert "Tuấn Gia Lâm" in MUTATION_SYSTEM_PROMPT
    assert "Linh Đà Nẵng" in MUTATION_SYSTEM_PROMPT


@pytest.mark.asyncio
async def test_mutation_handler_text_to_sql_fallback():
    """Verify handle_mutation_flow invokes Text-to-SQL fallback when token match returns empty."""
    from unittest.mock import AsyncMock, MagicMock, patch

    from telegram import Message, Update

    from src.bot.handlers.mutation import handle_mutation_flow
    from src.models.mutation import OrderMutationDelta

    async with get_db_connection(":memory:") as db:
        await init_db(db)

        oid = await create_order(
            db,
            Order(
                customer_name="Trần Văn Nam",
                customer_phone="0912345678",
                shipping_address="Hải Phòng",
                items_text="1 cuốn",
                status=OrderStatus.CHO_LAM,
            ),
        )

        mock_context = MagicMock()
        mock_context.user_data = {}
        mock_context.application = MagicMock()
        mock_context.application.bot_data = {
            "active_model_id": "test-model",
            "settings": MagicMock(nine_router_model_id="test-model"),
            "openai_client": MagicMock(),
            "db": db,
        }

        update = MagicMock(spec=Update)
        update.message = MagicMock(spec=Message)
        update.message.reply_to_message = None
        update.message.reply_text = AsyncMock()
        update.message.chat = MagicMock()
        update.message.chat.send_action = AsyncMock()

        # Mock extract_mutation_delta to return complex query that fast path fails on
        mock_delta = OrderMutationDelta(
            target_customer_keyword="khách mua đĩa hôm qua gửi về quê",
            new_notes="gọi trước khi giao",
        )

        # Mock execute_natural_language_search to return the order id
        with (
            patch("src.bot.handlers.mutation.extract_mutation_delta", AsyncMock(return_value=mock_delta)),
            patch("src.bot.handlers.mutation.find_orders_for_mutation", AsyncMock(return_value=[])),
            patch(
                "src.bot.handlers.mutation.execute_natural_language_search",
                AsyncMock(return_value=("SELECT * FROM orders WHERE id = 1", [{"id": oid}])),
            ),
        ):
            await handle_mutation_flow(update, mock_context, "sửa ghi chú đơn khách mua đĩa hôm qua gửi về quê")

        # Must display diff card for order oid
        assert update.message.reply_text.called
        call_text = update.message.reply_text.call_args[0][0]
        assert f"#{oid}" in call_text
        assert "gọi trước khi giao" in call_text

