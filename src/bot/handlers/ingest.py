import html
import logging
import uuid
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.constants import ChatAction
from telegram.ext import ContextTypes

from src.db.customers import get_customer_by_phone
from src.db.orders import get_customer_order_stats
from src.services.extractor import extract_order_from_text

logger = logging.getLogger(__name__)


def render_preview_card(draft: dict, stats: dict | None = None) -> tuple[str, InlineKeyboardMarkup]:
    """Format elderly-friendly HTML preview card and 1-tap inline buttons."""
    name = html.escape(draft.get("customer_name") or "[Chưa có]")
    phone = html.escape(draft.get("customer_phone") or "[Chưa có]")
    address = html.escape(draft.get("shipping_address") or "[Chưa có]")
    items = html.escape(draft.get("items_text") or "[Chưa có]")
    total = f"{draft.get('total_amount', 0):,} đ".replace(",", ".")
    cod = f"{draft.get('cod_amount', 0):,} đ".replace(",", ".")
    deposit = draft.get("deposit_amount", 0)

    # Customer history tag
    history_tag = ""
    warning_tag = ""
    if stats and stats.get("total_orders", 0) > 0:
        spent = f"{stats['total_spent']:,} đ".replace(",", ".")
        history_tag = f" <i>[Khách quen: {stats['total_orders']} đơn - {spent}]</i>"
        if stats.get("bom_count", 0) > 0:
            warning_tag = f"\n⚠️ <b>CẢNH BÁO: Khách từng có {stats['bom_count']} đơn BOM HÀNG!</b>"

    deposit_info = f" (đã cọc {deposit:,} đ)".replace(",", ".") if deposit > 0 else ""

    text = (
        f"📦 <b>ĐƠN HÀNG MỚI (Xem trước)</b>\n"
        f"👤 <b>Khách:</b> {name}{history_tag}\n"
        f"📞 <b>SĐT:</b> <code>{phone}</code>\n"
        f"📍 <b>Địa chỉ:</b> {address}\n"
        f"📼 <b>Băng cassette:</b> {items}\n"
        f"💰 <b>Tổng tiền:</b> {total}\n"
        f"💵 <b>Tiền COD thu:</b> {cod}{deposit_info}"
        f"{warning_tag}\n"
        f"────────────────────\n"
        f"Bác bấm nút bên dưới để xác nhận nhé:"
    )

    draft_id = draft["draft_id"]
    keyboard = [
        [
            InlineKeyboardButton("✅ Xác nhận lưu", callback_data=f"ord:cf:{draft_id}"),
            InlineKeyboardButton("❌ Huỷ bỏ", callback_data=f"ord:ca:{draft_id}"),
        ]
    ]
    return text, InlineKeyboardMarkup(keyboard)


async def handle_text_order(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle incoming text order message."""
    if not update.message or not update.message.text:
        return

    text = update.message.text.strip()
    if text.startswith("/"):
        return  # Allow command handlers to process

    await update.message.chat.send_action(ChatAction.TYPING)

    app_context = context.application.bot_data.get("app_context")
    if not app_context:
        # Fallback to direct bot_data references if app_context not wrapped
        settings = context.application.bot_data.get("settings")
        openai_client = context.application.bot_data.get("openai_client")
        db = context.application.bot_data.get("db")
    else:
        settings = getattr(app_context, "settings", None)
        openai_client = getattr(app_context, "openai_client", None)
        db = getattr(app_context, "db", None)

    if not openai_client or not settings:
        logger.error("OpenAI client or settings missing from application data")
        await update.message.reply_text(
            "⚠️ Hệ thống bóc tách đang bận hoặc gián đoạn kết nối. Bác vui lòng thử gửi lại tin nhắn sau giây lát nhé!"
        )
        return

    extracted = await extract_order_from_text(
        client=openai_client,
        model_id=settings.nine_router_model_id,
        text=text,
    )

    if not extracted or not extracted.customer_phone:
        await update.message.reply_text(
            "Em không nhận diện được đơn hàng từ tin nhắn này. Bác vui lòng gửi lại tin nhắn có số điện thoại khách nhé!"
        )
        return

    # Check existing customer stats
    stats = None
    if db:
        customer = await get_customer_by_phone(db, extracted.customer_phone)
        if customer and customer.id:
            stats = await get_customer_order_stats(db, customer.id)
            # Auto-fill address if missing and customer has 1 address
            if not extracted.shipping_address and len(customer.addresses) == 1:
                extracted.shipping_address = customer.addresses[0]

    draft_id = uuid.uuid4().hex[:8]
    draft_data = {
        "draft_id": draft_id,
        "customer_name": extracted.customer_name,
        "customer_phone": extracted.customer_phone,
        "shipping_address": extracted.shipping_address,
        "items_text": extracted.items_text,
        "total_amount": extracted.total_amount,
        "cod_amount": extracted.cod_amount,
        "deposit_amount": extracted.deposit_amount,
        "payment_method": extracted.payment_method,
        "notes": extracted.notes,
        "raw_text": text,
        "photo_file_ids": [],
    }

    pending_orders = context.user_data.setdefault("pending_orders", {})
    pending_orders[draft_id] = draft_data

    preview_text, reply_markup = render_preview_card(draft_data, stats)
    await update.message.reply_text(
        text=preview_text,
        reply_markup=reply_markup,
        parse_mode="HTML",
    )
