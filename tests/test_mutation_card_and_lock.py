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


@pytest.mark.asyncio
async def test_mutate_order_with_lock_success():
    """Verify mutate_order_with_lock updates fields and records audit history."""
    from src.db.connection import get_db_connection
    from src.db.orders import create_order, get_order_by_id, mutate_order_with_lock
    from src.db.schema import init_db

    async with get_db_connection(":memory:") as db:
        await init_db(db)

        order = Order(
            customer_name="Nguyễn Văn A",
            customer_phone="0912345678",
            shipping_address="123 Lê Lợi, Q1",
            items_text="1 cuốn",
            total_amount=150000,
            cod_amount=150000,
            status=OrderStatus.CHO_LAM,
        )
        order_id = await create_order(db, order)
        original_order = await get_order_by_id(db, order_id)
        assert original_order is not None

        delta = {
            "shipping_address": "456 Nguyễn Huệ, Q1",
            "cod_amount": 200000,
            "status": OrderStatus.DANG_LAM,
            "new_notes": "Giao sau 18h tối",
        }

        success, changes, updated_order = await mutate_order_with_lock(
            db,
            order_id=order_id,
            expected_updated_at=original_order.updated_at,
            delta_dict=delta,
            user_id=999,
            user_name="Nhân viên Quân",
        )

        assert success is True
        assert changes is not None
        assert "shipping_address" in changes
        assert changes["shipping_address"]["old"] == "123 Lê Lợi, Q1"
        assert changes["shipping_address"]["new"] == "456 Nguyễn Huệ, Q1"
        assert changes["cod_amount"]["new"] == 200000
        assert changes["status"]["new"] == "DANG_LAM"
        assert changes["notes"]["new"] == "Giao sau 18h tối"

        assert updated_order is not None
        assert updated_order.shipping_address == "456 Nguyễn Huệ, Q1"
        assert updated_order.cod_amount == 200000
        assert updated_order.status == OrderStatus.DANG_LAM
        assert updated_order.notes == "Giao sau 18h tối"

        # Verify audit history row inserted
        async with db.execute(
            "SELECT * FROM order_history WHERE order_id = ? AND action = 'MUTATE'",
            (order_id,),
        ) as cursor:
            hist_rows = await cursor.fetchall()
            assert len(hist_rows) == 1
            assert hist_rows[0]["user_name"] == "Nhân viên Quân"
            assert "456 Nguyễn Huệ" in hist_rows[0]["changes_json"]


@pytest.mark.asyncio
async def test_mutate_order_with_lock_conflict():
    """Verify mutate_order_with_lock detects concurrent conflict and returns last change."""
    from src.db.connection import get_db_connection
    from src.db.orders import create_order, get_order_by_id, mutate_order_with_lock
    from src.db.schema import init_db

    async with get_db_connection(":memory:") as db:
        await init_db(db)

        order = Order(
            customer_name="Khách X",
            customer_phone="0987654321",
            shipping_address="Hà Nội",
            items_text="2 cuốn",
            total_amount=300000,
            cod_amount=300000,
            status=OrderStatus.CHO_LAM,
        )
        order_id = await create_order(db, order)
        original_order = await get_order_by_id(db, order_id)
        assert original_order is not None

        # Simulate first user mutating order
        s1, c1, o1 = await mutate_order_with_lock(
            db,
            order_id=order_id,
            expected_updated_at=original_order.updated_at,
            delta_dict={"shipping_address": "Đà Nẵng"},
            user_id=101,
            user_name="Admin An",
        )
        assert s1 is True

        # Second user tries with stale updated_at
        s2, last_change, current_ord = await mutate_order_with_lock(
            db,
            order_id=order_id,
            expected_updated_at=original_order.updated_at,  # Stale timestamp!
            delta_dict={"shipping_address": "Cần Thơ"},
            user_id=102,
            user_name="Admin Bình",
        )

        assert s2 is False
        assert last_change is not None
        assert last_change.get("user_name") == "Admin An"
        assert current_ord is not None
        assert current_ord.shipping_address == "Đà Nẵng"  # Unchanged by second user


@pytest.mark.asyncio
async def test_mutate_order_with_lock_datetime_string_normalization():
    """Verify mutate_order_with_lock handles datetime object vs string without false conflict."""
    from datetime import datetime
    from src.db.connection import get_db_connection
    from src.db.orders import create_order, get_order_by_id, mutate_order_with_lock
    from src.db.schema import init_db

    async with get_db_connection(":memory:") as db:
        await init_db(db)

        order = Order(
            customer_name="Khách Y",
            customer_phone="0911223344",
            shipping_address="Hải Phòng",
            items_text="1 cuốn",
            total_amount=100000,
            status=OrderStatus.CHO_LAM,
        )
        order_id = await create_order(db, order)
        fetched = await get_order_by_id(db, order_id)
        assert fetched is not None

        # fetched.updated_at may be datetime or str
        # Test passing it as string
        str_val = str(fetched.updated_at)
        s, c, updated = await mutate_order_with_lock(
            db,
            order_id=order_id,
            expected_updated_at=str_val,
            delta_dict={"items_text": "2 cuốn"},
            user_id=1,
            user_name="Admin",
        )
        assert s is True
        assert updated is not None
        assert updated.items_text == "2 cuốn"


@pytest.mark.asyncio
async def test_mutate_order_with_lock_deduplicates_columns():
    """Verify delta_dict with overlapping new_status and status does not generate duplicate SQL columns (WR-01)."""
    from src.db.connection import get_db_connection
    from src.db.orders import create_order, get_order_by_id, mutate_order_with_lock
    from src.db.schema import init_db

    async with get_db_connection(":memory:") as db:
        await init_db(db)

        order = Order(
            customer_name="Khách Z",
            customer_phone="0911223344",
            shipping_address="Hải Phòng",
            items_text="1 cuốn",
            total_amount=100000,
            status=OrderStatus.CHO_LAM,
        )
        order_id = await create_order(db, order)
        fetched = await get_order_by_id(db, order_id)
        assert fetched is not None

        delta = {
            "status": OrderStatus.DANG_LAM,
            "new_status": OrderStatus.DANG_LAM,
        }
        success, changes, updated = await mutate_order_with_lock(
            db,
            order_id=order_id,
            expected_updated_at=fetched.updated_at,
            delta_dict=delta,
            user_id=1,
            user_name="Admin",
        )
        assert success is True
        assert updated is not None
        assert updated.status == OrderStatus.DANG_LAM
        assert "status" in changes



