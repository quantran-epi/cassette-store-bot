from collections.abc import Sequence
from datetime import datetime, timedelta, timezone

import aiosqlite

from src.models.milestone import MilestonePeriod, MilestoneRule, MilestoneTargetType

TZ_VN = timezone(timedelta(hours=7))


def get_current_period_key(period: MilestonePeriod, dt: datetime | None = None) -> str:
    """Derive deterministic period key for deduplication in VN timezone."""
    now_vn = dt if dt is not None else datetime.now(TZ_VN)
    if period == MilestonePeriod.WEEK:
        return now_vn.strftime("%Y-%W")
    if period == MilestonePeriod.MONTH:
        return now_vn.strftime("%Y-%m")
    if period == MilestonePeriod.YEAR:
        return now_vn.strftime("%Y")
    return "all"


def _row_to_rule(row: aiosqlite.Row) -> MilestoneRule:
    """Convert database row to MilestoneRule domain model."""
    return MilestoneRule(
        id=row["id"],
        period=MilestonePeriod(row["period"]),
        target_type=MilestoneTargetType(row["target_type"]),
        target_value=int(row["target_value"]),
        only_delivered=bool(row["only_delivered"]),
        message_template=row["message_template"],
        effect_enabled=bool(row["effect_enabled"]),
        is_active=bool(row["is_active"]),
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


async def create_milestone_rule(db: aiosqlite.Connection, rule: MilestoneRule) -> int:
    """Insert a new milestone rule and return generated ID."""
    cursor = await db.execute(
        """
        INSERT INTO milestone_rules (
            period, target_type, target_value, only_delivered,
            message_template, effect_enabled, is_active
        ) VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (
            rule.period.value,
            rule.target_type.value,
            rule.target_value,
            1 if rule.only_delivered else 0,
            rule.message_template,
            1 if rule.effect_enabled else 0,
            1 if rule.is_active else 0,
        ),
    )
    await db.commit()
    return cursor.lastrowid  # type: ignore[return-value]


async def get_milestone_rule_by_id(
    db: aiosqlite.Connection, rule_id: int
) -> MilestoneRule | None:
    """Retrieve milestone rule by ID."""
    async with db.execute(
        "SELECT * FROM milestone_rules WHERE id = ?", (rule_id,)
    ) as cursor:
        row = await cursor.fetchone()
        return _row_to_rule(row) if row else None


async def list_milestone_rules(
    db: aiosqlite.Connection, active_only: bool = False
) -> Sequence[MilestoneRule]:
    """List milestone rules ordered by period, target_type, target_value."""
    query = "SELECT * FROM milestone_rules"
    if active_only:
        query += " WHERE is_active = 1"
    query += " ORDER BY period ASC, target_type ASC, target_value ASC, id ASC"

    async with db.execute(query) as cursor:
        rows = await cursor.fetchall()
        return [_row_to_rule(row) for row in rows]


async def update_milestone_rule(
    db: aiosqlite.Connection, rule: MilestoneRule
) -> bool:
    """Update milestone rule fields."""
    if not rule.id:
        return False
    cursor = await db.execute(
        """
        UPDATE milestone_rules
        SET period = ?,
            target_type = ?,
            target_value = ?,
            only_delivered = ?,
            message_template = ?,
            effect_enabled = ?,
            is_active = ?,
            updated_at = CURRENT_TIMESTAMP
        WHERE id = ?
        """,
        (
            rule.period.value,
            rule.target_type.value,
            rule.target_value,
            1 if rule.only_delivered else 0,
            rule.message_template,
            1 if rule.effect_enabled else 0,
            1 if rule.is_active else 0,
            rule.id,
        ),
    )
    await db.commit()
    return cursor.rowcount > 0


async def toggle_milestone_rule_active(
    db: aiosqlite.Connection, rule_id: int
) -> bool:
    """Toggle is_active state of a rule."""
    cursor = await db.execute(
        """
        UPDATE milestone_rules
        SET is_active = CASE WHEN is_active = 1 THEN 0 ELSE 1 END,
            updated_at = CURRENT_TIMESTAMP
        WHERE id = ?
        """,
        (rule_id,),
    )
    await db.commit()
    return cursor.rowcount > 0


async def delete_milestone_rule(db: aiosqlite.Connection, rule_id: int) -> bool:
    """Delete a milestone rule and its cascade logs."""
    cursor = await db.execute(
        "DELETE FROM milestone_rules WHERE id = ?", (rule_id,)
    )
    await db.commit()
    return cursor.rowcount > 0


async def has_milestone_triggered(
    db: aiosqlite.Connection, rule_id: int, period_key: str
) -> bool:
    """Check if rule has already triggered in specified period cycle."""
    async with db.execute(
        "SELECT 1 FROM milestone_logs WHERE rule_id = ? AND period_key = ?",
        (rule_id, period_key),
    ) as cursor:
        row = await cursor.fetchone()
        return row is not None


async def record_milestone_trigger(
    db: aiosqlite.Connection, rule_id: int, period_key: str, current_value: int
) -> bool:
    """Record milestone trigger. Returns True if inserted, False if already logged."""
    try:
        await db.execute(
            """
            INSERT INTO milestone_logs (rule_id, period_key, current_value)
            VALUES (?, ?, ?)
            """,
            (rule_id, period_key, current_value),
        )
        await db.commit()
        return True
    except aiosqlite.IntegrityError:
        return False


async def get_milestone_metric_value(
    db: aiosqlite.Connection,
    period: MilestonePeriod,
    target_type: MilestoneTargetType,
    only_delivered: bool,
    dt: datetime | None = None,
) -> int:
    """Query current aggregated metric value from orders table."""
    status_clause = (
        "status = 'DA_GIAO'"
        if only_delivered
        else "status NOT IN ('BOM_HANG', 'HUY_DON')"
    )
    metric_expr = (
        "COUNT(*)"
        if target_type == MilestoneTargetType.ORDER_COUNT
        else "COALESCE(SUM(total_amount), 0)"
    )

    period_key = get_current_period_key(period, dt)
    if period == MilestonePeriod.ALL_TIME:
        query = f"SELECT {metric_expr} FROM orders WHERE {status_clause}"
        params: tuple = ()
    elif period == MilestonePeriod.YEAR:
        query = (
            f"SELECT {metric_expr} FROM orders "
            f"WHERE {status_clause} AND strftime('%Y', created_at, '+7 hours') = ?"
        )
        params = (period_key,)
    elif period == MilestonePeriod.MONTH:
        query = (
            f"SELECT {metric_expr} FROM orders "
            f"WHERE {status_clause} AND strftime('%Y-%m', created_at, '+7 hours') = ?"
        )
        params = (period_key,)
    elif period == MilestonePeriod.WEEK:
        query = (
            f"SELECT {metric_expr} FROM orders "
            f"WHERE {status_clause} AND strftime('%Y-%W', created_at, '+7 hours') = ?"
        )
        params = (period_key,)
    else:
        return 0

    async with db.execute(query, params) as cursor:
        row = await cursor.fetchone()
        return int(row[0]) if (row and row[0] is not None) else 0
