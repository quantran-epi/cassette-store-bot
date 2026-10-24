import html
import logging
import re
from telegram import Update
from telegram.ext import ContextTypes

from src.db.customers import create_customer, get_customer_by_phone, update_customer
from src.db.orders import create_order
from src.models.customer import Customer
from src.models.order import Order, OrderStatus

logger = logging.getLogger(__name__)

CALLBACK_PATTERN = re.compile(r"^ord:(cf|ca):([a-f0-9]{8})$")


async def handle_order_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle 1-tap confirmation and cancellation callbacks for order drafts."""
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
        await query.edit_message_text(
            "Thao tác hết hạn, bác vui lòng gửi lại tin nhắn nhé!"
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
        draft = pending_orders.pop(draft_id)

        app_context = context.application.bot_data.get("app_context")
        db = getattr(app_context, "db", None) if app_context else context.application.bot_data.get("db")

        if not db:
            logger.error("Database connection missing in bot_data")
            await query.edit_message_text("⚠️ Lỗi cơ sở dữ liệu. Bác vui lòng thử lại sau!")
            return

        phone = draft["customer_phone"]
        name = draft["customer_name"] or "Khách lẻ"
        address = draft["shipping_address"] or ""

        # Match or create customer
        customer = await get_customer_by_phone(db, phone)
        if not customer:
            addresses = [address] if address else []
            new_customer = Customer(
                name=name,
                phones=[phone],
                addresses=addresses,
                notes=draft.get("notes") or "",
            )
            cust_id = await create_customer(db, new_customer)
            customer = new_customer
            customer.id = cust_id
        else:
            # If new address provided not already in customer's addresses, append it
            if address and address not in customer.addresses:
                customer.addresses.append(address)
                await update_customer(db, customer)

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
        order_id = await create_order(db, new_order)

        success_card = (
            f"✅ <b>ĐÃ LƯU ĐƠN HÀNG THÀNH CÔNG</b>\n"
            f"📦 <b>Mã đơn:</b> <code>#{order_id}</code>\n"
            f"👤 <b>Khách:</b> {html.escape(customer.name)}\n"
            f"📞 <b>SĐT:</b> <code>{phone}</code>\n"
            f"💰 <b>Tổng tiền:</b> {new_order.total_amount:,} đ\n"
            f"💵 <b>Tiền COD thu:</b> {new_order.cod_amount:,} đ\n"
            f"<i>Trạng thái: Chờ làm</i>"
        ).replace(",", ".")

        await query.edit_message_text(success_card, parse_mode="HTML")
