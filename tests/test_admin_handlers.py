import time
from unittest.mock import AsyncMock, MagicMock, patch
import pytest

from src.bot.handlers.admin import admin_command, handle_admin_callback, handle_admin_text_input
from src.bot.handlers.logs import handle_logs_callback, logs_command
from src.bot.security import UserRole
from src.config import Settings


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
        "db": db,
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

    # Active model in bot_data must be updated
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

    # Active model must remain unchanged
    assert context.bot_data["active_model_id"] == "gpt-4o-mini"
    update.callback_query.edit_message_text.assert_awaited_once()
    msg = update.callback_query.edit_message_text.call_args[1].get("text") or update.callback_query.edit_message_text.call_args[0][0]
    assert "Kiểm tra kết nối thất bại" in msg
    assert "HTTP 404 Not Found" in msg
    assert "gpt-4o-mini" in msg


@pytest.mark.asyncio
async def test_logs_command_and_callback():
    update = make_mock_update(user_id=999999, text="/logs")  # Super Admin
    context = make_mock_context(user_role=UserRole.SUPER_ADMIN)
    handler = MagicMock()
    handler.format_logs_for_telegram.return_value = "2026-10-25 INFO bot started"
    context.bot_data["log_handler"] = handler

    await logs_command(update, context)
    update.effective_message.reply_text.assert_awaited_once()
    text = update.effective_message.reply_text.call_args[0][0]
    assert "NHẬT KÝ HỆ THỐNG GẦN NHẤT" in text
    assert "<pre><code>2026-10-25 INFO bot started</code></pre>" in text

    # Callback refresh
    cb_update = make_mock_update(
        user_id=999999, is_callback=True, callback_data="adm:log:view:50:errors"
    )
    await handle_logs_callback(cb_update, context)
    handler.format_logs_for_telegram.assert_called_with(limit=50, errors_only=True)
    cb_update.callback_query.edit_message_text.assert_awaited_once()
