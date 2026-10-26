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
    TZ_VN,
    build_order_detail_keyboard,
    build_shipping_helper_card,
    build_shipping_helper_keyboard,
    build_status_selection_keyboard,
    render_order_detail_card,
    to_vn_datetime,
)
from src.db.connection import get_db_connection
from src.db.orders import (
    append_order_photos,
    delete_order,
    get_order_by_id,
    update_order_status,
    update_order_tracking,
)
from src.models.order import OrderStatus

logger = logging.getLogger(__name__)

STATUS_CALLBACK_PATTERN = re.compile(r"^ord_st(_menu|_cf)?:(\d+)(?::([A-Z_]+))?$")
ACTION_CALLBACK_PATTERN = re.compile(
    r"^ord_act:(track|add_photo|view_photo|remind|remind_del|cancel|ship_helper|del_prompt|del_confirm)(?::(\d+))?$"
)
SENSITIVE_STATUSES = {OrderStatus.BOM_HANG, OrderStatus.HUY_DON}


def _get_active_db_context(context: ContextTypes.DEFAULT_TYPE):
    """Resolve active database connection or create context connection."""
    bot_data = getattr(context, "bot_data", None)
    if not isinstance(bot_data, dict) and hasattr(context, "application"):
        app_bot_data = getattr(context.application, "bot_data", None)
        if isinstance(app_bot_data, dict):
            bot_data = app_bot_data
    if not isinstance(bot_data, dict):
        bot_data = {}

    app_context = bot_data.get("app_context")
    db = getattr(app_context, "db", None) if app_context else bot_data.get("db")
    settings = bot_data.get("settings")
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
            from src.db.reminders import get_reminders_by_order_id

            reminders = await get_reminders_by_order_id(active_db, order_id)
            card_text = render_order_detail_card(order, reminders=reminders)
            # Default to today's list back navigation in Vietnam local time
            vn_dt = to_vn_datetime(order.created_at) if isinstance(order.created_at, datetime) else None
            today_str = vn_dt.strftime("%Y-%m-%d") if vn_dt else ""
            keyboard = build_order_detail_keyboard(
                order, date_str=today_str, page=1, has_reminder=bool(reminders)
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
            if target_status in (OrderStatus.DA_DONG_GOI, OrderStatus.DA_TAO_DON):
                from src.services.notifications import (
                    broadcast_to_whitelist,
                    build_order_view_button,
                    format_order_packed_broadcast,
                    format_order_shipping_label_broadcast,
                )

                whitelist_ids = context.bot_data.get("whitelist_user_ids", set())
                op_name = user.full_name if user else None
                if target_status == OrderStatus.DA_DONG_GOI:
                    b_msg = format_order_packed_broadcast(updated_order, operator_name=op_name)
                else:
                    b_msg = format_order_shipping_label_broadcast(updated_order, operator_name=op_name)
                op_uid = user.id if user else None
                order_view_btn = (
                    build_order_view_button(updated_order.id) if updated_order.id else None
                )
                await broadcast_to_whitelist(
                    context.bot,
                    whitelist_ids,
                    b_msg,
                    reply_markup=order_view_btn,
                    exclude_user_id=op_uid,
                )

            from src.db.reminders import get_reminders_by_order_id

            reminders = await get_reminders_by_order_id(active_db, order_id)
            card_text = render_order_detail_card(updated_order, reminders=reminders)
            vn_dt = to_vn_datetime(updated_order.created_at) if isinstance(updated_order.created_at, datetime) else None
            today_str = vn_dt.strftime("%Y-%m-%d") if vn_dt else ""
            keyboard = build_order_detail_keyboard(
                updated_order, date_str=today_str, page=1, has_reminder=bool(reminders)
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

    # 4. Reminder input prompt
    if action_type == "remind":
        await query.answer()
        context.user_data["action_state"] = {
            "action": "await_reminder",
            "order_id": order_id,
            "expires_at": time.time() + 180,
        }

        db_ctx = _get_active_db_context(context)
        existing_rems = []
        async with db_ctx as active_db:
            if active_db:
                from src.db.reminders import get_reminders_by_order_id

                existing_rems = await get_reminders_by_order_id(active_db, order_id)

        chat_id = (
            update.effective_chat.id
            if update.effective_chat
            else (query.message.chat_id if query.message else None)
        )

        buttons = []
        if existing_rems:
            r = existing_rems[0]
            buttons.append(
                [
                    InlineKeyboardButton(
                        "🗑️ Huỷ lịch nhắc này",
                        callback_data=f"ord_act:remind_del:{order_id}",
                    )
                ]
            )
            prompt_text = (
                f"⏰ <b>LỊCH NHẮC ĐƠN HÀNG #{order_id}</b>\n"
                f"────────────────────\n"
                f"🕒 <b>ĐANG HẸN:</b> <code>{r.remind_at}</code>\n"
                f"📝 <b>NỘI DUNG:</b> {html.escape(r.reminder_text)}\n"
                f"────────────────────\n"
                f"Bác gửi tin nhắn thời gian mới nếu muốn đổi lịch hẹn, hoặc bấm nút dưới:"
            )
        else:
            prompt_text = (
                f"⏰ <b>ĐẶT LỊCH NHẮC VIỆC - ĐƠN #{order_id}</b>\n"
                f"────────────────────\n"
                f"Đơn này hiện chưa có lịch nhắc nào.\n"
                f"Bác hãy nhập thời gian và yêu cầu bằng tiếng Việt tự nhiên nhé.\n"
                f"Ví dụ:\n"
                f"• <i>\"Thứ 2 tuần sau 9h gửi hàng\"</i>\n"
                f"• <i>\"Chiều mai 15h gọi lại khách\"</i>\n"
                f"• <i>\"Ngày 28/10 đóng gói giao đi\"</i>\n\n"
                f"<i>(Bác gửi tin nhắn trực tiếp hoặc bấm Huỷ bên dưới)</i>"
            )

        buttons.append(
            [InlineKeyboardButton("❌ Huỷ bỏ", callback_data="ord_act:cancel")]
        )
        remind_kb = InlineKeyboardMarkup(buttons)

        if chat_id:
            await context.bot.send_message(
                chat_id=chat_id,
                text=prompt_text,
                reply_markup=remind_kb,
                parse_mode="HTML",
            )
        return

    if action_type == "remind_del":
        await query.answer("Đã huỷ lịch nhắc!")
        context.user_data.pop("action_state", None)
        db_ctx = _get_active_db_context(context)
        async with db_ctx as active_db:
            if active_db:
                from src.db.reminders import cancel_reminders_by_order_id

                await cancel_reminders_by_order_id(active_db, order_id)

        back_kb = InlineKeyboardMarkup(
            [[InlineKeyboardButton("👁️ Xem lại thẻ đơn", callback_data=f"ord_v_cur:{order_id}")]]
        )
        chat_id = (
            update.effective_chat.id
            if update.effective_chat
            else (query.message.chat_id if query.message else None)
        )
        if chat_id:
            await context.bot.send_message(
                chat_id=chat_id,
                text=f"🗑️ <b>ĐÃ HUỶ LỊCH NHẮC ĐƠN #{order_id}!</b>",
                reply_markup=back_kb,
                parse_mode="HTML",
            )
        return

    # 6. Shipping helper card & copy buttons
    if action_type == "ship_helper":
        await query.answer()
        db_ctx = _get_active_db_context(context)
        async with db_ctx as active_db:
            if not active_db:
                await query.answer("Lỗi kết nối cơ sở dữ liệu!", show_alert=True)
                return
            order = await get_order_by_id(active_db, order_id)
            if not order:
                await query.edit_message_text("⚠️ Đơn hàng không tồn tại hoặc đã bị xoá.")
                return
            card_text = build_shipping_helper_card(order)
            keyboard = build_shipping_helper_keyboard(order)
            try:
                await query.edit_message_text(text=card_text, reply_markup=keyboard, parse_mode="HTML")
            except BadRequest as e:
                if "Message is not modified" not in str(e):
                    raise
        return

    # 7. Delete order prompt (step 1: confirmation dialog)
    if action_type == "del_prompt":
        await query.answer()
        db_ctx = _get_active_db_context(context)
        async with db_ctx as active_db:
            if not active_db:
                await query.answer("Lỗi kết nối cơ sở dữ liệu!", show_alert=True)
                return
            order = await get_order_by_id(active_db, order_id)
            if not order:
                await query.edit_message_text("⚠️ Đơn hàng không tồn tại hoặc đã bị xoá.")
                return
            cust_name = html.escape(order.customer_name)
            confirm_kb = InlineKeyboardMarkup(
                [
                    [
                        InlineKeyboardButton(
                            "🗑️ XÁC NHẬN XOÁ ĐƠN",
                            callback_data=f"ord_act:del_confirm:{order_id}",
                        )
                    ],
                    [
                        InlineKeyboardButton(
                            "⬅️ Huỷ, quay lại",
                            callback_data=f"ord_v_cur:{order_id}",
                        )
                    ],
                ]
            )
            try:
                await query.edit_message_text(
                    text=(
                        f"⚠️ <b>XÁC NHẬN XOÁ ĐƠN HÀNG #{order_id}</b>\n\n"
                        f"Bác có chắc chắn muốn xoá vĩnh viễn đơn hàng của khách <b>{cust_name}</b> không?\n\n"
                        f"<i>(Hành động này sẽ xoá hoàn toàn đơn và lịch sử, không thể hoàn tác!)</i>"
                    ),
                    reply_markup=confirm_kb,
                    parse_mode="HTML",
                )
            except BadRequest as e:
                if "Message is not modified" not in str(e):
                    raise
        return

    # 8. Delete order confirm (step 2: execution & cascade delete)
    if action_type == "del_confirm":
        db_ctx = _get_active_db_context(context)
        async with db_ctx as active_db:
            if not active_db:
                await query.answer("Lỗi kết nối cơ sở dữ liệu!", show_alert=True)
                return
            success = await delete_order(active_db, order_id)
            if not success:
                await query.answer("Đơn hàng không tồn tại hoặc đã bị xoá trước đó!", show_alert=True)
                return
            await query.answer("✅ Đã xoá đơn hàng thành công!", show_alert=False)
            now_vn = datetime.now(TZ_VN)
            today_str = now_vn.strftime("%Y-%m-%d")
            back_kb = InlineKeyboardMarkup(
                [
                    [
                        InlineKeyboardButton(
                            "📦 Về danh sách đơn hôm nay",
                            callback_data=f"ord_dt:{today_str}",
                        )
                    ]
                ]
            )
            try:
                await query.edit_message_text(
                    text=(
                        f"🗑️ <b>ĐÃ XOÁ ĐƠN HÀNG #{order_id}</b>\n\n"
                        f"Đơn hàng đã được xoá hoàn toàn khỏi hệ thống."
                    ),
                    reply_markup=back_kb,
                    parse_mode="HTML",
                )
            except BadRequest as e:
                if "Message is not modified" not in str(e):
                    raise
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
                    f"🚚 <b>Mã vận đơn:</b> <code>{escaped_code}</code>\n"
                    f"🔄 <b>Trạng thái:</b> <i>Đã tạo đơn</i>"
                )
                back_kb = None
                if order:
                    back_kb = InlineKeyboardMarkup(
                        [
                            [
                                InlineKeyboardButton("🚚 Xem đơn vận chuyển", callback_data=f"ord_act:ship_helper:{order_id}"),
                                InlineKeyboardButton("👁️ Xem chi tiết đơn", callback_data=f"ord_v_cur:{order_id}"),
                            ]
                        ]
                    )
                await update.message.reply_text(
                    text=card_text,
                    reply_markup=back_kb,
                    parse_mode="HTML",
                )
            else:
                await update.message.reply_text("⚠️ Không tìm thấy đơn hàng để cập nhật mã vận đơn.")
            return True

    if action == "await_reminder" and order_id and update.message and update.message.text:
        text = update.message.text.strip()
        if not text:
            await update.message.reply_text("Nội dung nhắc việc không được để trống. Bác gửi lại nhé!")
            return True

        from src.db.reminders import create_reminder
        from src.models.reminder import Reminder, ReminderStatus
        from src.services.extractor import extract_reminder_from_text

        bot_data = getattr(context, "bot_data", None)
        if not isinstance(bot_data, dict) and hasattr(context, "application"):
            bot_data = getattr(context.application, "bot_data", {})
        if not isinstance(bot_data, dict):
            bot_data = {}

        client = bot_data.get("openai_client")
        model_id = bot_data.get("active_model_id") or "gpt-4o-mini"

        remind_at, reminder_note = await extract_reminder_from_text(client, model_id, text)
        if not remind_at:
            await update.message.reply_text(
                "Chưa nhận diện được ngày giờ cụ thể. Bác vui lòng nhập rõ hơn (Ví dụ: 'Thứ 2 tuần sau 9h gửi hàng') nhé!"
            )
            return True

        db_ctx = _get_active_db_context(context)
        async with db_ctx as active_db:
            if not active_db:
                await update.message.reply_text("⚠️ Lỗi cơ sở dữ liệu. Bác vui lòng thử lại sau!")
                return True

            user = update.effective_user
            rem = Reminder(
                id=None,
                order_id=order_id,
                remind_at=remind_at,
                reminder_text=reminder_note,
                status=ReminderStatus.PENDING,
                created_by_user_id=user.id if user else None,
            )
            await create_reminder(active_db, rem)
            context.user_data.pop("action_state", None)

            back_kb = InlineKeyboardMarkup(
                [[InlineKeyboardButton("👁️ Xem lại thẻ đơn", callback_data=f"ord_v_cur:{order_id}")]]
            )
            await update.message.reply_text(
                f"✅ <b>ĐÃ ĐẶT LỊCH NHẮC THÀNH CÔNG!</b>\n"
                f"────────────────────\n"
                f"📦 <b>MÃ ĐƠN:</b> <code>#{order_id}</code>\n"
                f"⏰ <b>THỜI GIAN NHẮC:</b> <code>{remind_at}</code>\n"
                f"📝 <b>NỘI DUNG:</b> {html.escape(reminder_note)}\n"
                f"────────────────────\n"
                f"<i>Đến hạn hệ thống sẽ tự động phát thông báo tới tất cả người dùng!</i>",
                reply_markup=back_kb,
                parse_mode="HTML",
            )
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
