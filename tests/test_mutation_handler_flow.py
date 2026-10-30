import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from telegram import CallbackQuery, Message, Update

from src.bot.handlers.callbacks import handle_mutation_callback
from src.bot.handlers.ingest import handle_text_order
from src.bot.handlers.mutation import (
    handle_mutation_flow,
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
        assert "TRẠNG THÁI:" in card_text or "Trạng thái:" in card_text
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

        with patch(
            "src.bot.handlers.mutation.extract_mutation_delta",
            new=AsyncMock(return_value=fake_delta),
        ):
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
        await create_order(
            db,
            Order(
                customer_name="Nguyễn Văn A",
                customer_phone="0901111111",
                shipping_address="Đà Nẵng",
                items_text="Băng 1",
                status=OrderStatus.CHO_LAM,
            ),
        )
        await create_order(
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

        with patch(
            "src.bot.handlers.mutation.extract_mutation_delta",
            new=AsyncMock(return_value=fake_delta),
        ):
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

        with patch(
            "src.bot.handlers.mutation.extract_mutation_delta",
            new=AsyncMock(return_value=fake_delta),
        ):
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
        await get_order_by_id(db, oid)
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
async def test_ingest_treats_mutation_like_text_as_new_order(mock_context):
    """Natural text never enters mutation flow without an explicit menu action."""
    from src.models.extractor import ExtractedOrder

    update = MagicMock(spec=Update)
    update.message = MagicMock(spec=Message)
    update.message.text = "huỷ đơn 5"
    update.message.reply_to_message = None
    update.message.reply_text = AsyncMock()

    extracted = ExtractedOrder(
        customer_name="Khách mới",
        customer_phone="0912345678",
        items_text="1 băng",
        total_amount=100000,
        cod_amount=100000,
    )
    with (
        patch(
            "src.bot.handlers.mutation.handle_mutation_flow", new=AsyncMock()
        ) as mock_mut_flow,
        patch(
            "src.bot.handlers.ingest.extract_order_from_text",
            new=AsyncMock(return_value=extracted),
        ),
        patch(
            "src.bot.handlers.ingest.process_extracted_order", new=AsyncMock()
        ) as mock_create,
    ):
        await handle_text_order(update, mock_context)

    mock_mut_flow.assert_not_awaited()
    mock_create.assert_awaited_once()
    assert mock_create.await_args.kwargs["raw_text"] == "huỷ đơn 5"


@pytest.mark.asyncio
async def test_mutation_flow_finds_order_when_updating_phone(mock_context):
    """Test order discovery succeeds when mutating phone with customer keyword (CR-01)."""
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
        update.message.text = "đổi sđt anh Nam thành 0988776655"
        update.message.reply_text = AsyncMock()
        update.message.chat.send_action = AsyncMock()

        delta = OrderMutationDelta(
            target_customer_keyword="Nam",
            new_customer_phone="0988776655",
        )
        with patch(
            "src.bot.handlers.mutation.extract_mutation_delta", new=AsyncMock(return_value=delta)
        ):
            await handle_mutation_flow(update, mock_context, "đổi sđt anh Nam thành 0988776655")

        assert update.message.reply_text.called
        card_text = update.message.reply_text.call_args[0][0]
        assert f"SỬA ĐƠN HÀNG #{oid}" in card_text


@pytest.mark.asyncio
async def test_find_orders_for_mutation_avoids_ha_noi_false_match(mock_context):
    """find_orders_for_mutation strictly prioritizes customer_name so 'chị Hà' never matches 'Hà Nội' address."""
    from src.db.orders import find_orders_for_mutation

    async with get_db_connection(":memory:") as db:
        await init_db(db)
        oid_ha = await create_order(
            db,
            Order(
                customer_name="Chị Hà",
                customer_phone="0911000111",
                shipping_address="12 Quang Trung, P.10, Gò Vấp",
                items_text="2 cuốn",
                status=OrderStatus.CHO_LAM,
            ),
        )
        await create_order(
            db,
            Order(
                customer_name="Anh Minh",
                customer_phone="0988000222",
                shipping_address="10 Hoàn Kiếm, Hà Nội",
                items_text="2 cuốn",
                status=OrderStatus.CHO_LAM,
            ),
        )

        matches = await find_orders_for_mutation(db, keyword="chị hà", limit=5)
        assert len(matches) == 1
        assert matches[0].id == oid_ha
        assert matches[0].customer_name == "Chị Hà"


@pytest.mark.asyncio
async def test_mutation_selection_extracts_delta_with_selected_order_context(mock_context):
    """When picking an order from disambiguation, delta is extracted using the selected order's context."""
    from src.bot.handlers.mutation import handle_mutation_selection

    async with get_db_connection(":memory:") as db:
        await init_db(db)
        order1 = await create_order(
            db,
            Order(
                customer_name="Chị Hà",
                customer_phone="0911000111",
                shipping_address="12 Quang Trung, P.10, Gò Vấp, TP.HCM",
                items_text="2 cuốn",
                status=OrderStatus.CHO_LAM,
            ),
        )
        mock_context.application.bot_data["db"] = db

        draft_id = "draft_dis"
        orig_text = "sửa đơn chị hà, địa chỉ không phải là đường quang trung mà là đường điện biên, các thông tin địa chỉ còn lại giữ nguyên"
        mock_context.user_data["pending_mutations"] = {
            draft_id: {
                "draft_id": draft_id,
                "original_text": orig_text,
                "matched_order_ids": [order1],
                "expires_at": time.time() + 180,
            }
        }

        update = MagicMock(spec=Update)
        update.callback_query = MagicMock(spec=CallbackQuery)
        update.callback_query.answer = AsyncMock()
        update.callback_query.edit_message_text = AsyncMock()

        merged_delta = OrderMutationDelta(
            new_shipping_address="12 Điện Biên, P.10, Gò Vấp, TP.HCM",
        )

        with patch(
            "src.bot.handlers.mutation.extract_mutation_delta",
            new=AsyncMock(return_value=merged_delta),
        ) as mock_ext:
            await handle_mutation_selection(update, mock_context, draft_id, order1)

            # Verify extract_mutation_delta received order1's context
            assert mock_ext.called
            call_kwargs = mock_ext.call_args.kwargs
            current_order_passed = call_kwargs.get("current_order")
            assert current_order_passed is not None
            assert (
                current_order_passed["shipping_address"] == "12 Quang Trung, P.10, Gò Vấp, TP.HCM"
            )

        # Verify visual diff card rendered with merged address
        assert update.callback_query.edit_message_text.called
        card_text = update.callback_query.edit_message_text.call_args[0][0]
        assert "12 Quang Trung, P.10, Gò Vấp, TP.HCM" in card_text
        assert "12 Điện Biên, P.10, Gò Vấp, TP.HCM" in card_text
        # Verify draft updated
        draft = mock_context.user_data["pending_mutations"][draft_id]
        assert draft["order_id"] == order1
        assert draft["delta"]["new_shipping_address"] == "12 Điện Biên, P.10, Gò Vấp, TP.HCM"
