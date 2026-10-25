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
            INSERT INTO admin_users (telegram_id, name, role, updated_at)
            VALUES (?, 'Super Admin', 'SUPER_ADMIN', CURRENT_TIMESTAMP)
            ON CONFLICT(telegram_id) DO UPDATE SET
                role = 'SUPER_ADMIN',
                updated_at = CURRENT_TIMESTAMP
            """,
            (super_admin_id,),
        )

    if whitelist_ids:
        for user_id in whitelist_ids:
            if super_admin_id is not None and user_id == super_admin_id:
                continue
            await db.execute(
                """
                INSERT INTO admin_users (telegram_id, name, role, updated_at)
                VALUES (?, '', 'STAFF', CURRENT_TIMESTAMP)
                ON CONFLICT(telegram_id) DO NOTHING
                """,
                (user_id,),
            )

    await db.commit()
