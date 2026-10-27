import aiosqlite
import pytest

from src.db.customers import add_address, create_customer
from src.db.orders import (
    append_order_photos,
    count_orders_by_date,
    count_orders_by_status,
    create_order,
    get_customer_order_stats,
    get_order_by_id,
    list_orders_by_date,
    list_orders_by_status,
    update_order_status,
    update_order_tracking,
)
from src.models.customer import Customer
from src.models.order import Order, OrderStatus


def test_order_status_enum_values():
    """OrderStatus enum must define 8 valid states."""
    expected = {
        "CHO_LAM",
        "DANG_LAM",
        "DA_DONG_GOI",
        "DA_TAO_DON",
        "SHIPPER_DA_LAY",
        "DA_GIAO",
        "BOM_HANG",
        "HUY_DON",
    }
    actual = {s.value for s in OrderStatus}
    assert actual == expected
    assert len(OrderStatus) == 8


def test_order_domain_model_defaults():
    """Order domain model has expected defaults."""
    order = Order(
        customer_name="Nguyễn Văn A",
        customer_phone="0901234567",
        shipping_address="123 Lê Lợi, Q1, HCM",
        items_text="Băng Tuấn Vũ 1, Băng Chế Linh 2",
        total_amount=300000,
        cod_amount=300000,
    )
    assert order.status == OrderStatus.CHO_LAM
    assert order.payment_method == "COD"
    assert order.photo_file_ids == []
    assert order.tracking_code is None
    assert order.customer_id is None


@pytest.mark.asyncio
async def test_create_and_get_order_roundtrip(test_db):
    """create_order stores customer snapshot and all fields; get_order_by_id reconstructs it."""
    order = Order(
        customer_id=None,
        customer_name="Trần Thị B",
        customer_phone="0912345678",
        shipping_address="456 Nguyễn Huệ, Q1, HCM",
        items_text="2 cuốn Băng Trịnh Công Sơn",
        total_amount=450000,
        cod_amount=0,
        payment_method="BANK_TRANSFER",
        status=OrderStatus.CHO_LAM,
        tracking_code=None,
        photo_file_ids=["file_id_abc1", "file_id_abc2"],
        raw_text="Gửi 2 cuốn Trịnh Công Sơn về 456 Nguyễn Huệ cho B 0912345678",
    )
    order_id = await create_order(test_db, order)
    assert order_id > 0

    saved = await get_order_by_id(test_db, order_id)
    assert saved is not None
    assert saved.id == order_id
    assert saved.customer_name == "Trần Thị B"
    assert saved.customer_phone == "0912345678"
    assert saved.shipping_address == "456 Nguyễn Huệ, Q1, HCM"
    assert saved.items_text == "2 cuốn Băng Trịnh Công Sơn"
    assert saved.total_amount == 450000
    assert saved.cod_amount == 0
    assert saved.payment_method == "BANK_TRANSFER"
    assert saved.status == OrderStatus.CHO_LAM
    assert saved.photo_file_ids == ["file_id_abc1", "file_id_abc2"]
    assert saved.raw_text == "Gửi 2 cuốn Trịnh Công Sơn về 456 Nguyễn Huệ cho B 0912345678"
    assert saved.created_at is not None
    assert saved.updated_at is not None


@pytest.mark.asyncio
async def test_order_status_db_check_constraint(test_db):
    """Inserting invalid status directly via SQL raises IntegrityError due to CHECK constraint."""
    with pytest.raises(aiosqlite.IntegrityError):
        await test_db.execute(
            """
            INSERT INTO orders (customer_name, customer_phone, shipping_address, items_text, status)
            VALUES (?, ?, ?, ?, ?)
            """,
            ("Ai đó", "0900000000", "Địa chỉ X", "Băng X", "INVALID_STATUS"),
        )


@pytest.mark.asyncio
async def test_update_order_status(test_db):
    """update_order_status changes status and updates timestamp."""
    order = Order(
        customer_name="Khách A",
        customer_phone="0901111111",
        shipping_address="Hà Nội",
        items_text="1 Băng",
        total_amount=150000,
        cod_amount=150000,
    )
    order_id = await create_order(test_db, order)

    success = await update_order_status(test_db, order_id, OrderStatus.DA_DONG_GOI)
    assert success is True

    updated = await get_order_by_id(test_db, order_id)
    assert updated is not None
    assert updated.status == OrderStatus.DA_DONG_GOI


@pytest.mark.asyncio
async def test_update_order_tracking(test_db):
    """update_order_tracking updates tracking code."""
    order = Order(
        customer_name="Khách B",
        customer_phone="0902222222",
        shipping_address="Đà Nẵng",
        items_text="1 Băng",
    )
    order_id = await create_order(test_db, order)

    success = await update_order_tracking(test_db, order_id, "VNPOST123456")
    assert success is True

    updated = await get_order_by_id(test_db, order_id)
    assert updated is not None
    assert updated.tracking_code == "VNPOST123456"


@pytest.mark.asyncio
async def test_append_and_get_photos(test_db):
    """append_order_photos appends photo file_ids to existing array."""
    order = Order(
        customer_name="Khách C",
        customer_phone="0903333333",
        shipping_address="Cần Thơ",
        items_text="1 Băng",
        photo_file_ids=["photo_1"],
    )
    order_id = await create_order(test_db, order)

    success = await append_order_photos(test_db, order_id, ["photo_2", "photo_3"])
    assert success is True

    updated = await get_order_by_id(test_db, order_id)
    assert updated is not None
    assert updated.photo_file_ids == ["photo_1", "photo_2", "photo_3"]


@pytest.mark.asyncio
async def test_append_photos_to_empty(test_db):
    """append_order_photos handles orders starting with empty photos."""
    order = Order(
        customer_name="Khách D",
        customer_phone="0904444444",
        shipping_address="Huế",
        items_text="1 Băng",
    )
    order_id = await create_order(test_db, order)

    success = await append_order_photos(test_db, order_id, ["photo_new"])
    assert success is True

    updated = await get_order_by_id(test_db, order_id)
    assert updated is not None
    assert updated.photo_file_ids == ["photo_new"]


@pytest.mark.asyncio
async def test_list_orders_by_status(test_db):
    """list_orders_by_status filters orders correctly and paginates."""
    for i in range(3):
        await create_order(
            test_db,
            Order(
                customer_name=f"Khách {i}",
                customer_phone=f"090000000{i}",
                shipping_address="HCM",
                items_text=f"Băng {i}",
                status=OrderStatus.CHO_LAM,
            ),
        )
    await create_order(
        test_db,
        Order(
            customer_name="Khách Khác",
            customer_phone="0999999999",
            shipping_address="HCM",
            items_text="Băng Khác",
            status=OrderStatus.DA_GIAO,
        ),
    )

    cho_lam_orders = await list_orders_by_status(test_db, OrderStatus.CHO_LAM)
    assert len(cho_lam_orders) == 3

    da_giao_orders = await list_orders_by_status(test_db, OrderStatus.DA_GIAO)
    assert len(da_giao_orders) == 1
    assert da_giao_orders[0].customer_name == "Khách Khác"


@pytest.mark.asyncio
async def test_count_orders_by_status(test_db):
    """count_orders_by_status counts each status and returns 0 when none."""
    assert await count_orders_by_status(test_db, OrderStatus.CHO_LAM) == 0

    statuses = [OrderStatus.CHO_LAM, OrderStatus.CHO_LAM, OrderStatus.DANG_LAM]
    for i, st in enumerate(statuses):
        await create_order(
            test_db,
            Order(
                customer_name=f"Khách {i}",
                customer_phone=f"090000000{i}",
                shipping_address="HCM",
                items_text="Băng",
                status=st,
            ),
        )

    assert await count_orders_by_status(test_db, OrderStatus.CHO_LAM) == 2
    assert await count_orders_by_status(test_db, OrderStatus.DANG_LAM) == 1
    assert await count_orders_by_status(test_db, OrderStatus.DA_DONG_GOI) == 0


@pytest.mark.asyncio
async def test_get_non_existent_order(test_db):
    """get_order_by_id returns None when ID not found."""
    assert await get_order_by_id(test_db, 99999) is None


@pytest.mark.asyncio
async def test_get_customer_order_stats(test_db):
    """get_customer_order_stats calculates total orders, spend excluding HUY_DON, and BOM_HANG count."""
    # Customer without orders returns 0 stats
    stats_empty = await get_customer_order_stats(test_db, 99999)
    assert stats_empty == {"total_orders": 0, "total_spent": 0, "bom_count": 0}

    # Create customer
    customer = Customer(
        name="Khách Thống Kê",
        phones=["0918888888"],
        addresses=["123 Test Street"],
    )
    cust_id = await create_customer(test_db, customer)

    # Create 3 orders: CHO_LAM (150k), BOM_HANG (200k), HUY_DON (300k)
    await create_order(
        test_db,
        Order(
            customer_id=cust_id,
            customer_name=customer.name,
            customer_phone=customer.phones[0],
            shipping_address=customer.addresses[0],
            items_text="Băng 1",
            total_amount=150000,
            status=OrderStatus.CHO_LAM,
        ),
    )
    await create_order(
        test_db,
        Order(
            customer_id=cust_id,
            customer_name=customer.name,
            customer_phone=customer.phones[0],
            shipping_address=customer.addresses[0],
            items_text="Băng 2",
            total_amount=200000,
            status=OrderStatus.BOM_HANG,
        ),
    )
    await create_order(
        test_db,
        Order(
            customer_id=cust_id,
            customer_name=customer.name,
            customer_phone=customer.phones[0],
            shipping_address=customer.addresses[0],
            items_text="Băng 3",
            total_amount=300000,
            status=OrderStatus.HUY_DON,
        ),
    )

    stats = await get_customer_order_stats(test_db, cust_id)
    assert stats["total_orders"] == 3
    # HUY_DON excluded from spend -> 150000 + 200000 = 350000
    assert stats["total_spent"] == 350000
    assert stats["bom_count"] == 1


@pytest.mark.asyncio
async def test_add_address_idempotent_and_append(test_db):
    """add_address appends new address, avoids duplicates case-insensitively, trims whitespace."""
    cust_id = await create_customer(
        test_db,
        Customer(
            name="Khách Địa Chỉ",
            phones=["0919999999"],
            addresses=["123 Lê Lợi, Q1"],
        ),
    )

    # Duplicate with different case and whitespace should not append
    res1 = await add_address(test_db, cust_id, "  123 lê lợi, q1  ")
    assert res1 is False

    # New distinct address appends
    res2 = await add_address(test_db, cust_id, "456 Nguyễn Huệ, Q1")
    assert res2 is True

    # Duplicate of newly added address should not append
    res3 = await add_address(test_db, cust_id, "456 NGUYỄN HUỆ, Q1")
    assert res3 is False


@pytest.mark.asyncio
async def test_list_and_count_orders_by_date_utc7(test_db):
    """list_orders_by_date and count_orders_by_date match records using date(created_at, '+7 hours')."""
    # 2026-10-24 18:00:00 UTC -> 2026-10-25 01:00:00 UTC+7 (belongs to 2026-10-25)
    await test_db.execute(
        """
        INSERT INTO orders (customer_name, customer_phone, shipping_address, items_text, total_amount, created_at)
        VALUES ('Khách Tối 24', '0901', 'HCM', 'Băng 1', 100000, '2026-10-24 18:00:00')
        """
    )
    # 2026-10-24 05:00:00 UTC -> 2026-10-24 12:00:00 UTC+7 (belongs to 2026-10-24)
    await test_db.execute(
        """
        INSERT INTO orders (customer_name, customer_phone, shipping_address, items_text, total_amount, created_at)
        VALUES ('Khách Trưa 24', '0902', 'HN', 'Băng 2', 200000, '2026-10-24 05:00:00')
        """
    )
    # 2026-10-23 20:00:00 UTC -> 2026-10-24 03:00:00 UTC+7 (belongs to 2026-10-24)
    await test_db.execute(
        """
        INSERT INTO orders (customer_name, customer_phone, shipping_address, items_text, total_amount, created_at)
        VALUES ('Khách Khuya 23', '0903', 'ĐN', 'Băng 3', 300000, '2026-10-23 20:00:00')
        """
    )
    await test_db.commit()

    # Query for 2026-10-24 (should find Khách Trưa 24 and Khách Khuya 23)
    orders_24 = await list_orders_by_date(test_db, "2026-10-24", limit=5, offset=0)
    count_24 = await count_orders_by_date(test_db, "2026-10-24")
    assert count_24 == 2
    assert len(orders_24) == 2
    names_24 = [o.customer_name for o in orders_24]
    assert "Khách Trưa 24" in names_24
    assert "Khách Khuya 23" in names_24
    assert "Khách Tối 24" not in names_24

    # Query for 2026-10-25 (should find Khách Tối 24)
    orders_25 = await list_orders_by_date(test_db, "2026-10-25", limit=5, offset=0)
    count_25 = await count_orders_by_date(test_db, "2026-10-25")
    assert count_25 == 1
    assert len(orders_25) == 1
    assert orders_25[0].customer_name == "Khách Tối 24"

    # Pagination offset/limit test
    paged = await list_orders_by_date(test_db, "2026-10-24", limit=1, offset=1)
    assert len(paged) == 1
    assert paged[0].customer_name == "Khách Khuya 23"


@pytest.mark.asyncio
async def test_create_order_persists_and_reads_tape_columns(test_db):
    """create_order writes the derived 3 columns; get_order_by_id round-trips them."""
    from src.models.order import TapeItem

    order_id = await create_order(
        test_db,
        Order(
            customer_name="Khách Phôi",
            customer_phone="0911222333",
            shipping_address="Hà Nội",
            items_text="6 sony 90p",
            tapes=[TapeItem(label="sony 90p", qty=6)],
            tape_genres=["nhạc vàng"],
            tape_artists=["Chế Linh", "Thanh Tuyền"],
        ),
    )

    saved = await get_order_by_id(test_db, order_id)
    assert saved is not None
    assert saved.tape_quantity == 6
    assert saved.tapes[0].label == "sony 90p"
    assert saved.tapes[0].qty == 6
    assert saved.tape_genres == ["nhạc vàng"]
    assert saved.tape_artists == ["Chế Linh", "Thanh Tuyền"]


@pytest.mark.asyncio
async def test_legacy_row_with_null_tape_columns_reads_as_none(test_db):
    """Old orders keep NULL columns; they read as tape_quantity None and tapes []."""
    cursor = await test_db.execute(
        """
        INSERT INTO orders (
            customer_name, customer_phone, shipping_address, items_text
        )
        VALUES ('Khách Cũ', '0900111222', 'Đà Nẵng', '3 băng maxell 90p')
        """
    )
    legacy_id = cursor.lastrowid
    await test_db.commit()

    legacy = await get_order_by_id(test_db, legacy_id)
    assert legacy is not None
    assert legacy.tape_quantity is None
    assert legacy.tapes == []
    assert legacy.tape_genres == []
    assert legacy.tape_artists == []

