from unittest.mock import AsyncMock, MagicMock

import pytest
from telegram import Chat, Message, Update, User
from telegram.ext import ContextTypes

from src.bot.handlers.base import ping_command
from src.config import Settings


def _create_mock_update_and_context(settings: Settings):
    """Helper to mock telegram Update and Context with settings."""
    user = User(id=111, first_name="Admin", is_bot=False)
    chat = Chat(id=111, type="private")
    message = MagicMock(spec=Message)
    message.reply_text = AsyncMock()

    update = MagicMock(spec=Update)
    update.effective_user = user
    update.effective_chat = chat
    update.effective_message = message

    context = MagicMock(spec=ContextTypes.DEFAULT_TYPE)
    context.bot_data = {"settings": settings}

    return update, context, message


@pytest.mark.asyncio
async def test_ping_command_db_ok(tmp_path):
    """When DB is accessible, ping replies with Bot Running and Database OK (WAL mode)."""
    db_file = tmp_path / "test.db"
    settings = Settings(
        telegram_bot_token="test_token:ABC-123",
        telegram_whitelist_user_ids=[111],
        sqlite_db_path=str(db_file),
    )

    update, context, message = _create_mock_update_and_context(settings)
    await ping_command(update, context)

    message.reply_text.assert_awaited_once()
    reply_text = message.reply_text.call_args[0][0]
    assert "🏓 Pong!" in reply_text
    assert "Bot: Running" in reply_text
    assert "Database: OK" in reply_text


@pytest.mark.asyncio
async def test_ping_command_db_error():
    """When DB path is invalid or unconnectable, ping reports Database ERROR gracefully."""
    settings = Settings(
        telegram_bot_token="test_token:ABC-123",
        telegram_whitelist_user_ids=[111],
        sqlite_db_path="/non_existent_directory_98765/impossible.db",
    )

    update, context, message = _create_mock_update_and_context(settings)
    await ping_command(update, context)

    message.reply_text.assert_awaited_once()
    reply_text = message.reply_text.call_args[0][0]
    assert "🏓 Pong!" in reply_text
    assert "Bot: Running" in reply_text
    assert "Database: ERROR" in reply_text


def test_main_module_importable():
    """main.py must be importable without executing the polling loop."""
    import main

    assert hasattr(main, "main")
    assert callable(main.main)
