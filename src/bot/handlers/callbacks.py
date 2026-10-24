import html
import logging
import re
from contextlib import nullcontext

from telegram import Update
from telegram.ext import ContextTypes

from src.bot.handlers.ingest import render_preview_card
from src.db.connection import get_db_connection
from src.db.customers import add_address, create_customer, get_customer_by_phone
from src.db.orders import create_order
from src.models.customer import Customer
from src.models.order import Order, OrderStatus

logger = logging.getLogger(__name__)

CALLBACK_PATTERN = re.compile(r"^ord:(cf|ca|ad):([a-f0-9]{8})(?::(\d+))?$")


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

        app_context = context.application.bot_data.get("app_context")
        db = (
            getattr(app_context, "db", None)
            if app_context
            else context.application.bot_data.get("db")
        )

        settings = context.application.bot_data.get("settings")
        db_path = getattr(settings, "sqlite_db_path", "cassette_store.db") if settings else "cassette_store.db"

        # If persistent connection is not in bot_data, create a context connection
        db_ctx = nullcontext(db) if db else get_db_connection(db_path)

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
