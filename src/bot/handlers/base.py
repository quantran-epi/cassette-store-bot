import asyncio
import logging

from telegram import Update
from telegram.ext import ContextTypes

from src.db.connection import get_db_connection

logger = logging.getLogger(__name__)


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /start command for whitelisted users."""
    user = update.effective_user
    user_id = user.id if user else "Unknown"
    first_name = user.first_name if user else "bạn"

    text = (
        f"Xin chào {first_name}!\n\n"
        f"🤖 Bot Quản Lý Đơn Hàng Băng Cassette sẵn sàng phục vụ.\n"
        f"Telegram User ID nhận diện: `{user_id}`\n\n"
        f"Sử dụng lệnh /ping để kiểm tra trạng thái hoạt động."
    )
    if update.effective_message:
        await update.effective_message.reply_text(text, parse_mode="Markdown")


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
