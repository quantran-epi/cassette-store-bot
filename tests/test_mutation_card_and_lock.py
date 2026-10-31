import pytest

from src.bot.keyboards import (
    DIVIDER,
    render_mutation_diff_card,
    render_mutation_disambiguation_card,
    render_order_detail_card,
    render_order_list_card,
)
from src.models.order import Order, OrderStatus


def test_divider_length_is_16():
    """Verify section divider is exactly 16 characters."""
    assert len(DIVIDER) == 16
    assert DIVIDER == "••••••••••••••••"


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
    assert "📦 <b>#1 — Khách A</b>" in card
    assert "📦 <b>#2 — Khách B</b>" in card
    # Separator check between end of order 1 block and order 2 header
    assert "\n────────\n📦 <b>#2 — Khách B</b>" in card


def test_render_mutation_disambiguation_card():
    """Verify mutation disambiguation list renders full order info separated by empty lines."""
    orders = [
        Order(
            id=12,
            customer_name="Bác Tuấn",
            customer_phone="0912345678",
            shipping_address="123 Lê Duẩn, Hà Nội",
            items_text="Tuấn Vũ 1",
            total_amount=350000,
            status=OrderStatus.CHO_LAM,
        ),
        Order(
            id=15,
            customer_name="Bác Tuấn",
            customer_phone="0988776655",
            shipping_address="Cầu Giấy, Hà Nội",
            items_text="Chế Linh",
            total_amount=500000,
            status=OrderStatus.DA_GIAO,
        ),
    ]
    card = render_mutation_disambiguation_card(orders, keyword="Bác Tuấn")
    assert "CHỌN ĐƠN HÀNG CẦN SỬA" in card
    assert "Bác Tuấn" in card
    assert "#12 — Bác Tuấn" in card
    assert "0912345678" in card
    assert "123 Lê Duẩn, Hà Nội" in card
    assert "350.000 đ" in card
    assert "#15 — Bác Tuấn" in card
    assert "0988776655" in card
    assert "Cầu Giấy, Hà Nội" in card
    assert "500.000 đ" in card
    assert "\n────────\n📦 <b>#15 — Bác Tuấn</b>" in card


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
    assert "hết hạn sau 5 phút" in card

    # Changed fields
    assert "TRẠNG THÁI:" in card or "Trạng thái:" in card
    assert "Chờ làm" in card
    assert "➡️" in card
    assert "Đang làm" in card

    assert "ĐỊA CHỈ:" in card or "Địa chỉ:" in card
    assert "123 Lê Lợi, Q1, TP.HCM" in card
    assert "456 Nguyễn Huệ, Q1, TP.HCM" in card

    assert "TIỀN COD" in card or "Tiền COD:" in card
    assert "250.000 đ" in card
    assert "300.000 đ" in card

    # Unchanged fields should not appear
    assert "SĐT:" not in card
    assert "BĂNG" not in card and "Băng:" not in card
    assert "MÃ VẬN ĐƠN:" not in card and "Mã vận đơn:" not in card


def test_render_mutation_diff_card_tape_quantity_line():
    """When items change, diff shows SỐ BĂNG old ➡️ new."""
    order = Order(
        id=22,
        customer_name="Bác Sửa",
        customer_phone="0912345678",
        shipping_address="Hà Nội",
        items_text="1 cuốn",
        tape_quantity=1,
    )
    card = render_mutation_diff_card(order, {"new_items_text": "6 sony 90p"})
    assert "SỐ BĂNG:" in card
    assert "➡️" in card
    assert "<b>6</b>" in card


def test_render_mutation_diff_card_artist_change():
    """When items change, diff shows CA SĨ old ➡️ new."""
    order = Order(
        id=24,
        customer_name="Bác Ca Sĩ",
        customer_phone="0912345678",
        shipping_address="Hà Nội",
        items_text="1 cuốn Chế Linh",
        tape_quantity=1,
        tape_artists=["Chế Linh"],
    )
    card = render_mutation_diff_card(
        order,
        {"new_items_text": "2 cuốn Thanh Tuyền", "new_tape_artists": ["Thanh Tuyền"]},
    )
    assert "CA SĨ:" in card
    assert "Chế Linh" in card
    assert "Thanh Tuyền" in card


def test_render_mutation_diff_card_no_tape_line_when_items_unchanged():
    """Unchanged items_text must not add a SỐ BĂNG line."""
    order = Order(
        id=23,
        customer_name="Bác Khác",
        customer_phone="0912345678",
        shipping_address="Hà Nội",
        items_text="1 cuốn",
    )
    card = render_mutation_diff_card(order, {"new_shipping_address": "Đà Nẵng"})
    assert "SỐ BĂNG:" not in card
    assert "CA SĨ:" not in card


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


@pytest.mark.asyncio
async def test_mutate_order_with_lock_consecutive_mutations():
    """Verify consecutive mutations on the same order succeed without false-positive conflict."""
    from src.db.connection import get_db_connection
    from src.db.orders import create_order, get_order_by_id, mutate_order_with_lock
    from src.db.schema import init_db

    async with get_db_connection(":memory:") as db:
        await init_db(db)

        order = Order(
            customer_name="Bác Ba",
            customer_phone="0911223344",
            shipping_address="Hải Phòng",
            items_text="1 cuốn",
            total_amount=100000,
            status=OrderStatus.CHO_LAM,
        )
        order_id = await create_order(db, order)
        fetched1 = await get_order_by_id(db, order_id)
        assert fetched1 is not None

        # Mutation 1: Change address
        s1, c1, o1 = await mutate_order_with_lock(
            db,
            order_id=order_id,
            expected_updated_at=fetched1.updated_at,
            delta_dict={"shipping_address": "Hà Nội"},
            user_id=1,
            user_name="Admin",
        )
        assert s1 is True
        assert o1 is not None
        assert o1.shipping_address == "Hà Nội"

        # Mutation 2: Consecutive change immediately using o1.updated_at
        # In actual Telegram flow, o1.updated_at is a Python datetime object or string with 6 microsecond digits
        # while SQLite stored it with strftime 3 millisecond digits.
        fetched2 = await get_order_by_id(db, order_id)
        assert fetched2 is not None

        s2, c2, o2 = await mutate_order_with_lock(
            db,
            order_id=order_id,
            expected_updated_at=str(fetched2.updated_at),
            delta_dict={"status": OrderStatus.DANG_LAM},
            user_id=1,
            user_name="Admin",
        )
        assert s2 is True, "Second consecutive mutation must not fail with false optimistic lock conflict"
        assert o2 is not None
        assert o2.status == OrderStatus.DANG_LAM


@pytest.mark.asyncio
async def test_mutate_order_with_lock_microsecond_vs_millisecond_normalization():
    """Verify 6-digit microsecond string matches 3-digit SQLite timestamp without conflict."""
    from src.db.connection import get_db_connection
    from src.db.orders import create_order, mutate_order_with_lock
    from src.db.schema import init_db

    async with get_db_connection(":memory:") as db:
        await init_db(db)

        order = Order(
            customer_name="Bác Ba",
            customer_phone="0911223344",
            shipping_address="Hải Phòng",
            items_text="1 cuốn",
            total_amount=100000,
            status=OrderStatus.CHO_LAM,
        )
        order_id = await create_order(db, order)

        # Force a 3-digit millisecond timestamp into SQLite
        await db.execute(
            "UPDATE orders SET updated_at = '2026-10-25 10:05:37.024' WHERE id = ?",
            (order_id,),
        )
        await db.commit()

        # Pass 6-digit microsecond format as expected_updated_at (e.g. from Python str(datetime))
        s, c, updated = await mutate_order_with_lock(
            db,
            order_id=order_id,
            expected_updated_at="2026-10-25 10:05:37.024000",
            delta_dict={"items_text": "3 cuốn"},
            user_id=1,
            user_name="Admin",
        )
        assert s is True
        assert updated is not None
        assert updated.items_text == "3 cuốn"


@pytest.mark.asyncio
async def test_mutation_items_change_recomputes_tape_columns():
    """Changing items_text recomputes all 3 columns; old tapes are gone."""
    from src.db.connection import get_db_connection
    from src.db.orders import create_order, get_order_by_id, mutate_order_with_lock
    from src.db.schema import init_db

    async with get_db_connection(":memory:") as db:
        await init_db(db)

        order_id = await create_order(
            db,
            Order(
                customer_name="Khách Phôi",
                customer_phone="0911223344",
                shipping_address="Hà Nội",
                items_text="1 cuốn",
                total_amount=100000,
            ),
        )
        fetched = await get_order_by_id(db, order_id)
        assert fetched is not None

        success, changes, updated = await mutate_order_with_lock(
            db,
            order_id=order_id,
            expected_updated_at=fetched.updated_at,
            delta_dict={"new_items_text": "6 sony 90p"},
            user_name="Admin",
        )
        assert success is True
        assert updated is not None
        assert updated.tape_quantity == 6
        assert "sony 90p" in updated.tapes[0].label
        assert "cuon" not in updated.tapes[0].label  # old value not merged


@pytest.mark.asyncio
async def test_mutation_unrelated_field_preserves_tape_columns():
    """Changing shipping_address leaves the tape columns untouched."""
    from src.db.connection import get_db_connection
    from src.db.orders import create_order, get_order_by_id, mutate_order_with_lock
    from src.db.schema import init_db

    async with get_db_connection(":memory:") as db:
        await init_db(db)

        order_id = await create_order(
            db,
            Order(
                customer_name="Khách Phôi",
                customer_phone="0911223344",
                shipping_address="Hà Nội",
                items_text="6 sony 90p",
                total_amount=100000,
            ),
        )
        fetched = await get_order_by_id(db, order_id)
        assert fetched is not None
        assert fetched.tape_quantity == 6

        success, _, updated = await mutate_order_with_lock(
            db,
            order_id=order_id,
            expected_updated_at=fetched.updated_at,
            delta_dict={"new_shipping_address": "Đà Nẵng"},
            user_name="Admin",
        )
        assert success is True
        assert updated is not None
        assert updated.shipping_address == "Đà Nẵng"
        assert updated.tape_quantity == 6
        assert updated.tapes == fetched.tapes


@pytest.mark.asyncio
async def test_find_orders_for_mutation_strips_honorifics_and_fillers():
    """Verify find_orders_for_mutation matches DB customer even if keyword includes 'khách', 'bác', 'đơn'."""
    from src.db.connection import get_db_connection
    from src.db.orders import create_order, find_orders_for_mutation
    from src.db.schema import init_db

    async with get_db_connection(":memory:") as db:
        await init_db(db)

        # Create orders for customer 'Bác Ba'
        ord1 = Order(
            customer_name="Bác Ba",
            customer_phone="0911223344",
            shipping_address="Hải Phòng",
            items_text="1 cuốn",
            total_amount=100000,
            status=OrderStatus.CHO_LAM,
        )
        ord2 = Order(
            customer_name="Bác Ba",
            customer_phone="0911223344",
            shipping_address="Hà Nội",
            items_text="2 cuốn",
            total_amount=200000,
            status=OrderStatus.DANG_LAM,
        )
        ord3 = Order(
            customer_name="Anh Hà",
            customer_phone="0988776655",
            shipping_address="Đà Nẵng",
            items_text="1 cuốn",
            total_amount=150000,
            status=OrderStatus.CHO_LAM,
        )
        await create_order(db, ord1)
        await create_order(db, ord2)
        await create_order(db, ord3)

        # 1. Search with 'khách Bác Ba'
        matches = await find_orders_for_mutation(db, keyword="khách Bác Ba")
        assert len(matches) == 2
        assert all(m.customer_name == "Bác Ba" for m in matches)

        # 2. Search with 'đơn của anh Hà'
        matches_ha = await find_orders_for_mutation(db, keyword="đơn của anh Hà")
        assert len(matches_ha) == 1
        assert matches_ha[0].customer_name == "Anh Hà"





