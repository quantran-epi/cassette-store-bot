import logging
import re
from contextlib import nullcontext
from datetime import datetime, timedelta, timezone
from math import ceil

from telegram import Update
from telegram.error import BadRequest
from telegram.ext import ContextTypes

from src.bot.keyboards import (
    TZ_VN,
    build_date_picker_keyboard,
    build_order_detail_keyboard,
    build_order_list_keyboard,
    render_order_detail_card,
    render_order_list_card,
)
from src.db.connection import get_db_connection
from src.db.orders import count_orders_by_date, get_order_by_id, list_orders_by_date

logger = logging.getLogger(__name__)

ORDER_NAV_PATTERN = re.compile(r"^ord_(dt|pg|v|bk):(.+)$")


def _get_active_db_context(context: ContextTypes.DEFAULT_TYPE):
    """Resolve active database connection or create context connection."""
    app_context = context.application.bot_data.get("app_context")
    db = getattr(app_context, "db", None) if app_context else context.application.bot_data.get("db")
    settings = context.application.bot_data.get("settings")
    db_path = getattr(settings, "sqlite_db_path", "cassette_store.db") if settings else "cassette_store.db"
    return nullcontext(db) if db else get_db_connection(db_path)


async def handle_menu_reply(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle 2x2 Reply Keyboard button clicks per D-01, D-02, D-03, D-04."""
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

    if text == "❓ Trợ giúp":
        await update.message.reply_text(
            "❓ <b>HƯỚNG DẪN SỬ DỤNG BOT</b>\n\n"
            "• <b>📦 Đơn hôm nay:</b> Xem nhanh danh sách các đơn hàng phát sinh trong ngày.\n"
            "• <b>📋 Xem theo ngày:</b> Xem lại đơn của các ngày trước.\n"
            "• <b>📝 Nhập đơn mới:</b> Dán tin nhắn đặt hàng của khách để tạo đơn tự động.\n"
            "• <b>Chạm để Copy:</b> Trên thẻ chi tiết đơn, chạm vào SĐT hoặc Địa chỉ để sao chép nhanh sang app giao hàng.\n\n"
            "Nếu gặp khó khăn, bác cứ bấm các nút to trên màn hình để thao tác nhé!",
            parse_mode="HTML",
        )
        return


async def handle_order_nav_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle order navigation callbacks: ord_dt, ord_pg, ord_v, ord_bk."""
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

            card_text = render_order_detail_card(order)
            keyboard = build_order_detail_keyboard(order, date_str=date_str, page=page)

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
