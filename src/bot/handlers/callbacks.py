import html
import json
import logging
import re
import time
from contextlib import nullcontext
from datetime import datetime

from telegram import Update
from telegram.ext import ContextTypes

from src.bot.handlers.ingest import render_preview_card
from src.bot.handlers.mutation import (
    handle_mutation_selection,
    handle_status_suggestion_selection,
)
from src.bot.keyboards import (
    DIVIDER,
    STATUS_NAMES,
    build_order_detail_keyboard,
    render_order_detail_card,
    to_vn_datetime,
)
from src.db.connection import get_db_connection
from src.db.customers import add_address, create_customer, get_customer_by_phone
from src.db.orders import create_order, mutate_order_with_lock
from src.models.customer import Customer
from src.models.order import Order, OrderStatus

logger = logging.getLogger(__name__)

CALLBACK_PATTERN = re.compile(r"^ord:(cf|ca|ad):([a-f0-9]{8})(?::(\d+))?$")
MUTATION_CALLBACK_PATTERN = re.compile(
    r"^ord_mut_(cf|ca|sel|st):([a-f0-9]{8})(?::(.*))?$"
)


def _get_active_db_context(context: ContextTypes.DEFAULT_TYPE):
    """Resolve active database connection or create context connection."""
    app_context = context.application.bot_data.get("app_context")
    db = getattr(app_context, "db", None) if app_context else context.application.bot_data.get("db")
    settings = context.application.bot_data.get("settings")
    db_path = getattr(settings, "sqlite_db_path", "cassette_store.db") if settings else "cassette_store.db"
    return nullcontext(db) if db else get_db_connection(db_path)


async def handle_order_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle 1-tap confirmation, cancellation, and address selection callbacks."""
    query = update.callback_query
    if not query or not query.data:
        return

    # Answer callback query immediately to avoid 30-second spinning loader
    await query.answer()

    match = CALLBACK_PATTERN.match(query.data)
    if not match:
        return

    action, draft_id = match.group(1), match.group(2)
    pending_orders = context.user_data.get("pending_orders", {})

    if draft_id not in pending_orders:
        await query.edit_message_text("Thao tác hết hạn, bác vui lòng gửi lại tin nhắn nhé!")
        return

    draft = pending_orders[draft_id]

    # Handle address selection (ord:ad:<draft_id>:<index>)
    if action == "ad":
        idx_str = match.group(3)
        available = draft.get("available_addresses", [])
        if idx_str is not None:
            addr_idx = int(idx_str)
            # Bounds check per T-02-05
            if 0 <= addr_idx < len(available):
                draft["shipping_address"] = available[addr_idx]
                draft["address_auto_filled"] = False

        stats = draft.get("stats")
        preview_text, reply_markup = render_preview_card(draft, stats)
        await query.edit_message_text(
            text=preview_text,
            reply_markup=reply_markup,
            parse_mode="HTML",
        )
        return

    # Handle cancellation (0 DB writes)
    if action == "ca":
        pending_orders.pop(draft_id, None)
        await query.edit_message_text(
            "❌ <b>ĐÃ HUỶ ĐƠN HÀNG</b>\n<i>Đơn nháp đã được huỷ bỏ.</i>",
            parse_mode="HTML",
        )
        return

    # Handle confirmation (persist customer & order to SQLite)
    if action == "cf":
        pending_orders.pop(draft_id, None)

        db_ctx = _get_active_db_context(context)

        async with db_ctx as active_db:
            if not active_db:
                logger.error("Database connection could not be established")
                await query.edit_message_text("⚠️ Lỗi cơ sở dữ liệu. Bác vui lòng thử lại sau!")
                return

            phone = draft["customer_phone"]
            name = draft["customer_name"] or "Khách lẻ"
            address = draft["shipping_address"] or ""

            # Match or create customer
            customer = await get_customer_by_phone(active_db, phone)
            if not customer:
                addresses = [address] if address else []
                new_customer = Customer(
                    name=name,
                    phones=[phone],
                    addresses=addresses,
                    notes=draft.get("notes") or "",
                )
                cust_id = await create_customer(active_db, new_customer)
                customer = new_customer
                customer.id = cust_id
            else:
                # If customer provided a new address, append idempotently (D-06)
                if address:
                    await add_address(active_db, customer.id, address)

            eff_user = update.effective_user
            creator_id = eff_user.id if eff_user and isinstance(eff_user.id, int) else None
            creator_name = str(eff_user.full_name) if eff_user and isinstance(eff_user.full_name, str) else None

            # Create Order
            new_order = Order(
                customer_id=customer.id,
                customer_name=customer.name,
                customer_phone=phone,
                shipping_address=address,
                items_text=draft.get("items_text") or "",
                total_amount=draft.get("total_amount", 0),
                cod_amount=draft.get("cod_amount", 0),
                payment_method=draft.get("payment_method", "COD"),
                status=OrderStatus.CHO_LAM,
                photo_file_ids=draft.get("photo_file_ids") or [],
                raw_text=draft.get("raw_text") or "",
                created_by_user_id=creator_id,
                created_by_name=creator_name,
            )
            order_id = await create_order(active_db, new_order)

            photo_tag = ""
            if new_order.photo_file_ids:
                photo_tag = f"\n📷 <b>Ảnh đính kèm:</b> {len(new_order.photo_file_ids)} ảnh"

            success_card = (
                f"✅ <b>ĐÃ LƯU ĐƠN HÀNG THÀNH CÔNG</b>\n"
                f"📦 <b>Mã đơn:</b> <code>#{order_id}</code>\n"
                f"👤 <b>Khách:</b> {html.escape(customer.name)}\n"
                f"📞 <b>SĐT:</b> <code>{phone}</code>\n"
                f"💰 <b>Tổng tiền:</b> {new_order.total_amount:,} đ\n"
                f"💵 <b>Tiền COD thu:</b> {new_order.cod_amount:,} đ"
                f"{photo_tag}\n"
                f"<i>Trạng thái: Chờ làm</i>"
            ).replace(",", ".")

            await query.edit_message_text(success_card, parse_mode="HTML")


async def handle_mutation_callback(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """Handle natural language order mutation callbacks (ord_mut_cf, ord_mut_ca, ord_mut_sel, ord_mut_st)."""
    query = update.callback_query
    if not query or not query.data:
        return

    await query.answer()

    match = MUTATION_CALLBACK_PATTERN.match(query.data)
    if not match:
        return

    action, draft_id, extra = match.group(1), match.group(2), match.group(3)
    pending_mutations = context.user_data.get("pending_mutations", {})

    if draft_id not in pending_mutations:
        await query.edit_message_text(
            "⏰ <b>YÊU CẦU SỬA ĐƠN ĐÃ HẾT HẠN (120s)</b>\n"
            "<i>Thao tác sửa đơn đã tự động huỷ bỏ để đảm bảo an toàn. Bác vui lòng nhắn lại câu lệnh nhé!</i>",
            reply_markup=None,
            parse_mode="HTML",
        )
        return

    draft = pending_mutations[draft_id]

    # Check TTL expiry (120s) per D-12
    if time.time() > draft.get("expires_at", 0):
        oid = draft.get("order_id", "")
        pending_mutations.pop(draft_id, None)
        await query.edit_message_text(
            f"⏰ <b>YÊU CẦU SỬA ĐƠN ĐÃ HẾT HẠN (120s)</b>\n"
            f"<i>Thao tác sửa đơn #{oid} đã tự động huỷ bỏ để đảm bảo an toàn. Bác vui lòng nhắn lại câu lệnh nhé!</i>",
            reply_markup=None,
            parse_mode="HTML",
        )
        return

    # Handle cancellation (ord_mut_ca) per D-12
    if action == "ca":
        oid = draft.get("order_id", "")
        pending_mutations.pop(draft_id, None)
        await query.edit_message_text(
            f"❌ <b>ĐÃ HUỶ YÊU CẦU SỬA ĐƠN</b>\n"
            f"<i>Đơn hàng #{oid} được giữ nguyên, không có thay đổi nào được lưu.</i>",
            reply_markup=None,
            parse_mode="HTML",
        )
        return

    # Handle target order selection (ord_mut_sel:<draft_id>:<order_id>) per D-10
    if action == "sel":
        if extra:
            try:
                selected_oid = int(extra)
                await handle_mutation_selection(update, context, draft_id, selected_oid)
            except ValueError:
                pass
        return

    # Handle status suggestion selection (ord_mut_st:<draft_id>:<order_id>:<status>) per D-13
    if action == "st":
        if extra and ":" in extra:
            parts = extra.split(":", 1)
            try:
                st_oid = int(parts[0])
                st_val = parts[1]
                await handle_status_suggestion_selection(
                    update, context, draft_id, st_oid, st_val
                )
            except ValueError:
                pass
        return

    # Handle confirmation (ord_mut_cf) per D-14, D-15, D-17, D-18
    if action == "cf":
        pending_mutations.pop(draft_id, None)
        order_id = draft.get("order_id")
        expected_updated_at = draft.get("expected_updated_at")
        delta_dict = draft.get("delta", {})

        eff_user = update.effective_user
        user_id = eff_user.id if eff_user and isinstance(eff_user.id, int) else None
        user_name = str(eff_user.full_name) if eff_user and isinstance(eff_user.full_name, str) else "Admin"

        db_ctx = _get_active_db_context(context)
        async with db_ctx as active_db:
            if not active_db or not order_id:
                await query.edit_message_text("⚠️ Lỗi cơ sở dữ liệu. Bác vui lòng thử lại sau!")
                return

            success, changes, fresh_order = await mutate_order_with_lock(
                db=active_db,
                order_id=order_id,
                expected_updated_at=expected_updated_at,
                delta_dict=delta_dict,
                user_id=user_id,
                user_name=user_name,
            )

        if not success:
            # Optimistic concurrency conflict notice per D-17 & D-18
            modifier = "một người khác"
            mod_time = ""
            changes_summary = ""
            if changes:
                modifier = html.escape(changes.get("user_name") or "một người khác")
                mod_time = html.escape(str(changes.get("created_at") or ""))
                raw_changes = changes.get("changes") or {}
                if not raw_changes and "changes_json" in changes:
                    try:
                        raw_changes = json.loads(changes["changes_json"])
                    except Exception:
                        raw_changes = {}
                change_lines = []
                for k, v in raw_changes.items():
                    if isinstance(v, dict):
                        old_v = html.escape(str(v.get("old", "")))
                        new_v = html.escape(str(v.get("new", "")))
                        change_lines.append(f"• {k}: {old_v} ➡️ {new_v}")
                    else:
                        change_lines.append(f"• {k}: {html.escape(str(v))}")
                changes_summary = "\n".join(change_lines) if change_lines else "• Cập nhật thông tin đơn"

            conflict_msg = (
                f"⚠️ <b>XUNG ĐỘT SỬA ĐƠN HÀNG #{order_id}!</b>\n"
                f"{DIVIDER}\n"
                f"Đơn hàng này vừa được <b>{modifier}</b> sửa lúc <b>{mod_time}</b>:\n"
                f"{changes_summary}\n\n"
                f"Thao tác sửa của bác đã tạm dừng để tránh đè dữ liệu. Dưới đây là thông tin mới nhất:\n"
                f"{DIVIDER}\n"
            )
            if fresh_order:
                conflict_msg += render_order_detail_card(fresh_order)
                vn_dt = to_vn_datetime(fresh_order.created_at) if isinstance(fresh_order.created_at, datetime) else None
                today_str = vn_dt.strftime("%Y-%m-%d") if vn_dt else ""
                kb = build_order_detail_keyboard(fresh_order, date_str=today_str, page=1)
                await query.edit_message_text(conflict_msg, reply_markup=kb, parse_mode="HTML")
            else:
                await query.edit_message_text(conflict_msg, parse_mode="HTML")
            return

        # Success: edit message in-place to Updated Order Card per D-14
        if fresh_order:
            vn_dt = to_vn_datetime(fresh_order.created_at) if isinstance(fresh_order.created_at, datetime) else None
            today_str = vn_dt.strftime("%Y-%m-%d") if vn_dt else ""
            card_body = render_order_detail_card(fresh_order)
            success_card = (
                f"✅ <b>ĐÃ CẬP NHẬT THÀNH CÔNG ĐƠN #{order_id}!</b>\n"
                f"{card_body}"
            )
            kb = build_order_detail_keyboard(fresh_order, date_str=today_str, page=1)
            await query.edit_message_text(success_card, reply_markup=kb, parse_mode="HTML")
        else:
            await query.edit_message_text(
                f"✅ <b>ĐÃ CẬP NHẬT THÀNH CÔNG ĐƠN #{order_id}!</b>",
                parse_mode="HTML",
            )
