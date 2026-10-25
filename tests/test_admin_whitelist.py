import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.bot.handlers.admin import handle_admin_callback, handle_admin_text_input
from src.bot.security import UserRole
from src.config import Settings


def make_mock_update(
    user_id: int = 123456,
    text: str = "",
    is_callback: bool = False,
    callback_data: str | None = None,
):
    update = MagicMock()
    user = MagicMock()
    user.id = user_id
    user.first_name = "AdminUser"
    update.effective_user = user

    if is_callback:
        query = MagicMock()
        query.data = callback_data
        query.from_user = user
        query.answer = AsyncMock()
        query.edit_message_text = AsyncMock()
        update.callback_query = query
        update.effective_message = None
    else:
        msg = MagicMock()
        msg.text = text
        msg.reply_text = AsyncMock()
        update.effective_message = msg
        update.callback_query = None

    return update


def make_mock_context(
    user_role: UserRole = UserRole.ADMIN,
    db: MagicMock | None = None,
    super_admin_id: int | None = 999999,
):
    context = MagicMock()
    settings = MagicMock(spec=Settings)
    settings.sqlite_db_path = "test.db"
    settings.telegram_super_admin_id = super_admin_id
    settings.nine_router_model_id = "gpt-4o-mini"

    context.bot_data = {
        "settings": settings,
        "admin_roles": {123456: user_role, 999999: UserRole.SUPER_ADMIN, 555: UserRole.STAFF},
        "whitelist_user_ids": {123456, 999999, 555},
        "active_model_id": "gpt-4o-mini",
        "start_time": time.time(),
        "db": db or MagicMock(),
        "openai_client": MagicMock(),
    }
    context.user_data = {}
    return context


@pytest.mark.asyncio
async def test_whitelist_view_user():
    update = make_mock_update(user_id=123456, is_callback=True, callback_data="adm:wl:view:555")
    context = make_mock_context(user_role=UserRole.ADMIN)

    with patch(
        "src.bot.handlers.admin.get_admin_user",
        new=AsyncMock(
            return_value={
                "telegram_id": 555,
                "name": "Staff Five",
                "role": "STAFF",
                "created_at": "2026-10-25 10:00:00",
            }
        ),
    ):
        await handle_admin_callback(update, context)

    update.callback_query.edit_message_text.assert_awaited_once()
    msg = update.callback_query.edit_message_text.call_args[1].get("text") or update.callback_query.edit_message_text.call_args[0][0]
    assert "555" in msg
    assert "Staff Five" in msg
    assert "STAFF" in msg


@pytest.mark.asyncio
async def test_whitelist_delete_confirmation_and_execution():
    # Step 1: Request delete
    req_update = make_mock_update(user_id=123456, is_callback=True, callback_data="adm:wl:rm_req:555")
    context = make_mock_context(user_role=UserRole.ADMIN)

    with patch(
        "src.bot.handlers.admin.get_admin_user",
        new=AsyncMock(
            return_value={
                "telegram_id": 555,
                "name": "Staff Five",
                "role": "STAFF",
                "created_at": "2026-10-25 10:00:00",
            }
        ),
    ):
        await handle_admin_callback(req_update, context)

    req_update.callback_query.edit_message_text.assert_awaited_once()
    msg = req_update.callback_query.edit_message_text.call_args[1].get("text") or req_update.callback_query.edit_message_text.call_args[0][0]
    assert "XÁC NHẬN XOÁ QUYỀN TRUY CẬP" in msg
    assert "555" in msg

    # Step 2: Confirm delete
    cf_update = make_mock_update(user_id=123456, is_callback=True, callback_data="adm:wl:rm_cf:555")
    with patch("src.bot.handlers.admin.delete_admin_user", new=AsyncMock(return_value=True)), patch(
        "src.bot.handlers.admin.list_admin_users", new=AsyncMock(return_value=[])
    ):
        await handle_admin_callback(cf_update, context)

    # 555 must be purged from whitelist_user_ids and admin_roles
    assert 555 not in context.bot_data["whitelist_user_ids"]
    assert 555 not in context.bot_data["admin_roles"]
    cf_update.callback_query.answer.assert_awaited_with("✅ Đã xoá người dùng khỏi Whitelist", show_alert=True)


@pytest.mark.asyncio
async def test_root_super_admin_cannot_be_deleted():
    update = make_mock_update(user_id=123456, is_callback=True, callback_data="adm:wl:rm_cf:999999")
    context = make_mock_context(user_role=UserRole.ADMIN, super_admin_id=999999)

    await handle_admin_callback(update, context)

    # 999999 must NOT be removed
    assert 999999 in context.bot_data["whitelist_user_ids"]
    assert 999999 in context.bot_data["admin_roles"]
    update.callback_query.answer.assert_awaited_with(
        "🛡️ Không thể chỉnh sửa, hạ quyền hoặc xoá Root Super Admin!", show_alert=True
    )


@pytest.mark.asyncio
async def test_add_whitelist_text_input_success_and_role_selection():
    context = make_mock_context(user_role=UserRole.ADMIN)
    context.user_data["action_state"] = {
        "action": "await_whitelist_id",
        "expires_at": time.time() + 60,
    }

    update = make_mock_update(user_id=123456, text="777888 Tran Van B")
    handled = await handle_admin_text_input(update, context)

    assert handled is True
    assert "action_state" not in context.user_data
    update.effective_message.reply_text.assert_awaited_once()
    msg = update.effective_message.reply_text.call_args[0][0]
    assert "777888" in msg
    assert "Tran Van B" in msg


@pytest.mark.asyncio
async def test_add_whitelist_text_input_invalid_format():
    context = make_mock_context(user_role=UserRole.ADMIN)
    context.user_data["action_state"] = {
        "action": "await_whitelist_id",
        "expires_at": time.time() + 60,
    }

    update = make_mock_update(user_id=123456, text="invalid_non_numeric_id")
    handled = await handle_admin_text_input(update, context)

    assert handled is True
    # Still waiting, not cleared
    assert "action_state" in context.user_data
    update.effective_message.reply_text.assert_awaited_once()
    msg = update.effective_message.reply_text.call_args[0][0]
    assert "ID không hợp lệ" in msg


@pytest.mark.asyncio
async def test_add_whitelist_text_input_timeout():
    context = make_mock_context(user_role=UserRole.ADMIN)
    context.user_data["action_state"] = {
        "action": "await_whitelist_id",
        "expires_at": time.time() - 5,  # expired
    }

    update = make_mock_update(user_id=123456, text="777888")
    handled = await handle_admin_text_input(update, context)

    assert handled is False
    assert "action_state" not in context.user_data
    update.effective_message.reply_text.assert_not_awaited()


@pytest.mark.asyncio
async def test_whitelist_role_pick_cannot_demote_root_super_admin():
    update = make_mock_update(
        user_id=123456,
        is_callback=True,
        callback_data="adm:wl:role_pick:999999:STAFF",
    )
    context = make_mock_context(user_role=UserRole.ADMIN)

    await handle_admin_callback(update, context)

    # 999999 role must remain SUPER_ADMIN
    assert context.bot_data["admin_roles"][999999] == UserRole.SUPER_ADMIN
    update.callback_query.answer.assert_awaited_with(
        "🛡️ Không thể chỉnh sửa, hạ quyền hoặc xoá Root Super Admin!", show_alert=True
    )
    update.callback_query.edit_message_text.assert_not_awaited()
