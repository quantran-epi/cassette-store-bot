from unittest.mock import AsyncMock, MagicMock

import pytest

from src.models.mutation import IntentDecision, IntentType
from src.models.order import OrderStatus
from src.services.intent_router import (
    classify_intent,
    extract_order_id_from_reply,
    parse_fast_path_status,
)


def test_extract_order_id_from_reply():
    """Extract Order ID integer from replied bot messages."""
    assert extract_order_id_from_reply("📦 <b>CHI TIẾT ĐƠN HÀNG #12</b>\nKhách: Nam") == 12
    assert extract_order_id_from_reply("CHI TIẾT ĐƠN HÀNG #456") == 456
    assert extract_order_id_from_reply("Mã đơn: 789") == 789
    assert extract_order_id_from_reply("Mã đơn #99") == 99
    assert extract_order_id_from_reply("Tin nhắn linh tinh không có mã đơn") is None
    assert extract_order_id_from_reply(None) is None


def test_parse_fast_path_status():
    """Parse short status commands into (order_id, target_status) in 0ms without LLM."""
    assert parse_fast_path_status("huỷ đơn 12") == (12, OrderStatus.HUY_DON)
    assert parse_fast_path_status("hủy đơn #12") == (12, OrderStatus.HUY_DON)
    assert parse_fast_path_status("đơn 12 đã giao") == (12, OrderStatus.DA_GIAO)
    assert parse_fast_path_status("đơn #12 giao thành công") == (12, OrderStatus.DA_GIAO)
    assert parse_fast_path_status("đơn 12 bom hàng") == (12, OrderStatus.BOM_HANG)
    assert parse_fast_path_status("đơn 12 bom") == (12, OrderStatus.BOM_HANG)
    assert parse_fast_path_status("đã đóng gói đơn 15") == (15, OrderStatus.DA_DONG_GOI)
    assert parse_fast_path_status("làm đơn 12") == (12, OrderStatus.DANG_LAM)
    assert parse_fast_path_status("bắt đầu làm đơn 12") == (12, OrderStatus.DANG_LAM)

    # Negative cases
    assert parse_fast_path_status("sửa địa chỉ đơn 12 thành Cầu Giấy") is None
    assert parse_fast_path_status("tìm đơn 12") is None


async def _intent(text: str, client=None, *, has_reply_order: bool = False) -> IntentType:
    decision = await classify_intent(text, client, "dummy", has_reply_order)
    assert isinstance(decision, IntentDecision)
    return decision.intent


@pytest.mark.asyncio
async def test_classify_intent_reply_and_prefixes():
    assert await _intent("đổi địa chỉ sang Cầu Giấy", has_reply_order=True) == IntentType.MUTATE
    assert await _intent("huỷ đơn 12") == IntentType.MUTATE
    assert await _intent("sửa số điện thoại 0912345678") == IntentType.MUTATE
    assert await _intent("doi dia chi sang 15 Le Loi") == IntentType.MUTATE
    assert await _intent("cập nhật mã vận đơn SPX123") == IntentType.MUTATE
    assert await _intent("thay ghi chú thành giao sau 6h") == IntentType.MUTATE


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("tìm khách anh Nam", IntentType.CUSTOMER_PROFILE),
        ("khách Hà Nội", IntentType.CUSTOMER_PROFILE),
        ("khách Nam đã mua bao giờ chưa", IntentType.ORDER_SEARCH),
        ("khách Nam có mấy đơn", IntentType.CUSTOMER_ANALYTICS),
        ("tim khach Nhat", IntentType.CUSTOMER_PROFILE),
        ("tìm khách Ái", IntentType.CUSTOMER_PROFILE),
        ("tìm khách 0903123456", IntentType.CUSTOMER_PROFILE),
        ("tìm đơn anh Nam", IntentType.ORDER_SEARCH),
        ("tim don anh Nam", IntentType.ORDER_SEARCH),
        ("lịch sử đơn hàng", IntentType.ORDER_SEARCH),
        ("0903123456 có mấy đơn rồi", IntentType.CUSTOMER_ANALYTICS),
        ("Khách nào mua nhiều đơn nhất nhỉ", IntentType.CUSTOMER_ANALYTICS),
        ("khach nao mua nhieu don nhat", IntentType.CUSTOMER_ANALYTICS),
        ("khách mua nhiều nhất", IntentType.CUSTOMER_ANALYTICS),
        ("top 5 khách chi tiêu nhiều nhất", IntentType.CUSTOMER_ANALYTICS),
        ("ai mua nhiều nhất", IntentType.CUSTOMER_ANALYTICS),
        ("khách nào chi tiêu nhiều nhất", IntentType.CUSTOMER_ANALYTICS),
    ],
)
async def test_classify_intent_search_routes(text, expected):
    assert await _intent(text) == expected


@pytest.mark.asyncio
async def test_classify_intent_create_and_mutate_with_phone():
    raw_order = "Anh Bình 0903123456 số 10 Nguyễn Huệ lấy 2 băng Tuấn Vũ 200k"
    assert await _intent(raw_order) == IntentType.CREATE
    assert await _intent("sửa địa chỉ đơn 0912345678 thành Cầu Giấy nhé") == IntentType.MUTATE


@pytest.mark.asyncio
async def test_classify_intent_llm_fallback():
    mock_client = MagicMock()
    mock_choice = MagicMock()
    mock_choice.message.content = "MUTATE"
    mock_resp = MagicMock()
    mock_resp.choices = [mock_choice]
    mock_client.chat.completions.create = AsyncMock(return_value=mock_resp)

    decision = await classify_intent("tuần sau giao cũng được nhé shop", mock_client, "gpt-4o-mini")
    assert decision.intent == IntentType.MUTATE
    assert decision.source == "llm"
    mock_client.chat.completions.create.assert_awaited_once()
