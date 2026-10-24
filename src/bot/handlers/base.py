import asyncio
import logging

from telegram import Update
from telegram.ext import ContextTypes

from src.bot.keyboards import build_main_menu_reply_keyboard
from src.db.connection import get_db_connection

logger = logging.getLogger(__name__)


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /start command for whitelisted users with persistent 2x2 reply keyboard."""
    user = update.effective_user
    user_id = user.id if user else "Unknown"
    first_name = user.first_name if user else "bác"

    text = (
        f"Xin chào {first_name}!\n\n"
        f"🤖 Bot Quản Lý Đơn Hàng Băng Cassette sẵn sàng phục vụ.\n"
        f"Telegram User ID nhận diện: `{user_id}`\n\n"
        f"Bác chỉ cần bấm các nút to bên dưới để xem đơn hoặc gửi tin nhắn đặt hàng bất kỳ lúc nào nhé!"
    )
    keyboard = build_main_menu_reply_keyboard()
    if update.effective_message:
        await update.effective_message.reply_text(
            text,
            reply_markup=keyboard,
            parse_mode="Markdown",
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


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /help command providing bot usage guidance per D-01."""
    text = (
        "❓ <b>HƯỚNG DẪN SỬ DỤNG BOT</b>\n\n"
        "• <b>📦 Đơn hôm nay:</b> Xem nhanh danh sách các đơn hàng phát sinh trong ngày.\n"
        "• <b>📋 Xem theo ngày:</b> Xem lại đơn của các ngày trước.\n"
        "• <b>📝 Nhập đơn mới:</b> Dán tin nhắn đặt hàng của khách để tạo đơn tự động.\n"
        "• <b>🔍 Tra cứu đơn:</b> Tìm kiếm đơn hàng hoặc hỏi thống kê bằng câu nói tự nhiên.\n"
        "• <b>Chạm để Copy:</b> Trên thẻ chi tiết đơn, chạm vào SĐT hoặc Địa chỉ để sao chép nhanh sang app giao hàng.\n\n"
        "Nếu gặp khó khăn, bác cứ bấm các nút to trên màn hình để thao tác nhé!"
    )
    if update.effective_message:
        await update.effective_message.reply_text(text, parse_mode="HTML")

