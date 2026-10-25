import html
import os
import time
from contextlib import nullcontext
from datetime import datetime
import aiosqlite
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.error import BadRequest
from telegram.ext import ContextTypes

from src.bot.keyboards import (
    TZ_VN,
    build_admin_main_keyboard,
    build_model_switcher_keyboard,
    build_whitelist_confirm_delete_keyboard,
    build_whitelist_keyboard,
    build_whitelist_user_detail_keyboard,
)
from src.bot.security import UserRole, get_user_role, require_role
from src.db.admin import (
    create_or_update_admin_user,
    delete_admin_user,
    get_admin_user,
    list_admin_users,
)
from src.db.connection import get_db_connection
from src.db.orders import count_orders_by_date
from src.db.settings import get_json_setting, set_json_setting, set_setting
from src.services.llm_probe import probe_model_reachability

DEFAULT_MODELS = ["gpt-4o-mini", "gpt-4o", "claude-3-5-haiku", "gemini-1.5-flash"]


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


def format_uptime(uptime_seconds: float) -> str:
    """Format uptime in human-friendly Vietnamese."""
    total_sec = max(0, int(uptime_seconds))
    days = total_sec // 86400
    hours = (total_sec % 86400) // 3600
    minutes = (total_sec % 3600) // 60
    seconds = total_sec % 60

    if days > 0:
        return f"{days} ngày {hours} giờ {minutes} phút"
    if hours > 0:
        return f"{hours} giờ {minutes} phút"
    return f"{minutes} phút {seconds} giây"


async def render_dashboard_card(
    context: ContextTypes.DEFAULT_TYPE,
    user_role: UserRole,
    db: aiosqlite.Connection | None = None,
) -> str:
    """Render HTML string for Screen 1 admin dashboard."""
    start_time = context.bot_data.get("start_time", time.time())
    uptime_str = format_uptime(time.time() - start_time)

    settings = context.bot_data.get("settings")
    db_path = getattr(settings, "sqlite_db_path", "cassette_store.db") if settings else "cassette_store.db"
    wal_path = f"{db_path}-wal"

    db_size_mb = (os.path.getsize(db_path) / (1024 * 1024)) if os.path.exists(db_path) else 0.0
    wal_size_mb = (os.path.getsize(wal_path) / (1024 * 1024)) if os.path.exists(wal_path) else 0.0

    active_model_id = context.bot_data.get("active_model_id") or (
        getattr(settings, "nine_router_model_id", "gpt-4o-mini") if settings else "gpt-4o-mini"
    )

    today_vn = datetime.now(TZ_VN).date().isoformat()
    db_ctx = nullcontext(db) if db is not None else _get_active_db_context(context)
    async with db_ctx as active_db:
        today_order_count = await count_orders_by_date(active_db, today_vn) if active_db else 0

    role_badge = "👑" if user_role == UserRole.SUPER_ADMIN else ("🛡️" if user_role == UserRole.ADMIN else "👤")

    return (
        f"🛠️ <b>BẢNG ĐIỀU KHIỂN QUẢN TRỊ</b>\n"
        f"────────────────────\n"
        f"⏱️ <b>Uptime:</b> {uptime_str}\n"
        f"💾 <b>Database:</b> SQLite WAL (DB: {db_size_mb:.2f} MB | WAL: {wal_size_mb:.2f} MB)\n"
        f"🤖 <b>Model LLM:</b> <code>{html.escape(active_model_id)}</code> (Trạng thái: ✅ Hoạt động)\n"
        f"📦 <b>Đơn hôm nay:</b> {today_order_count} đơn hàng\n"
        f"────────────────────\n"
        f"Vai trò của bạn: {role_badge} <b>{user_role.value}</b>"
    )


@require_role(UserRole.ADMIN)
async def admin_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Display administrative dashboard via /admin."""
    user = update.effective_user
    if not user or not update.effective_message:
        return

    user_role = get_user_role(context, user.id)
    card_text = await render_dashboard_card(context, user_role)
    keyboard = build_admin_main_keyboard(user_role)

    await update.effective_message.reply_text(
        card_text,
        reply_markup=keyboard,
        parse_mode="HTML",
    )


@require_role(UserRole.ADMIN)
async def handle_admin_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Route all adm:* callback interactions with in-place editing."""
    query = update.callback_query
    user = update.effective_user
    if not query or not query.data or not user:
        return

    data = query.data
    settings = context.bot_data.get("settings")
    super_admin_id = getattr(settings, "telegram_super_admin_id", None)
    user_role = get_user_role(context, user.id)

    async with _get_active_db_context(context) as db:
        # 1. Dashboard actions
        if data == "adm:dash:close":
            await query.answer()
            try:
                await query.edit_message_text("❌ Đã đóng menu quản trị.")
            except BadRequest as e:
                if "Message is not modified" not in str(e):
                    raise
            return

        if data == "adm:dash:refresh":
            await query.answer("Đã làm mới dữ liệu")
            card_text = await render_dashboard_card(context, user_role)
            keyboard = build_admin_main_keyboard(user_role)
            try:
                await query.edit_message_text(card_text, reply_markup=keyboard, parse_mode="HTML")
            except BadRequest as e:
                if "Message is not modified" not in str(e):
                    raise
            return

        if data == "adm:bkp:trigger":
            await query.answer("💾 Chức năng sao lưu DB sẽ khả dụng trong Phase 6.", show_alert=True)
            return

        if data == "adm:noop":
            await query.answer()
            return

        # 2. Whitelist CRUD
        if data.startswith("adm:wl:list:"):
            await query.answer()
            page = int(data.split(":")[3]) if len(data.split(":")) > 3 else 1
            users = await list_admin_users(db) if db else []
            total_users = len(users)

            lines: list[str] = []
            for u in users:
                uid = u["telegram_id"]
                urole = u.get("role", "STAFF")
                uname = u.get("name", "") or "Chưa đặt tên"
                badge = "👑" if urole == "SUPER_ADMIN" else ("🛡️" if urole == "ADMIN" else "👤")
                lines.append(f"{badge} <b>{html.escape(uname)}</b> (<code>{uid}</code>) - {urole}")

            user_content = "\n".join(lines) if lines else "<i>(Chưa có tài khoản nào)</i>"
            card_text = (
                f"👥 <b>QUẢN LÝ DANH SÁCH TRUY CẬP (WHITELIST)</b>\n"
                f"────────────────────\n"
                f"Tổng số tài khoản: <b>{total_users}</b>\n\n"
                f"{user_content}\n"
                f"────────────────────\n"
                f"<i>Bấm vào tài khoản bên dưới để xem chi tiết / phân quyền, hoặc thêm mới:</i>"
            )
            keyboard = build_whitelist_keyboard(users, current_page=page, total_pages=1)
            try:
                await query.edit_message_text(card_text, reply_markup=keyboard, parse_mode="HTML")
            except BadRequest as e:
                if "Message is not modified" not in str(e):
                    raise
            return

        if data.startswith("adm:wl:view:"):
            await query.answer()
            target_id = int(data.split(":")[3])
            target_user = await get_admin_user(db, target_id) if db else None
            if not target_user:
                target_user = {
                    "telegram_id": target_id,
                    "name": "Chưa đặt tên",
                    "role": "STAFF",
                    "created_at": "Không xác định",
                }

            is_root = (super_admin_id is not None and target_id == super_admin_id)
            trole = target_user.get("role", "STAFF")
            tname = target_user.get("name", "") or "Chưa đặt tên"
            badge = "👑" if trole == "SUPER_ADMIN" else ("🛡️" if trole == "ADMIN" else "👤")
            created_at = target_user.get("created_at", "")

            card_text = (
                f"👤 <b>THÔNG TIN TÀI KHOẢN</b>\n"
                f"────────────────────\n"
                f"🆔 <b>Telegram ID:</b> <code>{target_id}</code>\n"
                f"👤 <b>Tên hiển thị:</b> {html.escape(tname)}\n"
                f"🛡️ <b>Vai trò hiện tại:</b> {badge} <b>{trole}</b>\n"
                f"🕒 <b>Ngày cấp quyền:</b> {created_at}\n"
                f"────────────────────"
            )
            keyboard = build_whitelist_user_detail_keyboard(target_user, is_root=is_root)
            try:
                await query.edit_message_text(card_text, reply_markup=keyboard, parse_mode="HTML")
            except BadRequest as e:
                if "Message is not modified" not in str(e):
                    raise
            return

        if data.startswith("adm:wl:role:"):
            parts = data.split(":")
            target_id = int(parts[3])
            new_role = parts[4]

            if super_admin_id is not None and target_id == super_admin_id:
                await query.answer("🛡️ Không thể chỉnh sửa, hạ quyền hoặc xoá Root Super Admin!", show_alert=True)
                return

            target_user = await get_admin_user(db, target_id) if db else None
            name = target_user.get("name", "") if target_user else ""
            if db:
                await create_or_update_admin_user(db, target_id, name, new_role)
            context.bot_data.setdefault("admin_roles", {})[target_id] = UserRole(new_role)

            await query.answer(f"✅ Đã đổi vai trò sang {new_role}", show_alert=True)
            # Refresh detail view
            updated_user = {"telegram_id": target_id, "name": name, "role": new_role, "created_at": target_user.get("created_at", "") if target_user else ""}
            keyboard = build_whitelist_user_detail_keyboard(updated_user, is_root=False)
            badge = "👑" if new_role == "SUPER_ADMIN" else ("🛡️" if new_role == "ADMIN" else "👤")
            card_text = (
                f"👤 <b>THÔNG TIN TÀI KHOẢN</b>\n"
                f"────────────────────\n"
                f"🆔 <b>Telegram ID:</b> <code>{target_id}</code>\n"
                f"👤 <b>Tên hiển thị:</b> {html.escape(name or 'Chưa đặt tên')}\n"
                f"🛡️ <b>Vai trò hiện tại:</b> {badge} <b>{new_role}</b>\n"
                f"🕒 <b>Ngày cấp quyền:</b> {updated_user['created_at']}\n"
                f"────────────────────"
            )
            try:
                await query.edit_message_text(card_text, reply_markup=keyboard, parse_mode="HTML")
            except BadRequest as e:
                if "Message is not modified" not in str(e):
                    raise
            return

        if data.startswith("adm:wl:rm_req:"):
            await query.answer()
            target_id = int(data.split(":")[3])
            if super_admin_id is not None and target_id == super_admin_id:
                await query.answer("🛡️ Không thể chỉnh sửa, hạ quyền hoặc xoá Root Super Admin!", show_alert=True)
                return

            target_user = await get_admin_user(db, target_id) if db else None
            tname = target_user.get("name", "") if target_user else "Chưa đặt tên"
            trole = target_user.get("role", "STAFF") if target_user else "STAFF"

            card_text = (
                f"⚠️ <b>XÁC NHẬN XOÁ QUYỀN TRUY CẬP</b>\n"
                f"────────────────────\n"
                f"👤 <b>Tên:</b> {html.escape(tname or 'Chưa đặt tên')}\n"
                f"🆔 <b>Telegram ID:</b> <code>{target_id}</code>\n"
                f"🛡️ <b>Vai trò:</b> {trole}\n"
                f"────────────────────\n"
                f"Người này sẽ mất quyền sử dụng bot ngay lập tức.\n"
                f"Bạn có chắc chắn muốn xoá không?"
            )
            keyboard = build_whitelist_confirm_delete_keyboard(target_id)
            try:
                await query.edit_message_text(card_text, reply_markup=keyboard, parse_mode="HTML")
            except BadRequest as e:
                if "Message is not modified" not in str(e):
                    raise
            return

        if data.startswith("adm:wl:rm_cf:"):
            target_id = int(data.split(":")[3])
            if super_admin_id is not None and target_id == super_admin_id:
                await query.answer("🛡️ Không thể chỉnh sửa, hạ quyền hoặc xoá Root Super Admin!", show_alert=True)
                return

            if db:
                await delete_admin_user(db, target_id, super_admin_id)

            context.bot_data.get("whitelist_user_ids", set()).discard(target_id)
            context.bot_data.get("admin_roles", {}).pop(target_id, None)

            await query.answer("✅ Đã xoá người dùng khỏi Whitelist", show_alert=True)

            users = await list_admin_users(db) if db else []
            keyboard = build_whitelist_keyboard(users, current_page=1, total_pages=1)
            card_text = (
                f"👥 <b>QUẢN LÝ DANH SÁCH TRUY CẬP (WHITELIST)</b>\n"
                f"────────────────────\n"
                f"Tổng số tài khoản: <b>{len(users)}</b>\n\n"
                f"<i>Bấm vào tài khoản bên dưới để xem chi tiết / phân quyền, hoặc thêm mới:</i>"
            )
            try:
                await query.edit_message_text(card_text, reply_markup=keyboard, parse_mode="HTML")
            except BadRequest as e:
                if "Message is not modified" not in str(e):
                    raise
            return

        if data == "adm:wl:add_prompt":
            await query.answer()
            context.user_data["action_state"] = {
                "action": "await_whitelist_id",
                "expires_at": time.time() + 60,
            }
            card_text = (
                f"➕ <b>THÊM TÀI KHOẢN VÀO WHITELIST</b>\n"
                f"────────────────────\n"
                f"Vui lòng gửi tin nhắn chứa <b>Telegram User ID</b> của người dùng (và tuỳ chọn Tên, ví dụ: <code>123456789 Nguyen Van A</code>).\n\n"
                f"⏳ <i>Hết hạn sau 60 giây.</i>"
            )
            keyboard = InlineKeyboardMarkup(
                [[InlineKeyboardButton("❌ Huỷ", callback_data="adm:wl:add_cancel")]]
            )
            try:
                await query.edit_message_text(card_text, reply_markup=keyboard, parse_mode="HTML")
            except BadRequest as e:
                if "Message is not modified" not in str(e):
                    raise
            return

        if data == "adm:wl:add_cancel":
            await query.answer("Đã huỷ thêm tài khoản")
            context.user_data.pop("action_state", None)
            context.user_data.pop("pending_add_user", None)
            users = await list_admin_users(db) if db else []
            keyboard = build_whitelist_keyboard(users, current_page=1, total_pages=1)
            card_text = (
                f"👥 <b>QUẢN LÝ DANH SÁCH TRUY CẬP (WHITELIST)</b>\n"
                f"────────────────────\n"
                f"Tổng số tài khoản: <b>{len(users)}</b>\n\n"
                f"<i>Bấm vào tài khoản bên dưới để xem chi tiết / phân quyền, hoặc thêm mới:</i>"
            )
            try:
                await query.edit_message_text(card_text, reply_markup=keyboard, parse_mode="HTML")
            except BadRequest as e:
                if "Message is not modified" not in str(e):
                    raise
            return

        if data.startswith("adm:wl:role_pick:"):
            parts = data.split(":")
            target_id = int(parts[3])
            chosen_role = parts[4]

            if super_admin_id is not None and target_id == super_admin_id:
                await query.answer("🛡️ Không thể chỉnh sửa, hạ quyền hoặc xoá Root Super Admin!", show_alert=True)
                return

            pending = context.user_data.pop("pending_add_user", {})
            name = pending.get("name", "") if pending.get("telegram_id") == target_id else ""

            if db:
                await create_or_update_admin_user(db, target_id, name, chosen_role)

            context.bot_data.setdefault("whitelist_user_ids", set()).add(target_id)
            context.bot_data.setdefault("admin_roles", {})[target_id] = UserRole(chosen_role)

            await query.answer(f"✅ Đã thêm người dùng {target_id} ({chosen_role})", show_alert=True)

            target_user = {"telegram_id": target_id, "name": name, "role": chosen_role, "created_at": "Vừa xong"}
            badge = "👑" if chosen_role == "SUPER_ADMIN" else ("🛡️" if chosen_role == "ADMIN" else "👤")
            card_text = (
                f"👤 <b>THÔNG TIN TÀI KHOẢN</b>\n"
                f"────────────────────\n"
                f"🆔 <b>Telegram ID:</b> <code>{target_id}</code>\n"
                f"👤 <b>Tên hiển thị:</b> {html.escape(name or 'Chưa đặt tên')}\n"
                f"🛡️ <b>Vai trò hiện tại:</b> {badge} <b>{chosen_role}</b>\n"
                f"🕒 <b>Ngày cấp quyền:</b> Vừa xong\n"
                f"────────────────────"
            )
            keyboard = build_whitelist_user_detail_keyboard(target_user, is_root=False)
            try:
                await query.edit_message_text(card_text, reply_markup=keyboard, parse_mode="HTML")
            except BadRequest as e:
                if "Message is not modified" not in str(e):
                    raise
            return

        # 3. Model switcher
        if data == "adm:mdl:menu":
            await query.answer()
            available_models = (
                await get_json_setting(db, "available_models", default=DEFAULT_MODELS)
                if db
                else DEFAULT_MODELS
            )
            active_model = context.bot_data.get("active_model_id") or (
                getattr(settings, "nine_router_model_id", "gpt-4o-mini") if settings else "gpt-4o-mini"
            )
            card_text = (
                f"🤖 <b>CẤU HÌNH MODEL LLM (9ROUTER)</b>\n"
                f"────────────────────\n"
                f"Model đang kích hoạt: <code>{html.escape(active_model)}</code>\n"
                f"Trạng thái gateway: ✅ Sẵn sàng\n\n"
                f"<i>Chọn model khả dụng bên dưới hoặc nhập model mới:</i>"
            )
            keyboard = build_model_switcher_keyboard(available_models, active_model)
            try:
                await query.edit_message_text(card_text, reply_markup=keyboard, parse_mode="HTML")
            except BadRequest as e:
                if "Message is not modified" not in str(e):
                    raise
            return

        if data.startswith("adm:mdl:sel:"):
            candidate_model = data.split("adm:mdl:sel:")[1]
            openai_client = context.bot_data.get("openai_client")
            current_model = context.bot_data.get("active_model_id") or "gpt-4o-mini"

            success, probe_msg = await probe_model_reachability(
                openai_client, candidate_model, timeout=5.0
            )

            if success:
                if db:
                    await set_setting(db, "active_model_id", candidate_model, description="Active LLM model")
                context.bot_data["active_model_id"] = candidate_model
                await query.answer(f"✅ Đã chuyển sang model: {candidate_model}", show_alert=True)

                available_models = (
                    await get_json_setting(db, "available_models", default=DEFAULT_MODELS)
                    if db
                    else DEFAULT_MODELS
                )
                card_text = (
                    f"🤖 <b>CẤU HÌNH MODEL LLM (9ROUTER)</b>\n"
                    f"────────────────────\n"
                    f"✅ Đã chuyển sang model: <code>{html.escape(candidate_model)}</code>\n"
                    f"Trạng thái gateway: ✅ Sẵn sàng\n\n"
                    f"<i>Chọn model khả dụng bên dưới hoặc nhập model mới:</i>"
                )
                keyboard = build_model_switcher_keyboard(available_models, candidate_model)
                try:
                    await query.edit_message_text(card_text, reply_markup=keyboard, parse_mode="HTML")
                except BadRequest as e:
                    if "Message is not modified" not in str(e):
                        raise
            else:
                await query.answer("❌ Kiểm tra kết nối thất bại!", show_alert=True)
                card_text = (
                    f"❌ <b>Kiểm tra kết nối thất bại!</b>\n"
                    f"Model: <code>{html.escape(candidate_model)}</code>\n"
                    f"Lỗi: <i>{html.escape(probe_msg)}</i>\n\n"
                    f"Đã giữ nguyên model cũ: <code>{html.escape(current_model)}</code>."
                )
                keyboard = InlineKeyboardMarkup(
                    [
                        [InlineKeyboardButton("⬅️ Quay lại", callback_data="adm:mdl:menu")],
                        [InlineKeyboardButton("❌ Đóng", callback_data="adm:dash:close")],
                    ]
                )
                try:
                    await query.edit_message_text(card_text, reply_markup=keyboard, parse_mode="HTML")
                except BadRequest as e:
                    if "Message is not modified" not in str(e):
                        raise
            return

        if data == "adm:mdl:input_prompt":
            await query.answer()
            context.user_data["action_state"] = {
                "action": "await_model_name",
                "expires_at": time.time() + 60,
            }
            card_text = (
                f"✏️ <b>NHẬP TÊN MODEL LLM MỚI</b>\n"
                f"────────────────────\n"
                f"Vui lòng gửi tin nhắn chứa tên model (Model ID) từ 9router (VD: <code>meta-llama/llama-3.3-70b-instruct</code>).\n\n"
                f"⏳ <i>Hết hạn sau 60 giây.</i>"
            )
            keyboard = InlineKeyboardMarkup(
                [[InlineKeyboardButton("❌ Huỷ", callback_data="adm:mdl:input_cancel")]]
            )
            try:
                await query.edit_message_text(card_text, reply_markup=keyboard, parse_mode="HTML")
            except BadRequest as e:
                if "Message is not modified" not in str(e):
                    raise
            return

        if data == "adm:mdl:input_cancel":
            await query.answer("Đã huỷ nhập model")
            context.user_data.pop("action_state", None)
            available_models = (
                await get_json_setting(db, "available_models", default=DEFAULT_MODELS)
                if db
                else DEFAULT_MODELS
            )
            active_model = context.bot_data.get("active_model_id") or "gpt-4o-mini"
            card_text = (
                f"🤖 <b>CẤU HÌNH MODEL LLM (9ROUTER)</b>\n"
                f"────────────────────\n"
                f"Model đang kích hoạt: <code>{html.escape(active_model)}</code>\n"
                f"Trạng thái gateway: ✅ Sẵn sàng\n\n"
                f"<i>Chọn model khả dụng bên dưới hoặc nhập model mới:</i>"
            )
            keyboard = build_model_switcher_keyboard(available_models, active_model)
            try:
                await query.edit_message_text(card_text, reply_markup=keyboard, parse_mode="HTML")
            except BadRequest as e:
                if "Message is not modified" not in str(e):
                    raise
            return


async def handle_admin_text_input(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    """Handle administrative text inputs when an action prompt is active with 60s TTL."""
    action_state = context.user_data.get("action_state")
    if not action_state or not update.effective_message or not update.effective_message.text:
        return False

    now = time.time()
    if now > action_state.get("expires_at", 0):
        context.user_data.pop("action_state", None)
        return False

    action = action_state.get("action")
    raw_text = update.effective_message.text.strip()

    if action == "await_whitelist_id":
        parts = raw_text.split(maxsplit=1)
        id_str = parts[0]
        if not id_str.isdigit():
            await update.effective_message.reply_text(
                "⚠️ <b>ID không hợp lệ</b>\n"
                "Telegram User ID phải là chuỗi số nguyên dương (VD: <code>123456789</code>).\n"
                "Vui lòng thử lại hoặc bấm [❌ Huỷ].",
                parse_mode="HTML",
            )
            return True

        target_id = int(id_str)
        name = parts[1].strip() if len(parts) > 1 else ""

        context.user_data.pop("action_state", None)
        context.user_data["pending_add_user"] = {
            "telegram_id": target_id,
            "name": name,
        }

        prompt_text = (
            f"👤 <b>CHỌN VAI TRÒ CHO TÀI KHOẢN</b>\n"
            f"────────────────────\n"
            f"🆔 <b>Telegram ID:</b> <code>{target_id}</code>\n"
            f"👤 <b>Tên:</b> {html.escape(name or 'Chưa đặt tên')}\n"
            f"────────────────────\n"
            f"Vui lòng chọn vai trò cấp cho tài khoản này:"
        )
        keyboard = InlineKeyboardMarkup(
            [
                [
                    InlineKeyboardButton(
                        "🛡️ Admin",
                        callback_data=f"adm:wl:role_pick:{target_id}:ADMIN",
                    ),
                    InlineKeyboardButton(
                        "👤 Nhân viên",
                        callback_data=f"adm:wl:role_pick:{target_id}:STAFF",
                    ),
                ],
                [
                    InlineKeyboardButton("❌ Huỷ", callback_data="adm:wl:add_cancel"),
                ],
            ]
        )
        await update.effective_message.reply_text(
            prompt_text, reply_markup=keyboard, parse_mode="HTML"
        )
        return True

    if action == "await_model_name":
        candidate_model = raw_text
        context.user_data.pop("action_state", None)
        openai_client = context.bot_data.get("openai_client")
        current_model = context.bot_data.get("active_model_id") or "gpt-4o-mini"

        success, probe_msg = await probe_model_reachability(
            openai_client, candidate_model, timeout=5.0
        )

        if success:
            async with _get_active_db_context(context) as db:
                if db:
                    await set_setting(db, "active_model_id", candidate_model, description="Active LLM model")
                    # Add to available_models if not already present
                    models = await get_json_setting(db, "available_models", default=DEFAULT_MODELS)
                    if candidate_model not in models:
                        models.append(candidate_model)
                        await set_json_setting(db, "available_models", models, description="Selectable models")
                    display_models = models
                else:
                    display_models = DEFAULT_MODELS

            context.bot_data["active_model_id"] = candidate_model
            card_text = (
                f"🤖 <b>CẤU HÌNH MODEL LLM (9ROUTER)</b>\n"
                f"────────────────────\n"
                f"✅ Đã chuyển sang model: <code>{html.escape(candidate_model)}</code>\n"
                f"Trạng thái gateway: ✅ Sẵn sàng\n\n"
                f"<i>Chọn model khả dụng bên dưới hoặc nhập model mới:</i>"
            )
            keyboard = build_model_switcher_keyboard(display_models, candidate_model)
            await update.effective_message.reply_text(
                card_text, reply_markup=keyboard, parse_mode="HTML"
            )
        else:
            card_text = (
                f"❌ <b>Kiểm tra kết nối thất bại!</b>\n"
                f"Model: <code>{html.escape(candidate_model)}</code>\n"
                f"Lỗi: <i>{html.escape(probe_msg)}</i>\n\n"
                f"Đã giữ nguyên model cũ: <code>{html.escape(current_model)}</code>."
            )
            keyboard = InlineKeyboardMarkup(
                [
                    [InlineKeyboardButton("⬅️ Quay lại", callback_data="adm:mdl:menu")],
                    [InlineKeyboardButton("❌ Đóng", callback_data="adm:dash:close")],
                ]
            )
            await update.effective_message.reply_text(
                card_text, reply_markup=keyboard, parse_mode="HTML"
            )
        return True

    return False
