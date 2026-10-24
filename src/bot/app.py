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
from src.bot.handlers.ingest import handle_photo_order, handle_text_order
from src.bot.handlers.orders import handle_menu_reply, handle_order_nav_callback
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

    api_key_str = settings.nine_router_api_key.get_secret_value() or "dummy_key_for_init"
    openai_client = AsyncOpenAI(
        base_url=settings.nine_router_base_url,
        api_key=api_key_str,
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

    # Register main menu Reply Keyboard handler (MUST be registered before LLM text ingestion)
    app.add_handler(
        MessageHandler(
            filters.Regex(r"^(📦 Đơn hôm nay|📋 Xem theo ngày|📝 Nhập đơn mới|❓ Trợ giúp)$"),
            handle_menu_reply,
        ),
        group=0,
    )

    # Register navigation and order callbacks at group 0
    app.add_handler(
        CallbackQueryHandler(
            handle_order_nav_callback,
            pattern=r"^(ord_(dt|pg|v|bk):|ord_noop$|ord_act:(pick_date|new)$)",
        ),
        group=0,
    )
    app.add_handler(
        CallbackQueryHandler(handle_order_callback, pattern=r"^ord:(cf|ca|ad):"),
        group=0,
    )
    app.add_handler(
        MessageHandler(filters.PHOTO, handle_photo_order),
        group=0,
    )
    app.add_handler(
        MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text_order),
        group=0,
    )

    return app
