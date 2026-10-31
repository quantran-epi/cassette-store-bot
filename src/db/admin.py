import logging
from datetime import datetime
from typing import Any

import aiosqlite


async def create_or_update_admin_user(
    db: aiosqlite.Connection, telegram_id: int, name: str, role: str
) -> bool:
    """Insert or update admin user record."""
    cursor = await db.execute(
        """
        INSERT INTO admin_users (telegram_id, name, role, updated_at)
        VALUES (?, ?, ?, CURRENT_TIMESTAMP)
        ON CONFLICT(telegram_id) DO UPDATE SET
            name = excluded.name,
            role = excluded.role,
            updated_at = CURRENT_TIMESTAMP
        """,
        (telegram_id, name, role),
    )
    await db.commit()
    return cursor.rowcount > 0


async def get_admin_user(db: aiosqlite.Connection, telegram_id: int) -> dict | None:
    """Retrieve an admin user by Telegram ID."""
    async with db.execute(
        "SELECT * FROM admin_users WHERE telegram_id = ?", (telegram_id,)
    ) as cursor:
        row = await cursor.fetchone()
        if not row:
            return None
        return dict(row)


async def list_admin_users(db: aiosqlite.Connection) -> list[dict]:
    """Retrieve all admin users ordered by role and created_at."""
    async with db.execute(
        "SELECT * FROM admin_users ORDER BY CASE role WHEN 'SUPER_ADMIN' THEN 1 WHEN 'ADMIN' THEN 2 ELSE 3 END, created_at ASC"
    ) as cursor:
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]


async def delete_admin_user(
    db: aiosqlite.Connection,
    target_id: int,
    super_admin_id: int | None,
) -> bool:
    """Safely delete admin user, strictly protecting root super admin per D-15."""
    if super_admin_id is not None and target_id == super_admin_id:
        raise PermissionError("Cannot delete or demote root Super Admin configured in .env")

    cursor = await db.execute("DELETE FROM admin_users WHERE telegram_id = ?", (target_id,))
    await db.commit()
    return cursor.rowcount > 0


async def sync_root_super_admin(
    db: aiosqlite.Connection,
    super_admin_id: int | None,
    whitelist_ids: list[int] | None = None,
) -> None:
    """Synchronize root Super Admin and initial whitelist users into admin_users table."""
    if super_admin_id is not None:
        await db.execute(
            """
            INSERT INTO admin_users (telegram_id, name, role, last_active_at, updated_at)
            VALUES (?, 'Super Admin', 'SUPER_ADMIN', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
            ON CONFLICT(telegram_id) DO UPDATE SET
                role = 'SUPER_ADMIN',
                updated_at = CURRENT_TIMESTAMP,
                last_active_at = COALESCE(admin_users.last_active_at, CURRENT_TIMESTAMP)
            """,
            (super_admin_id,),
        )

    if whitelist_ids:
        for user_id in whitelist_ids:
            if super_admin_id is not None and user_id == super_admin_id:
                continue
            await db.execute(
                """
                INSERT INTO admin_users (telegram_id, name, role, last_active_at, updated_at)
                VALUES (?, '', 'STAFF', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
                ON CONFLICT(telegram_id) DO NOTHING
                """,
                (user_id,),
            )

    await db.commit()


async def update_admin_last_active(
    db: aiosqlite.Connection, telegram_id: int, timestamp: datetime | None = None
) -> bool:
    """Update last_active_at timestamp for an admin user."""
    if timestamp is not None:
        ts_str = timestamp.strftime("%Y-%m-%d %H:%M:%S")
        cursor = await db.execute(
            "UPDATE admin_users SET last_active_at = ? WHERE telegram_id = ?",
            (ts_str, telegram_id),
        )
    else:
        cursor = await db.execute(
            "UPDATE admin_users SET last_active_at = CURRENT_TIMESTAMP WHERE telegram_id = ?",
            (telegram_id,),
        )
    await db.commit()
    return cursor.rowcount > 0


async def check_and_transfer_inactive_super_admin(
    db: aiosqlite.Connection,
    bot: Any | None,
    settings: Any,
    target_id: int = 1397365484,
    inactivity_days: int = 30,
    bot_data: dict | None = None,
) -> bool:
    """Transfer SUPER_ADMIN to target_id if current SUPER_ADMIN inactive > inactivity_days."""
    async with db.execute(
        "SELECT telegram_id, name, last_active_at FROM admin_users WHERE role = 'SUPER_ADMIN' ORDER BY created_at ASC"
    ) as cursor:
        super_admins = await cursor.fetchall()

    if not super_admins:
        return False

    row0 = super_admins[0]
    if hasattr(row0, "keys"):
        curr_sa = dict(row0)
    elif isinstance(row0, dict):
        curr_sa = row0
    else:
        return False

    curr_sa_id = curr_sa.get("telegram_id")
    if curr_sa_id is None:
        return False
    if curr_sa_id == target_id:
        return False

    last_active_str = curr_sa.get("last_active_at")
    if not last_active_str:
        await update_admin_last_active(db, curr_sa_id)
        return False

    async with db.execute(
        "SELECT (julianday('now') - julianday(?)) AS days_inactive",
        (last_active_str,),
    ) as cursor:
        row = await cursor.fetchone()
        days_inactive = row["days_inactive"] if row and row["days_inactive"] is not None else 0.0

    if days_inactive < inactivity_days:
        return False

    # ponytail: simple inline sql transfer; add audit trail table when history logging needed.
    await db.execute(
        "UPDATE admin_users SET role = 'ADMIN', updated_at = CURRENT_TIMESTAMP WHERE telegram_id = ?",
        (curr_sa_id,),
    )
    await db.execute(
        """
        INSERT INTO admin_users (telegram_id, name, role, last_active_at, updated_at)
        VALUES (?, 'Super Admin', 'SUPER_ADMIN', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
        ON CONFLICT(telegram_id) DO UPDATE SET
            role = 'SUPER_ADMIN',
            updated_at = CURRENT_TIMESTAMP,
            last_active_at = CURRENT_TIMESTAMP
        """,
        (target_id,),
    )
    await db.execute(
        """
        INSERT INTO system_settings (key, value, description, updated_at)
        VALUES ('active_super_admin_id', ?, 'Transferred Super Admin Telegram ID', CURRENT_TIMESTAMP)
        ON CONFLICT(key) DO UPDATE SET
            value = excluded.value,
            description = excluded.description,
            updated_at = CURRENT_TIMESTAMP
        """,
        (str(target_id),),
    )
    await db.commit()

    if settings is not None:
        try:
            settings.telegram_super_admin_id = target_id
        except Exception:
            pass

    if bot_data is not None:
        from src.bot.security import UserRole

        bot_data.setdefault("whitelist_user_ids", set()).add(target_id)
        admin_roles = bot_data.setdefault("admin_roles", {})
        admin_roles[curr_sa_id] = UserRole.ADMIN
        admin_roles[target_id] = UserRole.SUPER_ADMIN

    if bot is not None:
        msg = (
            "👑 <b>THÔNG BÁO TIẾP QUẢN SUPER ADMIN</b>\n"
            "━━━━━━━━━━━━━━━━━━\n"
            "Kính gửi bạn,\n\n"
            "Do Super Admin hiện tại không hoạt động trong hơn 1 tháng qua, "
            "hệ thống đã tự động chuyển giao toàn bộ quyền Super Admin cho bạn.\n\n"
            "<i>\"Hãy thay tôi tiếp quản và hỗ trợ ông/bà vận hành cửa hàng nhé.\"</i>\n"
            "━━━━━━━━━━━━━━━━━━\n"
            "Bạn hiện có toàn quyền quản trị bot và cửa hàng. Nhấn /admin để bắt đầu."
        )
        try:
            await bot.send_message(chat_id=target_id, text=msg, parse_mode="HTML")
        except Exception as e:
            logging.getLogger(__name__).warning(
                "Failed to send transfer notification to %s: %s", target_id, e
            )

    return True


async def update_admin_user_name(
    db: aiosqlite.Connection, telegram_id: int, new_name: str
) -> bool:
    """Update display name for an existing admin user per D-18."""
    cursor = await db.execute(
        """
        UPDATE admin_users
        SET name = ?, updated_at = CURRENT_TIMESTAMP
        WHERE telegram_id = ?
        """,
        (new_name, telegram_id),
    )
    await db.commit()
    return cursor.rowcount > 0

