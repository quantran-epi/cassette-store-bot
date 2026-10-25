from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.bot.handlers.admin import handle_admin_callback, handle_admin_text_input
from src.bot.handlers.backup import backup_command
from src.bot.keyboards import build_backup_schedule_keyboard
from src.bot.security import UserRole


def make_mock_update(user_id: int, is_callback: bool = False, callback_data: str = "", text: str = ""):
    update = MagicMock()
    user = MagicMock()
    user.id = user_id
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


def make_mock_context(user_role: UserRole = UserRole.ADMIN, super_admin_id: int = 999):
    context = MagicMock()
    settings = MagicMock()
    settings.sqlite_db_path = "test.db"
    settings.telegram_super_admin_id = super_admin_id
    settings.nine_router_model_id = "gpt-4o-mini"

    context.bot_data = {
        "settings": settings,
        "admin_roles": {super_admin_id: UserRole.SUPER_ADMIN, 888: UserRole.ADMIN},
        "whitelist_user_ids": {super_admin_id, 888},
    }
    context.user_data = {}
    return context


@pytest.mark.asyncio
async def test_backup_command_as_super_admin():
    """Test 1: Super Admin calling /backup sends progress, creates snapshot, updates status, and sends document."""
    update = make_mock_update(user_id=999, is_callback=False, text="/backup")
    progress_msg = MagicMock()
    progress_msg.edit_text = AsyncMock()
    update.effective_message.reply_text = AsyncMock(return_value=progress_msg)

    context = make_mock_context(user_role=UserRole.SUPER_ADMIN, super_admin_id=999)

    stats = {
        "gz_path": "/tmp/backups/test.sqlite3.gz",
        "raw_path": "/tmp/backups/test.sqlite3",
        "timestamp_str": "2026-10-25 15:30:00",
        "raw_size": 2048000,
        "gz_size": 512000,
        "order_count": 25,
        "customer_count": 10,
        "is_oversized": False,
    }

    mock_db = MagicMock()
    with patch("src.bot.handlers.backup._get_active_db_context") as mock_db_ctx, \
         patch("src.bot.handlers.backup.execute_backup", new_callable=AsyncMock) as mock_exec, \
         patch("src.bot.handlers.backup.send_backup_document", new_callable=AsyncMock) as mock_send:

        mock_ctx = MagicMock()
        mock_ctx.__aenter__ = AsyncMock(return_value=mock_db)
        mock_ctx.__aexit__ = AsyncMock(return_value=None)
        mock_db_ctx.return_value = mock_ctx

        mock_exec.return_value = stats
        mock_send.return_value = True

        await backup_command(update, context)

        update.effective_message.reply_text.assert_awaited_once()
        assert "Đang tạo snapshot" in update.effective_message.reply_text.await_args[0][0]

        mock_send.assert_awaited_once()
        assert mock_send.await_args.kwargs["chat_id"] == 999
        assert "25 đơn hàng" in mock_send.await_args.kwargs["caption"]
        progress_msg.edit_text.assert_awaited_once()
        assert "thành công" in progress_msg.edit_text.await_args[0][0]


@pytest.mark.asyncio
async def test_backup_command_unauthorized():
    """Test 2: Non-Super-Admin calling /backup is rejected."""
    update = make_mock_update(user_id=888, is_callback=False, text="/backup")
    context = make_mock_context(user_role=UserRole.ADMIN, super_admin_id=999)

    with patch("src.bot.handlers.backup.execute_backup", new_callable=AsyncMock) as mock_exec:
        await backup_command(update, context)
        mock_exec.assert_not_called()
        update.effective_message.reply_text.assert_awaited_once()
        assert "Từ chối truy cập" in update.effective_message.reply_text.await_args[0][0]


@pytest.mark.asyncio
async def test_admin_menu_backup_trigger_super_admin():
    """Test 3a: Super Admin clicking adm:bkp:trigger executes backup in-place."""
    update = make_mock_update(user_id=999, is_callback=True, callback_data="adm:bkp:trigger")
    context = make_mock_context(user_role=UserRole.SUPER_ADMIN, super_admin_id=999)

    stats = {
        "gz_path": "/tmp/backups/test.sqlite3.gz",
        "raw_path": "/tmp/backups/test.sqlite3",
        "timestamp_str": "2026-10-25 15:30:00",
        "raw_size": 2048000,
        "gz_size": 512000,
        "order_count": 25,
        "customer_count": 10,
        "is_oversized": False,
    }

    mock_db = MagicMock()
    with patch("src.bot.handlers.admin._get_active_db_context") as mock_db_ctx, \
         patch("src.services.backup.execute_backup", new_callable=AsyncMock) as mock_exec, \
         patch("src.services.backup.send_backup_document", new_callable=AsyncMock) as mock_send:

        mock_ctx = MagicMock()
        mock_ctx.__aenter__ = AsyncMock(return_value=mock_db)
        mock_ctx.__aexit__ = AsyncMock(return_value=None)
        mock_db_ctx.return_value = mock_ctx

        mock_exec.return_value = stats
        mock_send.return_value = True

        await handle_admin_callback(update, context)

        update.callback_query.answer.assert_awaited_once()
        assert update.callback_query.edit_message_text.await_count >= 1
        mock_send.assert_awaited_once()


@pytest.mark.asyncio
async def test_admin_menu_backup_trigger_regular_admin():
    """Test 3b: Regular Admin clicking adm:bkp:trigger receives alert popup."""
    update = make_mock_update(user_id=888, is_callback=True, callback_data="adm:bkp:trigger")
    context = make_mock_context(user_role=UserRole.ADMIN, super_admin_id=999)

    with patch("src.services.backup.execute_backup", new_callable=AsyncMock) as mock_exec:
        await handle_admin_callback(update, context)
        mock_exec.assert_not_called()
        update.callback_query.answer.assert_awaited_once()
        assert update.callback_query.answer.await_args.kwargs.get("show_alert") is True
        assert "Chỉ Super Admin" in update.callback_query.answer.await_args[0][0]


@pytest.mark.asyncio
async def test_backup_schedule_menu_navigation_and_presets():
    """Test 4: adm:bkp:menu opens schedule picker and adm:bkp:set:03:00 reschedules."""
    # Test menu display
    update = make_mock_update(user_id=999, is_callback=True, callback_data="adm:bkp:menu")
    context = make_mock_context(user_role=UserRole.SUPER_ADMIN, super_admin_id=999)

    mock_db = MagicMock()
    with patch("src.bot.handlers.admin._get_active_db_context") as mock_db_ctx, \
         patch("src.bot.handlers.admin.get_setting", new_callable=AsyncMock, return_value="02:00"):

        mock_ctx = MagicMock()
        mock_ctx.__aenter__ = AsyncMock(return_value=mock_db)
        mock_ctx.__aexit__ = AsyncMock(return_value=None)
        mock_db_ctx.return_value = mock_ctx

        await handle_admin_callback(update, context)

        update.callback_query.answer.assert_awaited_once()
        update.callback_query.edit_message_text.assert_awaited_once()
        card_text = update.callback_query.edit_message_text.await_args[0][0]
        assert "ĐẶT GIỜ SAO LƯU TỰ ĐỘNG" in card_text
        assert "02:00" in card_text

    # Test preset selection adm:bkp:set:03:00
    update_set = make_mock_update(user_id=999, is_callback=True, callback_data="adm:bkp:set:03:00")

    with patch("src.bot.handlers.admin._get_active_db_context") as mock_db_ctx, \
         patch("src.bot.handlers.admin.set_setting", new_callable=AsyncMock) as mock_set_setting, \
         patch("src.bot.handlers.admin.get_setting", new_callable=AsyncMock, return_value="03:00"), \
         patch("src.bot.app.schedule_daily_backup") as mock_reschedule:

        mock_ctx = MagicMock()
        mock_ctx.__aenter__ = AsyncMock(return_value=mock_db)
        mock_ctx.__aexit__ = AsyncMock(return_value=None)
        mock_db_ctx.return_value = mock_ctx

        await handle_admin_callback(update_set, context)

        mock_set_setting.assert_awaited_once_with(
            mock_db, "backup_schedule_time", "03:00", description="Daily backup schedule time"
        )
        mock_reschedule.assert_called_once_with(context.application, "03:00")
        assert update_set.callback_query.answer.await_count >= 1


@pytest.mark.asyncio
async def test_backup_schedule_custom_prompt_validation():
    """Test 5: adm:bkp:custom_prompt sets prompt state and handle_admin_text_input validates HH:MM format."""
    update = make_mock_update(user_id=999, is_callback=True, callback_data="adm:bkp:custom_prompt")
    context = make_mock_context(user_role=UserRole.SUPER_ADMIN, super_admin_id=999)

    mock_db = MagicMock()
    with patch("src.bot.handlers.admin._get_active_db_context") as mock_db_ctx:
        mock_ctx = MagicMock()
        mock_ctx.__aenter__ = AsyncMock(return_value=mock_db)
        mock_ctx.__aexit__ = AsyncMock(return_value=None)
        mock_db_ctx.return_value = mock_ctx

        await handle_admin_callback(update, context)

    assert context.user_data.get("action_state") is not None
    assert context.user_data["action_state"]["action"] == "await_backup_time"

    # Test invalid time input
    update_invalid = make_mock_update(user_id=999, is_callback=False, text="25:99")

    handled = await handle_admin_text_input(update_invalid, context)
    assert handled is True
    update_invalid.effective_message.reply_text.assert_awaited_once()
    assert "không hợp lệ" in update_invalid.effective_message.reply_text.await_args[0][0]
    assert context.user_data.get("action_state") is not None

    # Test valid time input
    update_valid = make_mock_update(user_id=999, is_callback=False, text="04:30")

    with patch("src.bot.handlers.admin._get_active_db_context") as mock_db_ctx, \
         patch("src.bot.handlers.admin.set_setting", new_callable=AsyncMock) as mock_set_setting, \
         patch("src.bot.app.schedule_daily_backup") as mock_reschedule:

        mock_ctx = MagicMock()
        mock_ctx.__aenter__ = AsyncMock(return_value=mock_db)
        mock_ctx.__aexit__ = AsyncMock(return_value=None)
        mock_db_ctx.return_value = mock_ctx

        handled = await handle_admin_text_input(update_valid, context)
        assert handled is True
        mock_set_setting.assert_awaited_once()
        mock_reschedule.assert_called_once_with(context.application, "04:30")
        assert context.user_data.get("action_state") is None
        assert "04:30" in update_valid.effective_message.reply_text.await_args[0][0]


def test_build_backup_schedule_keyboard():
    """Verify build_backup_schedule_keyboard contains preset times and indicators."""
    kb = build_backup_schedule_keyboard("02:00")
    callbacks = [btn.callback_data for row in kb.inline_keyboard for btn in row]
    assert "adm:bkp:set:01:00" in callbacks
    assert "adm:bkp:set:02:00" in callbacks
    assert "adm:bkp:set:03:00" in callbacks
    assert "adm:bkp:set:04:00" in callbacks
    assert "adm:bkp:custom_prompt" in callbacks
    assert "adm:dash:refresh" in callbacks

    # Check that 02:00 has checkmark
    labels = [btn.text for row in kb.inline_keyboard for btn in row]
    assert any("[✓] 02:00" in lbl for lbl in labels)
