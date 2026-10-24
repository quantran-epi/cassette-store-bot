import html
import logging
import uuid
from contextlib import nullcontext

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.constants import ChatAction
from telegram.ext import ContextTypes

from src.db.connection import get_db_connection
from src.db.customers import get_customer_by_phone
from src.db.orders import get_customer_order_stats
from src.models.extractor import ExtractedOrder
from src.services.extractor import extract_order_from_text

logger = logging.getLogger(__name__)


def render_preview_card(draft: dict, stats: dict | None = None) -> tuple[str, InlineKeyboardMarkup]:
    """Format elderly-friendly HTML preview card and 1-tap inline buttons."""
    name = html.escape(draft.get("customer_name") or "[Chưa có]")
    phone = html.escape(draft.get("customer_phone") or "[Chưa có]")
    address_val = draft.get("shipping_address") or "[Chưa có]"
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

    address_label = "📍 <b>Địa chỉ:</b>"
    if draft.get("address_auto_filled"):
        address_label = "📍 <b>Địa chỉ</b> <i>(tự lấy từ đơn trước)</i>:"

    photo_tag = ""
    photos = draft.get("photo_file_ids") or []
    if photos:
        photo_tag = f"\n📷 <b>Ảnh đính kèm:</b> {len(photos)} ảnh"

    text = (
        f"📦 <b>ĐƠN HÀNG MỚI (Xem trước)</b>\n"
        f"👤 <b>Khách:</b> {name}{history_tag}\n"
        f"📞 <b>SĐT:</b> <code>{phone}</code>\n"
        f"{address_label} {html.escape(address_val)}\n"
        f"📼 <b>Băng cassette:</b> {items}\n"
        f"💰 <b>Tổng tiền:</b> {total}\n"
        f"💵 <b>Tiền COD thu:</b> {cod}{deposit_info}"
        f"{photo_tag}"
        f"{warning_tag}\n"
        f"────────────────────\n"
        f"Bác bấm nút bên dưới để xác nhận nhé:"
    )

    draft_id = draft["draft_id"]
    keyboard: list[list[InlineKeyboardButton]] = []

    # Optional address picker buttons for returning customer with multiple addresses
    available_addresses = draft.get("available_addresses") or []
    if len(available_addresses) >= 2:
        for idx, addr in enumerate(available_addresses):
            short_addr = (addr[:18] + "...") if len(addr) > 18 else addr
            btn_text = f"📍 Đổi: {short_addr}"
            keyboard.append(
                [InlineKeyboardButton(btn_text, callback_data=f"ord:ad:{draft_id}:{idx}")]
            )

    keyboard.append(
        [
            InlineKeyboardButton("✅ Xác nhận lưu", callback_data=f"ord:cf:{draft_id}"),
            InlineKeyboardButton("❌ Huỷ bỏ", callback_data=f"ord:ca:{draft_id}"),
        ]
    )
    return text, InlineKeyboardMarkup(keyboard)


async def process_extracted_order(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    extracted: ExtractedOrder,
    raw_text: str,
    photo_file_ids: list[str] | None = None,
) -> None:
    """Check customer history, auto-fill address, create draft, and reply with preview card."""
    if not extracted.customer_phone:
        await update.message.reply_text(
            "Em không nhận diện được đơn hàng từ tin nhắn này. Bác vui lòng gửi lại tin nhắn có số điện thoại khách nhé!"
        )
        return

    app_context = context.application.bot_data.get("app_context")
    db = getattr(app_context, "db", None) if app_context else context.application.bot_data.get("db")
    settings = context.application.bot_data.get("settings")
    db_path = getattr(settings, "sqlite_db_path", "cassette_store.db") if settings else "cassette_store.db"

    stats = None
    address_auto_filled = False
    available_addresses: list[str] = []

    db_ctx = nullcontext(db) if db else get_db_connection(db_path)
    try:
        async with db_ctx as active_db:
            if active_db:
                customer = await get_customer_by_phone(active_db, extracted.customer_phone)
                if customer and customer.id:
                    stats = await get_customer_order_stats(active_db, customer.id)
                    if not extracted.shipping_address:
                        if len(customer.addresses) == 1:
                            extracted.shipping_address = customer.addresses[0]
                            address_auto_filled = True
                        elif len(customer.addresses) >= 2:
                            extracted.shipping_address = customer.addresses[-1]
                            available_addresses = list(customer.addresses)
    except Exception as e:
        logger.warning("Customer history lookup failed: %s", e)

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
        "raw_text": raw_text,
        "photo_file_ids": photo_file_ids or [],
        "address_auto_filled": address_auto_filled,
        "available_addresses": available_addresses,
        "stats": stats,
    }

    pending_orders = context.user_data.setdefault("pending_orders", {})
    pending_orders[draft_id] = draft_data

    preview_text, reply_markup = render_preview_card(draft_data, stats)
    await update.message.reply_text(
        text=preview_text,
        reply_markup=reply_markup,
        parse_mode="HTML",
    )


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
        settings = context.application.bot_data.get("settings")
        openai_client = context.application.bot_data.get("openai_client")
    else:
        settings = getattr(app_context, "settings", None)
        openai_client = getattr(app_context, "openai_client", None)

    if not openai_client or not settings:
        logger.error("OpenAI client or settings missing from application data")
        await update.message.reply_text(
            "⚠️ Hệ thống bóc tách đang bận hoặc gián đoạn kết nối. Bác vui lòng thử gửi lại tin nhắn sau giây lát nhé!"
        )
        return

    try:
        extracted = await extract_order_from_text(
            client=openai_client,
            model_id=settings.nine_router_model_id,
            text=text,
        )
    except Exception:
        logger.exception("Failed to extract order via 9router gateway")
        await update.message.reply_text(
            "⚠️ Hệ thống bóc tách đang bận hoặc gián đoạn kết nối. Bác vui lòng thử gửi lại tin nhắn sau giây lát nhé!"
        )
        return

    if not extracted:
        await update.message.reply_text(
            "Em không nhận diện được đơn hàng từ tin nhắn này. Bác vui lòng gửi lại tin nhắn có số điện thoại khách nhé!"
        )
        return

    await process_extracted_order(update, context, extracted, raw_text=text, photo_file_ids=[])


async def handle_photo_order(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle incoming photo with caption as an order message."""
    if not update.message or not update.message.photo:
        return

    caption = (update.message.caption or "").strip()
    if not caption:
        await update.message.reply_text(
            "Bác vui lòng gửi kèm ảnh với phần chú thích (caption) là thông tin đơn hàng nhé!"
        )
        return

    # Take highest resolution photo file_id per D-09 / T-02-06
    highest_res_photo = update.message.photo[-1]
    photo_file_id = highest_res_photo.file_id

    await update.message.chat.send_action(ChatAction.TYPING)

    app_context = context.application.bot_data.get("app_context")
    if not app_context:
        settings = context.application.bot_data.get("settings")
        openai_client = context.application.bot_data.get("openai_client")
    else:
        settings = getattr(app_context, "settings", None)
        openai_client = getattr(app_context, "openai_client", None)

    if not openai_client or not settings:
        logger.error("OpenAI client or settings missing from application data")
        await update.message.reply_text(
            "⚠️ Hệ thống bóc tách đang bận hoặc gián đoạn kết nối. Bác vui lòng thử gửi lại tin nhắn sau giây lát nhé!"
        )
        return

    try:
        extracted = await extract_order_from_text(
            client=openai_client,
            model_id=settings.nine_router_model_id,
            text=caption,
        )
    except Exception:
        logger.exception("Failed to extract photo order caption via 9router gateway")
        await update.message.reply_text(
            "⚠️ Hệ thống bóc tách đang bận hoặc gián đoạn kết nối. Bác vui lòng thử gửi lại tin nhắn sau giây lát nhé!"
        )
        return

    if not extracted:
        await update.message.reply_text(
            "Em không nhận diện được đơn hàng từ tin nhắn này. Bác vui lòng gửi lại tin nhắn có số điện thoại khách nhé!"
        )
        return

    await process_extracted_order(
        update,
        context,
        extracted,
        raw_text=caption,
        photo_file_ids=[photo_file_id],
    )
