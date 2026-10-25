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

    keys = set(row.keys())
    created_by_user_id = row["created_by_user_id"] if "created_by_user_id" in keys else None
    created_by_name = row["created_by_name"] if "created_by_name" in keys else None

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
        created_by_user_id=created_by_user_id,
        created_by_name=created_by_name,
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
            status, tracking_code, photo_file_ids, raw_text,
            created_by_user_id, created_by_name
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
            order.created_by_user_id,
            order.created_by_name,
        ),
    )
    order_id = cursor.lastrowid
    await db.execute(
        """
        INSERT INTO order_history (order_id, user_id, user_name, action, changes_json)
        VALUES (?, ?, ?, 'CREATE', ?)
        """,
        (
            order_id,
            order.created_by_user_id,
            order.created_by_name,
            json.dumps({"status": order.status.value, "total_amount": order.total_amount}, ensure_ascii=False),
        ),
    )
    await db.commit()
    return order_id  # type: ignore[return-value]


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


async def record_order_history(
    db: aiosqlite.Connection,
    order_id: int,
    user_id: int | None,
    user_name: str | None,
    action: str,
    changes: dict | None = None,
) -> None:
    """Record order audit trail history entry (D-16)."""
    await db.execute(
        """
        INSERT INTO order_history (order_id, user_id, user_name, action, changes_json)
        VALUES (?, ?, ?, ?, ?)
        """,
        (
            order_id,
            user_id,
            user_name,
            action,
            json.dumps(changes or {}, ensure_ascii=False),
        ),
    )
    await db.commit()


ACTIVE_MUTATION_STATUSES = (
    "CHO_LAM",
    "DANG_LAM",
    "DA_DONG_GOI",
    "DA_TAO_DON",
    "SHIPPER_DA_LAY",
)
TERMINAL_MUTATION_STATUSES = ("DA_GIAO", "BOM_HANG", "HUY_DON")


async def find_orders_for_mutation(
    db: aiosqlite.Connection,
    order_id: int | None = None,
    keyword: str | None = None,
    phone: str | None = None,
    limit: int = 5,
) -> list[Order]:
    """Retrieve orders for mutation prioritizing active lifecycle states before completed ones (D-07)."""
    if order_id is not None:
        ord_obj = await get_order_by_id(db, order_id)
        return [ord_obj] if ord_obj else []

    conds: list[str] = []
    params: list[str] = []
    if phone:
        conds.append("customer_phone LIKE ?")
        params.append(f"%{phone.strip()}%")
    elif keyword:
        from src.db.connection import remove_accents
        kw_clean = remove_accents(keyword.strip())
        conds.append(
            "(unaccent(customer_name) LIKE ? OR unaccent(shipping_address) LIKE ? OR customer_phone LIKE ?)"
        )
        params.extend([f"%{kw_clean}%", f"%{kw_clean}%", f"%{kw_clean}%"])

    where_filter = f"AND ({' AND '.join(conds)})" if conds else ""

    # 1. Fetch active orders
    placeholders_active = ",".join(f"'{s}'" for s in ACTIVE_MUTATION_STATUSES)
    active_query = f"""
        SELECT * FROM orders
        WHERE status IN ({placeholders_active}) {where_filter}
        ORDER BY created_at DESC, id DESC
        LIMIT ?
    """
    async with db.execute(active_query, (*params, limit)) as cursor:
        active_rows = await cursor.fetchall()
        results = [_row_to_order(r) for r in active_rows]

    # 2. If fewer than limit, backfill with terminal orders
    remaining = limit - len(results)
    if remaining > 0:
        placeholders_term = ",".join(f"'{s}'" for s in TERMINAL_MUTATION_STATUSES)
        term_query = f"""
            SELECT * FROM orders
            WHERE status IN ({placeholders_term}) {where_filter}
            ORDER BY created_at DESC, id DESC
            LIMIT ?
        """
        async with db.execute(term_query, (*params, remaining)) as cursor:
            term_rows = await cursor.fetchall()
            results.extend([_row_to_order(r) for r in term_rows])

    return results


async def mutate_order_with_lock(
    db: aiosqlite.Connection,
    order_id: int,
    expected_updated_at: str | None,
    delta_dict: dict,
    user_id: int | None = None,
    user_name: str | None = None,
) -> tuple[bool, dict | None, Order | None]:
    """Execute atomic order mutation with optimistic lock WHERE id=? AND updated_at=? (D-15, D-16, D-17)."""
    # 1. Fetch current order row
    async with db.execute("SELECT * FROM orders WHERE id = ?", (order_id,)) as cursor:
        row = await cursor.fetchone()
        if not row:
            return False, None, None

    # 2. Compare updated_at
    current_updated_at_str = str(row["updated_at"] or "")
    expected_updated_at_str = str(expected_updated_at or "")

    if current_updated_at_str != expected_updated_at_str:
        # Conflict! Read latest history record per D-17
        async with db.execute(
            "SELECT * FROM order_history WHERE order_id = ? ORDER BY id DESC LIMIT 1",
            (order_id,),
        ) as h_cur:
            last_change = await h_cur.fetchone()
            hist_dict = dict(last_change) if last_change else {}
            if "changes_json" in hist_dict and isinstance(hist_dict["changes_json"], str):
                try:
                    hist_dict["changes"] = json.loads(hist_dict["changes_json"])
                except Exception:
                    hist_dict["changes"] = {}
            return False, hist_dict, _row_to_order(row)

    # 3. Dynamic UPDATE building
    row_keys = set(row.keys())
    fields: list[str] = []
    params: list = []
    changes: dict = {}

    for col, new_val in delta_dict.items():
        # Handle field renaming or mapping
        target_col = col
        if col.startswith("new_"):
            target_col = col[4:]

        if target_col in row_keys:
            # Handle enum to string conversion
            val_to_save = new_val.value if hasattr(new_val, "value") else new_val
            current_val = row[target_col]
            if current_val != val_to_save:
                fields.append(f"{target_col} = ?")
                params.append(val_to_save)
                changes[target_col] = {"old": current_val, "new": val_to_save}

    if not fields:
        # No actual fields changed
        return True, {}, _row_to_order(row)

    fields.append("updated_at = strftime('%Y-%m-%d %H:%M:%f', 'now')")
    sql = f"UPDATE orders SET {', '.join(fields)} WHERE id = ? AND updated_at = ?"
    params.extend([order_id, row["updated_at"]])

    cursor = await db.execute(sql, params)
    if cursor.rowcount == 0:
        # Concurrency race right between select and update
        async with db.execute(
            "SELECT * FROM order_history WHERE order_id = ? ORDER BY id DESC LIMIT 1",
            (order_id,),
        ) as h_cur:
            last_change = await h_cur.fetchone()
            hist_dict = dict(last_change) if last_change else {}
        fresh = await get_order_by_id(db, order_id)
        return False, hist_dict, fresh

    # 4. Insert audit record into order_history
    await db.execute(
        """
        INSERT INTO order_history (order_id, user_id, user_name, action, changes_json)
        VALUES (?, ?, ?, 'MUTATE', ?)
        """,
        (order_id, user_id, user_name, json.dumps(changes, ensure_ascii=False)),
    )
    await db.commit()

    fresh_order = await get_order_by_id(db, order_id)
    return True, changes, fresh_order

