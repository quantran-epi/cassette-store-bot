import logging
import re
from contextlib import nullcontext
from datetime import datetime
from math import ceil

from telegram import InlineKeyboardMarkup, Update
from telegram.error import BadRequest
from telegram.ext import ContextTypes

from src.bot.handlers.base import send_tutorial
from src.bot.keyboards import (
    TZ_VN,
    build_date_picker_keyboard,
    build_order_detail_keyboard,
    build_order_list_keyboard,
    build_status_order_list_keyboard,
    render_order_detail_card,
    render_order_list_card,
    render_status_order_list_card,
)
from src.db.connection import get_db_connection
from src.db.orders import (
    count_orders_by_date,
    count_orders_by_status,
    get_order_by_id,
    list_orders_by_date,
    list_orders_by_status,
)
from src.db.reminders import get_reminders_by_order_id
from src.models.order import OrderStatus

logger = logging.getLogger(__name__)

ORDER_NAV_PATTERN = re.compile(r"^ord_(dt|pg|v|bk):(.+)$")


def _get_active_db_context(context: ContextTypes.DEFAULT_TYPE):
    """Resolve active database connection or create context connection."""
    app_context = context.application.bot_data.get("app_context")
    db = getattr(app_context, "db", None) if app_context else context.application.bot_data.get("db")
    settings = context.application.bot_data.get("settings")
    db_path = getattr(settings, "sqlite_db_path", "cassette_store.db") if settings else "cassette_store.db"
    return nullcontext(db) if db else get_db_connection(db_path)


async def _render_status_list_page(
    active_db, status: OrderStatus, page: int, limit: int = 10
) -> tuple[str, InlineKeyboardMarkup]:
    """Render one page of a status-filtered list, clamping page into range."""
    total = await count_orders_by_status(active_db, status)
    total_pages = max(1, ceil(total / limit))
    page = min(max(page, 1), total_pages)

    orders = await list_orders_by_status(
        active_db, status, limit=limit, offset=(page - 1) * limit
    )
    card_text = render_status_order_list_card(
        orders=orders,
        status=status,
        page=page,
        total_pages=total_pages,
        total_orders=total,
    )
    keyboard = build_status_order_list_keyboard(
        orders=orders,
        status=status,
        page=page,
        total_pages=total_pages,
    )
    return card_text, keyboard


async def handle_menu_reply(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle 3x2 Reply Keyboard button clicks per D-01, D-02, D-03, D-04."""
    if context.user_data:
        context.user_data.pop("action_state", None)

    if not update.message or not update.message.text:
        return

    text = update.message.text.strip()
    now_vn = datetime.now(TZ_VN)
    today_vn = now_vn.strftime("%Y-%m-%d")

    if text == "📦 Đơn hôm nay":
        db_ctx = _get_active_db_context(context)
        async with db_ctx as active_db:
            if not active_db:
                logger.error("DB connection unavailable for handle_menu_reply")
                await update.message.reply_text("⚠️ Lỗi cơ sở dữ liệu. Bác vui lòng thử lại sau!")
                return

            orders = await list_orders_by_date(active_db, today_vn, limit=5, offset=0)
            total = await count_orders_by_date(active_db, today_vn)
            total_pages = max(1, ceil(total / 5))

            card_text = render_order_list_card(
                orders=orders,
                date_str=today_vn,
                page=1,
                total_pages=total_pages,
                total_orders=total,
            )
            keyboard = build_order_list_keyboard(
                orders=orders,
                date_str=today_vn,
                page=1,
                total_pages=total_pages,
            )
            await update.message.reply_text(
                text=card_text,
                reply_markup=keyboard,
                parse_mode="HTML",
            )
        return

    if text == "⏳ Đơn chờ làm":
        db_ctx = _get_active_db_context(context)
        async with db_ctx as active_db:
            if not active_db:
                logger.error("DB connection unavailable for handle_menu_reply")
                await update.message.reply_text("⚠️ Lỗi cơ sở dữ liệu. Bác vui lòng thử lại sau!")
                return

            card_text, keyboard = await _render_status_list_page(
                active_db, OrderStatus.CHO_LAM, 1
            )
            await update.message.reply_text(
                text=card_text,
                reply_markup=keyboard,
                parse_mode="HTML",
            )
        return

    if text == "📋 Xem theo ngày":
        keyboard = build_date_picker_keyboard(base_date=now_vn)
        await update.message.reply_text(
            text="📅 <b>CHỌN NGÀY XEM ĐƠN HÀNG</b>\n\nBác chạm vào ngày muốn xem bên dưới nhé:",
            reply_markup=keyboard,
            parse_mode="HTML",
        )
        return

    if text == "📝 Nhập đơn mới":
        await update.message.reply_text(
            "📝 <b>NHẬP ĐƠN HÀNG MỚI</b>\n\n"
            "Bác chỉ cần dán đoạn tin nhắn đặt hàng của khách vào đây "
            "(hoặc gửi ảnh chụp đơn hàng kèm chú thích text).\n\n"
            "Bot sẽ tự động bóc tách tên, số điện thoại, địa chỉ và tiền hàng cho bác duyệt!",
            parse_mode="HTML",
        )
        return

    if text == "🔍 Tra cứu đơn":
        from src.bot.handlers.search import handle_search_menu_reply

        await handle_search_menu_reply(update, context)
        return

    if text == "🔄 Đổi trạng thái":
        from src.bot.handlers.bulk_status import start_bulk_status

        await start_bulk_status(update, context)
        return

    if text == "❓ Trợ giúp":
        await send_tutorial(update, context, 0, message=update.message)
        return


async def handle_order_nav_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle order navigation callbacks: ord_dt, ord_pg, ord_v, ord_bk, ord_ls, ord_vls."""
    query = update.callback_query
    if not query or not query.data:
        return

    await query.answer()
    data = query.data

    # Ignore no-op page indicator button
    if data == "ord_noop":
        return

    # Handle pick date from list card empty state / footer
    if data == "ord_act:pick_date":
        now_vn = datetime.now(TZ_VN)
        keyboard = build_date_picker_keyboard(base_date=now_vn)
        try:
            await query.edit_message_text(
                text="📅 <b>CHỌN NGÀY XEM ĐƠN HÀNG</b>\n\nBác chạm vào ngày muốn xem bên dưới nhé:",
                reply_markup=keyboard,
                parse_mode="HTML",
            )
        except BadRequest as e:
            if "Message is not modified" not in str(e):
                raise
        return

    # Handle direct new order prompt from empty list card
    if data == "ord_act:new":
        if context.user_data:
            context.user_data.pop("action_state", None)
        try:
            await query.edit_message_text(
                text="📝 <b>NHẬP ĐƠN HÀNG MỚI</b>\n\n"
                "Bác hãy dán đoạn tin nhắn đặt hàng của khách vào ô chat bên dưới nhé!",
                parse_mode="HTML",
            )
        except BadRequest as e:
            if "Message is not modified" not in str(e):
                raise
        return

    # Status-filtered list: ord_ls:<STATUS>:<page>
    if data.startswith("ord_ls:"):
        parts = data.split(":")
        if len(parts) < 2:
            return
        try:
            status = OrderStatus(parts[1])
        except ValueError:
            return  # ignore garbage status from client callback
        try:
            page = int(parts[2]) if len(parts) > 2 else 1
        except ValueError:
            page = 1

        db_ctx = _get_active_db_context(context)
        async with db_ctx as active_db:
            if not active_db:
                logger.error("DB connection unavailable for status list")
                await query.edit_message_text("⚠️ Lỗi cơ sở dữ liệu. Bác vui lòng thử lại sau!")
                return

            card_text, keyboard = await _render_status_list_page(active_db, status, page)
            try:
                await query.edit_message_text(
                    text=card_text,
                    reply_markup=keyboard,
                    parse_mode="HTML",
                )
            except BadRequest as e:
                if "Message is not modified" not in str(e):
                    raise
        return

    # Detail view opened from a status list: ord_vls:<STATUS>:<id>:<page>
    if data.startswith("ord_vls:"):
        parts = data.split(":")
        if len(parts) < 3:
            return
        try:
            status = OrderStatus(parts[1])
            order_id = int(parts[2])
            page = int(parts[3]) if len(parts) > 3 else 1
        except ValueError:
            return

        db_ctx = _get_active_db_context(context)
        async with db_ctx as active_db:
            if not active_db:
                logger.error("DB connection unavailable for order detail")
                await query.edit_message_text("⚠️ Lỗi cơ sở dữ liệu. Bác vui lòng thử lại sau!")
                return

            order = await get_order_by_id(active_db, order_id)
            if not order:
                try:
                    await query.edit_message_text("⚠️ Đơn hàng không tồn tại hoặc đã bị xoá.")
                except BadRequest as e:
                    if "Message is not modified" not in str(e):
                        raise
                return

            reminders = await get_reminders_by_order_id(active_db, order_id)
            card_text = render_order_detail_card(order, reminders=reminders)
            back_cb = f"ord_ls:{status.value}:{page}"
            if context.user_data is not None:
                context.user_data[f"ord_back_{order_id}"] = back_cb
            keyboard = build_order_detail_keyboard(
                order,
                date_str=datetime.now(TZ_VN).strftime("%Y-%m-%d"),
                page=page,
                back_callback_data=back_cb,
                has_reminder=bool(reminders),
            )
            try:
                await query.edit_message_text(
                    text=card_text,
                    reply_markup=keyboard,
                    parse_mode="HTML",
                )
            except BadRequest as e:
                if "Message is not modified" not in str(e):
                    raise
        return

    match = ORDER_NAV_PATTERN.match(data)
    if not match:
        return

    action = match.group(1)
    payload = match.group(2)

    db_ctx = _get_active_db_context(context)
    async with db_ctx as active_db:
        if not active_db:
            logger.error("DB connection unavailable for handle_order_nav_callback")
            await query.edit_message_text("⚠️ Lỗi cơ sở dữ liệu. Bác vui lòng thử lại sau!")
            return

        if action in ("dt", "pg", "bk"):
            # ord_dt:YYYY-MM-DD
            # ord_pg:YYYY-MM-DD:PAGE
            # ord_bk:YYYY-MM-DD:PAGE
            parts = payload.split(":")
            date_str = parts[0]
            page = int(parts[1]) if len(parts) > 1 else 1
            limit = 5
            offset = (page - 1) * limit

            total = await count_orders_by_date(active_db, date_str)
            total_pages = max(1, ceil(total / limit))
            if page > total_pages:
                page = total_pages
                offset = (page - 1) * limit

            orders = await list_orders_by_date(active_db, date_str, limit=limit, offset=offset)
            card_text = render_order_list_card(
                orders=orders,
                date_str=date_str,
                page=page,
                total_pages=total_pages,
                total_orders=total,
            )
            keyboard = build_order_list_keyboard(
                orders=orders,
                date_str=date_str,
                page=page,
                total_pages=total_pages,
            )

            try:
                await query.edit_message_text(
                    text=card_text,
                    reply_markup=keyboard,
                    parse_mode="HTML",
                )
            except BadRequest as e:
                if "Message is not modified" not in str(e):
                    raise
            return

        if action == "v":
            # ord_v:ID:DATE:PAGE
            parts = payload.split(":")
            order_id = int(parts[0])
            date_str = parts[1] if len(parts) > 1 else datetime.now(TZ_VN).strftime("%Y-%m-%d")
            page = int(parts[2]) if len(parts) > 2 else 1

            order = await get_order_by_id(active_db, order_id)
            if not order:
                try:
                    await query.edit_message_text(
                        "⚠️ Đơn hàng không tồn tại hoặc đã bị xoá.",
                    )
                except BadRequest as e:
                    if "Message is not modified" not in str(e):
                        raise
                return

            reminders = await get_reminders_by_order_id(active_db, order_id)
            card_text = render_order_detail_card(order, reminders=reminders)
            back_cb = f"ord_bk:{date_str}:{page}"
            if context.user_data is not None:
                context.user_data[f"ord_back_{order_id}"] = back_cb
            keyboard = build_order_detail_keyboard(
                order,
                date_str=date_str,
                page=page,
                back_callback_data=back_cb,
                has_reminder=bool(reminders),
            )

            try:
                await query.edit_message_text(
                    text=card_text,
                    reply_markup=keyboard,
                    parse_mode="HTML",
                )
            except BadRequest as e:
                if "Message is not modified" not in str(e):
                    logger.error("Failed to edit message for order detail %d: %s", order_id, e)
                    # Fallback: if edit fails (e.g. caption/media mismatch or Telegram formatting glitch), send fresh message
                    await query.message.reply_text(
                        text=card_text,
                        reply_markup=keyboard,
                        parse_mode="HTML",
                    )
            except Exception as e:
                logger.exception("Unexpected error showing order detail %d: %s", order_id, e)
                await query.message.reply_text(
                    text=card_text,
                    reply_markup=keyboard,
                    parse_mode="HTML",
                )
            return
