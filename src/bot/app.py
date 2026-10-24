from dataclasses import dataclass
import aiosqlite
from openai import AsyncOpenAI
from telegram import Update
from telegram.ext import (
    Application,
    ApplicationBuilder,
    CallbackQueryHandler,
    CommandHandler,
    MessageHandler,
    TypeHandler,
    filters,
)

from src.bot.handlers.base import ping_command, start_command
from src.bot.handlers.callbacks import handle_order_callback
from src.bot.handlers.ingest import handle_text_order
from src.bot.security import whitelist_gate
from src.config import Settings


@dataclass
class AppContext:
    """Central container for application dependencies."""

    settings: Settings
    openai_client: AsyncOpenAI
    db: aiosqlite.Connection | None = None


def build_application(settings: Settings, db: aiosqlite.Connection | None = None) -> Application:
    """Build and configure the Telegram Bot Application."""
    app = ApplicationBuilder().token(settings.telegram_bot_token.get_secret_value()).build()

    openai_client = AsyncOpenAI(
        base_url=settings.nine_router_base_url,
        api_key=settings.nine_router_api_key.get_secret_value(),
    )
    app_context = AppContext(
        settings=settings,
        openai_client=openai_client,
        db=db,
    )

    # Store settings, whitelist set, and app_context in bot_data
    app.bot_data["settings"] = settings
    app.bot_data["whitelist_user_ids"] = set(settings.telegram_whitelist_user_ids)
    app.bot_data["app_context"] = app_context
    app.bot_data["db"] = db
    app.bot_data["openai_client"] = openai_client

    # Register security gate at group -1 (runs before any application handler)
    app.add_handler(TypeHandler(Update, whitelist_gate), group=-1)

    # Register base command handlers at group 0
    app.add_handler(CommandHandler("start", start_command), group=0)
    app.add_handler(CommandHandler("ping", ping_command), group=0)

    # Register ingestion and callback handlers at group 0
    app.add_handler(CallbackQueryHandler(handle_order_callback, pattern=r"^ord:(cf|ca):"), group=0)
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text_order), group=0)

    return app
