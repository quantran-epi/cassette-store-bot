import html
import logging
import re
import time
from contextlib import nullcontext
from datetime import datetime

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, InputMediaPhoto, Update
from telegram.error import BadRequest
from telegram.ext import ContextTypes

from src.bot.keyboards import (
    STATUS_NAMES,
    build_order_detail_keyboard,
    build_status_selection_keyboard,
    render_order_detail_card,
    to_vn_datetime,
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
        if context.user_data:
            context.user_data.pop("action_state", None)
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
            # Default to today's list back navigation in Vietnam local time
            vn_dt = to_vn_datetime(order.created_at) if isinstance(order.created_at, datetime) else None
            today_str = vn_dt.strftime("%Y-%m-%d") if vn_dt else ""
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

        user = query.from_user
        success = await update_order_status(
            active_db,
            order_id,
            target_status,
            user_id=user.id if user else None,
            user_name=user.full_name if user else None,
        )
        if not success:
            await query.answer(text="Không tìm thấy đơn để cập nhật!", show_alert=True)
            return

        # Instant toast alert without spinner per D-08
        await query.answer(text=f"✅ Đã chuyển sang: {target_label}", show_alert=False)

        updated_order = await get_order_by_id(active_db, order_id)
        if updated_order:
            card_text = render_order_detail_card(updated_order)
            vn_dt = to_vn_datetime(updated_order.created_at) if isinstance(updated_order.created_at, datetime) else None
            today_str = vn_dt.strftime("%Y-%m-%d") if vn_dt else ""
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


async def handle_order_action_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle order actions: tracking code prompt, photo viewer, photo prompt, and cancel."""
    query = update.callback_query
    if not query or not query.data:
        return

    data = query.data

    # Cancel action
    if data == "ord_act:cancel":
        await query.answer(text="Đã huỷ thao tác!", show_alert=False)
        context.user_data.pop("action_state", None)
        try:
            await query.edit_message_text(
                "❌ <b>ĐÃ HUỶ THAO TÁC</b>\n<i>Bác có thể tiếp tục chọn các chức năng khác từ menu nhé!</i>",
                parse_mode="HTML",
            )
        except BadRequest as e:
            if "Message is not modified" not in str(e):
                raise
        return

    match = ACTION_CALLBACK_PATTERN.match(data)
    if not match:
        return

    action_type = match.group(1)
    order_id_str = match.group(2)
    if not order_id_str:
        return
    order_id = int(order_id_str)

    # 1. Tracking code input prompt
    if action_type == "track":
        await query.answer()
        context.user_data["action_state"] = {
            "action": "await_tracking",
            "order_id": order_id,
            "expires_at": time.time() + 120,
        }
        cancel_kb = InlineKeyboardMarkup(
            [[InlineKeyboardButton("❌ Huỷ bỏ thao tác", callback_data="ord_act:cancel")]]
        )
        try:
            await query.edit_message_text(
                text=f"🚚 <b>NHẬP MÃ VẬN ĐƠN CHO ĐƠN #{order_id}</b>\n\n"
                f"Bác gõ hoặc dán mã vận đơn vào ô chat cho đơn này nhé.\n\n"
                f"<i>(Thời gian chờ là 2 phút)</i>",
                reply_markup=cancel_kb,
                parse_mode="HTML",
            )
        except BadRequest as e:
            if "Message is not modified" not in str(e):
                raise
        return

    # 2. Add photo prompt
    if action_type == "add_photo":
        await query.answer()
        context.user_data["action_state"] = {
            "action": "await_photo",
            "order_id": order_id,
            "expires_at": time.time() + 120,
        }
        cancel_kb = InlineKeyboardMarkup(
            [[InlineKeyboardButton("❌ Huỷ bỏ thao tác", callback_data="ord_act:cancel")]]
        )
        try:
            await query.edit_message_text(
                text=f"📷 <b>GỬI THÊM ẢNH CHO ĐƠN #{order_id}</b>\n\n"
                f"Bác gửi 1 hoặc nhiều ảnh cho đơn này nhé.\n\n"
                f"<i>(Thời gian chờ là 2 phút)</i>",
                reply_markup=cancel_kb,
                parse_mode="HTML",
            )
        except BadRequest as e:
            if "Message is not modified" not in str(e):
                raise
        return

    # 3. View photos album
    if action_type == "view_photo":
        db_ctx = _get_active_db_context(context)
        async with db_ctx as active_db:
            if not active_db:
                await query.answer("Lỗi kết nối cơ sở dữ liệu!", show_alert=True)
                return

            order = await get_order_by_id(active_db, order_id)
            if not order or not order.photo_file_ids:
                await query.answer("Đơn này chưa có ảnh nào bác nhé!", show_alert=True)
                return

            await query.answer()

            chat_id = update.effective_chat.id if update.effective_chat else query.message.chat_id
            photo_ids = order.photo_file_ids

            if len(photo_ids) == 1:
                await context.bot.send_photo(
                    chat_id=chat_id,
                    photo=photo_ids[0],
                    caption=f"📷 Ảnh đính kèm đơn #{order_id}",
                )
            else:
                # Chunk into max 10 photos per media group per Telegram limits (T-03-06, Pitfall 4)
                for chunk in [photo_ids[i : i + 10] for i in range(0, len(photo_ids), 10)]:
                    if len(chunk) == 1:
                        await context.bot.send_photo(
                            chat_id=chat_id,
                            photo=chunk[0],
                            caption=f"📷 Ảnh đính kèm đơn #{order_id}",
                        )
                    else:
                        media = [
                            InputMediaPhoto(
                                media=fid,
                                caption=f"📷 Ảnh đính kèm đơn #{order_id}" if fid == chunk[0] else None,
                            )
                            for fid in chunk
                        ]
                        await context.bot.send_media_group(chat_id=chat_id, media=media)
        return


async def handle_action_state_text(
    update: Update, context: ContextTypes.DEFAULT_TYPE, state: dict
) -> bool:
    """Handle text input when action_state is active (e.g. await_tracking). Returns True if handled."""
    action = state.get("action")
    order_id = state.get("order_id")

    if action == "await_tracking" and order_id and update.message and update.message.text:
        tracking_code = update.message.text.strip()
        # Security mitigation T-03-04: strip whitespace, max 100 chars, non-empty
        if not tracking_code:
            await update.message.reply_text("Mã vận đơn không được để trống. Bác gửi lại nhé!")
            return True

        if len(tracking_code) > 100:
            tracking_code = tracking_code[:100]

        db_ctx = _get_active_db_context(context)
        async with db_ctx as active_db:
            if not active_db:
                await update.message.reply_text("⚠️ Lỗi cơ sở dữ liệu. Bác vui lòng thử lại sau!")
                return True

            user = update.effective_user
            success = await update_order_tracking(
                active_db,
                order_id,
                tracking_code,
                user_id=user.id if user else None,
                user_name=user.full_name if user else None,
            )
            context.user_data.pop("action_state", None)

            if success:
                order = await get_order_by_id(active_db, order_id)
                escaped_code = html.escape(tracking_code)
                card_text = (
                    f"✅ <b>ĐÃ CẬP NHẬT MÃ VẬN ĐƠN</b>\n\n"
                    f"📦 <b>Đơn:</b> <code>#{order_id}</code>\n"
                    f"🚚 <b>Mã vận đơn:</b> <code>{escaped_code}</code>"
                )
                back_kb = None
                if order:
                    vn_dt = to_vn_datetime(order.created_at) if isinstance(order.created_at, datetime) else None
                    today_str = vn_dt.strftime("%Y-%m-%d") if vn_dt else ""
                    back_kb = InlineKeyboardMarkup(
                        [[InlineKeyboardButton("👁️ Xem lại thẻ đơn", callback_data=f"ord_v_cur:{order_id}")]]
                    )
                await update.message.reply_text(
                    text=card_text,
                    reply_markup=back_kb,
                    parse_mode="HTML",
                )
            else:
                await update.message.reply_text("⚠️ Không tìm thấy đơn hàng để cập nhật mã vận đơn.")
            return True

    return False


async def handle_action_state_photo(
    update: Update, context: ContextTypes.DEFAULT_TYPE, state: dict
) -> bool:
    """Handle photo input when action_state is active (e.g. await_photo). Returns True if handled."""
    action = state.get("action")
    order_id = state.get("order_id")

    if action == "await_photo" and order_id and update.message and update.message.photo:
        highest_res_photo = update.message.photo[-1]
        file_id = highest_res_photo.file_id

        db_ctx = _get_active_db_context(context)
        async with db_ctx as active_db:
            if not active_db:
                await update.message.reply_text("⚠️ Lỗi cơ sở dữ liệu. Bác vui lòng thử lại sau!")
                return True

            success = await append_order_photos(active_db, order_id, [file_id])
            if success:
                order = await get_order_by_id(active_db, order_id)
                count = len(order.photo_file_ids) if order else 1
                back_kb = InlineKeyboardMarkup(
                    [[InlineKeyboardButton("👁️ Xem lại thẻ đơn", callback_data=f"ord_v_cur:{order_id}")]]
                )
                await update.message.reply_text(
                    text=f"✅ <b>ĐÃ THÊM ẢNH THÀNH CÔNG</b>\n\n"
                    f"Đơn #{order_id} hiện có <b>{count} ảnh</b> đính kèm.\n"
                    f"Bác có thể gửi thêm ảnh nữa hoặc bấm xem lại thẻ đơn nhé!",
                    reply_markup=back_kb,
                    parse_mode="HTML",
                )
            else:
                await update.message.reply_text("⚠️ Không tìm thấy đơn hàng để thêm ảnh.")
            return True

    return False
