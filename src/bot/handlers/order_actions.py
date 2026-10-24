import logging
import re
import time
from contextlib import nullcontext

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, InputMediaPhoto, Update
from telegram.error import BadRequest
from telegram.ext import ContextTypes

from src.bot.keyboards import (
    STATUS_NAMES,
    build_order_detail_keyboard,
    build_status_selection_keyboard,
    render_order_detail_card,
)
from src.db.connection import get_db_connection
from src.db.orders import (
    append_order_photos,
    get_order_by_id,
    update_order_status,
    update_order_tracking,
)
from src.models.order import OrderStatus

logger = logging.getLogger(__name__)

STATUS_CALLBACK_PATTERN = re.compile(r"^ord_st(_menu|_cf)?:(\d+)(?::([A-Z_]+))?$")
ACTION_CALLBACK_PATTERN = re.compile(r"^ord_act:(track|add_photo|view_photo|cancel)(?::(\d+))?$")
SENSITIVE_STATUSES = {OrderStatus.BOM_HANG, OrderStatus.HUY_DON}


def _get_active_db_context(context: ContextTypes.DEFAULT_TYPE):
    """Resolve active database connection or create context connection."""
    app_context = context.application.bot_data.get("app_context")
    db = getattr(app_context, "db", None) if app_context else context.application.bot_data.get("db")
    settings = context.application.bot_data.get("settings")
    db_path = getattr(settings, "sqlite_db_path", "cassette_store.db") if settings else "cassette_store.db"
    return nullcontext(db) if db else get_db_connection(db_path)


async def handle_order_status_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle 1-tap status transition, sensitive 2-step confirmation, and status menu."""
    query = update.callback_query
    if not query or not query.data:
        return

    data = query.data

    # Return to order detail card: ord_v_cur:{order_id}
    if data.startswith("ord_v_cur:"):
        await query.answer()
        parts = data.split(":")
        order_id = int(parts[1])
        db_ctx = _get_active_db_context(context)
        async with db_ctx as active_db:
            if not active_db:
                await query.edit_message_text("⚠️ Lỗi cơ sở dữ liệu.")
                return
            order = await get_order_by_id(active_db, order_id)
            if not order:
                await query.edit_message_text("⚠️ Đơn hàng không tồn tại.")
                return
            card_text = render_order_detail_card(order)
            # Default to today's list back navigation
            today_str = order.created_at.strftime("%Y-%m-%d") if order.created_at else ""
            keyboard = build_order_detail_keyboard(order, date_str=today_str, page=1)
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

    # Status menu expansion: ord_st_menu:{order_id}
    if data.startswith("ord_st_menu:"):
        await query.answer()
        parts = data.split(":")
        order_id = int(parts[1])
        db_ctx = _get_active_db_context(context)
        async with db_ctx as active_db:
            if not active_db:
                await query.edit_message_text("⚠️ Lỗi cơ sở dữ liệu.")
                return
            order = await get_order_by_id(active_db, order_id)
            if not order:
                await query.edit_message_text("⚠️ Đơn hàng không tồn tại.")
                return
            menu_keyboard = build_status_selection_keyboard(order_id, order.status)
            try:
                await query.edit_message_text(
                    text=f"🔄 <b>CHỌN TRẠNG THÁI CHO ĐƠN #{order_id}</b>\n\n"
                    f"Bác chạm vào trạng thái muốn chuyển bên dưới nhé:",
                    reply_markup=menu_keyboard,
                    parse_mode="HTML",
                )
            except BadRequest as e:
                if "Message is not modified" not in str(e):
                    raise
        return

    # Check status transitions: ord_st:{order_id}:{status} or ord_st_cf:{order_id}:{status}
    match = STATUS_CALLBACK_PATTERN.match(data)
    if not match:
        return

    sub_action = match.group(1)  # "_cf" or None
    order_id = int(match.group(2))
    status_str = match.group(3)

    if not status_str:
        return

    try:
        target_status = OrderStatus(status_str)
    except ValueError:
        await query.answer(text="Trạng thái không hợp lệ!", show_alert=True)
        return

    target_label = STATUS_NAMES.get(target_status, target_status.value)

    # Sensitive confirmation modal check per D-07
    is_confirmation = sub_action == "_cf"
    if target_status in SENSITIVE_STATUSES and not is_confirmation:
        await query.answer()
        confirm_keyboard = InlineKeyboardMarkup(
            [
                [
                    InlineKeyboardButton(
                        f"⚠️ Xác nhận {target_label}",
                        callback_data=f"ord_st_cf:{order_id}:{target_status.value}",
                    )
                ],
                [
                    InlineKeyboardButton(
                        "Quay lại",
                        callback_data=f"ord_v_cur:{order_id}",
                    )
                ],
            ]
        )
        try:
            await query.edit_message_text(
                text=f"⚠️ <b>XÁC NHẬN CHUYỂN TRẠNG THÁI</b>\n\n"
                f"Bác có chắc chắn muốn chuyển đơn <b>#{order_id}</b> sang trạng thái <b>{target_label}</b> không?\n\n"
                f"<i>(Hành động này sẽ kết thúc xử lý đơn hàng)</i>",
                reply_markup=confirm_keyboard,
                parse_mode="HTML",
            )
        except BadRequest as e:
            if "Message is not modified" not in str(e):
                raise
        return

    # Normal transition or confirmed sensitive transition
    db_ctx = _get_active_db_context(context)
    async with db_ctx as active_db:
        if not active_db:
            await query.answer(text="Lỗi kết nối cơ sở dữ liệu!", show_alert=True)
            return

        success = await update_order_status(active_db, order_id, target_status)
        if not success:
            await query.answer(text="Không tìm thấy đơn để cập nhật!", show_alert=True)
            return

        # Instant toast alert without spinner per D-08
        await query.answer(text=f"✅ Đã chuyển sang: {target_label}", show_alert=False)

        updated_order = await get_order_by_id(active_db, order_id)
        if updated_order:
            card_text = render_order_detail_card(updated_order)
            today_str = updated_order.created_at.strftime("%Y-%m-%d") if updated_order.created_at else ""
            keyboard = build_order_detail_keyboard(updated_order, date_str=today_str, page=1)
            try:
                await query.edit_message_text(
                    text=card_text,
                    reply_markup=keyboard,
                    parse_mode="HTML",
                )
            except BadRequest as e:
                if "Message is not modified" not in str(e):
                    raise
