import asyncio
import html
import logging
import time
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

MEDIA_GROUP_DEBOUNCE_SECONDS: float = 0.8
_MEDIA_GROUP_BUFFERS: dict[str, dict] = {}
_PROCESSED_MEDIA_GROUPS: dict[str, float] = {}


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

    # Check for active action_state (e.g. await_tracking) per D-12
    action_state = context.user_data.get("action_state")
    if action_state:
        expires_at = action_state.get("expires_at", 0)
        if time.time() <= expires_at:
            from src.bot.handlers.order_actions import handle_action_state_text

            handled = await handle_action_state_text(update, context, action_state)
            if handled:
                return
        else:
            # Expired after 120s: clean up state and proceed to regular ingestion
            context.user_data.pop("action_state", None)

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

    # Check for active action_state (e.g. await_photo) per D-11, D-12
    action_state = context.user_data.get("action_state")
    if action_state:
        expires_at = action_state.get("expires_at", 0)
        if time.time() <= expires_at:
            from src.bot.handlers.order_actions import handle_action_state_photo

            handled = await handle_action_state_photo(update, context, action_state)
            if handled:
                return
        else:
            # Expired after 120s: clean up state and proceed to regular ingestion
            context.user_data.pop("action_state", None)

async def _extract_and_process_photo_order(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    caption: str,
    photo_file_ids: list[str],
) -> None:
    """Extract order info from photo caption and reply with preview card."""
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
        photo_file_ids=photo_file_ids,
    )


async def handle_photo_order(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle incoming photo or photo album with caption as an order message."""
    if not update.message or not update.message.photo:
        return

    # Check for active action_state (e.g. await_photo) per D-11, D-12
    action_state = context.user_data.get("action_state")
    if action_state:
        expires_at = action_state.get("expires_at", 0)
        if time.time() <= expires_at:
            from src.bot.handlers.order_actions import handle_action_state_photo

            handled = await handle_action_state_photo(update, context, action_state)
            if handled:
                return
        else:
            # Expired after 120s: clean up state and proceed to regular ingestion
            context.user_data.pop("action_state", None)

    media_group_id = getattr(update.message, "media_group_id", None)
    if not isinstance(media_group_id, str):
        media_group_id = None

    # Single photo flow (media_group_id is None)
    if not media_group_id:
        caption = (update.message.caption or "").strip()
        if not caption:
            await update.message.reply_text(
                "Bác vui lòng gửi kèm ảnh với phần chú thích (caption) là thông tin đơn hàng nhé!"
            )
            return

        highest_res_photo = update.message.photo[-1]
        photo_file_id = highest_res_photo.file_id
        await _extract_and_process_photo_order(
            update,
            context,
            caption,
            [photo_file_id],
        )
        return

    # Media group album flow
    now = time.time()
    # Prune expired processed media groups (>60s)
    to_prune = [mg_id for mg_id, ts in _PROCESSED_MEDIA_GROUPS.items() if now - ts > 60.0]
    for mg_id in to_prune:
        _PROCESSED_MEDIA_GROUPS.pop(mg_id, None)

    if media_group_id in _PROCESSED_MEDIA_GROUPS:
        return

    caption = (update.message.caption or "").strip()
    highest_res_photo = update.message.photo[-1]
    photo_file_id = highest_res_photo.file_id

    # If album buffer already exists, append photo and capture caption if provided
    if media_group_id in _MEDIA_GROUP_BUFFERS:
        buf = _MEDIA_GROUP_BUFFERS[media_group_id]
        if photo_file_id not in buf["photos"]:
            buf["photos"].append(photo_file_id)
        if caption and not buf["caption"]:
            buf["caption"] = caption
            buf["caption_update"] = update
        return

    # First photo in album: initialize buffer and start debounce window
    buf = {
        "photos": [photo_file_id],
        "caption": caption,
        "caption_update": update if caption else None,
        "first_update": update,
    }
    _MEDIA_GROUP_BUFFERS[media_group_id] = buf

    try:
        await asyncio.sleep(MEDIA_GROUP_DEBOUNCE_SECONDS)

        effective_update = buf["caption_update"] or buf["first_update"]
        final_caption = buf["caption"]
        photos = list(buf["photos"])

        if not final_caption:
            await effective_update.message.reply_text(
                "Bác vui lòng gửi kèm ảnh với phần chú thích (caption) là thông tin đơn hàng nhé!"
            )
            return

        await _extract_and_process_photo_order(
            effective_update,
            context,
            final_caption,
            photos,
        )
    finally:
        _MEDIA_GROUP_BUFFERS.pop(media_group_id, None)
        _PROCESSED_MEDIA_GROUPS[media_group_id] = time.time()
