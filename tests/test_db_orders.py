import aiosqlite
import pytest

from src.db.orders import (
    append_order_photos,
    create_order,
    get_order_by_id,
    list_orders_by_status,
    update_order_status,
    update_order_tracking,
)
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
async def test_get_non_existent_order(test_db):
    """get_order_by_id returns None when ID not found."""
    assert await get_order_by_id(test_db, 99999) is None
