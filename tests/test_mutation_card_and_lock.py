import html
import pytest
from src.bot.keyboards import (
    DIVIDER,
    render_mutation_diff_card,
    render_order_detail_card,
    render_order_list_card,
)
from src.models.order import Order, OrderStatus


def test_divider_length_is_14():
    """Verify section divider is exactly 14 characters per D-19."""
    assert len(DIVIDER) == 14
    assert DIVIDER == "──────────────"


def test_render_order_list_card_spacing():
    """Verify consecutive orders in render_order_list_card are separated by blank lines per D-19."""
    orders = [
        Order(
            id=1,
            customer_name="Khách A",
            customer_phone="0912345678",
            shipping_address="Hà Nội",
            items_text="1 cuốn Tuấn Vũ",
            total_amount=100000,
            status=OrderStatus.CHO_LAM,
        ),
        Order(
            id=2,
            customer_name="Khách B",
            customer_phone="0987654321",
            shipping_address="Đà Nẵng",
            items_text="2 cuốn Chế Linh",
            total_amount=200000,
            status=OrderStatus.DANG_LAM,
        ),
    ]
    card = render_order_list_card(orders, "2026-10-25", 1, 1, 2)
    # Consecutive orders should be separated by \n\n (empty line)
    assert "📦 <b>Đơn #1</b> - Khách A" in card
    assert "📦 <b>Đơn #2</b> - Khách B" in card
    # Double newline check between end of order 1 block and order 2 header
    assert "\n\n📦 <b>Đơn #2</b>" in card


def test_render_order_detail_card_with_creator():
    """Verify creator attribution (bởi {created_by_name}) rendered if present per D-16."""
    from datetime import datetime, timezone
    order_with_creator = Order(
        id=10,
        customer_name="Bác Ba",
        customer_phone="0901234567",
        shipping_address="Sài Gòn",
        items_text="3 cuốn",
        created_by_name="Quân Admin",
        created_at=datetime(2026, 10, 25, 14, 30, tzinfo=timezone.utc),
    )
    card = render_order_detail_card(order_with_creator)
    assert "(bởi Quân Admin)" in card

    order_without_creator = Order(
        id=11,
        customer_name="Bác Tư",
        customer_phone="0901234568",
        shipping_address="Sài Gòn",
        items_text="1 cuốn",
        created_at=datetime(2026, 10, 25, 14, 30, tzinfo=timezone.utc),
    )
    card_no_creator = render_order_detail_card(order_without_creator)
    assert "(bởi" not in card_no_creator


def test_render_mutation_diff_card_only_changed_fields():
    """Verify diff card renders heading and only fields present in delta per D-11."""
    order = Order(
        id=12,
        customer_name="Nguyễn Văn Nam",
        customer_phone="0912345678",
        shipping_address="123 Lê Lợi, Q1, TP.HCM",
        items_text="2 cuốn Tuấn Vũ",
        total_amount=250000,
        cod_amount=250000,
        status=OrderStatus.CHO_LAM,
        tracking_code=None,
    )

    delta = {
        "shipping_address": "456 Nguyễn Huệ, Q1, TP.HCM",
        "cod_amount": 300000,
        "status": OrderStatus.DANG_LAM,
    }

    card = render_mutation_diff_card(order, delta)
    assert "XÁC NHẬN SỬA ĐƠN HÀNG #12" in card
    assert "Nguyễn Văn Nam" in card
    assert DIVIDER in card
    assert "hết hạn sau 120s" in card

    # Changed fields
    assert "Trạng thái:" in card
    assert "Chờ làm" in card
    assert "➡️" in card
    assert "Đang làm" in card

    assert "Địa chỉ:" in card
    assert "123 Lê Lợi, Q1, TP.HCM" in card
    assert "456 Nguyễn Huệ, Q1, TP.HCM" in card

    assert "Tiền COD:" in card
    assert "250.000 đ" in card
    assert "300.000 đ" in card

    # Unchanged fields should not appear
    assert "SĐT:" not in card
    assert "Băng:" not in card
    assert "Mã vận đơn:" not in card


def test_render_mutation_diff_card_html_escaping():
    """Verify HTML special characters in old/new values are escaped."""
    order = Order(
        id=15,
        customer_name="<script>alert(1)</script>",
        customer_phone="0912345678",
        shipping_address="Hẻm 1/2 <vào sâu>",
        items_text="Băng 1 & 2",
        status=OrderStatus.CHO_LAM,
    )
    delta = {
        "shipping_address": "Hẻm 1/2 <ra ngoài>",
        "notes": "Ghi chú & yêu cầu mới <urgent>",
    }
    card = render_mutation_diff_card(order, delta)
    assert "<script>" not in card
    assert "&lt;script&gt;" in card
    assert "&lt;vào sâu&gt;" in card
    assert "&lt;ra ngoài&gt;" in card
    assert "&lt;urgent&gt;" in card
