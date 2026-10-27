import asyncio
import logging
import time
import zoneinfo
from dataclasses import dataclass
from datetime import time as dt_time

import aiosqlite
from openai import AsyncOpenAI
from telegram import Update
from telegram.ext import (
    Application,
    ApplicationBuilder,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    TypeHandler,
    filters,
)

from src.bot.handlers.admin import admin_command, handle_admin_callback
from src.bot.handlers.backup import (
    backup_command,
    handle_backup_document,
    handle_restore_callback,
)
from src.bot.handlers.base import (
    handle_tutorial_callback,
    help_command,
    ping_command,
    start_command,
)
from src.bot.handlers.callbacks import handle_mutation_callback, handle_order_callback
from src.bot.handlers.ingest import handle_photo_order, handle_text_order
from src.bot.handlers.logs import handle_logs_callback, logs_command
from src.bot.handlers.order_actions import (
    handle_order_action_callback,
    handle_order_status_callback,
)
from src.bot.handlers.orders import handle_menu_reply, handle_order_nav_callback
from src.bot.handlers.search import handle_customer_callback, handle_search_callback
from src.bot.logging_handler import RingBufferLogHandler
from src.bot.security import UserRole, whitelist_gate
from src.config import Settings
from src.db.admin import list_admin_users, sync_root_super_admin
from src.db.settings import get_maintenance_mode, get_setting

VN_TZ = zoneinfo.ZoneInfo("Asia/Ho_Chi_Minh")
JOB_BACKUP_NAME = "daily_database_backup"
JOB_REMINDER_NAME = "check_due_reminders"
HEARTBEAT_PATH = "/tmp/bot_heartbeat"
JOB_HEARTBEAT_NAME = "bot_liveness_heartbeat"


async def heartbeat_job_callback(context: ContextTypes.DEFAULT_TYPE) -> None:
    """Periodic job updating heartbeat timestamp file for container healthcheck."""
    try:
        now_ts = str(time.time())
        with open(HEARTBEAT_PATH, "w", encoding="utf-8") as f:
            f.write(now_ts)
    except Exception as e:
        logging.getLogger(__name__).warning("Failed to update heartbeat file: %s", e)


def schedule_heartbeat_job(app: Application) -> None:
    """Schedule repeating heartbeat file touch every 30s."""
    if not app.job_queue:
        return
    for job in app.job_queue.get_jobs_by_name(JOB_HEARTBEAT_NAME):
        job.schedule_removal()
    app.job_queue.run_repeating(
        heartbeat_job_callback,
        interval=30,
        first=1,
        name=JOB_HEARTBEAT_NAME,
    )


async def post_shutdown_cleanup(app: Application) -> None:
    """Execute clean WAL checkpoint and close database resources on SIGTERM/SIGINT."""
    logger = logging.getLogger(__name__)
    logger.info("Initiating graceful shutdown sequence...")
    settings = app.bot_data.get("settings")
    db_path = getattr(settings, "sqlite_db_path", "cassette_store.db")

    start_t = time.perf_counter()
    try:
        async with aiosqlite.connect(db_path) as db:
            cursor = await db.execute("PRAGMA wal_checkpoint(TRUNCATE);")
            res = await cursor.fetchall()
            dur = (time.perf_counter() - start_t) * 1000
            logger.info("SQLite WAL checkpoint TRUNCATE completed in %.2fms: %s", dur, res)
    except Exception as e:
        logger.error("Error during WAL checkpoint in post_shutdown: %s", e)
    finally:
        logger.info("Graceful shutdown finished cleanly.")


HEARTBEAT_PATH = "/tmp/bot_heartbeat"
JOB_HEARTBEAT_NAME = "bot_liveness_heartbeat"


async def daily_backup_job_callback(context: ContextTypes.DEFAULT_TYPE) -> None:
    """Scheduled background job: execute hot backup and upload to Super Admin."""
    settings = context.bot_data.get("settings")
    if not settings:
        return
    super_admin_id = getattr(settings, "telegram_super_admin_id", None)
    if not super_admin_id:
        return

    try:
        from src.bot.handlers.admin import _get_active_db_context
        from src.services.backup import execute_backup, send_backup_document

        async with _get_active_db_context(context) as db:
            if not db:
                return
            stats = await execute_backup(db)

        if stats["is_oversized"]:
            await context.bot.send_message(
                chat_id=super_admin_id,
                text=(
                    f"⚠️ <b>[Sao lưu tự động] File nén >= 48MB</b>\n"
                    f"Dung lượng: <code>{stats['gz_size'] / (1024 * 1024):.2f} MB</code> (Giới hạn Telegram: 50MB)\n"
                    f"Đường dẫn server: <code>{stats['gz_path']}</code>"
                ),
                parse_mode="HTML",
            )
            return

        reduction = (1 - (stats["gz_size"] / max(stats["raw_size"], 1))) * 100
        caption = (
            f"💾 <b>BẢN SAO LƯU ĐỊNH KỲ TỰ ĐỘNG</b>\n"
            f"────────────────────\n"
            f"⏱️ <b>Thời gian:</b> {stats['timestamp_str']} (UTC+7)\n"
            f"📦 <b>Dung lượng:</b> {stats['raw_size'] / (1024 * 1024):.2f} MB ➔ {stats['gz_size'] / (1024 * 1024):.2f} MB (Giảm {reduction:.1f}%)\n"
            f"📊 <b>Dữ liệu:</b> {stats['order_count']} đơn hàng | {stats['customer_count']} khách hàng\n"
            f"────────────────────"
        )

        sent = await send_backup_document(
            bot=context.bot,
            chat_id=super_admin_id,
            file_path=stats["gz_path"],
            caption=caption,
        )
        if not sent:
            await context.bot.send_message(
                chat_id=super_admin_id,
                text=(
                    f"❌ <b>[Sao lưu tự động] Gửi file thất bại sau 3 lần thử</b>\n"
                    f"Bản sao lưu đã được giữ lại trên máy chủ: <code>{stats['gz_path']}</code>"
                ),
                parse_mode="HTML",
            )
    except Exception as e:
        logging.getLogger(__name__).exception("Scheduled backup failed: %s", e)
        try:
            await context.bot.send_message(
                chat_id=super_admin_id,
                text=f"❌ <b>[Sao lưu tự động] Gặp lỗi nghiêm trọng:</b> {e}",
                parse_mode="HTML",
            )
        except Exception:
            pass


def schedule_daily_backup(app: Application, time_str: str = "02:00") -> None:
    """Schedule or replace daily backup in JobQueue at target HH:MM UTC+7."""
    jq = getattr(app, "job_queue", None)
    if not jq:
        return
    for job in jq.get_jobs_by_name(JOB_BACKUP_NAME):
        job.schedule_removal()

    h, m = map(int, time_str.split(":"))
    target_time = dt_time(h, m, tzinfo=VN_TZ)
    jq.run_daily(
        daily_backup_job_callback,
        time=target_time,
        name=JOB_BACKUP_NAME,
    )


async def reminder_checker_job_callback(context: ContextTypes.DEFAULT_TYPE) -> None:
    """Scan and broadcast due reminders periodically."""
    db = context.bot_data.get("db")
    settings = context.bot_data.get("settings")
    whitelist_ids = context.bot_data.get("whitelist_user_ids", set())
    if not db and not settings:
        return

    from src.db.reminders import get_due_reminders, mark_reminder_sent
    from src.services.notifications import (
        broadcast_to_whitelist,
        build_order_view_button,
        format_reminder_broadcast,
    )

    async def _process(conn: aiosqlite.Connection) -> None:
        due = await get_due_reminders(conn)
        for r in due:
            rid = r["reminder_id"]
            oid = r.get("order_id")
            msg = format_reminder_broadcast(r)
            view_btn = build_order_view_button(oid) if oid else None
            await broadcast_to_whitelist(context.bot, whitelist_ids, msg, reply_markup=view_btn)
            await mark_reminder_sent(conn, rid)

    if db is not None:
        try:
            await _process(db)
        except Exception:
            logging.getLogger(__name__).exception("Error in reminder checker job")
    else:
        from src.db.connection import get_db_connection

        try:
            async with get_db_connection(settings.sqlite_db_path) as conn:
                await _process(conn)
        except Exception:
            logging.getLogger(__name__).exception("Error in reminder checker job")


def schedule_reminder_checker(app: Application) -> None:
    """Schedule repeating reminder checker in JobQueue every 30 seconds."""
    jq = getattr(app, "job_queue", None)
    if not jq:
        return
    for job in jq.get_jobs_by_name(JOB_REMINDER_NAME):
        job.schedule_removal()
    jq.run_repeating(
        reminder_checker_job_callback,
        interval=30,
        first=5,
        name=JOB_REMINDER_NAME,
    )


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

    maint_mode = await get_maintenance_mode(db)
    app.bot_data["maintenance_mode"] = maint_mode

    backup_time = await get_setting(db, "backup_schedule_time", default="02:00")
    schedule_daily_backup(app, backup_time or "02:00")
    schedule_reminder_checker(app)
    schedule_heartbeat_job(app)
    schedule_heartbeat_job(app)


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
        .post_shutdown(post_shutdown_cleanup)
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
    app.bot_data["maintenance_mode"] = False
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
    app.add_handler(CommandHandler("backup", backup_command), group=0)

    # Register main menu Reply Keyboard handler (MUST be registered before LLM text ingestion)
    app.add_handler(
        MessageHandler(
            filters.Regex(
                r"^(📦 Đơn hôm nay|⏳ Đơn chờ làm|📋 Xem theo ngày|📝 Nhập đơn mới|🔍 Tra cứu đơn|❓ Trợ giúp)$"
            ),
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
            handle_restore_callback,
            pattern=r"^adm:rst:",
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

    # Register tutorial navigation callbacks at group 0
    app.add_handler(
        CallbackQueryHandler(handle_tutorial_callback, pattern=r"^help:"),
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
    app.add_handler(
        CallbackQueryHandler(
            handle_customer_callback,
            pattern=r"^cus_",
        ),
        group=0,
    )

    # Register navigation and order callbacks at group 0
    app.add_handler(
        CallbackQueryHandler(
            handle_order_action_callback,
            pattern=r"^ord_act:(track|add_photo|view_photo|remind|remind_del|cancel|ship_helper|del_prompt|del_confirm|edit_menu|edit_fld)(:\d+)?(:[a-z_]+)?$",
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
            pattern=r"^(ord_(dt|pg|v|bk|ls|vls):|ord_noop$|ord_act:(pick_date|new)$)",
        ),
        group=0,
    )
    app.add_handler(
        CallbackQueryHandler(handle_mutation_callback, pattern=r"^ord_mut_"),
        group=0,
    )
    app.add_handler(
        CallbackQueryHandler(handle_order_callback, pattern=r"^ord:(cf|ca|ad|cs|bk|noop):"),
        group=0,
    )
    app.add_handler(
        MessageHandler(filters.PHOTO, handle_photo_order),
        group=0,
    )
    # Backup restore uploads must be matched before the generic TEXT handler.
    app.add_handler(
        MessageHandler(filters.Document.ALL, handle_backup_document),
        group=0,
    )
    app.add_handler(
        MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text_order),
        group=0,
    )

    return app
