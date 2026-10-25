from unittest.mock import AsyncMock, MagicMock

import pytest
from pydantic import SecretStr
from telegram import CallbackQuery, Message, Update, User
from telegram.ext import ApplicationHandlerStop, CallbackQueryHandler, CommandHandler, TypeHandler

from src.bot.app import build_application
from src.bot.handlers.base import ping_command, start_command
from src.bot.security import UserRole, whitelist_gate
from src.config import Settings


def make_mock_update(user_id: int | None = 123456, is_callback: bool = False):
    """Helper to construct mock Telegram Update."""
    update = MagicMock(spec=Update)
    if user_id is not None:
        user = MagicMock(spec=User)
        user.id = user_id
        update.effective_user = user
    else:
        update.effective_user = None

    if is_callback:
        cb = MagicMock(spec=CallbackQuery)
        cb.answer = AsyncMock()
        update.callback_query = cb
        update.effective_message = None
    else:
        update.callback_query = None
        msg = MagicMock(spec=Message)
        msg.reply_text = AsyncMock()
        update.effective_message = msg

    return update


def make_mock_context(whitelist_ids: set[int]):
    """Helper to construct mock Telegram ContextTypes."""
    context = MagicMock()
    context.bot_data = {"whitelist_user_ids": whitelist_ids}
    return context


async def test_whitelist_gate_allows_whitelisted_user():
    """Whitelisted user must pass through without exception."""
    update = make_mock_update(user_id=100)
    context = make_mock_context(whitelist_ids={100, 200})

    # Should not raise ApplicationHandlerStop
    await whitelist_gate(update, context)
    assert update.effective_message.reply_text.call_count == 0


async def test_whitelist_gate_rejects_stranger_message():
    """Stranger message must trigger polite refusal with User ID and stop handler."""
    stranger_id = 99999
    update = make_mock_update(user_id=stranger_id, is_callback=False)
    context = make_mock_context(whitelist_ids={100, 200})

    with pytest.raises(ApplicationHandlerStop):
        await whitelist_gate(update, context)

    update.effective_message.reply_text.assert_called_once()
    reply_text = update.effective_message.reply_text.call_args[0][0]
    assert str(stranger_id) in reply_text
    assert "quyền truy cập" in reply_text


async def test_whitelist_gate_rejects_stranger_callback():
    """Stranger callback button press must answer alert with User ID and stop handler."""
    stranger_id = 88888
    update = make_mock_update(user_id=stranger_id, is_callback=True)
    context = make_mock_context(whitelist_ids={100, 200})

    with pytest.raises(ApplicationHandlerStop):
        await whitelist_gate(update, context)

    update.callback_query.answer.assert_called_once()
    alert_text = update.callback_query.answer.call_args[0][0]
    assert str(stranger_id) in alert_text
    assert update.callback_query.answer.call_args[1].get("show_alert") is True


async def test_whitelist_gate_stops_on_none_user():
    """Update without effective_user must raise ApplicationHandlerStop."""
    update = make_mock_update(user_id=None)
    context = make_mock_context(whitelist_ids={100})

    with pytest.raises(ApplicationHandlerStop):
        await whitelist_gate(update, context)


async def test_start_command_replies_welcome():
    """Start command replies with greeting and recognized user ID."""
    update = make_mock_update(user_id=123)
    context = make_mock_context(whitelist_ids={123})

    await start_command(update, context)
    update.effective_message.reply_text.assert_called_once()
    msg = update.effective_message.reply_text.call_args[0][0]
    assert "123" in msg


async def test_ping_command_replies_pong():
    """Ping command replies with pong status."""
    update = make_mock_update(user_id=123)
    context = make_mock_context(whitelist_ids={123})

    await ping_command(update, context)
    update.effective_message.reply_text.assert_called_once()
    msg = update.effective_message.reply_text.call_args[0][0]
    assert "pong" in msg.lower() or "hoạt động" in msg.lower()


def test_build_application_registers_gate_at_group_minus_one():
    """build_application must register TypeHandler at group -1 and populate bot_data."""
    settings = Settings(
        telegram_bot_token=SecretStr("fake_token_for_app_build"),
        telegram_whitelist_user_ids=[111, 222],
    )

    app = build_application(settings)

    # Check bot_data contains whitelist set
    assert app.bot_data["whitelist_user_ids"] == {111, 222}

    # Check group -1 has TypeHandler
    minus_one_handlers = app.handlers.get(-1, [])
    assert len(minus_one_handlers) >= 1
    gate_handler = minus_one_handlers[0]
    assert isinstance(gate_handler, TypeHandler)
    assert gate_handler.callback == whitelist_gate

    # Check group 0 has start and ping commands
    zero_handlers = app.handlers.get(0, [])
    command_names = [
        h.commands
        for h in zero_handlers
        if isinstance(h, CommandHandler)
    ]
    # Flatten commands
    flat_commands = [cmd for sub in command_names for cmd in sub]
    assert "start" in flat_commands
    assert "ping" in flat_commands
    assert "admin" in flat_commands
    assert "logs" in flat_commands

    # Check bot_data has log_handler and admin components
    assert "log_handler" in app.bot_data
    assert "admin_roles" in app.bot_data
    assert "active_model_id" in app.bot_data

    # Check callback query handlers include adm:
    cb_patterns = [
        h.pattern.pattern
        for h in zero_handlers
        if isinstance(h, CallbackQueryHandler) and hasattr(h.pattern, "pattern")
    ]
    assert any("adm:" in p for p in cb_patterns)


@pytest.mark.asyncio
async def test_build_application_startup_db_sync(tmp_path):
    """Startup sync must load admin roles and settings from SQLite."""
    import aiosqlite
    from src.db.schema import init_db
    from src.db.settings import set_setting
    from src.bot.app import startup_sync

    db_path = str(tmp_path / "app_test.db")
    async with aiosqlite.connect(db_path) as db:
        await init_db(db)
        await set_setting(db, "active_model_id", "custom-synced-model")

    settings = Settings(
        telegram_bot_token=SecretStr("fake_token_for_app_build"),
        telegram_whitelist_user_ids=[111],
        telegram_super_admin_id=999,
        sqlite_db_path=db_path,
    )
    async with aiosqlite.connect(db_path) as db:
        db.row_factory = aiosqlite.Row
        app = build_application(settings, db=db)
        await startup_sync(app)

        assert 999 in app.bot_data["whitelist_user_ids"]
        assert app.bot_data["admin_roles"][999] == UserRole.SUPER_ADMIN
        assert 111 in app.bot_data["whitelist_user_ids"]
        assert app.bot_data["admin_roles"][111] == UserRole.STAFF
        assert app.bot_data["active_model_id"] == "custom-synced-model"
