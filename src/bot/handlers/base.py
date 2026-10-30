import asyncio
import html
import logging
import re
from datetime import datetime
from typing import Any, Coroutine

from telegram import CallbackQuery, Update
from telegram.constants import ChatAction
from telegram.error import BadRequest
from telegram.ext import ContextTypes

from src.bot.keyboards import TZ_VN, build_main_menu_reply_keyboard
from src.bot.tutorial import render_tutorial_page
from src.db.connection import get_db_connection

logger = logging.getLogger(__name__)

TUTORIAL_PAGE_PATTERN = re.compile(r"^help:page:(-?\d+)$")
TUTORIAL_TRY_PATTERN = re.compile(r"^help:try:([a-z_]+)$")


async def run_with_typing(chat, coro: Coroutine[Any, Any, Any]) -> Any:
    """Await `coro` while the chat shows "typing…" until it resolves."""
    stop_event = asyncio.Event()

    async def _keep_typing() -> None:
        while not stop_event.is_set():
            try:
                await chat.send_action(ChatAction.TYPING)
            except Exception as e:
                logger.debug("Failed to send typing chat action: %s", e)
            try:
                await asyncio.wait_for(stop_event.wait(), timeout=4.0)
            except asyncio.TimeoutError:
                pass

    typing_task = asyncio.create_task(_keep_typing())
    try:
        return await coro
    finally:
        stop_event.set()
        typing_task.cancel()
        try:
            await typing_task
        except asyncio.CancelledError:
            pass


# Whitelist kind -> existing callback. Client can never pass a target callback directly.
TRY_ACTIONS: dict[str, str] = {
    "today_orders": "ord_dt:{today}",
    "date_picker": "ord_act:pick_date",
    "search": "sch_new",
    "pending_orders": "ord_ls:CHO_LAM:1",
}


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /start command for whitelisted users with persistent reply keyboard."""
    user = update.effective_user
    user_id = user.id if user else "Unknown"
    first_name = user.first_name if user else "bác"

    safe_name = html.escape(first_name)
    text = (
        f"Xin chào {safe_name}!\n\n"
        f"🤖 Bot Quản Lý Đơn Hàng Băng Cassette sẵn sàng phục vụ.\n"
        f"Telegram User ID nhận diện: <code>{user_id}</code>\n\n"
        f"Bác chỉ cần bấm các nút to bên dưới để xem đơn hoặc gửi tin nhắn đặt hàng bất kỳ lúc nào nhé!"
    )
    keyboard = build_main_menu_reply_keyboard()
    if update.effective_message:
        await update.effective_message.reply_text(
            text,
            reply_markup=keyboard,
            parse_mode="HTML",
        )


async def ping_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /ping command to verify bot responsiveness and database connectivity."""
    db_status = "UNKNOWN"
    settings = context.bot_data.get("settings") if context.bot_data else None

    if settings and getattr(settings, "sqlite_db_path", None):
        try:
            # Probe DB with 5s timeout to prevent thread-lock DoS (T-01-11)
            async with asyncio.timeout(5.0):
                async with get_db_connection(settings.sqlite_db_path) as db:
                    async with db.execute("SELECT 1") as cursor:
                        await cursor.fetchone()
            db_status = "OK (WAL mode)"
        except Exception as e:
            logger.error("Database health probe failed during /ping: %s", e)
            db_status = "ERROR"
    else:
        db_status = "N/A"

    text = f"🏓 Pong!\nBot: Running\nDatabase: {db_status}"
    if update.effective_message:
        await update.effective_message.reply_text(text)


async def send_tutorial(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    page: int = 0,
    message=None,
) -> None:
    """Send one tutorial page as a fresh message (single source with /help)."""
    text, keyboard = render_tutorial_page(page)
    target = message or update.effective_message
    if target:
        await target.reply_text(text, reply_markup=keyboard, parse_mode="HTML")


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /help command: open the first tutorial page."""
    await send_tutorial(update, context, 0)


async def handle_tutorial_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle help:page:<n> navigation and help:try:<kind> shortcuts."""
    query = update.callback_query
    if not query or not query.data:
        return
    data = query.data

    if data == "help:noop":
        await query.answer()
        return

    m = TUTORIAL_PAGE_PATTERN.match(data)
    if m:
        await query.answer()
        text, keyboard = render_tutorial_page(int(m.group(1)))
        try:
            await query.edit_message_text(text, reply_markup=keyboard, parse_mode="HTML")
        except BadRequest as e:
            if "Message is not modified" not in str(e):
                raise
        return

    m = TUTORIAL_TRY_PATTERN.match(data)
    if not m:
        await query.answer()
        return

    kind = m.group(1)
    if kind not in TRY_ACTIONS:
        await query.answer()
        return

    today = datetime.now(TZ_VN).strftime("%Y-%m-%d")
    action = TRY_ACTIONS[kind].format(today=today)

    # Local imports: orders imports base, so a top-level import would cycle.
    from src.bot.handlers.orders import handle_order_nav_callback
    from src.bot.handlers.search import handle_search_callback

    # CallbackQuery is immutable in PTB, so hand the existing handlers a clone
    # carrying the target callback_data (same id, so query.answer still works).
    action_query = CallbackQuery(
        id=query.id,
        from_user=query.from_user,
        chat_instance=query.chat_instance,
        data=action,
        message=query.message,
        inline_message_id=query.inline_message_id,
    )
    action_query.set_bot(context.bot)  # returns None in PTB 22.x (in-place)
    action_update = Update(update_id=update.update_id, callback_query=action_query)
    action_update.set_bot(context.bot)

    if kind == "search":
        await handle_search_callback(action_update, context)
    else:
        await handle_order_nav_callback(action_update, context)
