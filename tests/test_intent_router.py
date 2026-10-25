from unittest.mock import AsyncMock, MagicMock

import pytest

from src.models.mutation import IntentType
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


@pytest.mark.asyncio
async def test_classify_intent_reply_and_prefixes():
    """classify_intent returns MUTATE when replying to order or starts with mutation prefixes."""
    # Has reply order context
    res = await classify_intent("đổi địa chỉ sang Cầu Giấy", client=None, model_id="dummy", has_reply_order=True)
    assert res == IntentType.MUTATE

    # Fast-path status command
    res = await classify_intent("huỷ đơn 12", client=None, model_id="dummy")
    assert res == IntentType.MUTATE

    # Mutation prefixes
    assert await classify_intent("sửa số điện thoại 0912345678", None, "dummy") == IntentType.MUTATE
    assert await classify_intent("đổi địa chỉ sang 15 Lê Lợi", None, "dummy") == IntentType.MUTATE
    assert await classify_intent("cập nhật mã vận đơn SPX123", None, "dummy") == IntentType.MUTATE
    assert await classify_intent("thay ghi chú thành giao sau 6h", None, "dummy") == IntentType.MUTATE


@pytest.mark.asyncio
async def test_classify_intent_search_and_create():
    """classify_intent detects SEARCH and CREATE accurately."""
    # Search queries
    assert await classify_intent("tìm đơn anh Nam", None, "dummy") == IntentType.SEARCH
    assert await classify_intent("hôm nay bán được bao nhiêu đơn", None, "dummy") == IntentType.SEARCH
    assert await classify_intent("lịch sử đơn hàng", None, "dummy") == IntentType.SEARCH

    # Order creation (contains phone number without mutation keywords)
    raw_order = "Anh Bình 0903123456 số 10 Nguyễn Huệ lấy 2 băng Tuấn Vũ 200k"
    assert await classify_intent(raw_order, None, "dummy") == IntentType.CREATE


@pytest.mark.asyncio
async def test_classify_intent_ambiguity_favors_mutate():
    """classify_intent resolves ambiguous text with phone number AND mutation keyword to MUTATE (D-02)."""
    ambiguous = "sửa địa chỉ đơn 0912345678 thành Cầu Giấy nhé"
    assert await classify_intent(ambiguous, None, "dummy") == IntentType.MUTATE


@pytest.mark.asyncio
async def test_classify_intent_llm_fallback():
    """classify_intent falls back to lightweight LLM when regex is uncertain (D-04)."""
    mock_client = MagicMock()
    mock_choice = MagicMock()
    mock_choice.message.content = "MUTATE"
    mock_resp = MagicMock()
    mock_resp.choices = [mock_choice]
    mock_client.chat.completions.create = AsyncMock(return_value=mock_resp)

    res = await classify_intent("tuần sau giao cũng được nhé shop", mock_client, "gpt-4o-mini")
    assert res == IntentType.MUTATE
    assert mock_client.chat.completions.create.called
