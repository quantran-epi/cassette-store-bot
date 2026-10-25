from unittest.mock import AsyncMock, MagicMock
import pytest
from telegram import InlineKeyboardMarkup

from src.bot.keyboards import (
    build_admin_main_keyboard,
    build_logs_keyboard,
    build_model_switcher_keyboard,
    build_whitelist_confirm_delete_keyboard,
    build_whitelist_keyboard,
    build_whitelist_user_detail_keyboard,
)
from src.bot.security import UserRole
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
    # Admin role
    kb = build_admin_main_keyboard(user_role=UserRole.ADMIN)
    assert isinstance(kb, InlineKeyboardMarkup)
    assert len(kb.inline_keyboard) == 3
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

    # Row 3: Refresh, Close
    assert len(kb.inline_keyboard[2]) == 2
    assert "Làm mới" in kb.inline_keyboard[2][0].text
    assert kb.inline_keyboard[2][0].callback_data == "adm:dash:refresh"
    assert "Đóng" in kb.inline_keyboard[2][1].text
    assert kb.inline_keyboard[2][1].callback_data == "adm:dash:close"


def test_build_whitelist_keyboard():
    users = [
        {"telegram_id": 111, "name": "Admin 1", "role": "ADMIN"},
        {"telegram_id": 222, "name": "Staff 1", "role": "STAFF"},
    ]
    kb = build_whitelist_keyboard(users, current_page=1, total_pages=1)
    assert isinstance(kb, InlineKeyboardMarkup)
    # Check buttons contain users
    callbacks = [btn.callback_data for row in kb.inline_keyboard for btn in row]
    assert "adm:wl:view:111" in callbacks
    assert "adm:wl:view:222" in callbacks
    assert "adm:wl:add_prompt" in callbacks
    assert "adm:dash:refresh" in callbacks or "adm:dash:back" in callbacks


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
    # Root user must not have delete or role switch callbacks
    assert "adm:wl:rm_req:999999" not in callbacks
    assert not any("adm:wl:role:999999:" in cb for cb in callbacks)
    # Must have disabled indicator or back button
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
    # Active model has [✓]
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
    assert "adm:dash:refresh" in callbacks or "adm:dash:back" in callbacks
