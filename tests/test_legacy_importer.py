from datetime import datetime
import json
import pytest

from src.models.customer import Customer
from src.models.order import OrderStatus
from src.services.legacy_importer import (
    ImportSummary,
    LegacyBlobImporter,
    map_legacy_customer,
    map_legacy_order,
    parse_legacy_blob,
)


def _make_sample_blob():
    return {
        "schemaVersion": 1,
        "createdAt": "2025-06-13T13:19:18.616Z",
        "payload": {
            "customer": {
                "customers": [
                    {
                        "id": "cust_1",
                        "name": "Nguyễn Văn Một",
                        "mobile": "0901111111",
                        "address": "111 Phố Một, Hà Nội",
                        "province": "Hà Nội",
                        "difficulty": "de",
                        "area": "bac",
                        "isVIP": True,
                        "isInBlacklist": False,
                        "note": "Khách quen",
                    },
                    {
                        "id": "cust_2",
                        "name": "Trần Thị Hai",
                        "mobile": "0902222222",
                        "address": "222 Phố Hai, TP.HCM",
                        "province": "TP.HCM",
                        "difficulty": "kho",
                        "area": "nam",
                        "isVIP": False,
                        "isInBlacklist": False,
                        "note": "",
                    },
                ]
            },
            "order": {
                "orders": [
                    {
                        "id": "ord_1",
                        "customerId": "cust_1",
                        "createdDate": "2025-06-01T10:00:00.000Z",
                        "placedItems": "2 cuốn Tuấn Vũ",
                        "status": "Đã giao thành công",
                        "paymentMethod": "Chuyển khoản trước",
                        "paymentAmount": 120000,
                        "codAmount": 0,
                        "shippingCode": "TRACK_001",
                    },
                    {
                        "id": "ord_2",
                        "customerId": "cust_1",
                        "createdDate": "2025-06-05T12:00:00.000Z",
                        "placedItems": "1 cuốn Chế Linh",
                        "status": "Đã tạo đơn",
                        "paymentMethod": "COD",
                        "paymentAmount": 60000,
                        "codAmount": 60000,
                        "shippingCode": "TRACK_002",
                    },
                    {
                        "id": "ord_3",
                        "customerId": "cust_2",
                        "createdDate": "2025-06-10T15:00:00.000Z",
                        "placedItems": "3 phôi Maxell",
                        "status": "Đã chuyển hoàn",
                        "paymentMethod": "COD",
                        "paymentAmount": 180000,
                        "codAmount": 180000,
                        "shippingCode": "TRACK_003",
                    },
                ]
            },
            "codPayments": [{"id": "cod_dummy"}],
            "syncFailures": [{"id": "sync_dummy"}],
            "appContext": {"trello": True},
        },
    }


def test_legacy_parser_extracts_only_customers_and_orders():
    blob = _make_sample_blob()
    customers, orders = parse_legacy_blob(blob)
    assert len(customers) == 2
    assert len(orders) == 3
    assert customers[0]["id"] == "cust_1"
    assert orders[0]["id"] == "ord_1"


def test_mapping_customer_and_order_fields():
    raw_cust = {
        "id": "c_abc",
        "name": "Trần Thị B",
        "mobile": "0987654321",
        "address": "456 Tran Hung Dao, Q1",
        "province": "TP.HCM",
        "difficulty": "de",
        "area": "nam",
        "isVIP": True,
        "isInBlacklist": False,
        "note": "Khách thích nhạc xưa",
    }
    customer = map_legacy_customer(raw_cust)
    assert customer.name == "Trần Thị B"
    assert customer.phones == ["0987654321"]
    assert "456 Tran Hung Dao, Q1" in customer.addresses[0]
    assert "VIP: True" in customer.notes
    assert "legacy_id: c_abc" in customer.notes

    raw_order = {
        "id": "o_123",
        "customerId": "c_abc",
        "createdDate": "2025-06-13T13:19:18.616Z",
        "placedItems": "2 cuốn Tuấn Vũ, 1 cuốn Chế Linh",
        "status": "Đã giao thành công",
        "paymentMethod": "Chuyển khoản trước",
        "paymentAmount": 150000,
        "codAmount": 0,
        "shippingCode": "VTP123456",
        "note": "Giao buoi sang",
    }
    cid_map = {"c_abc": 42}
    order_dict = map_legacy_order(raw_order, cid_map, customer)
    assert order_dict["customer_id"] == 42
    assert order_dict["customer_name"] == "Trần Thị B"
    assert order_dict["customer_phone"] == "0987654321"
    assert order_dict["status"] == OrderStatus.DA_GIAO.value
    assert order_dict["payment_method"] == "CHUYEN_KHOAN"
    assert order_dict["total_amount"] == 150000
    assert order_dict["cod_amount"] == 0
    assert order_dict["tracking_code"] == "VTP123456"
    assert order_dict["tape_quantity"] >= 1
    assert order_dict["created_at"] == "2025-06-13T13:19:18.616Z"


@pytest.mark.asyncio
async def test_customer_id_remapping(test_db):
    blob = _make_sample_blob()
    importer = LegacyBlobImporter(blob)
    summary = await importer.run(test_db, dry_run=False)

    assert summary.customers_created == 2
    assert summary.orders_created == 3

    # Check that SQLite customers table has integer IDs
    cust_rows = {}
    async with test_db.execute("SELECT id, name FROM customers") as cursor:
        async for row in cursor:
            cust_rows[row[1]] = row[0]

    assert len(cust_rows) == 2
    c1_id = cust_rows["Nguyễn Văn Một"]
    c2_id = cust_rows["Trần Thị Hai"]
    assert isinstance(c1_id, int)
    assert isinstance(c2_id, int)

    # Check foreign keys in orders
    async with test_db.execute("SELECT customer_id, customer_name, tracking_code FROM orders") as cursor:
        rows = await cursor.fetchall()
        assert len(rows) == 3
        for cid, cname, trk in rows:
            if trk in ("TRACK_001", "TRACK_002"):
                assert cid == c1_id
                assert cname == "Nguyễn Văn Một"
            elif trk == "TRACK_003":
                assert cid == c2_id
                assert cname == "Trần Thị Hai"


@pytest.mark.asyncio
async def test_importer_dry_run_leaves_database_untouched(test_db):
    blob = _make_sample_blob()
    importer = LegacyBlobImporter(blob)
    summary = await importer.run(test_db, dry_run=True)

    assert summary.customers_created == 2
    assert summary.orders_created == 3

    # DB must remain completely empty
    async with test_db.execute("SELECT COUNT(*) FROM customers") as cursor:
        row = await cursor.fetchone()
        assert row[0] == 0

    async with test_db.execute("SELECT COUNT(*) FROM orders") as cursor:
        row = await cursor.fetchone()
        assert row[0] == 0


@pytest.mark.asyncio
async def test_importer_idempotency(test_db):
    blob = _make_sample_blob()
    importer = LegacyBlobImporter(blob)

    # First run: writes data
    s1 = await importer.run(test_db, dry_run=False)
    assert s1.customers_created == 2
    assert s1.orders_created == 3

    # Second run: must create 0, reuse 2, skip 3
    s2 = await importer.run(test_db, dry_run=False)
    assert s2.customers_created == 0
    assert s2.customers_reused == 2
    assert s2.orders_created == 0
    assert s2.orders_skipped == 3

    # DB record counts must not double
    async with test_db.execute("SELECT COUNT(*) FROM customers") as cursor:
        assert (await cursor.fetchone())[0] == 2
    async with test_db.execute("SELECT COUNT(*) FROM orders") as cursor:
        assert (await cursor.fetchone())[0] == 3


@pytest.mark.asyncio
async def test_transaction_rollback_on_failure(test_db):
    blob = _make_sample_blob()
    importer = LegacyBlobImporter(blob)

    # Corrupt order placedItems with invalid schema or mock map_legacy_order failure
    import src.services.legacy_importer as importer_module

    original_map_order = importer_module.map_legacy_order
    call_count = 0

    def faulty_map_order(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        if call_count == 2:
            raise RuntimeError("Simulated crash mid-order-mapping")
        return original_map_order(*args, **kwargs)

    monkeypatch = pytest.MonkeyPatch()
    monkeypatch.setattr(importer_module, "map_legacy_order", faulty_map_order)

    try:
        with pytest.raises(RuntimeError, match="Simulated crash mid-order-mapping"):
            await importer.run(test_db, dry_run=False)
    finally:
        monkeypatch.undo()

    # Entire transaction should have rolled back: 0 customers, 0 orders
    async with test_db.execute("SELECT COUNT(*) FROM customers") as cursor:
        assert (await cursor.fetchone())[0] == 0
    async with test_db.execute("SELECT COUNT(*) FROM orders") as cursor:
        assert (await cursor.fetchone())[0] == 0


@pytest.mark.asyncio
async def test_existing_new_data_preserved(test_db):
    # Pre-populate DB with new customer & order created today
    cursor = await test_db.execute(
        """
        INSERT INTO customers (name, phones, addresses, notes)
        VALUES ('Khách Hàng Mới 2026', '["0999999999"]', '["Hà Nội"]', 'Tạo từ Telegram bot')
        """
    )
    new_cid = cursor.lastrowid
    await test_db.execute(
        """
        INSERT INTO orders (
            customer_id, customer_name, customer_phone, shipping_address,
            items_text, total_amount, cod_amount, payment_method, status, tracking_code
        ) VALUES (
            ?, 'Khách Hàng Mới 2026', '0999999999', 'Hà Nội',
            '1 cuốn mới 2026', 100000, 100000, 'COD', 'CHO_LAM', 'NEW_TRACK_999'
        )
        """,
        (new_cid,),
    )
    await test_db.commit()

    # Now run legacy migration
    blob = _make_sample_blob()
    importer = LegacyBlobImporter(blob)
    summary = await importer.run(test_db, dry_run=False)

    assert summary.customers_created == 2
    assert summary.orders_created == 3

    # Total customers = 1 existing + 2 legacy = 3
    async with test_db.execute("SELECT COUNT(*) FROM customers") as c_cur:
        assert (await c_cur.fetchone())[0] == 3

    # Total orders = 1 existing + 3 legacy = 4
    async with test_db.execute("SELECT COUNT(*) FROM orders") as o_cur:
        assert (await o_cur.fetchone())[0] == 4

    # Verify existing new data was unmodified
    async with test_db.execute("SELECT customer_name, tracking_code, status FROM orders WHERE id = 1") as o_cur:
        row = await o_cur.fetchone()
        assert row[0] == "Khách Hàng Mới 2026"
        assert row[1] == "NEW_TRACK_999"
        assert row[2] == "CHO_LAM"
