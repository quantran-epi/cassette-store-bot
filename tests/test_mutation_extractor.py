from unittest.mock import AsyncMock, MagicMock

import pytest
from openai import BadRequestError

from src.models.mutation import OrderMutationDelta
from src.models.order import OrderStatus
from src.services.mutation_extractor import extract_mutation_delta


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
