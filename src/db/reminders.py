from datetime import datetime
from zoneinfo import ZoneInfo

import aiosqlite

from src.models.reminder import Reminder, ReminderStatus

VN_TZ = ZoneInfo("Asia/Ho_Chi_Minh")


def _row_to_reminder(row: aiosqlite.Row) -> Reminder:
    return Reminder(
        id=row["id"],
        order_id=row["order_id"],
        remind_at=row["remind_at"],
        reminder_text=row["reminder_text"],
        status=ReminderStatus(row["status"]),
        created_by_user_id=row["created_by_user_id"],
        created_at=row["created_at"],
        sent_at=row["sent_at"],
    )


async def create_reminder(
    db: aiosqlite.Connection, reminder: Reminder, supersede_existing: bool = True
) -> int:
    """Insert a new reminder record, optionally superseding previous pending reminders for this order."""
    if supersede_existing:
        await db.execute(
            "UPDATE reminders SET status = 'CANCELLED' WHERE order_id = ? AND status = 'PENDING'",
            (reminder.order_id,),
        )

    remind_at_val = (
        reminder.remind_at.isoformat()
        if isinstance(reminder.remind_at, datetime)
        else str(reminder.remind_at)
    )
    cursor = await db.execute(
        """
        INSERT INTO reminders (order_id, remind_at, reminder_text, status, created_by_user_id)
        VALUES (?, ?, ?, ?, ?)
        """,
        (
            reminder.order_id,
            remind_at_val,
            reminder.reminder_text,
            reminder.status.value if isinstance(reminder.status, ReminderStatus) else reminder.status,
            reminder.created_by_user_id,
        ),
    )
    await db.commit()
    return cursor.lastrowid or 0


async def get_reminder_by_id(db: aiosqlite.Connection, reminder_id: int) -> Reminder | None:
    """Retrieve reminder by id."""
    async with db.execute("SELECT * FROM reminders WHERE id = ?", (reminder_id,)) as cursor:
        row = await cursor.fetchone()
        if not row:
            return None
        return _row_to_reminder(row)


async def get_reminders_by_order_id(
    db: aiosqlite.Connection, order_id: int, include_sent: bool = False
) -> list[Reminder]:
    """Retrieve reminders associated with an order."""
    query = "SELECT * FROM reminders WHERE order_id = ?"
    params: list = [order_id]
    if not include_sent:
        query += " AND status = 'PENDING'"
    query += " ORDER BY remind_at ASC"

    async with db.execute(query, params) as cursor:
        rows = await cursor.fetchall()
        return [_row_to_reminder(row) for row in rows]


async def get_due_reminders(
    db: aiosqlite.Connection, now_iso: str | None = None
) -> list[dict]:
    """Retrieve all pending reminders where remind_at <= now, joining order details."""
    if now_iso is None:
        now_iso = datetime.now(VN_TZ).strftime("%Y-%m-%d %H:%M:%S")

    query = """
        SELECT
            r.id AS reminder_id,
            r.order_id,
            r.remind_at,
            r.reminder_text,
            r.status AS reminder_status,
            r.created_by_user_id,
            o.customer_name,
            o.customer_phone,
            o.shipping_address,
            o.items_text,
            o.total_amount,
            o.status AS order_status
        FROM reminders r
        LEFT JOIN orders o ON r.order_id = o.id
        WHERE r.status = 'PENDING' AND r.remind_at <= ?
        ORDER BY r.remind_at ASC
    """
    async with db.execute(query, (now_iso,)) as cursor:
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]


async def mark_reminder_sent(db: aiosqlite.Connection, reminder_id: int) -> bool:
    """Mark reminder as SENT."""
    cursor = await db.execute(
        """
        UPDATE reminders
        SET status = 'SENT', sent_at = CURRENT_TIMESTAMP
        WHERE id = ?
        """,
        (reminder_id,),
    )
    await db.commit()
    return cursor.rowcount > 0


async def cancel_reminder(db: aiosqlite.Connection, reminder_id: int) -> bool:
    """Cancel a pending reminder."""
    cursor = await db.execute(
        """
        UPDATE reminders
        SET status = 'CANCELLED'
        WHERE id = ? AND status = 'PENDING'
        """,
        (reminder_id,),
    )
    await db.commit()
    return cursor.rowcount > 0


async def cancel_reminders_by_order_id(db: aiosqlite.Connection, order_id: int) -> bool:
    """Cancel all pending reminders for an order."""
    cursor = await db.execute(
        """
        UPDATE reminders
        SET status = 'CANCELLED'
        WHERE order_id = ? AND status = 'PENDING'
        """,
        (order_id,),
    )
    await db.commit()
    return cursor.rowcount > 0
