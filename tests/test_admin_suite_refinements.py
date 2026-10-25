from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from telegram import InlineKeyboardMarkup

from src.bot.handlers.admin import handle_admin_callback, handle_admin_text_input
from src.bot.keyboards import (
    build_model_switcher_keyboard,
    build_whitelist_user_detail_keyboard,
)
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
        "active_model_id": "gpt-4o-mini",
        "openai_client": MagicMock(),
    }
    context.user_data = {}
    return context


def test_model_switcher_empty_default_list():
    """Test 1: build_model_switcher_keyboard with empty available_models displays input prompt, no delete button."""
    kb = build_model_switcher_keyboard([], active_model="gpt-4o-mini")
    assert isinstance(kb, InlineKeyboardMarkup)
    callbacks = [btn.callback_data for row in kb.inline_keyboard for btn in row]
    assert "adm:mdl:input_prompt" in callbacks
    assert "adm:dash:refresh" in callbacks
    # No delete button since no other models exist
    assert "adm:mdl:del_menu" not in callbacks

    # When available_models has models other than active_model
    kb_with_models = build_model_switcher_keyboard(["gpt-4o-mini", "claude-3-5-sonnet"], active_model="gpt-4o-mini")
    callbacks_with_models = [btn.callback_data for row in kb_with_models.inline_keyboard for btn in row]
    assert "adm:mdl:del_menu" in callbacks_with_models


@pytest.mark.asyncio
async def test_model_switcher_addition_and_deletion():
    """Test 2: custom model addition appends to available_models, and adm:mdl:del deletes non-active model."""
    context = make_mock_context(user_role=UserRole.SUPER_ADMIN)
    context.user_data["action_state"] = {
        "action": "await_model_name",
        "expires_at": 9999999999,
    }

    update = make_mock_update(user_id=999, is_callback=False, text="meta-llama/llama-3.3-70b-instruct")

    mock_db = MagicMock()
    with patch("src.bot.handlers.admin.probe_model_reachability", new=AsyncMock(return_value=(True, "OK"))), \
         patch("src.bot.handlers.admin._get_active_db_context") as mock_db_ctx, \
         patch("src.bot.handlers.admin.set_setting", new_callable=AsyncMock), \
         patch("src.bot.handlers.admin.get_json_setting", new_callable=AsyncMock, return_value=[]), \
         patch("src.bot.handlers.admin.set_json_setting", new_callable=AsyncMock) as mock_set_json:

        mock_ctx = MagicMock()
        mock_ctx.__aenter__ = AsyncMock(return_value=mock_db)
        mock_ctx.__aexit__ = AsyncMock(return_value=None)
        mock_db_ctx.return_value = mock_ctx

        handled = await handle_admin_text_input(update, context)
        assert handled is True
        mock_set_json.assert_awaited_once_with(
            mock_db, "available_models", ["meta-llama/llama-3.3-70b-instruct"], description="Selectable models"
        )
        assert context.bot_data["active_model_id"] == "meta-llama/llama-3.3-70b-instruct"

    # Test open delete menu adm:mdl:del_menu
    update_del_menu = make_mock_update(user_id=999, is_callback=True, callback_data="adm:mdl:del_menu")
    with patch("src.bot.handlers.admin._get_active_db_context") as mock_db_ctx, \
         patch("src.bot.handlers.admin.get_json_setting", new_callable=AsyncMock, return_value=["gpt-4o-mini", "meta-llama/llama-3.3-70b-instruct"]):

        mock_ctx = MagicMock()
        mock_ctx.__aenter__ = AsyncMock(return_value=mock_db)
        mock_ctx.__aexit__ = AsyncMock(return_value=None)
        mock_db_ctx.return_value = mock_ctx

        await handle_admin_callback(update_del_menu, context)
        update_del_menu.callback_query.edit_message_text.assert_awaited_once()
        card_text = update_del_menu.callback_query.edit_message_text.await_args[0][0]
        assert "XOÁ MODEL KHỎI DANH SÁCH" in card_text

    # Test delete action adm:mdl:del:gpt-4o-mini (non-active)
    update_del = make_mock_update(user_id=999, is_callback=True, callback_data="adm:mdl:del:gpt-4o-mini")
    with patch("src.bot.handlers.admin._get_active_db_context") as mock_db_ctx, \
         patch("src.bot.handlers.admin.get_json_setting", new_callable=AsyncMock, return_value=["gpt-4o-mini", "meta-llama/llama-3.3-70b-instruct"]), \
         patch("src.bot.handlers.admin.set_json_setting", new_callable=AsyncMock) as mock_set_json_del:

        mock_ctx = MagicMock()
        mock_ctx.__aenter__ = AsyncMock(return_value=mock_db)
        mock_ctx.__aexit__ = AsyncMock(return_value=None)
        mock_db_ctx.return_value = mock_ctx

        await handle_admin_callback(update_del, context)
        mock_set_json_del.assert_awaited_once_with(
            mock_db, "available_models", ["meta-llama/llama-3.3-70b-instruct"], description="Selectable models"
        )
        assert update_del.callback_query.answer.await_count >= 1


@pytest.mark.asyncio
async def test_model_switcher_cannot_delete_active_model():
    """Test 3: attempting to delete active model is rejected with alert popup."""
    context = make_mock_context(user_role=UserRole.SUPER_ADMIN)
    context.bot_data["active_model_id"] = "gpt-4o-mini"

    update_del = make_mock_update(user_id=999, is_callback=True, callback_data="adm:mdl:del:gpt-4o-mini")
    mock_db = MagicMock()
    with patch("src.bot.handlers.admin._get_active_db_context") as mock_db_ctx, \
         patch("src.bot.handlers.admin.set_json_setting", new_callable=AsyncMock) as mock_set_json:

        mock_ctx = MagicMock()
        mock_ctx.__aenter__ = AsyncMock(return_value=mock_db)
        mock_ctx.__aexit__ = AsyncMock(return_value=None)
        mock_db_ctx.return_value = mock_ctx

        await handle_admin_callback(update_del, context)
        mock_set_json.assert_not_called()
        update_del.callback_query.answer.assert_awaited_once()
        assert update_del.callback_query.answer.await_args.kwargs.get("show_alert") is True
        assert "Không thể xoá model đang được kích hoạt" in update_del.callback_query.answer.await_args[0][0]


@pytest.mark.asyncio
async def test_whitelist_rename_user_flow():
    """Test 4: clicking rename button prompts for new name and updates SQLite admin_users.name."""
    # Check rename button in keyboard
    target_user = {"telegram_id": 777, "name": "Anh Ba", "role": "STAFF"}
    kb = build_whitelist_user_detail_keyboard(target_user, is_root=False)
    callbacks = [btn.callback_data for row in kb.inline_keyboard for btn in row]
    assert "adm:wl:rename_prompt:777" in callbacks

    # Check root admin detail keyboard also has rename button
    root_user = {"telegram_id": 999, "name": "Super Admin", "role": "SUPER_ADMIN"}
    kb_root = build_whitelist_user_detail_keyboard(root_user, is_root=True)
    callbacks_root = [btn.callback_data for row in kb_root.inline_keyboard for btn in row]
    assert "adm:wl:rename_prompt:999" in callbacks_root

    # Trigger rename prompt callback
    context = make_mock_context(user_role=UserRole.SUPER_ADMIN)
    update_prompt = make_mock_update(user_id=999, is_callback=True, callback_data="adm:wl:rename_prompt:777")

    mock_db = MagicMock()
    with patch("src.bot.handlers.admin._get_active_db_context") as mock_db_ctx:
        mock_ctx = MagicMock()
        mock_ctx.__aenter__ = AsyncMock(return_value=mock_db)
        mock_ctx.__aexit__ = AsyncMock(return_value=None)
        mock_db_ctx.return_value = mock_ctx

        await handle_admin_callback(update_prompt, context)

    assert context.user_data.get("action_state") is not None
    assert context.user_data["action_state"]["action"] == "await_user_rename"
    assert context.user_data["action_state"]["target_id"] == 777

    # Send new name in chat
    update_text = make_mock_update(user_id=999, is_callback=False, text="Chu Ba Ban Dia")
    with patch("src.bot.handlers.admin._get_active_db_context") as mock_db_ctx, \
         patch("src.bot.handlers.admin.update_admin_user_name", new_callable=AsyncMock) as mock_update_name, \
         patch("src.bot.handlers.admin.get_admin_user", new_callable=AsyncMock, return_value={"telegram_id": 777, "name": "Chu Ba Ban Dia", "role": "STAFF", "created_at": "2026-10-25"}):

        mock_ctx = MagicMock()
        mock_ctx.__aenter__ = AsyncMock(return_value=mock_db)
        mock_ctx.__aexit__ = AsyncMock(return_value=None)
        mock_db_ctx.return_value = mock_ctx

        handled = await handle_admin_text_input(update_text, context)
        assert handled is True
        mock_update_name.assert_awaited_once_with(mock_db, 777, "Chu Ba Ban Dia")
        assert context.user_data.get("action_state") is None
        update_text.effective_message.reply_text.assert_awaited_once()
        card = update_text.effective_message.reply_text.await_args[0][0]
        assert "Chu Ba Ban Dia" in card
