import aiosqlite
import pytest

from src.db.admin import (
    create_or_update_admin_user,
    delete_admin_user,
    get_admin_user,
    list_admin_users,
    sync_root_super_admin,
)
from src.db.schema import init_db
from src.db.settings import (
    get_json_setting,
    get_setting,
    set_json_setting,
    set_setting,
)


@pytest.fixture
async def in_memory_db():
    """Create in-memory SQLite database initialized with schema."""
    db = await aiosqlite.connect(":memory:")
    db.row_factory = aiosqlite.Row
    await init_db(db)
    yield db
    await db.close()


@pytest.mark.asyncio
async def test_init_db_creates_admin_and_settings_tables(in_memory_db):
    """Verify admin_users and system_settings tables are created with proper constraints."""
    async with in_memory_db.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name IN ('admin_users', 'system_settings')"
    ) as cursor:
        rows = await cursor.fetchall()
        table_names = {row["name"] for row in rows}
        assert "admin_users" in table_names
        assert "system_settings" in table_names

    # Test role CHECK constraint in admin_users
    with pytest.raises(aiosqlite.IntegrityError):
        await in_memory_db.execute(
            "INSERT INTO admin_users (telegram_id, name, role) VALUES (?, ?, ?)",
            (111, "Hacker", "INVALID_ROLE"),
        )
        await in_memory_db.commit()


@pytest.mark.asyncio
async def test_sync_root_super_admin(in_memory_db):
    """Verify sync_root_super_admin registers root super admin and whitelist users."""
    root_id = 999999
    whitelist_ids = [999999, 123456, 789012]

    await sync_root_super_admin(in_memory_db, super_admin_id=root_id, whitelist_ids=whitelist_ids)

    # Check root super admin
    root = await get_admin_user(in_memory_db, root_id)
    assert root is not None
    assert root["role"] == "SUPER_ADMIN"
    assert root["name"] == "Super Admin"

    # Check whitelist users created as STAFF if not exists
    user1 = await get_admin_user(in_memory_db, 123456)
    assert user1 is not None
    assert user1["role"] == "STAFF"

    all_users = await list_admin_users(in_memory_db)
    assert len(all_users) == 3


@pytest.mark.asyncio
async def test_delete_admin_user_root_protection(in_memory_db):
    """Verify root super admin cannot be deleted and raises PermissionError per D-15."""
    root_id = 999999
    staff_id = 123456

    await create_or_update_admin_user(in_memory_db, root_id, "Super Admin", "SUPER_ADMIN")
    await create_or_update_admin_user(in_memory_db, staff_id, "Staff 1", "STAFF")

    # Attempt to delete root super admin must raise PermissionError
    with pytest.raises(PermissionError, match="Cannot delete or demote root Super Admin"):
        await delete_admin_user(in_memory_db, target_id=root_id, super_admin_id=root_id)

    # Non-root deletion succeeds
    deleted = await delete_admin_user(in_memory_db, target_id=staff_id, super_admin_id=root_id)
    assert deleted is True

    staff = await get_admin_user(in_memory_db, staff_id)
    assert staff is None


@pytest.mark.asyncio
async def test_create_or_update_admin_user(in_memory_db):
    """Verify upsert operation for admin_users."""
    telegram_id = 456789

    # Insert
    created = await create_or_update_admin_user(in_memory_db, telegram_id, "Alex", "ADMIN")
    assert created is True

    user = await get_admin_user(in_memory_db, telegram_id)
    assert user is not None
    assert user["name"] == "Alex"
    assert user["role"] == "ADMIN"

    # Update role and name
    updated = await create_or_update_admin_user(in_memory_db, telegram_id, "Alex V2", "SUPER_ADMIN")
    assert updated is True

    user_v2 = await get_admin_user(in_memory_db, telegram_id)
    assert user_v2["name"] == "Alex V2"
    assert user_v2["role"] == "SUPER_ADMIN"


@pytest.mark.asyncio
async def test_settings_crud(in_memory_db):
    """Verify key-value and JSON setting persistence."""
    # Plain text setting
    val = await get_setting(in_memory_db, "active_model_id")
    assert val is None

    await set_setting(in_memory_db, "active_model_id", "gpt-4o-mini", description="Active LLM model")
    val = await get_setting(in_memory_db, "active_model_id")
    assert val == "gpt-4o-mini"

    # JSON setting
    models = ["gpt-4o-mini", "claude-3-5-haiku", "gemini-1.5-flash"]
    await set_json_setting(in_memory_db, "available_models", models, description="Allowed models list")

    loaded_models = await get_json_setting(in_memory_db, "available_models")
    assert loaded_models == models

    # Fallback default
    default_res = await get_json_setting(in_memory_db, "non_existent_key", default=["default_val"])
    assert default_res == ["default_val"]
