from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from telegram import CallbackQuery, Message, Update

from src.bot.handlers.base import handle_tutorial_callback, help_command
from src.bot.handlers.orders import handle_menu_reply
from src.bot.keyboards import InlineKeyboardMarkup
from src.bot.tutorial import (
    PAGE_COUNT,
    TUTORIAL_PAGES,
    build_tutorial_keyboard,
    render_tutorial_page,
)


def _flat_callbacks(markup: InlineKeyboardMarkup) -> list[str]:
    return [
        btn.callback_data
        for row in markup.inline_keyboard
        for btn in row
        if btn.callback_data is not None
    ]


def test_tutorial_pages_shape():
    """Static pages, each with title/body/try_kind; page 2 is the pending-orders guide."""
    assert PAGE_COUNT == len(TUTORIAL_PAGES) >= 5
    for page in TUTORIAL_PAGES:
        assert page["title"]
        assert page["body"]
        assert page["try_kind"] is None or isinstance(page["try_kind"], str)


def test_render_first_page_keeps_legacy_strings():
    """Page 1 keeps the title and 'Tra cứu đơn' strings older tests assert."""
    text, kb = render_tutorial_page(0)
    assert "HƯỚNG DẪN SỬ DỤNG BOT" in text
    assert f"Trang 1/{PAGE_COUNT}" in text
    assert "Tra cứu đơn" in text
    assert "ĐƠN CHỜ LÀM" in render_tutorial_page(1)[0]
    assert isinstance(kb, InlineKeyboardMarkup)


def test_navigation_bounds_and_indicator():
    """First page has no back, last has no next, indicator shows page count."""
    first_cbs = _flat_callbacks(build_tutorial_keyboard(0))
    assert not any(cb.startswith("help:page:-") for cb in first_cbs)
    assert "help:page:1" in first_cbs
    assert f"Trang 1/{PAGE_COUNT}" in [
        btn.text for row in build_tutorial_keyboard(0).inline_keyboard for btn in row
    ]

    last_idx = PAGE_COUNT - 1
    last_cbs = _flat_callbacks(build_tutorial_keyboard(last_idx))
    assert f"help:page:{last_idx - 1}" in last_cbs
    assert f"help:page:{PAGE_COUNT}" not in last_cbs

    mid_idx = PAGE_COUNT // 2
    assert PAGE_COUNT >= 5
    mid_cbs = _flat_callbacks(build_tutorial_keyboard(mid_idx))
    assert f"help:page:{mid_idx - 1}" in mid_cbs
    assert f"help:page:{mid_idx + 1}" in mid_cbs
    assert "help:noop" in mid_cbs


def test_try_now_button_present_only_when_defined():
    """Pages with try_kind expose help:try:<kind>; pages without don't."""
    for idx, page in enumerate(TUTORIAL_PAGES):
        cbs = _flat_callbacks(build_tutorial_keyboard(idx))
        if page["try_kind"]:
            assert f"help:try:{page['try_kind']}" in cbs
        else:
            assert not any(cb.startswith("help:try:") for cb in cbs)


def test_render_clamps_out_of_range():
    """Negative/too-large page indices clamp instead of raising."""
    low_text, _ = render_tutorial_page(-5)
    high_text, _ = render_tutorial_page(999)
    assert f"Trang 1/{PAGE_COUNT}" in low_text
    assert f"Trang {PAGE_COUNT}/{PAGE_COUNT}" in high_text


@pytest.mark.asyncio
async def test_help_command_matches_render_page_zero():
    """help_command replies with render_tutorial_page(0) text and keyboard."""
    message = MagicMock(spec=Message)
    message.reply_text = AsyncMock()
    update = MagicMock(spec=Update)
    update.effective_message = message

    await help_command(update, MagicMock())

    args, kwargs = message.reply_text.call_args
    expected_text, _ = render_tutorial_page(0)
    sent_text = kwargs.get("text", args[0] if args else "")
    assert sent_text == expected_text
    assert "help:page:1" in _flat_callbacks(kwargs["reply_markup"])


@pytest.mark.asyncio
async def test_menu_help_button_matches_help_command():
    """The '❓ Trợ giúp' reply button produces identical output to /help."""
    menu_message = MagicMock(spec=Message)
    menu_message.text = "❓ Trợ giúp"
    menu_message.reply_text = AsyncMock()
    menu_update = MagicMock(spec=Update)
    menu_update.message = menu_message
    menu_context = MagicMock()
    menu_context.user_data = {}

    await handle_menu_reply(menu_update, menu_context)

    help_message = MagicMock(spec=Message)
    help_message.reply_text = AsyncMock()
    help_update = MagicMock(spec=Update)
    help_update.effective_message = help_message

    await help_command(help_update, MagicMock())

    menu_args, menu_kwargs = menu_message.reply_text.call_args
    help_args, help_kwargs = help_message.reply_text.call_args
    menu_text = menu_kwargs.get("text", menu_args[0] if menu_args else "")
    help_text = help_kwargs.get("text", help_args[0] if help_args else "")
    assert menu_text == help_text
    assert _flat_callbacks(menu_kwargs["reply_markup"]) == _flat_callbacks(
        help_kwargs["reply_markup"]
    )


def _edited_text(query: MagicMock) -> str:
    args, kwargs = query.edit_message_text.call_args
    return kwargs.get("text", args[0] if args else "")


def _edited_markup(query: MagicMock) -> InlineKeyboardMarkup:
    _, kwargs = query.edit_message_text.call_args
    return kwargs["reply_markup"]


def _tutorial_query(data: str) -> tuple[MagicMock, MagicMock]:
    query = MagicMock()
    query.answer = AsyncMock()
    query.edit_message_text = AsyncMock()
    query.data = data
    query.id = "cb-1"
    update = MagicMock(spec=Update)
    update.update_id = 1
    update.callback_query = query
    return update, query


def _real_tutorial_query(data: str) -> tuple[Update, CallbackQuery]:
    """Real PTB objects: TelegramObject freezes attributes, so this catches
    code that tries to assign to query.data (a real bug we hit once)."""
    bot = MagicMock()
    update = Update.de_json(
        {
            "update_id": 1,
            "callback_query": {
                "id": "cb-1",
                "chat_instance": "ci",
                "data": data,
                "inline_message_id": "inline-1",
                "from": {"id": 1, "is_bot": False, "first_name": "Bác"},
            },
        },
        bot,
    )
    return update, update.callback_query


@pytest.mark.asyncio
async def test_page_navigation_and_clamping():
    """help:page:n edits to that page; out-of-range clamps."""
    update, query = _tutorial_query("help:page:1")
    await handle_tutorial_callback(update, MagicMock())
    query.answer.assert_awaited_once()
    assert f"Trang 2/{PAGE_COUNT}" in _edited_text(query)

    update, query = _tutorial_query("help:page:99")
    await handle_tutorial_callback(update, MagicMock())
    assert f"Trang {PAGE_COUNT}/{PAGE_COUNT}" in _edited_text(query)

    update, query = _tutorial_query("help:page:0")
    await handle_tutorial_callback(update, MagicMock())
    cbs = _flat_callbacks(_edited_markup(query))
    assert "help:page:-1" not in cbs


@pytest.mark.asyncio
async def test_try_now_dispatches_to_existing_handlers():
    """help:try:<kind> calls the existing handler with the mapped callback_data."""
    with patch(
        "src.bot.handlers.orders.handle_order_nav_callback", new_callable=AsyncMock
    ) as mock_nav, patch(
        "src.bot.handlers.search.handle_search_callback", new_callable=AsyncMock
    ) as mock_search:
        update, _ = _tutorial_query("help:try:today_orders")
        await handle_tutorial_callback(update, MagicMock())
        assert mock_nav.await_args.args[0].callback_query.data.startswith("ord_dt:")

        update, _ = _tutorial_query("help:try:search")
        await handle_tutorial_callback(update, MagicMock())
        mock_search.assert_awaited_once()
        assert mock_search.await_args.args[0].callback_query.data == "sch_new"

        mock_nav.reset_mock()
        mock_search.reset_mock()
        update, _ = _tutorial_query("help:try:pending_orders")
        await handle_tutorial_callback(update, MagicMock())
        mock_nav.assert_awaited_once()
        assert mock_nav.await_args.args[0].callback_query.data == "ord_ls:CHO_LAM:1"
        mock_search.assert_not_awaited()

        mock_nav.reset_mock()
        mock_search.reset_mock()
        update, query = _tutorial_query("help:try:bogus")
        await handle_tutorial_callback(update, MagicMock())
        mock_nav.assert_not_awaited()
        mock_search.assert_not_awaited()
        query.answer.assert_awaited_once()


@pytest.mark.asyncio
async def test_try_now_works_with_immutable_real_callback_query():
    """Regression: PTB freezes CallbackQuery, so assigning query.data raises."""
    update, query = _real_tutorial_query("help:try:today_orders")

    with patch(
        "src.bot.handlers.orders.handle_order_nav_callback", new_callable=AsyncMock
    ) as mock_nav:
        await handle_tutorial_callback(update, MagicMock())

    mock_nav.assert_awaited_once()
    assert mock_nav.await_args.args[0].callback_query.data.startswith("ord_dt:")
    assert query.data == "help:try:today_orders"


@pytest.mark.asyncio
async def test_unknown_data_is_ignored():
    """Malformed or unknown callback data just answers, never raises."""
    update, query = _tutorial_query("help:whatever")
    await handle_tutorial_callback(update, MagicMock())
    query.answer.assert_awaited_once()
    query.edit_message_text.assert_not_awaited()


def test_help_text_single_source():
    """The help title lives only in tutorial.py across src."""
    hits = [
        path
        for path in Path("src").rglob("*.py")
        if "HƯỚNG DẪN SỬ DỤNG BOT" in path.read_text(encoding="utf-8")
    ]
    assert [p.as_posix() for p in hits] == ["src/bot/tutorial.py"]
