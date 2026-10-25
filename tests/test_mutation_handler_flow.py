import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from telegram import CallbackQuery, Chat, Message, Update, User
from telegram.ext import ContextTypes

from src.bot.handlers.callbacks import handle_mutation_callback
from src.bot.handlers.ingest import handle_text_order
from src.bot.handlers.mutation import (
    handle_mutation_flow,
    handle_mutation_selection,
    handle_status_suggestion_selection,
)
from src.db.connection import get_db_connection
from src.db.orders import create_order, get_order_by_id
from src.db.schema import init_db
from src.models.mutation import OrderMutationDelta
from src.models.order import Order, OrderStatus


@pytest.fixture
def mock_context():
    context = MagicMock()
    context.user_data = {}
    context.application = MagicMock()
    context.application.bot_data = {
        "active_model_id": "test-model",
        "settings": MagicMock(nine_router_model_id="test-model"),
        "openai_client": MagicMock(),
    }
    return context


@pytest.mark.asyncio
async def test_mutation_flow_fast_path_status(mock_context):
    """Test fast-path status regex resolves immediately without calling LLM (D-06)."""
    async with get_db_connection(":memory:") as db:
        await init_db(db)
        order = Order(
            customer_name="Trần Văn Nam",
            customer_phone="0912345678",
            shipping_address="Hà Nội",
            items_text="1 cuốn",
            total_amount=150000,
            status=OrderStatus.CHO_LAM,
        )
        oid = await create_order(db, order)
        mock_context.application.bot_data["db"] = db

        update = MagicMock(spec=Update)
        update.message = MagicMock(spec=Message)
        update.message.reply_to_message = None
        update.message.text = f"huỷ đơn {oid}"
        update.message.reply_text = AsyncMock()

        await handle_mutation_flow(update, mock_context, f"huỷ đơn {oid}")

        # Check reply_text called with diff card
        assert update.message.reply_text.called
        call_args = update.message.reply_text.call_args[0]
        card_text = call_args[0]
        assert f"XÁC NHẬN SỬA ĐƠN HÀNG #{oid}" in card_text
        assert "Trạng thái:" in card_text
        assert "Đã huỷ đơn" in card_text

        # Check pending mutation draft stored with 120s TTL
        pending = mock_context.user_data.get("pending_mutations", {})
        assert len(pending) == 1
        draft = next(iter(pending.values()))
        assert draft["order_id"] == oid
        assert draft["delta"]["status"] == OrderStatus.HUY_DON
        assert draft["expires_at"] > time.time()


@pytest.mark.asyncio
async def test_mutation_flow_reply_order_context(mock_context):
    """Test extracting order ID from replied order card (D-05)."""
    async with get_db_connection(":memory:") as db:
        await init_db(db)
        order = Order(
            customer_name="Lê Văn C",
            customer_phone="0911223344",
            shipping_address="Hải Phòng",
            items_text="2 cuốn",
            total_amount=200000,
            status=OrderStatus.CHO_LAM,
        )
        oid = await create_order(db, order)
        mock_context.application.bot_data["db"] = db

        update = MagicMock(spec=Update)
        update.message = MagicMock(spec=Message)
        update.message.reply_to_message = MagicMock()
        update.message.reply_to_message.text = f"📦 CHI TIẾT ĐƠN HÀNG #{oid}\nTrạng thái: Chờ làm"
        update.message.reply_to_message.caption = None
        update.message.text = "đổi địa chỉ sang 123 Lê Duẩn, Hà Nội"
        update.message.reply_text = AsyncMock()
        update.message.chat.send_action = AsyncMock()

        fake_delta = OrderMutationDelta(
            new_shipping_address="123 Lê Duẩn, Hà Nội",
        )

        with patch("src.bot.handlers.mutation.extract_mutation_delta", new=AsyncMock(return_value=fake_delta)):
            await handle_mutation_flow(update, mock_context, "đổi địa chỉ sang 123 Lê Duẩn, Hà Nội")

        assert update.message.reply_text.called
        card_text = update.message.reply_text.call_args[0][0]
        assert f"XÁC NHẬN SỬA ĐƠN HÀNG #{oid}" in card_text
        assert "123 Lê Duẩn, Hà Nội" in card_text


@pytest.mark.asyncio
async def test_mutation_flow_disambiguation_multi_orders(mock_context):
    """Test disambiguation keyboard when multiple active orders match (D-08)."""
    async with get_db_connection(":memory:") as db:
        await init_db(db)
        oid1 = await create_order(
            db,
            Order(
                customer_name="Nguyễn Văn A",
                customer_phone="0901111111",
                shipping_address="Đà Nẵng",
                items_text="Băng 1",
                status=OrderStatus.CHO_LAM,
            ),
        )
        oid2 = await create_order(
            db,
            Order(
                customer_name="Nguyễn Văn A",
                customer_phone="0901111111",
                shipping_address="Đà Nẵng",
                items_text="Băng 2",
                status=OrderStatus.DANG_LAM,
            ),
        )
        mock_context.application.bot_data["db"] = db

        update = MagicMock(spec=Update)
        update.message = MagicMock(spec=Message)
        update.message.reply_to_message = None
        update.message.text = "sửa đơn của anh A"
        update.message.reply_text = AsyncMock()
        update.message.chat.send_action = AsyncMock()

        fake_delta = OrderMutationDelta(
            target_customer_keyword="Nguyễn Văn A",
            new_notes="Giao buổi sáng",
        )

        with patch("src.bot.handlers.mutation.extract_mutation_delta", new=AsyncMock(return_value=fake_delta)):
            await handle_mutation_flow(update, mock_context, "sửa đơn của anh A")

        assert update.message.reply_text.called
        call_kwargs = update.message.reply_text.call_args[1]
        prompt = update.message.reply_text.call_args[0][0]
        assert "CHỌN ĐƠN HÀNG CẦN SỬA" in prompt
        kb = call_kwargs["reply_markup"]
        assert len(kb.inline_keyboard) == 3  # 2 orders + 1 cancel


@pytest.mark.asyncio
async def test_mutation_flow_empty_guidance(mock_context):
    """Test empty guidance notice when 0 matching orders found (D-09)."""
    async with get_db_connection(":memory:") as db:
        await init_db(db)
        mock_context.application.bot_data["db"] = db

        update = MagicMock(spec=Update)
        update.message = MagicMock(spec=Message)
        update.message.reply_to_message = None
        update.message.text = "sửa đơn khách Hoàng Không Có"
        update.message.reply_text = AsyncMock()
        update.message.chat.send_action = AsyncMock()

        fake_delta = OrderMutationDelta(
            target_customer_keyword="Hoàng Không Có",
            new_notes="test",
        )

        with patch("src.bot.handlers.mutation.extract_mutation_delta", new=AsyncMock(return_value=fake_delta)):
            await handle_mutation_flow(update, mock_context, "sửa đơn khách Hoàng Không Có")

        assert update.message.reply_text.called
        text = update.message.reply_text.call_args[0][0]
        assert "KHÔNG TÌM THẤY ĐƠN HÀNG CẦN SỬA" in text


@pytest.mark.asyncio
async def test_mutation_callback_cf_success(mock_context):
    """Test ord_mut_cf confirmation success updates order and edits card (D-14)."""
    async with get_db_connection(":memory:") as db:
        await init_db(db)
        order = Order(
            customer_name="Khách Confirm",
            customer_phone="0912345678",
            shipping_address="Hà Nội",
            items_text="1 cuốn",
            total_amount=100000,
            status=OrderStatus.CHO_LAM,
        )
        oid = await create_order(db, order)
        original = await get_order_by_id(db, oid)
        mock_context.application.bot_data["db"] = db

        draft_id = "11223344"
        mock_context.user_data["pending_mutations"] = {
            draft_id: {
                "draft_id": draft_id,
                "order_id": oid,
                "expected_updated_at": str(original.updated_at),
                "delta": {"shipping_address": "Sài Gòn"},
                "expires_at": time.time() + 120,
            }
        }

        update = MagicMock(spec=Update)
        update.callback_query = MagicMock(spec=CallbackQuery)
        update.callback_query.data = f"ord_mut_cf:{draft_id}"
        update.callback_query.answer = AsyncMock()
        update.callback_query.edit_message_text = AsyncMock()
        update.effective_user = MagicMock()
        update.effective_user.id = 1234
        update.effective_user.full_name = "Quan Tran"

        await handle_mutation_callback(update, mock_context)

        assert update.callback_query.edit_message_text.called
        res_text = update.callback_query.edit_message_text.call_args[0][0]
        assert f"ĐÃ CẬP NHẬT THÀNH CÔNG ĐƠN #{oid}" in res_text
        assert "Sài Gòn" in res_text

        # Verify DB updated
        fresh = await get_order_by_id(db, oid)
        assert fresh.shipping_address == "Sài Gòn"


@pytest.mark.asyncio
async def test_mutation_callback_conflict_handling(mock_context):
    """Test ord_mut_cf detects optimistic conflict and shows alert (D-17, D-18)."""
    async with get_db_connection(":memory:") as db:
        await init_db(db)
        order = Order(
            customer_name="Khách Conflict",
            customer_phone="0912345678",
            shipping_address="Hà Nội",
            items_text="1 cuốn",
            total_amount=100000,
            status=OrderStatus.CHO_LAM,
        )
        oid = await create_order(db, order)
        original = await get_order_by_id(db, oid)
        mock_context.application.bot_data["db"] = db

        # Stale draft with non-matching updated_at
        draft_id = "aabbccdd"
        mock_context.user_data["pending_mutations"] = {
            draft_id: {
                "draft_id": draft_id,
                "order_id": oid,
                "expected_updated_at": "1999-01-01 00:00:00",  # Stale!
                "delta": {"shipping_address": "Đà Lạt"},
                "expires_at": time.time() + 120,
            }
        }

        update = MagicMock(spec=Update)
        update.callback_query = MagicMock(spec=CallbackQuery)
        update.callback_query.data = f"ord_mut_cf:{draft_id}"
        update.callback_query.answer = AsyncMock()
        update.callback_query.edit_message_text = AsyncMock()
        update.effective_user = MagicMock(id=1, full_name="User")

        await handle_mutation_callback(update, mock_context)

        assert update.callback_query.edit_message_text.called
        res_text = update.callback_query.edit_message_text.call_args[0][0]
        assert f"XUNG ĐỘT SỬA ĐƠN HÀNG #{oid}" in res_text


@pytest.mark.asyncio
async def test_mutation_callback_cancel_and_expiry(mock_context):
    """Test ord_mut_ca and TTL expiry clear buttons and edit message (D-12)."""
    draft_id = "12345678"
    mock_context.user_data["pending_mutations"] = {
        draft_id: {
            "draft_id": draft_id,
            "order_id": 99,
            "expires_at": time.time() + 120,
        }
    }

    update = MagicMock(spec=Update)
    update.callback_query = MagicMock(spec=CallbackQuery)
    update.callback_query.data = f"ord_mut_ca:{draft_id}"
    update.callback_query.answer = AsyncMock()
    update.callback_query.edit_message_text = AsyncMock()

    await handle_mutation_callback(update, mock_context)

    assert update.callback_query.edit_message_text.called
    res_text = update.callback_query.edit_message_text.call_args[0][0]
    assert "ĐÃ HUỶ YÊU CẦU SỬA ĐƠN" in res_text
    assert draft_id not in mock_context.user_data["pending_mutations"]


@pytest.mark.asyncio
async def test_ingest_routes_mutate_intent(mock_context):
    """Test ingest.handle_text_order routes MUTATE intent directly to mutation flow."""
    update = MagicMock(spec=Update)
    update.message = MagicMock(spec=Message)
    update.message.text = "huỷ đơn 5"
    update.message.reply_to_message = None
    update.message.reply_text = AsyncMock()

    with patch("src.bot.handlers.mutation.handle_mutation_flow", new=AsyncMock()) as mock_mut_flow:
        await handle_text_order(update, mock_context)
        assert mock_mut_flow.called
        assert mock_mut_flow.call_args[0][2] == "huỷ đơn 5"
