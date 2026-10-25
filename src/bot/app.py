import asyncio
from dataclasses import dataclass
import logging
import time

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

from src.bot.handlers.admin import admin_command, handle_admin_callback
from src.bot.handlers.base import help_command, ping_command, start_command
from src.bot.handlers.callbacks import handle_order_callback
from src.bot.handlers.ingest import handle_photo_order, handle_text_order
from src.bot.handlers.logs import handle_logs_callback, logs_command
from src.bot.handlers.order_actions import (
    handle_order_action_callback,
    handle_order_status_callback,
)
from src.bot.handlers.orders import handle_menu_reply, handle_order_nav_callback
from src.bot.handlers.search import handle_search_callback
from src.bot.logging_handler import RingBufferLogHandler
from src.bot.security import UserRole, whitelist_gate
from src.config import Settings
from src.db.admin import list_admin_users, sync_root_super_admin
from src.db.settings import get_setting


@dataclass
class AppContext:
    """Central container for application dependencies."""

    settings: Settings
    openai_client: AsyncOpenAI
    db: aiosqlite.Connection | None = None


async def _do_sync(app: Application, db: aiosqlite.Connection, settings: Settings) -> None:
    """Execute startup synchronization between settings, SQLite, and in-memory caches."""
    await sync_root_super_admin(
        db, settings.telegram_super_admin_id, settings.telegram_whitelist_user_ids
    )
    admin_users = await list_admin_users(db)
    for user in admin_users:
        uid = user["telegram_id"]
        role = user.get("role", "STAFF")
        app.bot_data["admin_roles"][uid] = UserRole(role)
        app.bot_data["whitelist_user_ids"].add(uid)

    active_model = await get_setting(db, "active_model_id")
    if active_model:
        app.bot_data["active_model_id"] = active_model


async def startup_sync(app: Application) -> None:
    """Synchronize root Super Admin and whitelist into SQLite and bot_data caches."""
    db = app.bot_data.get("db")
    settings = app.bot_data.get("settings")
    if not settings:
        return

    if db is not None:
        await _do_sync(app, db, settings)
    else:
        from src.db.connection import get_db_connection

        try:
            async with get_db_connection(settings.sqlite_db_path) as conn:
                await _do_sync(app, conn, settings)
        except Exception:
            logging.getLogger(__name__).exception("Startup synchronization failed")


def build_application(settings: Settings, db: aiosqlite.Connection | None = None) -> Application:
    """Build and configure the Telegram Bot Application."""
    app = (
        ApplicationBuilder()
        .token(settings.telegram_bot_token.get_secret_value())
        .post_init(startup_sync)
        .build()
    )

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

    # Initialize in-memory ring buffer log handler on root logger
    log_handler = RingBufferLogHandler(capacity=100)
    logging.getLogger().addHandler(log_handler)

    # Store settings, caches, and app_context in bot_data
    app.bot_data["settings"] = settings
    app.bot_data["whitelist_user_ids"] = set(settings.telegram_whitelist_user_ids)
    app.bot_data["admin_roles"] = {}
    app.bot_data["active_model_id"] = settings.nine_router_model_id
    app.bot_data["start_time"] = time.time()
    app.bot_data["log_handler"] = log_handler
    app.bot_data["app_context"] = app_context
    app.bot_data["db"] = db
    app.bot_data["openai_client"] = openai_client

    # Synchronize if loop is already running or db is provided
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None

    if loop and loop.is_running():
        loop.create_task(startup_sync(app))
    elif db is not None:
        try:
            asyncio.run(startup_sync(app))
        except RuntimeError:
            pass

    # Register security gate at group -1 (runs before any application handler)
    app.add_handler(TypeHandler(Update, whitelist_gate), group=-1)

    # Register base command handlers at group 0
    app.add_handler(CommandHandler("start", start_command), group=0)
    app.add_handler(CommandHandler("ping", ping_command), group=0)
    app.add_handler(CommandHandler("help", help_command), group=0)

    # Register admin commands at group 0
    app.add_handler(CommandHandler("admin", admin_command), group=0)
    app.add_handler(CommandHandler("logs", logs_command), group=0)

    # Register main menu Reply Keyboard handler (MUST be registered before LLM text ingestion)
    app.add_handler(
        MessageHandler(
            filters.Regex(r"^(📦 Đơn hôm nay|📋 Xem theo ngày|📝 Nhập đơn mới|🔍 Tra cứu đơn|❓ Trợ giúp)$"),
            handle_menu_reply,
        ),
        group=0,
    )

    # Register admin callback query handlers at group 0 (specific patterns first)
    app.add_handler(
        CallbackQueryHandler(
            handle_logs_callback,
            pattern=r"^adm:log:",
        ),
        group=0,
    )
    app.add_handler(
        CallbackQueryHandler(
            handle_admin_callback,
            pattern=r"^adm:",
        ),
        group=0,
    )

    # Register search callbacks at group 0
    app.add_handler(
        CallbackQueryHandler(
            handle_search_callback,
            pattern=r"^sch_",
        ),
        group=0,
    )

    # Register navigation and order callbacks at group 0
    app.add_handler(
        CallbackQueryHandler(
            handle_order_action_callback,
            pattern=r"^ord_act:(track|add_photo|view_photo|cancel)(:\d+)?$",
        ),
        group=0,
    )
    app.add_handler(
        CallbackQueryHandler(
            handle_order_status_callback,
            pattern=r"^(ord_st(_menu|_cf)?:|ord_v_cur:)",
        ),
        group=0,
    )
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
