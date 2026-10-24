from datetime import datetime

from telegram import CopyTextButton, InlineKeyboardMarkup, ReplyKeyboardMarkup

from src.bot.keyboards import (
    NEXT_STATUS_MAP,
    STATUS_NAMES,
    build_main_menu_reply_keyboard,
    build_order_detail_keyboard,
    render_order_detail_card,
)
from src.models.order import Order, OrderStatus


def test_status_names_and_next_status_map():
    """All 8 OrderStatus entries have Vietnamese labels, next steps mapped."""
    assert len(STATUS_NAMES) == 8
    for status in OrderStatus:
        assert status in STATUS_NAMES
        assert len(STATUS_NAMES[status]) > 0

    assert OrderStatus.CHO_LAM in NEXT_STATUS_MAP
    assert NEXT_STATUS_MAP[OrderStatus.CHO_LAM][0] == OrderStatus.DANG_LAM
    assert OrderStatus.SHIPPER_DA_LAY in NEXT_STATUS_MAP
    assert NEXT_STATUS_MAP[OrderStatus.SHIPPER_DA_LAY][0] == OrderStatus.DA_GIAO


def test_build_main_menu_reply_keyboard_structure():
    """Reply Keyboard is 2x2, persistent, and resizable (D-01, UI-02)."""
    markup = build_main_menu_reply_keyboard()
    assert isinstance(markup, ReplyKeyboardMarkup)
    assert markup.resize_keyboard is True
    assert markup.is_persistent is True
    assert len(markup.keyboard) == 2
    assert len(markup.keyboard[0]) == 2
    assert len(markup.keyboard[1]) == 2

    row0 = [btn.text for btn in markup.keyboard[0]]
    row1 = [btn.text for btn in markup.keyboard[1]]
    assert row0 == ["📦 Đơn hôm nay", "📋 Xem theo ngày"]
    assert row1 == ["📝 Nhập đơn mới", "❓ Trợ giúp"]


def test_render_order_detail_card_html_and_code():
    """Card renders HTML escape, mono code tags for phone and address (D-05, UI-04)."""
    order = Order(
        id=42,
        customer_name="Trần Văn <Test>",
        customer_phone="0912345678",
        shipping_address="123 Lê Lợi & Pasteur, Q1",
        items_text="Băng Nhạc Vàng & Trịnh",
        total_amount=350000,
        cod_amount=350000,
        status=OrderStatus.CHO_LAM,
        tracking_code="VNP987654321",
        photo_file_ids=["photo_1", "photo_2"],
        created_at=datetime(2026, 10, 24, 15, 30),
    )
    card = render_order_detail_card(order)

    # HTML escapes
    assert "&lt;Test&gt;" in card
    assert "&amp; Pasteur" in card
    assert "&amp; Trịnh" in card

    # Code tags for 1-tap copy
    assert "<code>0912345678</code>" in card
    assert "<code>123 Lê Lợi &amp; Pasteur, Q1</code>" in card
    assert "<code>VNP987654321</code>" in card

    # Status and amounts
    assert "⏳ Chờ làm" in card
    assert "350.000 đ" in card
    assert "2 ảnh" in card


def test_build_order_detail_keyboard_copy_buttons_and_callbacks():
    """Detail keyboard contains CopyTextButtons and valid callback_data <= 64 bytes."""
    order = Order(
        id=101,
        customer_name="Lê Văn C",
        customer_phone="0988776655",
        shipping_address="789 CMT8, Tân Bình, HCM",
        items_text="Băng Cải Lương",
        total_amount=200000,
        cod_amount=200000,
        status=OrderStatus.CHO_LAM,
        tracking_code="SPX11223344",
        photo_file_ids=["file_xyz"],
    )
    kb = build_order_detail_keyboard(order, date_str="2026-10-24", page=1)
    assert isinstance(kb, InlineKeyboardMarkup)

    # Flatten buttons and inspect
    flat_buttons = [btn for row in kb.inline_keyboard for btn in row]

    # Verify CopyTextButtons exist for phone and address
    copy_btns = [btn for btn in flat_buttons if btn.copy_text is not None]
    assert len(copy_btns) >= 2
    copy_texts = [btn.copy_text.text for btn in copy_btns]
    assert "0988776655" in copy_texts
    assert "789 CMT8, Tân Bình, HCM" in copy_texts
    assert "SPX11223344" in copy_texts

    # Verify callback_data lengths are <= 64 bytes UTF-8 (T-03-01)
    callback_btns = [btn for btn in flat_buttons if btn.callback_data is not None]
    for btn in callback_btns:
        byte_len = len(btn.callback_data.encode("utf-8"))
        assert byte_len <= 64, f"callback_data '{btn.callback_data}' exceeds 64 bytes"
