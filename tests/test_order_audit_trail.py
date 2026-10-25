import aiosqlite
import pytest

from src.db.connection import get_db_connection
from src.db.orders import (
    create_order,
    find_orders_for_mutation,
    get_order_by_id,
    record_order_history,
    update_order_status,
    update_order_tracking,
)
from src.db.schema import init_db
from src.models.order import Order, OrderStatus


@pytest.mark.asyncio
async def test_order_history_schema_creation():
    """init_db creates order_history table and index."""
    async with get_db_connection(":memory:") as db:
        await init_db(db)

        # Check table columns
        async with db.execute("PRAGMA table_info(order_history);") as cursor:
            rows = await cursor.fetchall()
            cols = {row["name"]: row["type"] for row in rows}

        assert "id" in cols
        assert "order_id" in cols
        assert "user_id" in cols
        assert "user_name" in cols
        assert "action" in cols
        assert "changes_json" in cols
        assert "created_at" in cols

        # Check index
        async with db.execute("PRAGMA index_list(order_history);") as cursor:
            indices = [row["name"] for row in await cursor.fetchall()]
        assert "idx_order_history_order_id" in indices


@pytest.mark.asyncio
async def test_orders_schema_migration_idempotent():
    """init_db idempotently adds created_by_user_id and created_by_name to existing orders table."""
    async with get_db_connection(":memory:") as db:
        # Create legacy orders table without creator columns
        await db.execute(
            """
            CREATE TABLE orders (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                customer_id INTEGER,
                customer_name TEXT NOT NULL,
                customer_phone TEXT NOT NULL,
                shipping_address TEXT NOT NULL,
                items_text TEXT NOT NULL,
                total_amount INTEGER NOT NULL DEFAULT 0,
                cod_amount INTEGER NOT NULL DEFAULT 0,
                payment_method TEXT NOT NULL DEFAULT 'COD',
                status TEXT NOT NULL DEFAULT 'CHO_LAM',
                tracking_code TEXT,
                photo_file_ids TEXT NOT NULL DEFAULT '[]',
                raw_text TEXT NOT NULL DEFAULT '',
                created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
            );
            """
        )
        await db.commit()

        # Run init_db migration twice to verify idempotence
        await init_db(db)
        await init_db(db)

        async with db.execute("PRAGMA table_info(orders);") as cursor:
            rows = await cursor.fetchall()
            cols = {row["name"]: row["type"] for row in rows}

        assert "created_by_user_id" in cols
        assert "created_by_name" in cols


@pytest.mark.asyncio
async def test_create_order_persists_creator_and_records_history(test_db: aiosqlite.Connection):
    """create_order stores creator columns and inserts initial CREATE audit trail."""
    order = Order(
        customer_name="Bác Nam",
        customer_phone="0912345678",
        shipping_address="12 Hàng Gai, Hoàn Kiếm, Hà Nội",
        items_text="2 cuốn Tuấn Vũ",
        total_amount=300000,
        cod_amount=300000,
        created_by_user_id=12345678,
        created_by_name="Quân Staff",
    )

    order_id = await create_order(test_db, order)
    saved_order = await get_order_by_id(test_db, order_id)
    assert saved_order is not None
    assert saved_order.created_by_user_id == 12345678
    assert saved_order.created_by_name == "Quân Staff"

    # Check order_history
    async with test_db.execute(
        "SELECT * FROM order_history WHERE order_id = ?", (order_id,)
    ) as cursor:
        rows = await cursor.fetchall()
        assert len(rows) == 1
        history = rows[0]
        assert history["action"] == "CREATE"
        assert history["user_id"] == 12345678
        assert history["user_name"] == "Quân Staff"


@pytest.mark.asyncio
async def test_record_order_history_helper(test_db: aiosqlite.Connection):
    """record_order_history helper inserts audit record with JSON changes."""
    order = Order(
        customer_name="Cô Hoa",
        customer_phone="0987654321",
        shipping_address="45 Đinh Tiên Hoàng, Đà Nẵng",
        items_text="1 cuốn Khánh Ly",
    )
    order_id = await create_order(test_db, order)

    changes = {"status": {"old": "CHO_LAM", "new": "DANG_LAM"}}
    await record_order_history(
        test_db,
        order_id=order_id,
        user_id=9999,
        user_name="Admin",
        action="STATUS_CHANGE",
        changes=changes,
    )

    async with test_db.execute(
        "SELECT * FROM order_history WHERE order_id = ? ORDER BY id DESC LIMIT 1",
        (order_id,),
    ) as cursor:
        row = await cursor.fetchone()
        assert row is not None
        assert row["action"] == "STATUS_CHANGE"
        assert row["user_id"] == 9999
        assert "DANG_LAM" in row["changes_json"]


@pytest.mark.asyncio
async def test_update_order_status_writes_audit_trail(test_db: aiosqlite.Connection):
    """update_order_status writes audit trail to order_history (WR-02)."""
    order = Order(
        customer_name="Bác Ba",
        customer_phone="0912345678",
        shipping_address="Hà Nội",
        items_text="1 cuốn",
        status=OrderStatus.CHO_LAM,
    )
    oid = await create_order(test_db, order)

    success = await update_order_status(
        test_db, oid, OrderStatus.DANG_LAM, user_id=111, user_name="Quân Staff"
    )
    assert success is True

    async with test_db.execute(
        "SELECT * FROM order_history WHERE order_id = ? ORDER BY id DESC LIMIT 1",
        (oid,),
    ) as cursor:
        row = await cursor.fetchone()
        assert row is not None
        assert row["action"] == "STATUS_CHANGE"
        assert row["user_id"] == 111
        assert row["user_name"] == "Quân Staff"
        assert "CHO_LAM" in row["changes_json"]
        assert "DANG_LAM" in row["changes_json"]


@pytest.mark.asyncio
async def test_update_order_tracking_writes_audit_trail(test_db: aiosqlite.Connection):
    """update_order_tracking writes audit trail to order_history (WR-02)."""
    order = Order(
        customer_name="Bác Bốn",
        customer_phone="0987654321",
        shipping_address="Hải Phòng",
        items_text="1 cuốn",
        tracking_code=None,
    )
    oid = await create_order(test_db, order)

    success = await update_order_tracking(
        test_db, oid, "VNPOST9999", user_id=222, user_name="Bác Admin"
    )
    assert success is True

    async with test_db.execute(
        "SELECT * FROM order_history WHERE order_id = ? ORDER BY id DESC LIMIT 1",
        (oid,),
    ) as cursor:
        row = await cursor.fetchone()
        assert row is not None
        assert row["action"] == "TRACKING_UPDATE"
        assert row["user_id"] == 222
        assert row["user_name"] == "Bác Admin"
        assert "VNPOST9999" in row["changes_json"]


@pytest.mark.asyncio
async def test_find_orders_for_mutation_prioritizes_active(test_db: aiosqlite.Connection):
    """find_orders_for_mutation prioritizes active lifecycle states before completed ones."""
    # Terminal order (older or newer)
    terminal_order = Order(
        customer_name="Trần Văn Bình",
        customer_phone="0903111222",
        shipping_address="100 Nguyễn Trãi, Q1, HCM",
        items_text="Băng cũ",
        status=OrderStatus.DA_GIAO,
    )
    id_terminal = await create_order(test_db, terminal_order)

    # Active order
    active_order = Order(
        customer_name="Trần Văn Bình",
        customer_phone="0903111222",
        shipping_address="200 Lê Lai, Q1, HCM",
        items_text="Băng mới",
        status=OrderStatus.DANG_LAM,
    )
    id_active = await create_order(test_db, active_order)

    # 1. Exact ID match
    results_id = await find_orders_for_mutation(test_db, order_id=id_terminal)
    assert len(results_id) == 1
    assert results_id[0].id == id_terminal

    # 2. Search by phone: active order should be first
    results_phone = await find_orders_for_mutation(test_db, phone="0903111222")
    assert len(results_phone) == 2
    assert results_phone[0].id == id_active
    assert results_phone[1].id == id_terminal

    # 3. Search by name/address keyword (unaccented)
    results_kw = await find_orders_for_mutation(test_db, keyword="tran van binh")
    assert len(results_kw) == 2
    assert results_kw[0].id == id_active
    assert results_kw[1].id == id_terminal
