from unittest.mock import AsyncMock, MagicMock

import pytest
from openai import BadRequestError

from src.models.mutation import OrderMutationDelta
from src.models.order import OrderStatus
from src.services.mutation_extractor import MUTATION_SYSTEM_PROMPT, extract_mutation_delta


def test_mutation_prompt_requests_tape_breakdown():
    """Prompt must ask for new_tapes/new_tape_genres when items change."""
    assert "new_tapes" in MUTATION_SYSTEM_PROMPT
    assert "new_tape_genres" in MUTATION_SYSTEM_PROMPT


def test_order_mutation_delta_phone_validation():
    """OrderMutationDelta validates and normalizes Vietnamese mobile numbers."""
    delta = OrderMutationDelta(new_customer_phone="+84 903 626 566")
    assert delta.new_customer_phone == "0903626566"

    delta2 = OrderMutationDelta(new_customer_phone="0912.345.678")
    assert delta2.new_customer_phone == "0912345678"

    delta3 = OrderMutationDelta(new_customer_phone="84987654321")
    assert delta3.new_customer_phone == "0987654321"

    # Invalid phone formats become None
    delta_invalid = OrderMutationDelta(new_customer_phone="123456")
    assert delta_invalid.new_customer_phone is None


def test_order_mutation_delta_5_field_groups():
    """OrderMutationDelta models all 5 field groups per MUT-03."""
    delta = OrderMutationDelta(
        target_order_id=12,
        target_customer_keyword="Bác Nam",
        # Group 1: Status
        new_status=OrderStatus.DA_DONG_GOI,
        status_disambiguation_needed=False,
        # Group 2: Tracking
        new_tracking_code="SPX123456VN",
        # Group 3: Notes
        new_notes="Giao buổi chiều",
        # Group 4: Money
        new_total_amount=350000,
        new_cod_amount=350000,
        # Group 5: Customer / Shipping
        new_customer_name="Nam Tuấn Vũ",
        new_customer_phone="0912345678",
        new_shipping_address="Số 10 Hàng Bài, Hoàn Kiếm, Hà Nội",
        new_items_text="3 cuốn Tuấn Vũ",
    )
    assert delta.target_order_id == 12
    assert delta.new_status == OrderStatus.DA_DONG_GOI
    assert delta.new_tracking_code == "SPX123456VN"
    assert delta.new_notes == "Giao buổi chiều"
    assert delta.new_total_amount == 350000
    assert delta.new_cod_amount == 350000
    assert delta.new_customer_name == "Nam Tuấn Vũ"
    assert delta.new_customer_phone == "0912345678"
    assert delta.new_shipping_address == "Số 10 Hàng Bài, Hoàn Kiếm, Hà Nội"
    assert delta.new_items_text == "3 cuốn Tuấn Vũ"


@pytest.mark.asyncio
async def test_extract_mutation_delta_tier1_parse():
    """extract_mutation_delta succeeds with Tier 1 beta.chat.completions.parse."""
    mock_client = MagicMock()
    mock_parsed_delta = OrderMutationDelta(
        target_order_id=25,
        new_shipping_address="45 Lê Duẩn, Đà Nẵng",
        new_notes="Giao trước 5h",
    )
    mock_choice = MagicMock()
    mock_choice.message.parsed = mock_parsed_delta
    mock_response = MagicMock()
    mock_response.choices = [mock_choice]
    mock_client.beta.chat.completions.parse = AsyncMock(return_value=mock_response)

    result = await extract_mutation_delta(
        mock_client,
        "gpt-4o-mini",
        "đơn 25 đổi địa chỉ sang 45 Lê Duẩn, Đà Nẵng, giao trước 5h",
    )

    assert result is not None
    assert result.target_order_id == 25
    assert result.new_shipping_address == "45 Lê Duẩn, Đà Nẵng"
    assert result.new_notes == "Giao trước 5h"
    assert mock_client.beta.chat.completions.parse.called


@pytest.mark.asyncio
async def test_extract_mutation_delta_tier2_fallback():
    """extract_mutation_delta falls back to json_object mode on Tier 1 BadRequestError."""
    mock_client = MagicMock()
    # Tier 1 fails with BadRequestError (e.g. 9router compatibility issue)
    mock_client.beta.chat.completions.parse = AsyncMock(
        side_effect=BadRequestError(
            message="Structured outputs not supported by provider",
            response=MagicMock(status_code=400),
            body={},
        )
    )

    # Tier 2 succeeds
    json_payload = (
        '{"target_order_id": 18, "new_tracking_code": "VTP998877", '
        '"new_status": "SHIPPER_DA_LAY", "new_total_amount": 250000, "new_cod_amount": 250000}'
    )
    mock_choice = MagicMock()
    mock_choice.message.content = json_payload
    mock_response = MagicMock()
    mock_response.choices = [mock_choice]
    mock_client.chat.completions.create = AsyncMock(return_value=mock_response)

    result = await extract_mutation_delta(
        mock_client,
        "custom-model",
        "đơn 18 mã vận đơn VTP998877 shipper đã lấy",
    )

    assert result is not None
    assert result.target_order_id == 18
    assert result.new_tracking_code == "VTP998877"
    assert result.new_status == OrderStatus.SHIPPER_DA_LAY
    assert result.new_total_amount == 250000
    assert mock_client.chat.completions.create.called


def test_clean_json_markdown_with_trailing_chatter():
    """_clean_json_markdown isolates JSON object even when LLM appends markdown notes or chatter."""
    from src.services.mutation_extractor import _clean_json_markdown

    raw_response = (
        "```json\n"
        "{\n"
        '  "target_order_id": null,\n'
        '  "target_customer_keyword": "Bác Ba",\n'
        '  "new_customer_phone": "0988776655"\n'
        "}\n"
        "```\n\n"
        "Bỏ qua: tra cứu ID đơn. Thêm khi: có API map tên khách ra ID đơn."
    )
    cleaned = _clean_json_markdown(raw_response)
    delta = OrderMutationDelta.model_validate_json(cleaned)
    assert delta.target_customer_keyword == "Bác Ba"
    assert delta.new_customer_phone == "0988776655"


def test_clean_json_markdown_without_fences_with_surrounding_text():
    """_clean_json_markdown finds {...} block even if markdown code block is absent."""
    from src.services.mutation_extractor import _clean_json_markdown

    raw_response = (
        "Dưới đây là kết quả bóc tách:\n"
        '{"target_order_id": 42, "new_notes": "Gọi trước khi giao"}\n'
        "Lưu ý: Không thay đổi tiền."
    )
    cleaned = _clean_json_markdown(raw_response)
    delta = OrderMutationDelta.model_validate_json(cleaned)
    assert delta.target_order_id == 42
    assert delta.new_notes == "Gọi trước khi giao"


@pytest.mark.asyncio
async def test_extract_mutation_delta_includes_current_order_context():
    """current_order is rendered as a <current_order> block before <message>."""
    mock_client = MagicMock()
    mock_choice = MagicMock()
    mock_choice.message.parsed = OrderMutationDelta(new_shipping_address="45 Lê Duẩn, Đà Nẵng")
    mock_response = MagicMock()
    mock_response.choices = [mock_choice]
    mock_client.beta.chat.completions.parse = AsyncMock(return_value=mock_response)

    draft = {
        "customer_name": "Chị Mai",
        "customer_phone": "0987654321",
        "shipping_address": "88 Lê Lợi, Hải Châu, Đà Nẵng",
        "items_text": "3 cuốn Tuấn Vũ",
        "total_amount": 500000,
        "cod_amount": 400000,
        "notes": "",
    }
    await extract_mutation_delta(
        mock_client,
        "gpt-4o-mini",
        "sửa địa chỉ sang 45 Lê Duẩn, Đà Nẵng",
        current_order=draft,
    )

    sent_messages = mock_client.beta.chat.completions.parse.call_args.kwargs["messages"]
    assert len(sent_messages) == 3
    assert "<current_order>" in sent_messages[1]["content"]
    assert "88 Lê Lợi, Hải Châu, Đà Nẵng" in sent_messages[1]["content"]
    assert "500.000 đ" in sent_messages[1]["content"]
    assert "<message>sửa địa chỉ sang 45 Lê Duẩn, Đà Nẵng</message>" == sent_messages[2]["content"]


@pytest.mark.asyncio
async def test_extract_mutation_delta_omits_current_order_by_default():
    """Without current_order the prompt stays two messages."""
    mock_client = MagicMock()
    mock_choice = MagicMock()
    mock_choice.message.parsed = OrderMutationDelta(new_notes="ok")
    mock_response = MagicMock()
    mock_response.choices = [mock_choice]
    mock_client.beta.chat.completions.parse = AsyncMock(return_value=mock_response)

    await extract_mutation_delta(mock_client, "gpt-4o-mini", "ghi chú giao sau 18h")

    sent_messages = mock_client.beta.chat.completions.parse.call_args.kwargs["messages"]
    assert len(sent_messages) == 2
    assert sent_messages[0]["role"] == "system"
    assert sent_messages[1]["content"] == "<message>ghi chú giao sau 18h</message>"


@pytest.mark.asyncio
async def test_search_target_orders_for_mutation():
    """search_target_orders_for_mutation executes generated SELECT and maps to Order models."""
    from src.db.connection import get_db_connection
    from src.db.orders import create_order
    from src.db.schema import init_db
    from src.models.order import Order
    from src.services.mutation_extractor import search_target_orders_for_mutation

    async with get_db_connection(":memory:") as db:
        await init_db(db)
        oid1 = await create_order(
            db,
            Order(
                customer_name="Chị Hà",
                customer_phone="0911000111",
                shipping_address="12 Quang Trung, P.10, Gò Vấp",
                items_text="1 cuốn",
                status=OrderStatus.CHO_LAM,
            ),
        )
        # Another order whose shipping address happens to have "Hà Nội"
        await create_order(
            db,
            Order(
                customer_name="Anh Tuấn",
                customer_phone="0988000222",
                shipping_address="Số 5 Bà Triệu, Hoàn Kiếm, Hà Nội",
                items_text="1 cuốn",
                status=OrderStatus.CHO_LAM,
            ),
        )

        mock_client = MagicMock()
        mock_choice = MagicMock()
        mock_choice.message.content = (
            "SELECT * FROM orders WHERE unaccent(customer_name) LIKE '%ha%' "
            "ORDER BY created_at DESC LIMIT 5"
        )
        mock_response = MagicMock(choices=[mock_choice])
        mock_client.chat.completions.create = AsyncMock(return_value=mock_response)

        results = await search_target_orders_for_mutation(
            mock_client,
            "test-model",
            db,
            "sửa đơn chị hà, địa chỉ không phải quang trung mà là điện biên",
        )

        assert len(results) == 1
        assert results[0].id == oid1
        assert results[0].customer_name == "Chị Hà"
        assert results[0].customer_phone == "0911000111"
