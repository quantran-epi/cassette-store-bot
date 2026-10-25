from unittest.mock import AsyncMock, MagicMock

import pytest
from telegram import CallbackQuery, Message, Update, User
from telegram.ext import ContextTypes

from src.bot.security import (
    ROLE_HIERARCHY,
    UserRole,
    get_user_role,
    require_role,
)


def make_mock_update(user_id: int | None = 123456, is_callback: bool = False):
    """Construct mock Telegram Update."""
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


def make_mock_context(admin_roles: dict[int, UserRole] | None = None):
    """Construct mock Telegram ContextTypes with admin_roles in bot_data."""
    context = MagicMock(spec=ContextTypes.DEFAULT_TYPE)
    context.bot_data = {"admin_roles": admin_roles or {}}
    return context


def test_user_role_enum_and_hierarchy():
    """Verify UserRole values and hierarchy ranking."""
    assert UserRole.SUPER_ADMIN == "SUPER_ADMIN"
    assert UserRole.ADMIN == "ADMIN"
    assert UserRole.STAFF == "STAFF"

    assert ROLE_HIERARCHY[UserRole.SUPER_ADMIN] == 3
    assert ROLE_HIERARCHY[UserRole.ADMIN] == 2
    assert ROLE_HIERARCHY[UserRole.STAFF] == 1


def test_get_user_role():
    """Verify get_user_role maps user IDs correctly or defaults to STAFF."""
    context = make_mock_context(
        {
            100: UserRole.SUPER_ADMIN,
            200: UserRole.ADMIN,
        }
    )
    assert get_user_role(context, 100) == UserRole.SUPER_ADMIN
    assert get_user_role(context, 200) == UserRole.ADMIN
    assert get_user_role(context, 300) == UserRole.STAFF


@pytest.mark.asyncio
async def test_require_role_allows_authorized_user():
    """Decorated function executes when user meets or exceeds role requirement."""
    target_func = AsyncMock(return_value="executed")
    decorated = require_role(UserRole.ADMIN)(target_func)

    # Super admin should pass
    super_admin_update = make_mock_update(user_id=100)
    context = make_mock_context({100: UserRole.SUPER_ADMIN, 200: UserRole.ADMIN, 300: UserRole.STAFF})

    res = await decorated(super_admin_update, context)
    assert res == "executed"
    target_func.assert_called_once_with(super_admin_update, context)

    # Admin should also pass
    target_func.reset_mock()
    admin_update = make_mock_update(user_id=200)
    res = await decorated(admin_update, context)
    assert res == "executed"
    target_func.assert_called_once_with(admin_update, context)


@pytest.mark.asyncio
async def test_require_role_denies_unauthorized_callback():
    """Decorated function halts and answers callback query with alert when role is insufficient."""
    target_func = AsyncMock()
    decorated = require_role(UserRole.SUPER_ADMIN)(target_func)

    # Admin attempting Super Admin callback
    update = make_mock_update(user_id=200, is_callback=True)
    context = make_mock_context({200: UserRole.ADMIN})

    await decorated(update, context)

    # Target func should NOT be called
    target_func.assert_not_called()

    # Callback answered with alert
    update.callback_query.answer.assert_called_once()
    args, kwargs = update.callback_query.answer.call_args
    assert "Yêu cầu: SUPER_ADMIN" in args[0] or "SUPER_ADMIN" in args[0]
    assert kwargs.get("show_alert") is True


@pytest.mark.asyncio
async def test_require_role_denies_unauthorized_message():
    """Decorated function halts and replies to message when role is insufficient."""
    target_func = AsyncMock()
    decorated = require_role(UserRole.ADMIN)(target_func)

    # Staff attempting Admin command
    update = make_mock_update(user_id=300, is_callback=False)
    context = make_mock_context({300: UserRole.STAFF})

    await decorated(update, context)

    target_func.assert_not_called()
    update.effective_message.reply_text.assert_called_once()
    args, kwargs = update.effective_message.reply_text.call_args
    assert "Từ chối truy cập" in args[0]
    assert "ADMIN" in args[0]
    assert kwargs.get("parse_mode") == "HTML"


@pytest.mark.asyncio
async def test_require_role_handles_none_user():
    """Decorated function returns without action if update has no effective_user."""
    target_func = AsyncMock()
    decorated = require_role(UserRole.STAFF)(target_func)

    update = make_mock_update(user_id=None)
    context = make_mock_context()

    await decorated(update, context)
    target_func.assert_not_called()
