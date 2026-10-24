from telegram import Update
from telegram.ext import Application, ApplicationBuilder, CommandHandler, TypeHandler

from src.bot.handlers.base import ping_command, start_command
from src.bot.security import whitelist_gate
from src.config import Settings


def build_application(settings: Settings) -> Application:
    """Build and configure the Telegram Bot Application."""
    app = ApplicationBuilder().token(settings.telegram_bot_token.get_secret_value()).build()

    # Store settings and whitelist set in bot_data for centralized access
    app.bot_data["settings"] = settings
    app.bot_data["whitelist_user_ids"] = set(settings.telegram_whitelist_user_ids)

    # Register security gate at group -1 (runs before any application handler)
    app.add_handler(TypeHandler(Update, whitelist_gate), group=-1)

    # Register base command handlers at group 0
    app.add_handler(CommandHandler("start", start_command), group=0)
    app.add_handler(CommandHandler("ping", ping_command), group=0)

    return app
