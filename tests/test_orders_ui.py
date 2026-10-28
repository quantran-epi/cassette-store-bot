from datetime import datetime
from unittest.mock import AsyncMock, MagicMock

import pytest
from telegram import (
    Chat,
    InlineKeyboardMarkup,
    Message,
    ReplyKeyboardMarkup,
    Update,
    User,
)
from telegram.ext import ContextTypes

from src.bot.handlers.base import start_command
from src.bot.handlers.order_actions import (
    handle_action_state_photo,
    handle_action_state_text,
    handle_order_action_callback,
    handle_order_status_callback,
)
from src.bot.handlers.orders import handle_menu_reply, handle_order_nav_callback
from src.bot.keyboards import (
    NEXT_STATUS_MAP,
    STATUS_NAMES,
    build_date_picker_keyboard,
    build_main_menu_reply_keyboard,
    build_order_detail_keyboard,
    build_order_list_keyboard,
    build_status_order_list_keyboard,
    build_status_selection_keyboard,
    format_customer_classification,
    format_order_compact_line,
    render_order_detail_card,
    render_order_list_card,
    render_status_order_list_card,
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
    """Reply Keyboard is 3x2, persistent, and resizable (D-01, UI-02)."""
    markup = build_main_menu_reply_keyboard()
    assert isinstance(markup, ReplyKeyboardMarkup)
    assert markup.resize_keyboard is True
    assert markup.is_persistent is True
    assert len(markup.keyboard) == 3
    for row in markup.keyboard:
        assert len(row) == 2

    rows = [[btn.text for btn in row] for row in markup.keyboard]
    assert rows[0] == ["📦 Đơn hôm nay", "⏳ Đơn chờ làm"]
    assert rows[1] == ["📋 Xem theo ngày", "📝 Nhập đơn mới"]
    assert rows[2] == ["🔍 Tra cứu đơn", "❓ Trợ giúp"]


@pytest.mark.parametrize(
    ("orders", "tier"),
    [(0, "KHÁCH VÃNG LAI"), (1, "KHÁCH MUA 1 LẦN"), (2, "KHÁCH QUEN"), (4, "KHÁCH QUEN"), (5, "KHÁCH THÂN THIẾT")],
)
def test_customer_frequency_tier_boundaries(orders, tier):
    text = format_customer_classification(orders, 0)
    assert f"TẦN SUẤT:</b> <b>{tier}</b>" in text
    assert f"({orders} đơn hoàn thành)" in text


@pytest.mark.parametrize(
    ("spend", "tier"),
    [
        (999999, "DƯỚI 1 TRIỆU"),
        (1000000, "1–DƯỚI 3 TRIỆU"),
        (2999999, "1–DƯỚI 3 TRIỆU"),
        (3000000, "3–DƯỚI 10 TRIỆU"),
        (9999999, "3–DƯỚI 10 TRIỆU"),
        (10000000, "TỪ 10 TRIỆU"),
    ],
)
def test_customer_spend_tier_boundaries(spend, tier):
    text = format_customer_classification(0, spend)
    assert f"CHI TIÊU:</b> <b>{tier}</b>" in text
    assert f"({spend:,} đ)".replace(",", ".") in text


def test_customer_classification_clamps_negative_values():
    text = format_customer_classification(-2, -100)
    assert "KHÁCH VÃNG LAI" in text
    assert "(0 đơn hoàn thành)" in text
    assert "DƯỚI 1 TRIỆU" in text
    assert "(0 đ)" in text


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
        customer_completed_orders=5,
        customer_completed_spend=10000000,
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
    assert "TẦN SUẤT:</b> <b>KHÁCH THÂN THIẾT</b>" in card
    assert "CHI TIÊU:</b> <b>TỪ 10 TRIỆU</b>" in card


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
            customer_completed_orders=2,
            customer_completed_spend=1500000,
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
    assert "TẦN SUẤT:</b> <b>KHÁCH QUEN</b>" in card
    assert "CHI TIÊU:</b> <b>1–DƯỚI 3 TRIỆU</b>" in card
    assert card.count("TẦN SUẤT:") == 1  # Order without hydrated stats is not mislabeled as zero.


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


def test_format_order_compact_line():
    """Compact line is single-line with id, escaped name, and formatted total (D-2)."""
    order = Order(
        id=7,
        customer_name="Bác <Ba>",
        customer_phone="0901",
        shipping_address="HCM",
        items_text="Băng",
        total_amount=1250000,
    )
    line = format_order_compact_line(order)
    assert "\n" not in line
    assert "<b>#7</b>" in line
    assert "Bác &lt;Ba&gt;" in line
    assert "1.250.000 đ" in line


def test_render_status_order_list_card_grouping_and_empty():
    """Status list card groups by VN date, paginates, and handles the empty state."""
    orders = [
        Order(
            id=1,
            customer_name="Khách A",
            customer_phone="0901",
            shipping_address="HCM",
            items_text="Băng",
            total_amount=100000,
            status=OrderStatus.CHO_LAM,
            created_at=datetime(2026, 10, 26, 10, 0),
            customer_completed_orders=1,
            customer_completed_spend=1000000,
        ),
        Order(
            id=2,
            customer_name="Khách B",
            customer_phone="0902",
            shipping_address="HCM",
            items_text="Băng",
            total_amount=200000,
            status=OrderStatus.CHO_LAM,
            created_at=datetime(2026, 10, 26, 8, 0),
        ),
        Order(
            id=3,
            customer_name="Khách C",
            customer_phone="0903",
            shipping_address="HCM",
            items_text="Băng",
            total_amount=300000,
            status=OrderStatus.CHO_LAM,
            created_at=datetime(2026, 10, 25, 9, 0),
        ),
    ]
    card = render_status_order_list_card(orders, OrderStatus.CHO_LAM, 1, 2, 12)
    assert "⏳ Chờ làm — <b>DANH SÁCH ĐƠN</b>" in card
    assert "Tổng cộng: <b>12 đơn</b> (Trang 1/2)" in card
    assert card.count("📅") == 2
    assert "📅 <b>26/10/2026</b> · 2 đơn" in card
    assert "📅 <b>25/10/2026</b> · 1 đơn" in card
    assert "#1" in card and "Khách A" in card and "100.000 đ" in card
    assert "#3" in card and "Khách C" in card and "300.000 đ" in card
    assert "TẦN SUẤT:</b> <b>KHÁCH MUA 1 LẦN</b>" in card
    assert "CHI TIÊU:</b> <b>1–DƯỚI 3 TRIỆU</b>" in card
    assert card.count("TẦN SUẤT:") == 1

    empty = render_status_order_list_card([], OrderStatus.DANG_LAM, 1, 1, 0)
    assert "Chưa có đơn nào ở trạng thái này bác nhé!" in empty


def test_build_status_order_list_keyboard_callbacks_and_chips():
    """Status list keyboard has detail/paging/chip callbacks, all <= 64 bytes."""
    orders = [
        Order(
            id=42,
            customer_name="Khách Dài Tên Rất Dài Để Bị Cắt Bớt",
            customer_phone="0901",
            shipping_address="HCM",
            items_text="Băng",
            total_amount=100000,
            status=OrderStatus.DANG_LAM,
        )
    ]
    kb = build_status_order_list_keyboard(orders, OrderStatus.DANG_LAM, page=2, total_pages=3)
    flat = [btn for row in kb.inline_keyboard for btn in row]
    callbacks = [btn.callback_data for btn in flat]

    assert "ord_vls:DANG_LAM:42:2" in callbacks
    assert "ord_ls:DANG_LAM:1" in callbacks
    assert "ord_ls:DANG_LAM:3" in callbacks
    assert "ord_ls:CHO_LAM:1" in callbacks
    assert "ord_ls:DANG_LAM:2" in callbacks  # active chip keeps page
    assert "ord_ls:DA_DONG_GOI:1" in callbacks
    assert "ord_noop" in callbacks

    for cb in callbacks:
        assert len(cb.encode("utf-8")) <= 64

    empty_kb = build_status_order_list_keyboard([], OrderStatus.CHO_LAM, page=1, total_pages=1)
    empty_cbs = [btn.callback_data for row in empty_kb.inline_keyboard for btn in row]
    assert "ord_ls:CHO_LAM:1" in empty_cbs
    assert "ord_act:new" in empty_cbs


def test_build_order_list_keyboard_has_filter_chips():
    """Both date-list branches (populated + empty) expose the 3 status chips."""
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
    populated = build_order_list_keyboard(orders, "2026-10-24", page=1, total_pages=1)
    populated_cbs = [btn.callback_data for row in populated.inline_keyboard for btn in row]
    assert "ord_ls:CHO_LAM:1" in populated_cbs
    assert "ord_ls:DANG_LAM:1" in populated_cbs
    assert "ord_ls:DA_DONG_GOI:1" in populated_cbs

    empty = build_order_list_keyboard([], "2026-10-24", page=1, total_pages=1)
    empty_cbs = [btn.callback_data for row in empty.inline_keyboard for btn in row]
    assert "ord_ls:CHO_LAM:1" in empty_cbs
    assert "ord_ls:DANG_LAM:1" in empty_cbs
    assert "ord_ls:DA_DONG_GOI:1" in empty_cbs


def test_app_registers_pending_orders_wiring():
    """Source-level guard: app.py must wire the button text and both callbacks."""
    from pathlib import Path

    source = Path("src/bot/app.py").read_text(encoding="utf-8")
    assert "⏳ Đơn chờ làm" in source
    assert "ord_(dt|pg|v|bk|ls|vls):" in source


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


@pytest.mark.asyncio
async def test_start_command_sends_reply_keyboard():
    """start_command attaches 3x2 persistent ReplyKeyboardMarkup (D-01, UI-01, UI-02)."""
    user = User(id=12345, first_name="Bác Ba", is_bot=False)
    chat = Chat(id=12345, type="private")
    message = MagicMock(spec=Message)
    message.reply_text = AsyncMock()

    update = MagicMock(spec=Update)
    update.effective_user = user
    update.effective_chat = chat
    update.effective_message = message

    context = MagicMock(spec=ContextTypes.DEFAULT_TYPE)

    await start_command(update, context)

    message.reply_text.assert_awaited_once()
    args, kwargs = message.reply_text.call_args
    sent_text = args[0]
    markup = kwargs.get("reply_markup")

    assert "Xin chào Bác Ba!" in sent_text
    assert "Bác chỉ cần bấm các nút to bên dưới" in sent_text
    assert isinstance(markup, ReplyKeyboardMarkup)
    assert markup.resize_keyboard is True
    assert markup.is_persistent is True
    assert len(markup.keyboard) == 3
    rows = [[btn.text for btn in row] for row in markup.keyboard]
    assert rows[0] == ["📦 Đơn hôm nay", "⏳ Đơn chờ làm"]
    assert rows[1] == ["📋 Xem theo ngày", "📝 Nhập đơn mới"]
    assert rows[2] == ["🔍 Tra cứu đơn", "❓ Trợ giúp"]


@pytest.mark.asyncio
async def test_handle_menu_reply_today_orders(test_db):
    """Clicking '📦 Đơn hôm nay' returns order list for today in Vietnam timezone."""
    from src.db.orders import create_order

    order = Order(
        customer_name="Khách Hôm Nay",
        customer_phone="0911223344",
        shipping_address="Hà Nội",
        items_text="Băng Nhạc Trẻ",
        total_amount=180000,
        cod_amount=180000,
    )
    order_id = await create_order(test_db, order)

    user = User(id=123, first_name="Bác Năm", is_bot=False)
    message = MagicMock(spec=Message)
    message.text = "📦 Đơn hôm nay"
    message.reply_text = AsyncMock()

    update = MagicMock(spec=Update)
    update.effective_user = user
    update.message = message

    context = MagicMock(spec=ContextTypes.DEFAULT_TYPE)
    context.application.bot_data = {"db": test_db}

    await handle_menu_reply(update, context)

    message.reply_text.assert_awaited_once()
    _, kwargs = message.reply_text.call_args
    card_text = kwargs.get("text", "")
    markup = kwargs.get("reply_markup")

    assert "ĐƠN HÀNG NGÀY" in card_text
    assert f"Đơn #{order_id}" in card_text
    assert "Khách Hôm Nay" in card_text
    assert isinstance(markup, InlineKeyboardMarkup)


@pytest.mark.asyncio
async def test_handle_menu_reply_pending_orders(test_db):
    """'⏳ Đơn chờ làm' renders paginated CHO_LAM list with status chips."""
    from src.db.orders import create_order

    for i in range(12):
        await create_order(
            test_db,
            Order(
                customer_name=f"Khách Chờ {i}",
                customer_phone=f"0900000{i:03d}",
                shipping_address="HCM",
                items_text="Băng",
                total_amount=100000,
                status=OrderStatus.CHO_LAM,
            ),
        )
    await create_order(
        test_db,
        Order(
            customer_name="Khách Đang Làm",
            customer_phone="0911111111",
            shipping_address="HN",
            items_text="Băng",
            total_amount=200000,
            status=OrderStatus.DANG_LAM,
        ),
    )

    message = MagicMock(spec=Message)
    message.text = "⏳ Đơn chờ làm"
    message.reply_text = AsyncMock()
    update = MagicMock(spec=Update)
    update.message = message
    context = MagicMock(spec=ContextTypes.DEFAULT_TYPE)
    context.application.bot_data = {"db": test_db}

    await handle_menu_reply(update, context)

    message.reply_text.assert_awaited_once()
    _, kwargs = message.reply_text.call_args
    card_text = kwargs.get("text", "")
    markup = kwargs.get("reply_markup")

    assert "⏳ Chờ làm — <b>DANH SÁCH ĐƠN</b>" in card_text
    assert "Tổng cộng: <b>12 đơn</b> (Trang 1/2)" in card_text
    assert "Khách Đang Làm" not in card_text
    flat_cbs = [btn.callback_data for row in markup.inline_keyboard for btn in row]
    assert "ord_ls:CHO_LAM:2" in flat_cbs
    assert any(cb.startswith("ord_vls:CHO_LAM:") for cb in flat_cbs)


@pytest.mark.asyncio
async def test_handle_order_nav_callback_status_list(test_db):
    """ord_ls: swaps status/page; ord_vls: opens detail with back to the status list; bad status ignored."""
    from src.db.orders import create_order

    oid = await create_order(
        test_db,
        Order(
            customer_name="Khách Đang Làm",
            customer_phone="0911111111",
            shipping_address="HN",
            items_text="Băng",
            total_amount=200000,
            status=OrderStatus.DANG_LAM,
        ),
    )

    query = MagicMock()
    query.answer = AsyncMock()
    query.edit_message_text = AsyncMock()
    update = MagicMock(spec=Update)
    update.callback_query = query
    context = MagicMock(spec=ContextTypes.DEFAULT_TYPE)
    context.application.bot_data = {"db": test_db}

    query.data = "ord_ls:DANG_LAM:1"
    await handle_order_nav_callback(update, context)
    ls_text = query.edit_message_text.call_args[1]["text"]
    ls_kb = query.edit_message_text.call_args[1]["reply_markup"]
    assert "🛠️ Đang làm — <b>DANH SÁCH ĐƠN</b>" in ls_text
    assert "Khách Đang Làm" in ls_text
    ls_cbs = [btn.callback_data for row in ls_kb.inline_keyboard for btn in row]
    assert f"ord_vls:DANG_LAM:{oid}:1" in ls_cbs

    query.edit_message_text.reset_mock()
    query.data = f"ord_vls:DANG_LAM:{oid}:1"
    await handle_order_nav_callback(update, context)
    detail_text = query.edit_message_text.call_args[1]["text"]
    detail_kb = query.edit_message_text.call_args[1]["reply_markup"]
    assert f"CHI TIẾT ĐƠN HÀNG #{oid}" in detail_text
    detail_cbs = [btn.callback_data for row in detail_kb.inline_keyboard for btn in row]
    assert "ord_ls:DANG_LAM:1" in detail_cbs

    # Garbage status must not raise and must not edit the message
    query.edit_message_text.reset_mock()
    query.data = "ord_ls:XXX:1"
    await handle_order_nav_callback(update, context)
    query.edit_message_text.assert_not_awaited()


@pytest.mark.asyncio
async def test_handle_menu_reply_other_buttons():
    """Clicking date picker, new order, or help returns appropriate responses."""
    user = User(id=123, first_name="Bác Năm", is_bot=False)
    message = MagicMock(spec=Message)
    message.reply_text = AsyncMock()
    update = MagicMock(spec=Update)
    update.effective_user = user
    update.message = message
    context = MagicMock(spec=ContextTypes.DEFAULT_TYPE)
    context.application.bot_data = {}

    # 1. 📋 Xem theo ngày
    message.text = "📋 Xem theo ngày"
    await handle_menu_reply(update, context)
    _, kwargs = message.reply_text.call_args
    assert "CHỌN NGÀY XEM ĐƠN HÀNG" in kwargs.get("text", "")
    assert isinstance(kwargs.get("reply_markup"), InlineKeyboardMarkup)

    # 2. 📝 Nhập đơn mới
    message.reply_text.reset_mock()
    message.text = "📝 Nhập đơn mới"
    await handle_menu_reply(update, context)
    args, kwargs = message.reply_text.call_args
    text_val = args[0] if args else kwargs.get("text", "")
    assert "NHẬP ĐƠN HÀNG MỚI" in text_val

    # 3. ❓ Trợ giúp
    message.reply_text.reset_mock()
    message.text = "❓ Trợ giúp"
    await handle_menu_reply(update, context)
    args, kwargs = message.reply_text.call_args
    text_val = args[0] if args else kwargs.get("text", "")
    assert "HƯỚNG DẪN SỬ DỤNG BOT" in text_val


@pytest.mark.asyncio
async def test_handle_order_nav_callback_flow(test_db):
    """Test date selection, pagination, detail card view, and back navigation."""
    from datetime import datetime

    from src.bot.keyboards import TZ_VN
    from src.db.orders import create_order

    today_str = datetime.now(TZ_VN).strftime("%Y-%m-%d")

    # Seed 6 orders for pagination test
    order_ids = []
    for i in range(1, 7):
        oid = await create_order(
            test_db,
            Order(
                customer_name=f"Khách {i}",
                customer_phone=f"090000000{i}",
                shipping_address=f"Địa chỉ {i}",
                items_text=f"Băng {i}",
                total_amount=100000 * i,
                cod_amount=100000 * i,
            ),
        )
        order_ids.append(oid)

    query = MagicMock()
    query.answer = AsyncMock()
    query.edit_message_text = AsyncMock()

    update = MagicMock(spec=Update)
    update.callback_query = query
    context = MagicMock(spec=ContextTypes.DEFAULT_TYPE)
    context.application.bot_data = {"db": test_db}

    # 1. Date selection callback ord_dt:YYYY-MM-DD
    query.data = f"ord_dt:{today_str}"
    await handle_order_nav_callback(update, context)
    query.answer.assert_awaited_once()
    query.edit_message_text.assert_awaited_once()
    dt_text = query.edit_message_text.call_args[1]["text"]
    assert "Trang 1/2" in dt_text

    # 2. Pagination callback ord_pg:YYYY-MM-DD:2
    query.answer.reset_mock()
    query.edit_message_text.reset_mock()
    query.data = f"ord_pg:{today_str}:2"
    await handle_order_nav_callback(update, context)
    pg_text = query.edit_message_text.call_args[1]["text"]
    assert "Trang 2/2" in pg_text

    # 3. View detail card ord_v:ID:DATE:PAGE
    first_oid = order_ids[-1]  # Most recent order is first
    query.answer.reset_mock()
    query.edit_message_text.reset_mock()
    query.data = f"ord_v:{first_oid}:{today_str}:1"
    await handle_order_nav_callback(update, context)
    v_text = query.edit_message_text.call_args[1]["text"]
    v_kb = query.edit_message_text.call_args[1]["reply_markup"]
    assert f"CHI TIẾT ĐƠN HÀNG #{first_oid}" in v_text
    assert any(btn.copy_text is not None for row in v_kb.inline_keyboard for btn in row)

    # 4. Back navigation callback ord_bk:DATE:PAGE
    query.answer.reset_mock()
    query.edit_message_text.reset_mock()
    query.data = f"ord_bk:{today_str}:1"
    await handle_order_nav_callback(update, context)
    bk_text = query.edit_message_text.call_args[1]["text"]
    assert "Trang 1/2" in bk_text


@pytest.mark.asyncio
async def test_order_status_normal_transition(test_db):
    """Normal status change updates DB immediately, shows toast alert, and refreshes card."""
    from src.db.orders import create_order, get_order_by_id

    order = Order(
        customer_name="Trần Thị Bình",
        customer_phone="0987654321",
        shipping_address="Đà Nẵng",
        items_text="Băng Hương Lan",
        total_amount=220000,
        cod_amount=220000,
        status=OrderStatus.CHO_LAM,
    )
    oid = await create_order(test_db, order)

    query = MagicMock()
    query.answer = AsyncMock()
    query.edit_message_text = AsyncMock()
    query.data = f"ord_st:{oid}:DANG_LAM"

    update = MagicMock(spec=Update)
    update.callback_query = query
    context = MagicMock(spec=ContextTypes.DEFAULT_TYPE)
    context.application.bot_data = {"db": test_db}

    await handle_order_status_callback(update, context)

    # Toast alert called
    query.answer.assert_awaited_once()
    assert "Đã chuyển sang: 🛠️ Đang làm" in query.answer.call_args[1]["text"]
    assert query.answer.call_args[1]["show_alert"] is False

    # DB verified
    db_order = await get_order_by_id(test_db, oid)
    assert db_order.status == OrderStatus.DANG_LAM

    # Message refreshed
    query.edit_message_text.assert_awaited_once()
    assert "🛠️ Đang làm" in query.edit_message_text.call_args[1]["text"]


@pytest.mark.asyncio
async def test_order_status_sensitive_requires_confirmation(test_db):
    """Sensitive status (BOM_HANG, HUY_DON) requires 2-step confirmation modal before DB write."""
    from src.db.orders import create_order, get_order_by_id

    order = Order(
        customer_name="Khách Bom",
        customer_phone="0911000999",
        shipping_address="Hải Phòng",
        items_text="Băng Giao Linh",
        total_amount=150000,
        cod_amount=150000,
        status=OrderStatus.CHO_LAM,
    )
    oid = await create_order(test_db, order)

    query = MagicMock()
    query.answer = AsyncMock()
    query.edit_message_text = AsyncMock()
    query.data = f"ord_st:{oid}:BOM_HANG"

    update = MagicMock(spec=Update)
    update.callback_query = query
    context = MagicMock(spec=ContextTypes.DEFAULT_TYPE)
    context.application.bot_data = {"db": test_db}

    await handle_order_status_callback(update, context)

    # Step 1: Must NOT update DB yet
    db_order = await get_order_by_id(test_db, oid)
    assert db_order.status == OrderStatus.CHO_LAM

    # Step 1: Confirmation modal rendered
    query.edit_message_text.assert_awaited_once()
    modal_text = query.edit_message_text.call_args[1]["text"]
    modal_kb = query.edit_message_text.call_args[1]["reply_markup"]
    assert "XÁC NHẬN CHUYỂN TRẠNG THÁI" in modal_text
    flat_cbs = [btn.callback_data for row in modal_kb.inline_keyboard for btn in row]
    assert f"ord_st_cf:{oid}:BOM_HANG" in flat_cbs
    assert f"ord_v_cur:{oid}" in flat_cbs

    # Step 2: Confirming via ord_st_cf updates DB
    query.answer.reset_mock()
    query.edit_message_text.reset_mock()
    query.data = f"ord_st_cf:{oid}:BOM_HANG"

    await handle_order_status_callback(update, context)

    # Toast alert called
    query.answer.assert_awaited_once()
    assert "Đã chuyển sang: 🚫 Bom hàng" in query.answer.call_args[1]["text"]

    # DB verified updated
    updated_order = await get_order_by_id(test_db, oid)
    assert updated_order.status == OrderStatus.BOM_HANG

    # Message refreshed with updated card
    query.edit_message_text.assert_awaited_once()
    assert "🚫 Bom hàng" in query.edit_message_text.call_args[1]["text"]


@pytest.mark.asyncio
async def test_static_edit_menu_and_flow(test_db):
    """Test static order edit menu and field update flow (Task 1)."""
    from src.bot.handlers.order_actions import (
        handle_action_state_text,
        handle_order_action_callback,
    )
    from src.bot.keyboards import build_order_detail_keyboard, build_order_edit_menu_keyboard
    from src.db.orders import create_order, get_order_by_id

    order = Order(
        customer_name="Chị Hà",
        customer_phone="0912345678",
        shipping_address="12 Quang Trung, P.10, Gò Vấp",
        items_text="2 cuốn Tuấn Vũ",
        total_amount=300000,
        cod_amount=300000,
        status=OrderStatus.CHO_LAM,
    )
    oid = await create_order(test_db, order)
    saved_order = await get_order_by_id(test_db, oid)

    # 1. Check edit button exists on detail keyboard
    detail_kb = build_order_detail_keyboard(saved_order, "2026-10-27", 1)
    flat_detail = [btn.callback_data for row in detail_kb.inline_keyboard for btn in row]
    assert f"ord_act:edit_menu:{oid}" in flat_detail

    # 2. Check edit menu keyboard has all required fields
    menu_kb = build_order_edit_menu_keyboard(oid)
    flat_menu = [btn.callback_data for row in menu_kb.inline_keyboard for btn in row]
    assert f"ord_act:edit_fld:{oid}:customer_name" in flat_menu
    assert f"ord_act:edit_fld:{oid}:customer_phone" in flat_menu
    assert f"ord_act:edit_fld:{oid}:shipping_address" in flat_menu
    assert f"ord_act:edit_fld:{oid}:total_amount" in flat_menu
    assert f"ord_act:edit_fld:{oid}:cod_amount" in flat_menu
    assert f"ord_act:edit_fld:{oid}:items_text" in flat_menu
    assert f"ord_act:edit_fld:{oid}:notes" in flat_menu
    assert f"ord_v_cur:{oid}" in flat_menu

    # 3. Simulate clicking edit_menu
    query = MagicMock()
    query.answer = AsyncMock()
    query.edit_message_text = AsyncMock()
    query.data = f"ord_act:edit_menu:{oid}"
    update = MagicMock(spec=Update)
    update.callback_query = query
    context = MagicMock(spec=ContextTypes.DEFAULT_TYPE)
    context.user_data = {}
    context.application.bot_data = {"db": test_db}

    await handle_order_action_callback(update, context)
    query.edit_message_text.assert_awaited_once()
    assert "SỬA THÔNG TIN ĐƠN HÀNG" in query.edit_message_text.call_args[1]["text"]

    # 4. Simulate clicking edit_fld for shipping_address
    query.edit_message_text.reset_mock()
    query.data = f"ord_act:edit_fld:{oid}:shipping_address"
    await handle_order_action_callback(update, context)
    query.edit_message_text.assert_awaited_once()
    assert "SỬA ĐỊA CHỈ NHẬN HÀNG" in query.edit_message_text.call_args[1]["text"]
    assert context.user_data.get("action_state", {}).get("action") == "await_edit_field"
    assert context.user_data.get("action_state", {}).get("field") == "shipping_address"

    # 5. Simulate user typing new shipping address
    msg_update = MagicMock(spec=Update)
    msg_update.message = MagicMock(spec=Message)
    msg_update.message.text = "12 Điện Biên, P.10, Gò Vấp"
    msg_update.message.reply_text = AsyncMock()
    msg_update.effective_user = MagicMock(id=999, full_name="Admin")

    handled = await handle_action_state_text(msg_update, context, context.user_data["action_state"])
    assert handled is True
    assert "action_state" not in context.user_data
    msg_update.message.reply_text.assert_awaited_once()
    reply_text = msg_update.message.reply_text.call_args[0][0]
    assert "ĐÃ CẬP NHẬT THÀNH CÔNG" in reply_text
    assert "12 Điện Biên, P.10, Gò Vấp" in reply_text

    # Verify DB order actually updated
    fresh = await get_order_by_id(test_db, oid)
    assert fresh.shipping_address == "12 Điện Biên, P.10, Gò Vấp"


@pytest.mark.asyncio
async def test_static_edit_validation_errors(test_db):
    """Test validation prevents bad input on static field editing."""
    import time

    from src.bot.handlers.order_actions import handle_action_state_text
    from src.db.orders import create_order, get_order_by_id

    order = Order(
        customer_name="Test Val",
        customer_phone="0912345678",
        shipping_address="Hà Nội",
        items_text="1 cuốn",
        total_amount=100000,
    )
    oid = await create_order(test_db, order)

    context = MagicMock(spec=ContextTypes.DEFAULT_TYPE)
    context.user_data = {
        "action_state": {
            "action": "await_edit_field",
            "order_id": oid,
            "field": "total_amount",
            "expires_at": time.time() + 180,
        }
    }
    context.application.bot_data = {"db": test_db}

    # Invalid amount input
    msg_update = MagicMock(spec=Update)
    msg_update.message = MagicMock(spec=Message)
    msg_update.message.text = "không phải tiền"
    msg_update.message.reply_text = AsyncMock()

    handled = await handle_action_state_text(msg_update, context, context.user_data["action_state"])
    assert handled is True
    # action_state remains so user can retry
    assert "action_state" in context.user_data
    err_reply = msg_update.message.reply_text.call_args[0][0]
    assert "Số tiền không hợp lệ" in err_reply

    # DB not changed
    fresh = await get_order_by_id(test_db, oid)
    assert fresh.total_amount == 100000


@pytest.mark.asyncio
async def test_order_status_bad_request_ignored(test_db):
    """BadRequest with 'Message is not modified' is caught safely without raising."""
    from telegram.error import BadRequest

    from src.db.orders import create_order

    order = Order(
        customer_name="Khách Test Safe",
        customer_phone="0933445566",
        shipping_address="Cần Thơ",
        items_text="Băng",
        total_amount=100000,
        cod_amount=100000,
        status=OrderStatus.CHO_LAM,
    )
    oid = await create_order(test_db, order)

    query = MagicMock()
    query.answer = AsyncMock()
    query.edit_message_text = AsyncMock(
        side_effect=BadRequest(
            "Message is not modified: specified new message content and reply markup are exactly the same as a current content and reply markup of the message"
        )
    )
    query.data = f"ord_st:{oid}:DANG_LAM"

    update = MagicMock(spec=Update)
    update.callback_query = query
    context = MagicMock(spec=ContextTypes.DEFAULT_TYPE)
    context.application.bot_data = {"db": test_db}

    # Should not raise exception
    await handle_order_status_callback(update, context)
    query.answer.assert_awaited_once()


@pytest.mark.asyncio
async def test_order_action_track_state_and_cancel():
    """ord_act:track sets action_state with 120s TTL; ord_act:cancel clears it."""
    import time

    query = MagicMock()
    query.answer = AsyncMock()
    query.edit_message_text = AsyncMock()
    query.data = "ord_act:track:88"

    update = MagicMock(spec=Update)
    update.callback_query = query
    context = MagicMock(spec=ContextTypes.DEFAULT_TYPE)
    context.user_data = {}

    await handle_order_action_callback(update, context)

    # State set
    state = context.user_data.get("action_state")
    assert state is not None
    assert state["action"] == "await_tracking"
    assert state["order_id"] == 88
    assert state["expires_at"] > time.time() + 100

    query.edit_message_text.assert_awaited_once()
    assert "NHẬP MÃ VẬN ĐƠN CHO ĐƠN #88" in query.edit_message_text.call_args[1]["text"]

    # Cancel action
    query.answer.reset_mock()
    query.edit_message_text.reset_mock()
    query.data = "ord_act:cancel"

    await handle_order_action_callback(update, context)

    assert "action_state" not in context.user_data
    query.edit_message_text.assert_awaited_once()
    assert "ĐÃ HUỶ THAO TÁC" in query.edit_message_text.call_args[0][0]


@pytest.mark.asyncio
async def test_handle_action_state_text_tracking_updates_db(test_db):
    """Sending text while in await_tracking updates DB tracking_code and clears state."""
    import time

    from src.db.orders import create_order, get_order_by_id

    oid = await create_order(
        test_db,
        Order(
            customer_name="Anh Nam",
            customer_phone="0911223344",
            shipping_address="Hà Nội",
            items_text="Băng",
            total_amount=120000,
        ),
    )

    message = MagicMock(spec=Message)
    message.text = "  VNP123456789VN  "
    message.reply_text = AsyncMock()

    update = MagicMock(spec=Update)
    update.message = message

    context = MagicMock(spec=ContextTypes.DEFAULT_TYPE)
    context.application.bot_data = {"db": test_db}
    state = {
        "action": "await_tracking",
        "order_id": oid,
        "expires_at": time.time() + 120,
    }
    context.user_data = {"action_state": state}

    handled = await handle_action_state_text(update, context, state)
    assert handled is True
    assert "action_state" not in context.user_data

    # DB verified
    db_order = await get_order_by_id(test_db, oid)
    assert db_order.tracking_code == "VNP123456789VN"

    message.reply_text.assert_awaited_once()
    assert "ĐÃ CẬP NHẬT MÃ VẬN ĐƠN" in message.reply_text.call_args[1]["text"]


@pytest.mark.asyncio
async def test_handle_text_order_bypasses_llm_when_action_state_active(test_db):
    """handle_text_order intercepts text when action_state is active without calling LLM."""
    import time

    from src.bot.handlers.ingest import handle_text_order
    from src.db.orders import create_order, get_order_by_id

    oid = await create_order(
        test_db,
        Order(
            customer_name="Chị Mai",
            customer_phone="0988776655",
            shipping_address="HCM",
            items_text="Băng",
            total_amount=150000,
        ),
    )

    message = MagicMock(spec=Message)
    message.text = "GHN_TRACK_9988"
    message.reply_text = AsyncMock()

    update = MagicMock(spec=Update)
    update.message = message

    context = MagicMock(spec=ContextTypes.DEFAULT_TYPE)
    context.application.bot_data = {"db": test_db}
    context.user_data = {
        "action_state": {
            "action": "await_tracking",
            "order_id": oid,
            "expires_at": time.time() + 120,
        }
    }

    await handle_text_order(update, context)

    # State cleared
    assert "action_state" not in context.user_data
    # Tracking updated
    db_order = await get_order_by_id(test_db, oid)
    assert db_order.tracking_code == "GHN_TRACK_9988"


@pytest.mark.asyncio
async def test_handle_order_action_view_photos(test_db):
    """view_photo calls send_photo for 1 image and send_media_group for >= 2 images."""
    from src.db.orders import create_order

    # Order 1: 1 photo
    oid1 = await create_order(
        test_db,
        Order(
            customer_name="Bác Một Ảnh",
            customer_phone="0911",
            shipping_address="HN",
            items_text="Băng",
            total_amount=100000,
            photo_file_ids=["file_one"],
        ),
    )

    # Order 2: 3 photos
    oid2 = await create_order(
        test_db,
        Order(
            customer_name="Bác Ba Ảnh",
            customer_phone="0922",
            shipping_address="HCM",
            items_text="Băng",
            total_amount=200000,
            photo_file_ids=["file_1", "file_2", "file_3"],
        ),
    )

    query = MagicMock()
    query.answer = AsyncMock()
    query.message.chat_id = 999
    update = MagicMock(spec=Update)
    update.callback_query = query
    update.effective_chat.id = 999

    context = MagicMock(spec=ContextTypes.DEFAULT_TYPE)
    context.application.bot_data = {"db": test_db}
    context.bot.send_photo = AsyncMock()
    context.bot.send_media_group = AsyncMock()

    # 1 photo test
    query.data = f"ord_act:view_photo:{oid1}"
    await handle_order_action_callback(update, context)
    context.bot.send_photo.assert_awaited_once()
    assert context.bot.send_photo.call_args[1]["photo"] == "file_one"

    # >= 2 photos test
    query.data = f"ord_act:view_photo:{oid2}"
    await handle_order_action_callback(update, context)
    context.bot.send_media_group.assert_awaited_once()
    media_arg = context.bot.send_media_group.call_args[1]["media"]
    assert len(media_arg) == 3


@pytest.mark.asyncio
async def test_handle_action_state_photo_appends_photos(test_db):
    """Sending photo while in await_photo appends photo file_id to order in DB."""
    import time

    from telegram import PhotoSize

    from src.db.orders import create_order, get_order_by_id

    oid = await create_order(
        test_db,
        Order(
            customer_name="Anh Thêm Ảnh",
            customer_phone="0933",
            shipping_address="Đà Nẵng",
            items_text="Băng",
            total_amount=100000,
            photo_file_ids=["photo_old"],
        ),
    )

    photo_small = MagicMock(spec=PhotoSize, file_id="thumb_id")
    photo_large = MagicMock(spec=PhotoSize, file_id="high_res_id")

    message = MagicMock(spec=Message)
    message.photo = [photo_small, photo_large]
    message.reply_text = AsyncMock()

    update = MagicMock(spec=Update)
    update.message = message

    context = MagicMock(spec=ContextTypes.DEFAULT_TYPE)
    context.application.bot_data = {"db": test_db}
    state = {
        "action": "await_photo",
        "order_id": oid,
        "expires_at": time.time() + 120,
    }

    handled = await handle_action_state_photo(update, context, state)
    assert handled is True

    db_order = await get_order_by_id(test_db, oid)
    assert db_order.photo_file_ids == ["photo_old", "high_res_id"]
    message.reply_text.assert_awaited_once()
    assert "ĐÃ THÊM ẢNH THÀNH CÔNG" in message.reply_text.call_args[1]["text"]


def test_render_order_detail_card_shows_tape_breakdown():
    """Detail card shows PHÔI BĂNG with count and breakdown."""
    from src.models.order import TapeItem

    order = Order(
        id=20,
        customer_name="Bác Phôi",
        customer_phone="0912345678",
        shipping_address="Hà Nội",
        items_text="6 sony 90p",
        tape_quantity=6,
        tapes=[TapeItem(label="sony 90p", qty=6)],
        tape_artists=["Chế Linh", "Thanh Tuyền"],
    )
    card = render_order_detail_card(order)
    assert "PHÔI BĂNG:" in card
    assert "6 cuốn" in card
    assert "sony 90p" in card
    assert "CA SĨ:" in card
    assert "Chế Linh, Thanh Tuyền" in card


def test_render_order_detail_card_legacy_null_shows_dash():
    """Legacy row (NULL tape_quantity) shows em dash, never 0."""
    order = Order(
        id=21,
        customer_name="Bác Cũ",
        customer_phone="0900111222",
        shipping_address="Đà Nẵng",
        items_text="3 băng maxell 90p",
    )
    card = render_order_detail_card(order)
    assert "PHÔI BĂNG:" in card
    assert "PHÔI BĂNG:</b> —" in card
    assert "CA SĨ:</b> —" in card
    assert "PHÔI BĂNG:</b> 0" not in card
