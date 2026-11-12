from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest
from openai import BadRequestError

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


PHONE_CASES = [
    ("0912345678", "0912345678"),
    ("0912 345 678", "0912345678"),
    ("0 9 1 2 3 4 5 6 7 8", "0912345678"),
    ("0912\t345\t678", "0912345678"),
    ("0912 345 678", "0912345678"),
    ("0912.345.678", "0912345678"),
    ("(0912) 345-678", "0912345678"),
    ("+84 912 345 678", "0912345678"),
    ("84-912-345-678", "0912345678"),
    ("0084 912 345 678", "0912345678"),
    ("", None),
    ("091234567", None),
    ("09123456789", None),
    ("10912345678", None),
    ("0912 345 67", None),
    ("0912 345 6789", None),
    ("0912 345 678 9", None),
    ("0912345678.9", None),
    ("0123456789", None),
    ("+85 912 345 678", None),
    ("+85 0912345678", None),
    ("+84 0912345678", None),
    ("0084 0912345678", None),
    ("+84 (0) 912 345 678", None),
    ("0084 912 345 6789", None),
    ("abc0912345678xyz", None),
    ("0912abc345678", None),
]


@pytest.mark.parametrize(("phone", "expected"), PHONE_CASES)
def test_phone_format_validation(phone, expected):
    assert ExtractedOrder(customer_phone=phone).customer_phone == expected


@pytest.mark.asyncio
@pytest.mark.parametrize("tier", ["partial", "json", "failed"])
@pytest.mark.parametrize(("phone", "expected"), PHONE_CASES)
async def test_phone_fallback_formats_and_boundaries(phone, expected, tier):
    """Phone recovery validates whole candidates; mocks never contact gateway."""
    client = MagicMock()
    response = MagicMock()
    response.choices[0].message.parsed = ExtractedOrder(
        customer_name="Khách thử", items_text="2 băng", total_amount=250000
    )
    response.choices[0].message.content = response.choices[0].message.parsed.model_dump_json()
    client.beta.chat.completions.parse = AsyncMock(
        return_value=response, side_effect=RuntimeError("offline") if tier != "partial" else None
    )
    client.chat.completions.create = AsyncMock(
        return_value=response, side_effect=RuntimeError("offline") if tier == "failed" else None
    )
    text = f"Khách thử ĐT {phone} lấy 2 băng thu 250k"

    result = await extract_order_from_text(client, "offline-test", text)

    if tier == "failed" and expected is None:
        assert result is None
    else:
        assert result is not None
        assert result.customer_phone == expected
        assert result.cod_amount == 250000
        if tier != "failed":
            assert result.customer_name == "Khách thử"
            assert result.items_text == "2 băng"
    assert client.beta.chat.completions.parse.await_args.kwargs["messages"][1] == {
        "role": "user", "content": f"<message>{text}</message>"
    }


@pytest.mark.asyncio
@pytest.mark.parametrize("prefix", ["ĐT", "Số 123"])
@pytest.mark.parametrize("suffix", ["2 băng thu 250k", "123 Lê Lợi lấy 2 băng", "\n123 Lê Lợi"])
async def test_phone_fallback_keeps_contiguous_phone_before_numeric_fields(prefix, suffix):
    client = MagicMock()
    client.beta.chat.completions.parse = AsyncMock(side_effect=RuntimeError("offline"))
    client.chat.completions.create = AsyncMock(side_effect=RuntimeError("offline"))
    result = await extract_order_from_text(client, "offline-test", f"{prefix} 0912345678 {suffix}")
    assert result is not None
    assert result.customer_phone == "0912345678"


@pytest.mark.asyncio
@pytest.mark.parametrize("phone", ["0912 345 67", "0912 345 678"])
@pytest.mark.parametrize("suffix", ["2 băng thu 250k", "3 cuốn Chế Linh", "2 bang", "3 cuon", "2 phôi", "250k", "250000 đồng"])
async def test_phone_fallback_does_not_borrow_digits_from_quantity(phone, suffix):
    client = MagicMock()
    client.beta.chat.completions.parse = AsyncMock(side_effect=RuntimeError("offline"))
    client.chat.completions.create = AsyncMock(side_effect=RuntimeError("offline"))
    result = await extract_order_from_text(client, "offline-test", f"ĐT {phone} {suffix}")
    if phone == "0912 345 67":
        assert result is None
    else:
        assert result is not None
        assert result.customer_phone == "0912345678"


def test_vietnamese_currency_normalization_model_defaults():
    """Ensure amounts cannot be negative and have proper defaults."""
    order = ExtractedOrder()
    assert order.total_amount == 0
    assert order.cod_amount == 0
    assert order.deposit_amount == 0
    assert order.payment_method == "COD"


def test_extracted_order_has_tapes_but_no_tape_quantity():
    """LLM tape_quantity=99 is discarded; tapes/genres are kept."""
    res = ExtractedOrder.model_validate_json(
        '{"customer_phone": "0912345678", "items_text": "6 sony 90p",'
        ' "tape_quantity": 99, "tapes": [{"label": " sony 90p ", "qty": 6}],'
        ' "tape_genres": [" nhạc vàng ", ""]}'
    )
    assert not hasattr(res, "tape_quantity")
    assert res.tapes[0].label == "sony 90p"
    assert res.tapes[0].qty == 6
    assert res.tape_genres == ["nhạc vàng"]


def test_extracted_order_drops_invalid_tapes():
    """Empty labels and qty < 1 are dropped during normalization."""
    res = ExtractedOrder.model_validate_json(
        '{"tapes": [{"label": "  ", "qty": 2}, {"label": "sony", "qty": 0},'
        ' {"label": "maxell 90p", "qty": 1}]}'
    )
    assert [t.label for t in res.tapes] == ["maxell 90p"]


def test_build_tape_columns_fallback_when_llm_returns_no_tapes():
    """No LLM tapes -> deterministic fallback is non-zero for non-empty text."""
    from src.services.tape_parser import build_tape_columns

    extracted = ExtractedOrder(customer_phone="0912345678", items_text="4 băng sony 90p")
    cols = build_tape_columns(
        extracted.items_text, extracted.tapes, extracted.tape_genres
    )
    assert cols.quantity == 4


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
    """If both Tier 1 and Tier 2 fail and no phone in text, returns None safely."""
    mock_client = MagicMock()
    request = httpx.Request("POST", "https://api.9router.com/v1/chat/completions")
    httpx.Response(500, request=request)
    mock_client.beta.chat.completions.parse = AsyncMock(side_effect=Exception("Network error"))
    mock_client.chat.completions.create = AsyncMock(side_effect=Exception("Connection refused"))

    res = await extract_order_from_text(mock_client, "gpt-4o-mini", "Tin nhắn lỗi không có số")
    assert res is None


@pytest.mark.asyncio
async def test_llm_extractor_deterministic_fallbacks():
    """Verify regex fallback recovers phone and COD if LLM drops them."""
    mock_client = MagicMock()
    # LLM returns partial JSON with missing phone and cod
    partial_json = '{"customer_name": "Nguyễn Văn A", "shipping_address": "Hà Nội", "total_amount": 250000}'
    mock_choice = MagicMock()
    mock_choice.message.content = partial_json
    mock_tier2_resp = MagicMock()
    mock_tier2_resp.choices = [mock_choice]
    mock_client.beta.chat.completions.parse = AsyncMock(side_effect=Exception("parse error"))
    mock_client.chat.completions.create = AsyncMock(return_value=mock_tier2_resp)

    raw_text = "Nguyễn Văn A Hà Nội ĐT 0912345678 2 băng Tuấn Vũ thu 250k"
    res = await extract_order_from_text(mock_client, "gpt-4o-mini", raw_text)

    assert res is not None
    assert res.customer_phone == "0912345678"
    assert res.cod_amount == 250000
    assert res.total_amount == 250000
