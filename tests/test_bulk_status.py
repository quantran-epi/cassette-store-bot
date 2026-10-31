"""Unit and integration tests for bulk order status change and returning customer icon."""

import pytest

from src.bot.keyboards import (
    _format_bulk_button_label,
    _returning_marker,
    build_bulk_pick_keyboard,
    build_bulk_status_keyboard,
    build_main_menu_reply_keyboard,
    format_order_compact_line,
    format_order_item_summary,
    render_bulk_confirm_card,
    render_bulk_done_card,
    render_bulk_intro_card,
    render_bulk_pick_card,
    render_bulk_status_card,
    render_order_detail_card,
)
from src.db.customers import create_customer
from src.db.orders import (
    bulk_update_order_status,
    create_order,
    find_orders_by_tracking_codes,
    get_order_by_id,
    list_orders_by_status,
)
from src.models.customer import Customer
from src.models.order import Order, OrderStatus


def _make_dummy_order(
    oid: int = 1,
    name: str = "Nguyễn Văn Tuấn",
    phone: str = "0912345678",
    status: OrderStatus = OrderStatus.CHO_LAM,
    tracking_code: str | None = None,
    any_count: int | None = None,
) -> Order:
    return Order(
        id=oid,
        customer_id=1,
        customer_name=name,
        customer_phone=phone,
        shipping_address="Hà Nội",
        items_text="Băng Tuấn Vũ 1",
        total_amount=250000,
        cod_amount=250000,
        status=status,
        tracking_code=tracking_code,
        customer_any_order_count=any_count,
    )


# ============================================================================
# 1. RETURNING CUSTOMER ICON TESTS
# ============================================================================


def test_returning_marker_none_or_single_order():
    """Customer with no prior order or only 1 order does not get returning icon."""
    o_none = _make_dummy_order(any_count=None)
    assert _returning_marker(o_none) == ""

    o_one = _make_dummy_order(any_count=1)
    assert _returning_marker(o_one) == ""

    o_zero = _make_dummy_order(any_count=0)
    assert _returning_marker(o_zero) == ""


def test_returning_marker_two_or_more_orders():
    """Customer with 2+ total orders (any status) gets 🔂 icon."""
    o_two = _make_dummy_order(any_count=2)
    assert _returning_marker(o_two) == " 🔂"

    o_many = _make_dummy_order(any_count=10)
    assert _returning_marker(o_many) == " 🔂"


def test_returning_marker_rendered_in_order_detail():
    order = _make_dummy_order(any_count=3)
    card = render_order_detail_card(order)
    assert "👤 <b>KHÁCH:</b> Nguyễn Văn Tuấn 🔂" in card


def test_returning_marker_rendered_in_item_summary():
    order = _make_dummy_order(oid=5, any_count=2)
    summary = format_order_item_summary(order)
    assert "📦 <b>#5 — Nguyễn Văn Tuấn 🔂</b>" in summary


def test_returning_marker_rendered_in_compact_line():
    order = _make_dummy_order(oid=7, any_count=4)
    line = format_order_compact_line(order)
    assert "📦 <b>#7</b> · Nguyễn Văn Tuấn 🔂 · 250.000 đ" in line


@pytest.mark.asyncio
async def test_returning_marker_db_integration(test_db):
    """Customer with multiple non-delivered orders gets any_orders >= 2, displaying icon."""
    cust_id = await create_customer(
        test_db,
        Customer(name="Bác Ba", phones=["0988000111"], addresses=["Sài Gòn"]),
    )
    # 2 pending orders, 0 delivered
    id1 = await create_order(
        test_db,
        Order(
            customer_id=cust_id,
            customer_name="Bác Ba",
            customer_phone="0988000111",
            shipping_address="Sài Gòn",
            items_text="Băng Chế Linh",
            total_amount=150000,
            status=OrderStatus.CHO_LAM,
        ),
    )
    await create_order(
        test_db,
        Order(
            customer_id=cust_id,
            customer_name="Bác Ba",
            customer_phone="0988000111",
            shipping_address="Sài Gòn",
            items_text="Băng Hương Lan",
            total_amount=200000,
            status=OrderStatus.CHO_LAM,
        ),
    )

    o1 = await get_order_by_id(test_db, id1)
    assert o1.customer_any_order_count == 2
    assert o1.customer_completed_orders == 0
    assert _returning_marker(o1) == " 🔂"

    # Batch hydration in list
    by_status = await list_orders_by_status(test_db, OrderStatus.CHO_LAM)
    ba_orders = [o for o in by_status if o.customer_id == cust_id]
    assert len(ba_orders) == 2
    assert all(o.customer_any_order_count == 2 for o in ba_orders)
    assert all(_returning_marker(o) == " 🔂" for o in ba_orders)


# ============================================================================
# 2. MENU KEYBOARD TESTS
# ============================================================================


def test_main_menu_replaces_help_with_bulk_status():
    kb = build_main_menu_reply_keyboard()
    button_texts = [btn.text for row in kb.keyboard for btn in row]
    assert "🔄 Đổi trạng thái" in button_texts
    assert "❓ Trợ giúp" not in button_texts


# ============================================================================
# 3. BULK DB OPERATIONS TESTS
# ============================================================================


@pytest.mark.asyncio
async def test_bulk_update_order_status(test_db):
    cust_id = await create_customer(
        test_db,
        Customer(name="Anh Tư", phones=["0977111222"], addresses=["Cần Thơ"]),
    )
    ids = []
    for i in range(3):
        oid = await create_order(
            test_db,
            Order(
                customer_id=cust_id,
                customer_name="Anh Tư",
                customer_phone="0977111222",
                shipping_address="Cần Thơ",
                items_text=f"Băng {i}",
                total_amount=100000 * (i + 1),
                status=OrderStatus.CHO_LAM,
            ),
        )
        ids.append(oid)

    # Bulk change 2 of the 3 orders to DA_DONG_GOI
    updated = await bulk_update_order_status(
        test_db,
        order_ids=[ids[0], ids[1]],
        new_status=OrderStatus.DA_DONG_GOI,
        user_id=123,
        user_name="Admin",
    )
    assert set(updated) == {ids[0], ids[1]}

    # Verify orders in DB
    o1 = await get_order_by_id(test_db, ids[0])
    o2 = await get_order_by_id(test_db, ids[1])
    o3 = await get_order_by_id(test_db, ids[2])
    assert o1.status == OrderStatus.DA_DONG_GOI
    assert o2.status == OrderStatus.DA_DONG_GOI
    assert o3.status == OrderStatus.CHO_LAM  # Not touched

    # Verify history recorded
    async with test_db.execute(
        "SELECT order_id, action FROM order_history WHERE order_id IN (?, ?)",
        (ids[0], ids[1]),
    ) as cursor:
        rows = await cursor.fetchall()
    change_events = [r for r in rows if r["action"] == "STATUS_CHANGE"]
    assert len(change_events) == 2


@pytest.mark.asyncio
async def test_find_orders_by_tracking_codes(test_db):
    cust_id = await create_customer(
        test_db,
        Customer(name="Khách Ship", phones=["0933333333"], addresses=["Hải Phòng"]),
    )
    id1 = await create_order(
        test_db,
        Order(
            customer_id=cust_id,
            customer_name="Khách Ship",
            customer_phone="0933333333",
            shipping_address="Hải Phòng",
            items_text="Băng 1",
            total_amount=100000,
            status=OrderStatus.SHIPPER_DA_LAY,
            tracking_code="GHN12345",
        ),
    )
    id2 = await create_order(
        test_db,
        Order(
            customer_id=cust_id,
            customer_name="Khách Ship",
            customer_phone="0933333333",
            shipping_address="Hải Phòng",
            items_text="Băng 2",
            total_amount=200000,
            status=OrderStatus.SHIPPER_DA_LAY,
            tracking_code="VN998877",
        ),
    )

    # Mixed case, whitespace
    matched = await find_orders_by_tracking_codes(
        test_db, ["  ghn12345  ", "vn998877", "NONEXISTENT"]
    )
    matched_ids = {o.id for o in matched}
    assert matched_ids == {id1, id2}


# ============================================================================
# 4. BULK UI RENDER & KEYBOARD TESTS
# ============================================================================


def test_bulk_button_label_format():
    o = _make_dummy_order(
        oid=5,
        name="Tuấn",
        phone="0912345678",
        status=OrderStatus.DA_GIAO,
        tracking_code="GHN999",
    )
    # Unchecked
    label_un = _format_bulk_button_label(o, checked=False)
    assert label_un.startswith("☐ #5 Tuấn")
    assert "5678" in label_un
    assert "GHN999" in label_un
    assert "✅" in label_un

    # Checked
    label_ck = _format_bulk_button_label(o, checked=True)
    assert label_ck.startswith("☑ #5 Tuấn")


def test_bulk_pick_keyboard_structure():
    orders = [
        _make_dummy_order(oid=1, name="Tuấn"),
        _make_dummy_order(oid=2, name="Nam"),
    ]
    selected = {1}
    kb = build_bulk_pick_keyboard(orders, selected, page=1, total_pages=1)
    # Row 0: Order 1 (toggle + view)
    assert len(kb.inline_keyboard[0]) == 2
    assert kb.inline_keyboard[0][0].callback_data == "bs:t:1"
    assert kb.inline_keyboard[0][1].callback_data == "bs:v:1"
    # Row 1: Order 2 (toggle + view)
    assert kb.inline_keyboard[1][0].callback_data == "bs:t:2"
    assert kb.inline_keyboard[1][1].callback_data == "bs:v:2"
    # Next button carries selected count
    flattened = [btn for row in kb.inline_keyboard for btn in row]
    next_btn = next(b for b in flattened if b.callback_data == "bs:next")
    assert "1 đơn" in next_btn.text


def test_bulk_status_keyboard_has_all_8_statuses():
    kb = build_bulk_status_keyboard()
    status_cbs = [
        btn.callback_data
        for row in kb.inline_keyboard
        for btn in row
        if btn.callback_data.startswith("bs:st:")
    ]
    assert len(status_cbs) == 8
    for st in OrderStatus:
        assert f"bs:st:{st.value}" in status_cbs


def test_bulk_cards_rendering():
    orders = [_make_dummy_order(oid=1, name="Tuấn"), _make_dummy_order(oid=2, name="Hải")]
    intro = render_bulk_intro_card()
    assert "ĐỔI TRẠNG THÁI HÀNG LOẠT" in intro
    assert "Bước 1/3" in intro

    pick = render_bulk_pick_card(
        orders=orders,
        selected_ids={1},
        page=1,
        total_pages=1,
        total_orders=2,
    )
    assert "Đã chọn: <b>1 đơn</b>" in pick

    st_card = render_bulk_status_card(orders)
    assert "Bước 2/3" in st_card
    assert "#1, #2" in st_card

    cf_card = render_bulk_confirm_card(orders, OrderStatus.DA_GIAO)
    assert "Bước 3/3" in cf_card
    assert "Đã giao thành công" in cf_card
    assert "#1" in cf_card
    assert "#2" in cf_card

    done = render_bulk_done_card(orders, OrderStatus.DA_GIAO)
    assert "ĐÃ ĐỔI XONG 2 ĐƠN" in done
