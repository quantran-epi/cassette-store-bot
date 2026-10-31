from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import aiosqlite
import pytest

from src.bot.app import _do_sync, inactivity_checker_job_callback
from src.bot.security import UserRole, whitelist_gate
from src.config import Settings
from src.db.admin import (
    check_and_transfer_inactive_super_admin,
    create_or_update_admin_user,
    get_admin_user,
    sync_root_super_admin,
    update_admin_last_active,
)
from src.db.schema import init_db
from src.db.settings import get_setting


@pytest.fixture
async def in_memory_db():
    """Create in-memory SQLite database initialized with schema."""
    db = await aiosqlite.connect(":memory:")
    db.row_factory = aiosqlite.Row
    await init_db(db)
    yield db
    await db.close()


@pytest.mark.asyncio
async def test_admin_users_schema_has_last_active_at(in_memory_db):
    """Verify admin_users table contains last_active_at column."""
    async with in_memory_db.execute("PRAGMA table_info(admin_users);") as cursor:
        cols = {row["name"] for row in await cursor.fetchall()}
        assert "last_active_at" in cols


@pytest.mark.asyncio
async def test_update_admin_last_active(in_memory_db):
    """Verify update_admin_last_active updates last_active_at timestamp."""
    user_id = 999
    await create_or_update_admin_user(in_memory_db, user_id, "Admin 1", "SUPER_ADMIN")

    custom_time = datetime(2025, 1, 15, 10, 30, 0)
    ok = await update_admin_last_active(in_memory_db, user_id, timestamp=custom_time)
    assert ok is True

    user = await get_admin_user(in_memory_db, user_id)
    assert user is not None
    assert user["last_active_at"] == "2025-01-15 10:30:00"

    # Update with default CURRENT_TIMESTAMP
    ok_now = await update_admin_last_active(in_memory_db, user_id)
    assert ok_now is True
    user_now = await get_admin_user(in_memory_db, user_id)
    assert user_now["last_active_at"] != "2025-01-15 10:30:00"


@pytest.mark.asyncio
async def test_transfer_super_admin_after_30_days_inactivity(in_memory_db):
    """Verify super admin is transferred to 1397365484 if inactive > 30 days."""
    old_sa_id = 888888
    target_id = 1397365484

    await sync_root_super_admin(in_memory_db, super_admin_id=old_sa_id)

    # Simulate inactive for 35 days
    past_time = datetime.now() - timedelta(days=35)
    await update_admin_last_active(in_memory_db, old_sa_id, timestamp=past_time)

    mock_bot = MagicMock()
    mock_bot.send_message = AsyncMock()

    settings = MagicMock()
    settings.telegram_super_admin_id = old_sa_id

    bot_data = {
        "whitelist_user_ids": {old_sa_id},
        "admin_roles": {old_sa_id: UserRole.SUPER_ADMIN},
    }

    transferred = await check_and_transfer_inactive_super_admin(
        db=in_memory_db,
        bot=mock_bot,
        settings=settings,
        target_id=target_id,
        inactivity_days=30,
        bot_data=bot_data,
    )

    assert transferred is True

    # 1. Old SA demoted to ADMIN
    old_sa = await get_admin_user(in_memory_db, old_sa_id)
    assert old_sa["role"] == "ADMIN"
    assert bot_data["admin_roles"][old_sa_id] == UserRole.ADMIN

    # 2. Target promoted to SUPER_ADMIN
    new_sa = await get_admin_user(in_memory_db, target_id)
    assert new_sa is not None
    assert new_sa["role"] == "SUPER_ADMIN"
    assert bot_data["admin_roles"][target_id] == UserRole.SUPER_ADMIN
    assert target_id in bot_data["whitelist_user_ids"]
    assert settings.telegram_super_admin_id == target_id

    # 3. active_super_admin_id persisted in system_settings
    active_sa_db = await get_setting(in_memory_db, "active_super_admin_id")
    assert active_sa_db == str(target_id)

    # 4. Message sent to target_id with required handoff message
    mock_bot.send_message.assert_called_once()
    call_kwargs = mock_bot.send_message.call_args.kwargs
    assert call_kwargs["chat_id"] == target_id
    assert "hãy thay tôi tiếp quản và hỗ trợ ông/bà vận hành cửa hàng nhé" in call_kwargs["text"].lower()


@pytest.mark.asyncio
async def test_no_transfer_when_super_admin_active_within_30_days(in_memory_db):
    """Verify no transfer occurs if super admin chatted within 30 days."""
    old_sa_id = 888888
    target_id = 1397365484

    await sync_root_super_admin(in_memory_db, super_admin_id=old_sa_id)

    # Active 5 days ago
    past_time = datetime.now() - timedelta(days=5)
    await update_admin_last_active(in_memory_db, old_sa_id, timestamp=past_time)

    mock_bot = MagicMock()
    mock_bot.send_message = AsyncMock()
    settings = MagicMock()
    settings.telegram_super_admin_id = old_sa_id

    bot_data = {
        "whitelist_user_ids": {old_sa_id},
        "admin_roles": {old_sa_id: UserRole.SUPER_ADMIN},
    }

    transferred = await check_and_transfer_inactive_super_admin(
        db=in_memory_db,
        bot=mock_bot,
        settings=settings,
        target_id=target_id,
        inactivity_days=30,
        bot_data=bot_data,
    )

    assert transferred is False
    mock_bot.send_message.assert_not_called()

    # Still SUPER_ADMIN
    old_sa = await get_admin_user(in_memory_db, old_sa_id)
    assert old_sa["role"] == "SUPER_ADMIN"


@pytest.mark.asyncio
async def test_no_transfer_when_already_target_super_admin(in_memory_db):
    """Verify no transfer if target user is already super admin."""
    target_id = 1397365484
    await sync_root_super_admin(in_memory_db, super_admin_id=target_id)

    transferred = await check_and_transfer_inactive_super_admin(
        db=in_memory_db,
        bot=None,
        settings=MagicMock(),
        target_id=target_id,
        inactivity_days=30,
    )
    assert transferred is False


@pytest.mark.asyncio
async def test_initializes_null_last_active_at_without_transfer(in_memory_db):
    """Verify null last_active_at gets initialized and does not transfer immediately."""
    sa_id = 777777
    await in_memory_db.execute(
        "INSERT INTO admin_users (telegram_id, name, role, last_active_at) VALUES (?, 'SA', 'SUPER_ADMIN', NULL)",
        (sa_id,),
    )
    await in_memory_db.commit()

    transferred = await check_and_transfer_inactive_super_admin(
        db=in_memory_db,
        bot=None,
        settings=MagicMock(),
        target_id=1397365484,
        inactivity_days=30,
    )
    assert transferred is False

    user = await get_admin_user(in_memory_db, sa_id)
    assert user["last_active_at"] is not None


@pytest.mark.asyncio
async def test_whitelist_gate_updates_last_active_timestamp(in_memory_db):
    """Verify whitelist_gate updates last_active_at when super admin chats."""
    sa_id = 999999
    await sync_root_super_admin(in_memory_db, super_admin_id=sa_id)

    update = MagicMock()
    update.effective_user.id = sa_id
    update.effective_message = MagicMock()
    update.message = MagicMock()
    update.callback_query = None

    settings = MagicMock()
    settings.telegram_super_admin_id = sa_id

    context = MagicMock()
    context.bot_data = {
        "whitelist_user_ids": {sa_id},
        "settings": settings,
        "db": in_memory_db,
        "maintenance_mode": False,
    }

    # Initial last_active_at
    await update_admin_last_active(in_memory_db, sa_id, timestamp=datetime(2025, 1, 1))

    await whitelist_gate(update, context)

    # Check updated
    user = await get_admin_user(in_memory_db, sa_id)
    assert user["last_active_at"] != "2025-01-01 00:00:00"
    assert "_sa_last_active_ts" in context.bot_data


@pytest.mark.asyncio
async def test_startup_sync_preserves_transferred_super_admin(in_memory_db):
    """Verify _do_sync preserves transferred super admin across bot reboot."""
    orig_root_sa = 111111
    target_sa = 1397365484

    # Setup settings with original root SA
    settings = MagicMock(spec=Settings)
    settings.telegram_super_admin_id = orig_root_sa
    settings.telegram_whitelist_user_ids = [orig_root_sa]
    settings.fallback_super_admin_id = target_sa
    settings.super_admin_inactivity_days = 30

    # Transfer happened prior to restart: recorded in system_settings
    from src.db.settings import set_setting
    await set_setting(in_memory_db, "active_super_admin_id", str(target_sa))

    app = MagicMock()
    app.bot_data = {
        "admin_roles": {},
        "whitelist_user_ids": set(),
        "settings": settings,
        "db": in_memory_db,
    }

    with patch("src.bot.app.schedule_daily_backup"), \
         patch("src.bot.app.schedule_reminder_checker"), \
         patch("src.bot.app.schedule_inactivity_checker"), \
         patch("src.bot.app.schedule_heartbeat_job"):
        await _do_sync(app, in_memory_db, settings)

    assert settings.telegram_super_admin_id == target_sa
    assert app.bot_data["admin_roles"][target_sa] == UserRole.SUPER_ADMIN


@pytest.mark.asyncio
async def test_inactivity_checker_job_callback(in_memory_db):
    """Verify periodic inactivity_checker_job_callback runs properly."""
    sa_id = 222222
    target_id = 1397365484
    await sync_root_super_admin(in_memory_db, super_admin_id=sa_id)
    past_time = datetime.now() - timedelta(days=40)
    await update_admin_last_active(in_memory_db, sa_id, timestamp=past_time)

    settings = MagicMock()
    settings.telegram_super_admin_id = sa_id
    settings.fallback_super_admin_id = target_id
    settings.super_admin_inactivity_days = 30

    mock_bot = MagicMock()
    mock_bot.send_message = AsyncMock()

    context = MagicMock()
    context.bot = mock_bot
    context.bot_data = {
        "settings": settings,
        "db": in_memory_db,
        "whitelist_user_ids": {sa_id},
        "admin_roles": {sa_id: UserRole.SUPER_ADMIN},
    }

    await inactivity_checker_job_callback(context)

    # Transferred
    target_user = await get_admin_user(in_memory_db, target_id)
    assert target_user["role"] == "SUPER_ADMIN"
    mock_bot.send_message.assert_called_once()
