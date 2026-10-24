import aiosqlite
import pytest

from src.db.connection import get_db_connection
from src.db.customers import (
    create_customer,
    get_customer_by_id,
    get_customer_by_phone,
    list_customers,
    update_customer,
)
from src.models.customer import Customer


@pytest.mark.asyncio
async def test_connection_pragmas_and_row_factory(tmp_path):
    """Test WAL mode, busy_timeout=5000, foreign_keys=ON, and row_factory."""
    db_file = str(tmp_path / "test.db")
    async with get_db_connection(db_file) as db:
        # Check row_factory
        assert db.row_factory == aiosqlite.Row

        # Check WAL pragma
        async with db.execute("PRAGMA journal_mode;") as cursor:
            row = await cursor.fetchone()
            assert row[0].upper() == "WAL"

        # Check busy_timeout pragma
        async with db.execute("PRAGMA busy_timeout;") as cursor:
            row = await cursor.fetchone()
            assert int(row[0]) == 5000

        # Check foreign_keys pragma
        async with db.execute("PRAGMA foreign_keys;") as cursor:
            row = await cursor.fetchone()
            assert int(row[0]) == 1


@pytest.mark.asyncio
async def test_connection_closes_after_context_manager(tmp_path):
    """Test connection closes properly after async context manager exits."""
    db_file = str(tmp_path / "test_close.db")
    async with get_db_connection(db_file) as db:
        conn = db
        async with conn.execute("SELECT 1;") as cursor:
            res = await cursor.fetchone()
            assert res[0] == 1

    # Attempting to execute on closed connection must fail
    with pytest.raises(Exception):
        await conn.execute("SELECT 1;")


@pytest.mark.asyncio
async def test_init_db_creates_customers_schema(test_db):
    """Test init_db creates customers table with expected columns and index."""
    # Check table existence and columns
    async with test_db.execute("PRAGMA table_info(customers);") as cursor:
        columns = {row["name"]: row["type"].upper() for row in await cursor.fetchall()}

    assert "id" in columns
    assert "name" in columns
    assert "phones" in columns
    assert "addresses" in columns
    assert "notes" in columns
    assert "created_at" in columns
    assert "updated_at" in columns

    # Check index idx_customers_name
    async with test_db.execute("PRAGMA index_list(customers);") as cursor:
        indices = [row["name"] for row in await cursor.fetchall()]
        assert "idx_customers_name" in indices


@pytest.mark.asyncio
async def test_customer_model_instantiation():
    """Test Customer domain model supports multiple phones and addresses per DATA-01."""
    customer = Customer(
        name="Nguyễn Văn A",
        phones=["0912345678", "0987654321"],
        addresses=["123 Lê Lợi, Q1, HCM", "456 Trần Hưng Đạo, Q5, HCM"],
        notes="Khách quen thích nhạc Trịnh",
    )
    assert customer.name == "Nguyễn Văn A"
    assert len(customer.phones) == 2
    assert len(customer.addresses) == 2
    assert customer.notes == "Khách quen thích nhạc Trịnh"
    assert customer.id is None


@pytest.mark.asyncio
async def test_create_and_get_customer_roundtrip(test_db):
    """Test create_customer and get_customer_by_id round-trip serialization."""
    customer_in = Customer(
        name="Trần Văn B",
        phones=["0901234567", "0907654321"],
        addresses=["Số 10 Hàng Gai, Hoàn Kiếm, Hà Nội"],
        notes="Giao giờ hành chính",
    )
    customer_id = await create_customer(test_db, customer_in)
    assert isinstance(customer_id, int)
    assert customer_id > 0

    customer_out = await get_customer_by_id(test_db, customer_id)
    assert customer_out is not None
    assert customer_out.id == customer_id
    assert customer_out.name == "Trần Văn B"
    assert customer_out.phones == ["0901234567", "0907654321"]
    assert customer_out.addresses == ["Số 10 Hàng Gai, Hoàn Kiếm, Hà Nội"]
    assert customer_out.notes == "Giao giờ hành chính"
    assert customer_out.created_at is not None
    assert customer_out.updated_at is not None


@pytest.mark.asyncio
async def test_get_customer_by_id_not_found(test_db):
    """Test get_customer_by_id returns None for non-existent id."""
    result = await get_customer_by_id(test_db, 99999)
    assert result is None


@pytest.mark.asyncio
async def test_get_customer_by_phone(test_db):
    """Test get_customer_by_phone searches within JSON phones array."""
    c1 = Customer(
        name="Lê Văn C",
        phones=["0911111111", "0922222222"],
        addresses=["Hải Phòng"],
    )
    c2 = Customer(
        name="Phạm Thị D",
        phones=["0933333333"],
        addresses=["Đà Nẵng"],
    )
    await create_customer(test_db, c1)
    id2 = await create_customer(test_db, c2)

    # Search for secondary phone of c1
    found_c1 = await get_customer_by_phone(test_db, "0922222222")
    assert found_c1 is not None
    assert found_c1.name == "Lê Văn C"

    # Search for primary phone of c2
    found_c2 = await get_customer_by_phone(test_db, "0933333333")
    assert found_c2 is not None
    assert found_c2.id == id2

    # Search for non-existent phone
    not_found = await get_customer_by_phone(test_db, "0999999999")
    assert not_found is None


@pytest.mark.asyncio
async def test_update_customer(test_db):
    """Test update_customer modifies fields and updates updated_at timestamp."""
    c = Customer(
        name="Hoàng E",
        phones=["0944444444"],
        addresses=["Cần Thơ"],
        notes="Ghi chú cũ",
    )
    cid = await create_customer(test_db, c)
    created_customer = await get_customer_by_id(test_db, cid)
    assert created_customer is not None

    # Update customer data
    created_customer.name = "Hoàng E (VIP)"
    created_customer.phones.append("0955555555")
    created_customer.addresses.append("Vĩnh Long")
    created_customer.notes = "Ghi chú mới"

    ok = await update_customer(test_db, created_customer)
    assert ok is True

    updated_customer = await get_customer_by_id(test_db, cid)
    assert updated_customer is not None
    assert updated_customer.name == "Hoàng E (VIP)"
    assert updated_customer.phones == ["0944444444", "0955555555"]
    assert len(updated_customer.addresses) == 2
    assert updated_customer.notes == "Ghi chú mới"


@pytest.mark.asyncio
async def test_update_customer_non_existent(test_db):
    """Test update_customer returns False when customer id does not exist."""
    fake_customer = Customer(
        id=99999,
        name="Ghost",
        phones=[],
        addresses=[],
    )
    ok = await update_customer(test_db, fake_customer)
    assert ok is False


@pytest.mark.asyncio
async def test_list_customers(test_db):
    """Test list_customers returns paginated list of Customer objects."""
    for i in range(5):
        await create_customer(
            test_db,
            Customer(
                name=f"Khách hàng {i}",
                phones=[f"090000000{i}"],
                addresses=[f"Địa chỉ {i}"],
            ),
        )

    all_customers = await list_customers(test_db, limit=10, offset=0)
    assert len(all_customers) == 5

    paged = await list_customers(test_db, limit=2, offset=2)
    assert len(paged) == 2
