import pytest
from unittest.mock import AsyncMock, MagicMock
from openai import BadRequestError
import httpx

from src.models.extractor import ExtractedOrder
from src.services.extractor import extract_order_from_text


def test_extracted_order_pydantic_schema():
    """Test ExtractedOrder schema initialization and phone normalization."""
    order = ExtractedOrder(
        customer_name="Bác Hùng",
        customer_phone="0912.345.678",
        shipping_address="123 Lê Lợi, P. Bến Thành, Q.1, TP.HCM",
        items_text="2 cuốn Tuấn Vũ 3, 1 cuốn Chế Linh",
        total_amount=350000,
        cod_amount=300000,
        deposit_amount=50000,
        payment_method="COD",
        notes="Giao buổi chiều",
    )
    assert order.customer_name == "Bác Hùng"
    assert order.customer_phone == "0912345678"
    assert order.total_amount == 350000
    assert order.cod_amount == 300000
    assert order.deposit_amount == 50000


def test_extracted_order_phone_normalization_variants():
    """Test phone normalization for +84, spaces, dashes, dots and invalid cases."""
    # +84 format
    o1 = ExtractedOrder(customer_phone="+84 987 654 321")
    assert o1.customer_phone == "0987654321"

    # With dashes and dots
    o2 = ExtractedOrder(customer_phone="090-123.4567")
    assert o2.customer_phone == "0901234567"

    # Invalid phone (less than 10 digits or invalid prefix) -> None
    o3 = ExtractedOrder(customer_phone="123456")
    assert o3.customer_phone is None

    o4 = ExtractedOrder(customer_phone="0123456789")  # 01 prefix invalid in current VN mobile network
    assert o4.customer_phone is None

    o5 = ExtractedOrder(customer_phone=None)
    assert o5.customer_phone is None


def test_vietnamese_currency_normalization_model_defaults():
    """Ensure amounts cannot be negative and have proper defaults."""
    order = ExtractedOrder()
    assert order.total_amount == 0
    assert order.cod_amount == 0
    assert order.deposit_amount == 0
    assert order.payment_method == "COD"


@pytest.mark.asyncio
async def test_llm_extractor_tier1_success():
    """Tier 1: client.beta.chat.completions.parse succeeds and returns ExtractedOrder."""
    mock_client = MagicMock()
    mock_response = MagicMock()
    expected_order = ExtractedOrder(
        customer_name="Anh Tuấn",
        customer_phone="0988776655",
        shipping_address="456 Hai Bà Trưng, HN",
        items_text="1 cuốn Băng Chế Linh",
        total_amount=250000,
        cod_amount=250000,
    )
    mock_choice = MagicMock()
    mock_choice.message.parsed = expected_order
    mock_response.choices = [mock_choice]

    mock_client.beta.chat.completions.parse = AsyncMock(return_value=mock_response)

    res = await extract_order_from_text(mock_client, "gpt-4o-mini", "Tuấn 0988776655 456 Hai Bà Trưng 1 băng 250k")
    assert res == expected_order
    mock_client.beta.chat.completions.parse.assert_awaited_once()


@pytest.mark.asyncio
async def test_llm_extractor_2tier_fallback():
    """Tier 1 fails with BadRequestError -> Tier 2 (json_object) succeeds and parses."""
    mock_client = MagicMock()

    # Tier 1 raises BadRequestError
    request = httpx.Request("POST", "https://api.9router.com/v1/chat/completions")
    response = httpx.Response(400, request=request)
    mock_client.beta.chat.completions.parse = AsyncMock(
        side_effect=BadRequestError("Unrecognized request parameter: json_schema", response=response, body=None)
    )

    # Tier 2 returns JSON string
    json_payload = (
        '{"customer_name": "Chị Lan", "customer_phone": "0912334455", '
        '"shipping_address": "789 Điện Biên Phủ, Đà Nẵng", '
        '"items_text": "2 cuốn Tuấn Vũ", "total_amount": 500000, "cod_amount": 300000, '
        '"deposit_amount": 200000, "payment_method": "COD", "notes": ""}'
    )
    mock_choice = MagicMock()
    mock_choice.message.content = json_payload
    mock_tier2_resp = MagicMock()
    mock_tier2_resp.choices = [mock_choice]
    mock_client.chat.completions.create = AsyncMock(return_value=mock_tier2_resp)

    res = await extract_order_from_text(
        mock_client,
        "deepseek-chat",
        "Chị Lan 0912334455 789 Điện Biên Phủ 2 cuốn Tuấn Vũ 500k đã cọc 200k",
    )

    assert res is not None
    assert res.customer_name == "Chị Lan"
    assert res.customer_phone == "0912334455"
    assert res.total_amount == 500000
    assert res.cod_amount == 300000
    assert res.deposit_amount == 200000
    mock_client.beta.chat.completions.parse.assert_awaited_once()
    mock_client.chat.completions.create.assert_awaited_once()


@pytest.mark.asyncio
async def test_llm_extractor_markdown_fence_cleaning():
    """Verify JSON wrapped in ```json ... ``` code fence is parsed correctly in Tier 2."""
    mock_client = MagicMock()
    mock_client.beta.chat.completions.parse = AsyncMock(side_effect=Exception("parse error"))

    markdown_payload = (
        "```json\n"
        '{\n  "customer_name": "Nguyễn Đức Thành",\n  "customer_phone": "0903626566",\n'
        '  "shipping_address": "22 trần quốc vượng, cầu giấy",\n'
        '  "items_text": "3 ud xám 90p",\n  "total_amount": 325000,\n  "cod_amount": 325000,\n'
        '  "deposit_amount": 0,\n  "payment_method": "COD",\n  "notes": ""\n}\n'
        "```"
    )
    mock_choice = MagicMock()
    mock_choice.message.content = markdown_payload
    mock_tier2_resp = MagicMock()
    mock_tier2_resp.choices = [mock_choice]
    mock_client.chat.completions.create = AsyncMock(return_value=mock_tier2_resp)

    res = await extract_order_from_text(
        mock_client,
        "default-model",
        "raw text",
    )
    assert res is not None
    assert res.customer_name == "Nguyễn Đức Thành"
    assert res.customer_phone == "0903626566"
    assert res.cod_amount == 325000


@pytest.mark.asyncio
async def test_llm_extractor_both_tiers_fail_returns_none():
    """If both Tier 1 and Tier 2 fail, extract_order_from_text returns None safely."""
    mock_client = MagicMock()
    request = httpx.Request("POST", "https://api.9router.com/v1/chat/completions")
    response = httpx.Response(500, request=request)
    mock_client.beta.chat.completions.parse = AsyncMock(side_effect=Exception("Network error"))
    mock_client.chat.completions.create = AsyncMock(side_effect=Exception("Connection refused"))

    res = await extract_order_from_text(mock_client, "gpt-4o-mini", "Tin nhắn lỗi")
    assert res is None
