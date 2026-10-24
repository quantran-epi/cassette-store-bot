import json
from collections.abc import Sequence

import aiosqlite

from src.models.customer import Customer


def _row_to_customer(row: aiosqlite.Row) -> Customer:
    """Convert a database row to Customer domain model."""
    return Customer(
        id=row["id"],
        name=row["name"],
        phones=json.loads(row["phones"]) if isinstance(row["phones"], str) else row["phones"],
        addresses=(
            json.loads(row["addresses"]) if isinstance(row["addresses"], str) else row["addresses"]
        ),
        notes=row["notes"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


async def create_customer(db: aiosqlite.Connection, customer: Customer) -> int:
    """Insert a customer record and return generated ID."""
    cursor = await db.execute(
        """
        INSERT INTO customers (name, phones, addresses, notes)
        VALUES (?, ?, ?, ?)
        """,
        (
            customer.name,
            json.dumps(customer.phones, ensure_ascii=False),
            json.dumps(customer.addresses, ensure_ascii=False),
            customer.notes,
        ),
    )
    await db.commit()
    return cursor.lastrowid  # type: ignore[return-value]


async def get_customer_by_id(db: aiosqlite.Connection, customer_id: int) -> Customer | None:
    """Retrieve customer by primary key ID."""
    async with db.execute("SELECT * FROM customers WHERE id = ?", (customer_id,)) as cursor:
        row = await cursor.fetchone()
        if not row:
            return None
        return _row_to_customer(row)


async def get_customer_by_phone(db: aiosqlite.Connection, phone: str) -> Customer | None:
    """Find a customer whose JSON phones array contains the target phone string."""
    query = """
        SELECT DISTINCT c.*
        FROM customers c, json_each(c.phones) AS p
        WHERE p.value = ?
        LIMIT 1
    """
    async with db.execute(query, (phone,)) as cursor:
        row = await cursor.fetchone()
        if not row:
            return None
        return _row_to_customer(row)


async def update_customer(db: aiosqlite.Connection, customer: Customer) -> bool:
    """Update existing customer details and timestamp. Return True if updated."""
    if customer.id is None:
        return False

    cursor = await db.execute(
        """
        UPDATE customers
        SET name = ?,
            phones = ?,
            addresses = ?,
            notes = ?,
            updated_at = CURRENT_TIMESTAMP
        WHERE id = ?
        """,
        (
            customer.name,
            json.dumps(customer.phones, ensure_ascii=False),
            json.dumps(customer.addresses, ensure_ascii=False),
            customer.notes,
            customer.id,
        ),
    )
    await db.commit()
    return cursor.rowcount > 0


async def list_customers(
    db: aiosqlite.Connection, limit: int = 50, offset: int = 0
) -> Sequence[Customer]:
    """List paginated customers ordered by created_at descending."""
    query = "SELECT * FROM customers ORDER BY created_at DESC LIMIT ? OFFSET ?"
    async with db.execute(query, (limit, offset)) as cursor:
        rows = await cursor.fetchall()
        return [_row_to_customer(row) for row in rows]
