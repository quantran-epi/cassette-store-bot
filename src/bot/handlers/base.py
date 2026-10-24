from telegram import Update
from telegram.ext import ContextTypes


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
    """Handle /ping command to verify bot responsiveness."""
    if update.effective_message:
        await update.effective_message.reply_text("🏓 Pong! Bot đang hoạt động bình thường.")
