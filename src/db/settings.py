import json
from typing import Any

import aiosqlite


async def get_setting(
    db: aiosqlite.Connection, key: str, default: str | None = None
) -> str | None:
    """Retrieve string setting value by key."""
    async with db.execute("SELECT value FROM system_settings WHERE key = ?", (key,)) as cursor:
        row = await cursor.fetchone()
        return row["value"] if row else default


async def set_setting(
    db: aiosqlite.Connection, key: str, value: str, description: str = ""
) -> None:
    """Insert or update string setting."""
    await db.execute(
        """
        INSERT INTO system_settings (key, value, description, updated_at)
        VALUES (?, ?, ?, CURRENT_TIMESTAMP)
        ON CONFLICT(key) DO UPDATE SET
            value = excluded.value,
            description = excluded.description,
            updated_at = CURRENT_TIMESTAMP
        """,
        (key, value, description),
    )
    await db.commit()


async def get_json_setting(
    db: aiosqlite.Connection, key: str, default: Any = None
) -> Any:
    """Retrieve JSON-deserialized setting by key."""
    val = await get_setting(db, key)
    if val is None:
        return default
    try:
        return json.loads(val)
    except (json.JSONDecodeError, TypeError):
        return default


async def set_json_setting(
    db: aiosqlite.Connection, key: str, value: Any, description: str = ""
) -> None:
    """Serialize and insert/update JSON setting."""
    encoded = json.dumps(value, ensure_ascii=False)
    await set_setting(db, key, encoded, description=description)


async def get_maintenance_mode(db: aiosqlite.Connection) -> bool:
    """Check if maintenance mode is enabled."""
    val = await get_setting(db, "maintenance_mode", default="false")
    return (val or "").strip().lower() == "true"


async def set_maintenance_mode(db: aiosqlite.Connection, enabled: bool) -> None:
    """Set maintenance mode state."""
    await set_setting(
        db,
        "maintenance_mode",
        "true" if enabled else "false",
        description="Bot maintenance mode toggle (pauses chat for non-super-admins)",
    )

