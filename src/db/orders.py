import asyncio
import json
from collections.abc import Sequence

import aiosqlite

from src.models.order import Order, OrderStatus

_order_photo_locks: dict[int, asyncio.Lock] = {}


def _row_to_order(row: aiosqlite.Row) -> Order:
    """Convert database row to Order domain model."""
    photos = row["photo_file_ids"]
    if isinstance(photos, str):
        try:
            photos = json.loads(photos)
        except json.JSONDecodeError:
            photos = []

    return Order(
        id=row["id"],
        customer_id=row["customer_id"],
        customer_name=row["customer_name"],
        customer_phone=row["customer_phone"],
        shipping_address=row["shipping_address"],
        items_text=row["items_text"],
        total_amount=row["total_amount"],
        cod_amount=row["cod_amount"],
        payment_method=row["payment_method"],
        status=OrderStatus(row["status"]),
        tracking_code=row["tracking_code"],
        photo_file_ids=photos,
        raw_text=row["raw_text"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


async def create_order(db: aiosqlite.Connection, order: Order) -> int:
    """Insert order record storing snapshot and return generated ID."""
    cursor = await db.execute(
        """
        INSERT INTO orders (
            customer_id, customer_name, customer_phone, shipping_address,
            items_text, total_amount, cod_amount, payment_method,
            status, tracking_code, photo_file_ids, raw_text
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            order.customer_id,
            order.customer_name,
            order.customer_phone,
            order.shipping_address,
            order.items_text,
            order.total_amount,
            order.cod_amount,
            order.payment_method,
            order.status.value,
            order.tracking_code,
            json.dumps(order.photo_file_ids, ensure_ascii=False),
            order.raw_text,
        ),
    )
    await db.commit()
    return cursor.lastrowid  # type: ignore[return-value]


async def get_order_by_id(db: aiosqlite.Connection, order_id: int) -> Order | None:
    """Retrieve order by ID."""
    async with db.execute("SELECT * FROM orders WHERE id = ?", (order_id,)) as cursor:
        row = await cursor.fetchone()
        if not row:
            return None
        return _row_to_order(row)


async def update_order_status(
    db: aiosqlite.Connection, order_id: int, new_status: OrderStatus
) -> bool:
    """Update order status and updated_at timestamp."""
    cursor = await db.execute(
        """
        UPDATE orders
        SET status = ?,
            updated_at = CURRENT_TIMESTAMP
        WHERE id = ?
        """,
        (new_status.value, order_id),
    )
    await db.commit()
    return cursor.rowcount > 0


async def update_order_tracking(
    db: aiosqlite.Connection, order_id: int, tracking_code: str
) -> bool:
    """Update order tracking code and updated_at timestamp."""
    cursor = await db.execute(
        """
        UPDATE orders
        SET tracking_code = ?,
            updated_at = CURRENT_TIMESTAMP
        WHERE id = ?
        """,
        (tracking_code, order_id),
    )
    await db.commit()
    return cursor.rowcount > 0


async def append_order_photos(
    db: aiosqlite.Connection, order_id: int, new_photo_ids: list[str]
) -> bool:
    """Append new photo file_ids to existing JSON array atomically using per-order lock."""
    if not new_photo_ids:
        return True

    lock = _order_photo_locks.setdefault(order_id, asyncio.Lock())
    async with lock:
        order = await get_order_by_id(db, order_id)
        if not order:
            return False

        combined = list(order.photo_file_ids) + list(new_photo_ids)
        cursor = await db.execute(
            """
            UPDATE orders
            SET photo_file_ids = ?,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (json.dumps(combined, ensure_ascii=False), order_id),
        )
        await db.commit()
        return cursor.rowcount > 0


async def list_orders_by_date(
    db: aiosqlite.Connection,
    date_str: str,
    limit: int = 5,
    offset: int = 0,
) -> Sequence[Order]:
    """List orders created on a given date (UTC+7) ordered by created_at DESC, id DESC."""
    query = """
        SELECT * FROM orders
        WHERE date(created_at, '+7 hours') = ?
        ORDER BY created_at DESC, id DESC
        LIMIT ? OFFSET ?
    """
    async with db.execute(query, (date_str, limit, offset)) as cursor:
        rows = await cursor.fetchall()
        return [_row_to_order(row) for row in rows]


async def count_orders_by_date(db: aiosqlite.Connection, date_str: str) -> int:
    """Count total orders created on a given date (UTC+7)."""
    query = "SELECT COUNT(*) FROM orders WHERE date(created_at, '+7 hours') = ?"
    async with db.execute(query, (date_str,)) as cursor:
        row = await cursor.fetchone()
        return int(row[0]) if row else 0


async def list_orders_by_status(
    db: aiosqlite.Connection,
    status: OrderStatus,
    limit: int = 50,
    offset: int = 0,
) -> Sequence[Order]:
    """List orders with matching status ordered by created_at descending."""
    query = """
        SELECT * FROM orders
        WHERE status = ?
        ORDER BY created_at DESC
        LIMIT ? OFFSET ?
    """
    async with db.execute(query, (status.value, limit, offset)) as cursor:
        rows = await cursor.fetchall()
        return [_row_to_order(row) for row in rows]


async def get_customer_order_stats(
    db: aiosqlite.Connection, customer_id: int
) -> dict[str, int]:
    """Retrieve customer lifetime order count, total spend, and BOM_HANG count."""
    query = """
        SELECT
            COUNT(*) AS total_orders,
            COALESCE(SUM(CASE WHEN status != 'HUY_DON' THEN total_amount ELSE 0 END), 0) AS total_spent,
            COUNT(CASE WHEN status = 'BOM_HANG' THEN 1 END) AS bom_count
        FROM orders
        WHERE customer_id = ?
    """
    async with db.execute(query, (customer_id,)) as cursor:
        row = await cursor.fetchone()
        if not row:
            return {"total_orders": 0, "total_spent": 0, "bom_count": 0}
        return {
            "total_orders": row["total_orders"],
            "total_spent": row["total_spent"],
            "bom_count": row["bom_count"],
        }

