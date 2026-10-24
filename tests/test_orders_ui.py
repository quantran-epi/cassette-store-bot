from datetime import datetime

from telegram import CopyTextButton, InlineKeyboardMarkup, ReplyKeyboardMarkup

from src.bot.keyboards import (
    NEXT_STATUS_MAP,
    STATUS_NAMES,
    build_date_picker_keyboard,
    build_main_menu_reply_keyboard,
    build_order_detail_keyboard,
    build_order_list_keyboard,
    build_status_selection_keyboard,
    render_order_detail_card,
    render_order_list_card,
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


def test_build_date_picker_keyboard():
    """Date picker has Today, Yesterday, and 3 previous days with valid callbacks."""
    base_dt = datetime(2026, 10, 24, 10, 0)
    kb = build_date_picker_keyboard(base_date=base_dt)
    assert isinstance(kb, InlineKeyboardMarkup)

    flat_buttons = [btn for row in kb.inline_keyboard for btn in row]
    texts = [btn.text for btn in flat_buttons]
    callbacks = [btn.callback_data for btn in flat_buttons]

    assert "Hôm nay" in texts
    assert "Hôm qua" in texts
    assert "ord_dt:2026-10-24" in callbacks
    assert "ord_dt:2026-10-23" in callbacks
    assert "ord_dt:2026-10-22" in callbacks
    assert "ord_dt:2026-10-21" in callbacks
    assert "ord_dt:2026-10-20" in callbacks

    for cb in callbacks:
        assert len(cb.encode("utf-8")) <= 64


def test_render_order_list_card_empty_and_populated():
    """List card handles empty state (D-04) and populated list (D-03)."""
    # Empty state
    empty_card = render_order_list_card([], "2026-10-24", page=1, total_pages=1, total_orders=0)
    assert "Ngày này chưa có đơn hàng nào bác nhé!" in empty_card

    # Populated state
    orders = [
        Order(
            id=1,
            customer_name="Khách 1",
            customer_phone="0901",
            shipping_address="HCM",
            items_text="Băng 1",
            total_amount=150000,
            status=OrderStatus.CHO_LAM,
        ),
        Order(
            id=2,
            customer_name="Khách 2",
            customer_phone="0902",
            shipping_address="HN",
            items_text="Băng 2",
            total_amount=250000,
            status=OrderStatus.DA_GIAO,
        ),
    ]
    card = render_order_list_card(orders, "2026-10-24", page=1, total_pages=2, total_orders=6)
    assert "24/10/2026" in card
    assert "Tổng cộng: <b>6 đơn</b> (Trang 1/2)" in card
    assert "Đơn #1" in card
    assert "Khách 1" in card
    assert "150.000 đ" in card
    assert "⏳ Chờ làm" in card
    assert "Đơn #2" in card
    assert "Khách 2" in card
    assert "250.000 đ" in card
    assert "✅ Đã giao thành công" in card


def test_build_order_list_keyboard_empty_and_pagination():
    """List keyboard supports empty state actions and pagination prev/next logic."""
    # Empty state
    empty_kb = build_order_list_keyboard([], "2026-10-24", page=1, total_pages=1)
    flat_empty = [btn for row in empty_kb.inline_keyboard for btn in row]
    empty_cbs = [btn.callback_data for btn in flat_empty]
    assert "ord_act:new" in empty_cbs
    assert "ord_act:pick_date" in empty_cbs

    orders = [
        Order(
            id=10,
            customer_name="Nguyễn Văn A",
            customer_phone="0901",
            shipping_address="HCM",
            items_text="Băng",
            total_amount=100000,
        )
    ]

    # Page 1 of 3: has Next, no Prev
    kb_p1 = build_order_list_keyboard(orders, "2026-10-24", page=1, total_pages=3)
    p1_cbs = [btn.callback_data for row in kb_p1.inline_keyboard for btn in row]
    assert "ord_v:10:2026-10-24:1" in p1_cbs
    assert "ord_pg:2026-10-24:2" in p1_cbs
    assert not any("ord_pg:2026-10-24:0" in cb for cb in p1_cbs)

    # Page 2 of 3: has Prev and Next
    kb_p2 = build_order_list_keyboard(orders, "2026-10-24", page=2, total_pages=3)
    p2_cbs = [btn.callback_data for row in kb_p2.inline_keyboard for btn in row]
    assert "ord_pg:2026-10-24:1" in p2_cbs
    assert "ord_pg:2026-10-24:3" in p2_cbs

    # Page 3 of 3: has Prev, no Next
    kb_p3 = build_order_list_keyboard(orders, "2026-10-24", page=3, total_pages=3)
    p3_cbs = [btn.callback_data for row in kb_p3.inline_keyboard for btn in row]
    assert "ord_pg:2026-10-24:2" in p3_cbs
    assert not any("ord_pg:2026-10-24:4" in cb for cb in p3_cbs)


def test_build_status_selection_keyboard():
    """Status selection keyboard has 8 status options with current highlighted and back button."""
    kb = build_status_selection_keyboard(order_id=55, current_status=OrderStatus.DANG_LAM)
    assert isinstance(kb, InlineKeyboardMarkup)
    flat_buttons = [btn for row in kb.inline_keyboard for btn in row]

    texts = [btn.text for btn in flat_buttons]
    callbacks = [btn.callback_data for btn in flat_buttons]

    # Current status is marked
    marked_text = [t for t in texts if "(Hiện tại)" in t]
    assert len(marked_text) == 1
    assert "🛠️ Đang làm (Hiện tại)" in marked_text[0]

    # Back button exists
    assert "ord_v_cur:55" in callbacks

    # Check 8 statuses mapped
    status_cbs = [cb for cb in callbacks if cb.startswith("ord_st:55:")]
    assert len(status_cbs) == 8
    for cb in callbacks:
        assert len(cb.encode("utf-8")) <= 64

