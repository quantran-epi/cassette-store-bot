import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from telegram import InlineKeyboardMarkup

from src.bot.handlers.admin import (
    DEFAULT_MODELS,
    admin_command,
    handle_admin_callback,
    handle_admin_text_input,
)
from src.bot.handlers.logs import handle_logs_callback, logs_command
from src.bot.keyboards import (
    build_admin_main_keyboard,
    build_logs_keyboard,
    build_model_switcher_keyboard,
    build_whitelist_confirm_delete_keyboard,
    build_whitelist_keyboard,
    build_whitelist_user_detail_keyboard,
)
from src.bot.security import UserRole
from src.config import Settings
from src.services.llm_probe import probe_model_reachability


@pytest.mark.asyncio
async def test_probe_model_reachability_success():
    client = MagicMock()
    client.chat = MagicMock()
    client.chat.completions = MagicMock()
    client.chat.completions.create = AsyncMock(return_value=MagicMock())

    success, msg = await probe_model_reachability(client, "gpt-4o-mini", timeout=5.0)

    assert success is True
    assert "200 OK" in msg or "thành công" in msg.lower()
    client.chat.completions.create.assert_awaited_once_with(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": "hi"}],
        max_tokens=1,
        timeout=5.0,
    )


@pytest.mark.asyncio
async def test_probe_model_reachability_failure():
    client = MagicMock()
    client.chat = MagicMock()
    client.chat.completions = MagicMock()
    client.chat.completions.create = AsyncMock(side_effect=Exception("Connection timed out"))

    success, msg = await probe_model_reachability(client, "non-existent-model", timeout=2.0)

    assert success is False
    assert "Connection timed out" in msg


def test_build_admin_main_keyboard_layout():
    kb = build_admin_main_keyboard(user_role=UserRole.ADMIN)
    assert isinstance(kb, InlineKeyboardMarkup)
    assert len(kb.inline_keyboard) == 5
    # Row 1: Whitelist, Model Switcher
    assert len(kb.inline_keyboard[0]) == 2
    assert "Whitelist" in kb.inline_keyboard[0][0].text
    assert kb.inline_keyboard[0][0].callback_data == "adm:wl:list:1"
    assert "Model" in kb.inline_keyboard[0][1].text
    assert kb.inline_keyboard[0][1].callback_data == "adm:mdl:menu"

    # Row 2: Logs, Backup
    assert len(kb.inline_keyboard[1]) == 2
    assert "Logs" in kb.inline_keyboard[1][0].text
    assert kb.inline_keyboard[1][0].callback_data == "adm:log:view:25:all"
    assert "Sao lưu" in kb.inline_keyboard[1][1].text
    assert kb.inline_keyboard[1][1].callback_data == "adm:bkp:trigger"

    # Row 3: Schedule, Milestones
    assert len(kb.inline_keyboard[2]) == 2
    assert "Đặt giờ sao lưu" in kb.inline_keyboard[2][0].text
    assert kb.inline_keyboard[2][0].callback_data == "adm:bkp:menu"
    assert "Mốc chúc mừng" in kb.inline_keyboard[2][1].text
    assert kb.inline_keyboard[2][1].callback_data == "adm:ms:list"

    # Row 4: Refresh
    assert len(kb.inline_keyboard[3]) == 1
    assert "Làm mới" in kb.inline_keyboard[3][0].text
    assert kb.inline_keyboard[3][0].callback_data == "adm:dash:refresh"

    # Row 5: Close
    assert len(kb.inline_keyboard[4]) == 1
    assert "Đóng" in kb.inline_keyboard[4][0].text
    assert kb.inline_keyboard[4][0].callback_data == "adm:dash:close"


def test_build_whitelist_keyboard():
    users = [
        {"telegram_id": 111, "name": "Admin 1", "role": "ADMIN"},
        {"telegram_id": 222, "name": "Staff 1", "role": "STAFF"},
    ]
    kb = build_whitelist_keyboard(users, current_page=1, total_pages=1)
    assert isinstance(kb, InlineKeyboardMarkup)
    callbacks = [btn.callback_data for row in kb.inline_keyboard for btn in row]
    assert "adm:wl:view:111" in callbacks
    assert "adm:wl:view:222" in callbacks
    assert "adm:wl:add_prompt" in callbacks
    assert "adm:dash:refresh" in callbacks


def test_build_whitelist_user_detail_keyboard_normal_user():
    user = {"telegram_id": 222, "name": "Staff 1", "role": "STAFF"}
    kb = build_whitelist_user_detail_keyboard(user, is_root=False)
    assert isinstance(kb, InlineKeyboardMarkup)
    callbacks = [btn.callback_data for row in kb.inline_keyboard for btn in row]
    assert "adm:wl:role:222:ADMIN" in callbacks
    assert "adm:wl:rm_req:222" in callbacks
    assert "adm:wl:list:1" in callbacks


def test_build_whitelist_user_detail_keyboard_root_user():
    user = {"telegram_id": 999999, "name": "Root Admin", "role": "SUPER_ADMIN"}
    kb = build_whitelist_user_detail_keyboard(user, is_root=True)
    assert isinstance(kb, InlineKeyboardMarkup)
    callbacks = [btn.callback_data for row in kb.inline_keyboard for btn in row]
    assert "adm:wl:rm_req:999999" not in callbacks
    assert not any("adm:wl:role:999999:" in cb for cb in callbacks)
    texts = [btn.text for row in kb.inline_keyboard for btn in row]
    assert any("Bảo vệ" in t or "Root" in t for t in texts)


def test_build_whitelist_confirm_delete_keyboard():
    kb = build_whitelist_confirm_delete_keyboard(222)
    assert isinstance(kb, InlineKeyboardMarkup)
    callbacks = [btn.callback_data for row in kb.inline_keyboard for btn in row]
    assert "adm:wl:rm_cf:222" in callbacks
    assert "adm:wl:view:222" in callbacks


def test_build_model_switcher_keyboard():
    models = ["gpt-4o-mini", "gpt-4o", "claude-3-5-haiku"]
    kb = build_model_switcher_keyboard(models, active_model="gpt-4o-mini")
    assert isinstance(kb, InlineKeyboardMarkup)
    button_map = {btn.text: btn.callback_data for row in kb.inline_keyboard for btn in row}
    assert "[✓] gpt-4o-mini" in button_map or "✓ gpt-4o-mini" in button_map
    assert "gpt-4o" in button_map
    assert "adm:mdl:sel:gpt-4o" in button_map.values()
    assert "adm:mdl:input_prompt" in button_map.values()


def test_build_logs_keyboard():
    kb = build_logs_keyboard(current_limit=25, errors_only=False)
    assert isinstance(kb, InlineKeyboardMarkup)
    callbacks = [btn.callback_data for row in kb.inline_keyboard for btn in row]
    assert "adm:log:view:25:all" in callbacks
    assert "adm:log:view:50:all" in callbacks
    assert "adm:log:view:25:errors" in callbacks
    assert "adm:dash:refresh" in callbacks


def make_mock_update(
    user_id: int = 123456,
    text: str = "/admin",
    is_callback: bool = False,
    callback_data: str | None = None,
):
    update = MagicMock()
    user = MagicMock()
    user.id = user_id
    user.first_name = "TestAdmin"
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
        "admin_roles": {123456: user_role, 999999: UserRole.SUPER_ADMIN},
        "whitelist_user_ids": {123456, 999999},
        "active_model_id": "gpt-4o-mini",
        "start_time": time.time() - 3661,  # 1 hour 1 min 1 sec ago
        "db": db or MagicMock(),
        "openai_client": MagicMock(),
    }
    context.user_data = {}
    return context


@pytest.mark.asyncio
async def test_admin_command_dashboard_rendering():
    update = make_mock_update(user_id=123456, text="/admin")
    context = make_mock_context(user_role=UserRole.ADMIN)

    with patch("src.bot.handlers.admin.count_orders_by_date", new=AsyncMock(return_value=7)):
        with patch("os.path.exists", return_value=True), patch("os.path.getsize", return_value=1024 * 1024):
            await admin_command(update, context)

    update.effective_message.reply_text.assert_awaited_once()
    call_args = update.effective_message.reply_text.call_args
    rendered_text = call_args[0][0]

    assert "BẢNG ĐIỀU KHIỂN QUẢN TRỊ" in rendered_text
    assert "Uptime:" in rendered_text
    assert "1.00 MB" in rendered_text
    assert "gpt-4o-mini" in rendered_text
    assert "7 đơn hàng" in rendered_text
    assert "ADMIN" in rendered_text


@pytest.mark.asyncio
async def test_admin_callback_model_switch_success():
    update = make_mock_update(
        user_id=123456,
        is_callback=True,
        callback_data="adm:mdl:sel:claude-3-5-haiku",
    )
    db = MagicMock()
    context = make_mock_context(user_role=UserRole.ADMIN, db=db)

    with patch(
        "src.bot.handlers.admin.probe_model_reachability",
        new=AsyncMock(return_value=(True, "OK")),
    ), patch("src.bot.handlers.admin.set_setting", new=AsyncMock()):
        await handle_admin_callback(update, context)

    assert context.bot_data["active_model_id"] == "claude-3-5-haiku"
    update.callback_query.edit_message_text.assert_awaited_once()
    msg = update.callback_query.edit_message_text.call_args[1].get("text") or update.callback_query.edit_message_text.call_args[0][0]
    assert "claude-3-5-haiku" in msg


@pytest.mark.asyncio
async def test_admin_callback_model_switch_failure():
    update = make_mock_update(
        user_id=123456,
        is_callback=True,
        callback_data="adm:mdl:sel:broken-model",
    )
    db = MagicMock()
    context = make_mock_context(user_role=UserRole.ADMIN, db=db)

    with patch(
        "src.bot.handlers.admin.probe_model_reachability",
        new=AsyncMock(return_value=(False, "HTTP 404 Not Found")),
    ):
        await handle_admin_callback(update, context)

    assert context.bot_data["active_model_id"] == "gpt-4o-mini"
    update.callback_query.edit_message_text.assert_awaited_once()
    msg = update.callback_query.edit_message_text.call_args[1].get("text") or update.callback_query.edit_message_text.call_args[0][0]
    assert "Kiểm tra kết nối thất bại" in msg
    assert "HTTP 404 Not Found" in msg
    assert "gpt-4o-mini" in msg


@pytest.mark.asyncio
async def test_admin_handlers_resolve_db_when_bot_data_db_is_none():
    update = make_mock_update(user_id=123456, text="/admin")
    context = make_mock_context(user_role=UserRole.ADMIN)
    context.bot_data["db"] = None

    mock_db = MagicMock()
    with patch("src.bot.handlers.admin.get_db_connection") as mock_get_conn:
        mock_ctx = AsyncMock()
        mock_ctx.__aenter__.return_value = mock_db
        mock_ctx.__aexit__.return_value = None
        mock_get_conn.return_value = mock_ctx

        with patch("src.bot.handlers.admin.count_orders_by_date", new=AsyncMock(return_value=12)):
            with patch("os.path.exists", return_value=True), patch("os.path.getsize", return_value=1024 * 1024):
                await admin_command(update, context)

        mock_get_conn.assert_called_once_with("test.db")
        rendered_text = update.effective_message.reply_text.call_args[0][0]
        assert "12 đơn hàng" in rendered_text


@pytest.mark.asyncio
async def test_handle_admin_text_input_add_model_does_not_mutate_default_models():
    initial_default_len = len(DEFAULT_MODELS)
    candidate = "meta-llama/llama-3.3-70b-instruct"

    context = make_mock_context(user_role=UserRole.ADMIN)
    context.user_data["action_state"] = {
        "action": "await_model_name",
        "expires_at": time.time() + 60,
    }
    update = make_mock_update(user_id=123456, text=candidate)

    with patch(
        "src.bot.handlers.admin.probe_model_reachability",
        new=AsyncMock(return_value=(True, "OK")),
    ), patch(
        "src.bot.handlers.admin.get_json_setting",
        new=AsyncMock(return_value=DEFAULT_MODELS),
    ), patch(
        "src.bot.handlers.admin.set_setting",
        new=AsyncMock(),
    ), patch(
        "src.bot.handlers.admin.set_json_setting",
        new=AsyncMock(),
    ):
        handled = await handle_admin_text_input(update, context)

    assert handled is True
    assert len(DEFAULT_MODELS) == initial_default_len
    assert candidate not in DEFAULT_MODELS
    assert context.bot_data["active_model_id"] == candidate


@pytest.mark.asyncio
async def test_logs_command_and_callback():
    update = make_mock_update(user_id=999999, text="/logs")
    context = make_mock_context(user_role=UserRole.SUPER_ADMIN)
    handler = MagicMock()
    handler.format_logs_for_telegram.return_value = "2026-10-25 INFO bot started"
    context.bot_data["log_handler"] = handler

    await logs_command(update, context)
    update.effective_message.reply_text.assert_awaited_once()
    text = update.effective_message.reply_text.call_args[0][0]
    assert "NHẬT KÝ HỆ THỐNG GẦN NHẤT" in text
    assert "<pre><code>2026-10-25 INFO bot started</code></pre>" in text

    cb_update = make_mock_update(
        user_id=999999, is_callback=True, callback_data="adm:log:view:50:errors"
    )
    await handle_logs_callback(cb_update, context)
    handler.format_logs_for_telegram.assert_called_with(limit=50, errors_only=True)
    cb_update.callback_query.edit_message_text.assert_awaited_once()
