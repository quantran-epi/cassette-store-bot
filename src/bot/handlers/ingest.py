import asyncio
import html
import json
import logging
import time
import uuid
from contextlib import nullcontext

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import Application, ContextTypes

from src.bot.handlers.base import run_with_typing
from src.bot.keyboards import format_customer_classification
from src.db.connection import get_db_connection
from src.db.customers import get_customer_by_phone
from src.db.orders import get_customer_order_stats
from src.models.extractor import ExtractedOrder
from src.models.mutation import IntentType
from src.services.extractor import extract_order_from_text
from src.services.intent_router import classify_intent, extract_order_id_from_reply
from src.services.order_search import is_search_intent
from src.services.tape_parser import build_tape_columns

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

    classification = format_customer_classification(
        stats.get("total_orders", 0) if stats else 0,
        stats.get("total_spent", 0) if stats else 0,
    )
    warning_tag = ""
    if stats and stats.get("bom_count", 0) > 0:
        warning_tag = f"\n⚠️ <b>CẢNH BÁO: Khách từng có {stats['bom_count']} đơn BOM HÀNG!</b>"

    deposit_info = f" (đã cọc {deposit:,} đ)".replace(",", ".") if deposit > 0 else ""

    address_label = "📍 <b>ĐỊA CHỈ:</b>"
    if draft.get("address_auto_filled"):
        address_label = "📍 <b>ĐỊA CHỈ</b> <i>(tự lấy từ đơn trước)</i>:"

    photo_tag = ""
    photos = draft.get("photo_file_ids") or []
    if photos:
        photo_tag = f"\n📷 <b>ẢNH ĐÍNH KÈM:</b> {len(photos)} ảnh"

    notes_tag = ""
    if draft.get("notes"):
        notes_tag = f"\n📝 <b>GHI CHÚ:</b> {html.escape(draft['notes'])}"

    tape_tag = ""
    if draft.get("tape_quantity") is not None or draft.get("tapes"):
        from src.models.order import TapeItem
        from src.services.tape_parser import format_tape_summary

        tape_summary = format_tape_summary(
            draft.get("tape_quantity"),
            [TapeItem(**t) for t in draft.get("tapes") or []],
        )
        tape_tag = f"\n📼 <b>PHÔI BĂNG:</b> {html.escape(tape_summary)}"

    artist_tag = ""
    if draft.get("tape_artists"):
        from src.services.tape_parser import format_artist_summary

        artist_tag = (
            f"\n🎤 <b>CA SĨ:</b> "
            f"{html.escape(format_artist_summary(draft.get('tape_artists') or []))}"
        )

    reminder_tag = ""
    if draft.get("reminder_at"):
        r_note = html.escape(draft.get("reminder_note") or "Yêu cầu nhắc việc")
        reminder_tag = f"\n⏰ <b>LỊCH NHẮC:</b> {draft['reminder_at']} (<i>{r_note}</i>)"

    text = (
        f"📦 <b>ĐƠN HÀNG MỚI (Xem trước)</b>\n"
        f"👤 <b>KHÁCH:</b> {name}\n"
        f"{classification}\n"
        f"📞 <b>SĐT:</b> <code>{phone}</code>\n"
        f"{address_label} {html.escape(address_val)}\n"
        f"📼 <b>BĂNG CASSETTE:</b> {items}{tape_tag}{artist_tag}\n"
        f"💰 <b>TỔNG TIỀN:</b> <b>{total}</b>\n"
        f"💵 <b>TIỀN COD THU:</b> <b>{cod}</b>{deposit_info}"
        f"{notes_tag}"
        f"{reminder_tag}"
        f"{photo_tag}"
        f"{warning_tag}\n"
        f"────────────────────\n"
        f"Bác bấm nút bên dưới để xác nhận (hoặc chat để sửa đơn) nhé:"
    )

    draft_id = draft["draft_id"]
    keyboard: list[list[InlineKeyboardButton]] = []

    # Optional address picker buttons for returning customer with multiple addresses
    available_addresses = draft.get("available_addresses") or []
    current_addr = (draft.get("shipping_address") or "").strip()
    if len(available_addresses) >= 2:
        for idx, addr in enumerate(available_addresses):
            short_addr = (addr[:22] + "...") if len(addr) > 22 else addr
            if addr.strip() == current_addr:
                btn_text = f"🔘 {short_addr}"
            else:
                btn_text = f"⚪ {short_addr}"
            keyboard.append(
                [InlineKeyboardButton(btn_text, callback_data=f"ord:ad:{draft_id}:{idx}")]
            )

    # Customer detail & order history button
    customer_id = draft.get("customer_id")
    if customer_id:
        total_orders = stats.get("total_orders", 0) if stats else 0
        btn_text = (
            f"👤 Chi tiết khách ({total_orders} đơn xong)"
            if total_orders > 0
            else "👤 Chi tiết khách hàng"
        )
        keyboard.append([InlineKeyboardButton(btn_text, callback_data=f"ord:cs:{draft_id}:1")])

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
    db_path = (
        getattr(settings, "sqlite_db_path", "cassette_store.db")
        if settings
        else "cassette_store.db"
    )

    stats = None
    customer_id = None
    address_auto_filled = False
    available_addresses: list[str] = []

    db_ctx = nullcontext(db) if db else get_db_connection(db_path)
    try:
        async with db_ctx as active_db:
            if active_db:
                customer = await get_customer_by_phone(active_db, extracted.customer_phone)
                if customer and customer.id:
                    customer_id = customer.id
                    stats = await get_customer_order_stats(active_db, customer.id)
                    # Auto-fill customer name if missing from extracted order
                    if not extracted.customer_name and customer.name:
                        extracted.customer_name = customer.name

                    if not extracted.shipping_address:
                        if len(customer.addresses) == 1:
                            extracted.shipping_address = customer.addresses[0]
                            address_auto_filled = True
                        elif len(customer.addresses) >= 2:
                            extracted.shipping_address = customer.addresses[-1]
                            address_auto_filled = True
                            available_addresses = list(customer.addresses)
                    elif len(customer.addresses) >= 1:
                        available_addresses = list(customer.addresses)
                        if extracted.shipping_address not in available_addresses:
                            available_addresses.append(extracted.shipping_address)
    except Exception as e:
        logger.warning("Customer history lookup failed: %s", e)

    cols = build_tape_columns(
        extracted.items_text,
        extracted.tapes,
        extracted.tape_genres,
        extracted.tape_artists,
    )

    draft_id = uuid.uuid4().hex[:8]
    draft_data = {
        "draft_id": draft_id,
        "customer_id": customer_id,
        "customer_name": extracted.customer_name,
        "customer_phone": extracted.customer_phone,
        "shipping_address": extracted.shipping_address,
        "items_text": extracted.items_text,
        "tape_quantity": cols.quantity,
        "tapes": json.loads(cols.tapes_json),
        "tape_genres": json.loads(cols.genres_json),
        "tape_artists": json.loads(cols.artists_json),
        "total_amount": extracted.total_amount,
        "cod_amount": extracted.cod_amount,
        "deposit_amount": extracted.deposit_amount,
        "payment_method": extracted.payment_method,
        "notes": extracted.notes,
        "reminder_at": getattr(extracted, "reminder_at", None),
        "reminder_note": getattr(extracted, "reminder_note", None),
        "raw_text": raw_text,
        "photo_file_ids": photo_file_ids or [],
        "address_auto_filled": address_auto_filled,
        "available_addresses": available_addresses,
        "stats": stats,
    }

    pending_orders = context.user_data.setdefault("pending_orders", {})
    pending_orders[draft_id] = draft_data
    context.user_data["active_draft_id"] = draft_id

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

    # Check for active action_state (e.g. await_tracking or admin prompts) per D-12
    action_state = context.user_data.get("action_state")
    if action_state:
        action_name = action_state.get("action", "")
        if action_name in (
            "await_whitelist_id",
            "await_model_name",
            "await_backup_time",
            "await_user_rename",
        ):
            from src.bot.handlers.admin import handle_admin_text_input

            handled = await handle_admin_text_input(update, context)
            if handled:
                return

        expires_at = action_state.get("expires_at", 0)
        if time.time() <= expires_at:
            from src.bot.handlers.order_actions import handle_action_state_text

            handled = await handle_action_state_text(update, context, action_state)
            if handled:
                return
        else:
            # Expired after 120s: clean up state and proceed to regular ingestion
            context.user_data.pop("action_state", None)

    # Check for active preview draft editing session (no timeout - ends on confirm or cancel)
    active_draft_id = context.user_data.get("active_draft_id")
    pending_orders = context.user_data.get("pending_orders", {})
    if active_draft_id and active_draft_id in pending_orders:
        if text.lower() in (
            "huỷ",
            "hủy",
            "cancel",
            "bo",
            "bỏ",
            "thôi",
            "thoát",
            "không lưu",
            "khong luu",
        ):
            pending_orders.pop(active_draft_id, None)
            context.user_data.pop("active_draft_id", None)
            await update.message.reply_text(
                text="❌ <b>ĐÃ HUỶ ĐƠN HÀNG</b>\n<i>Đơn nháp đã được huỷ bỏ.</i>",
                parse_mode="HTML",
            )
            return

        app_context = context.application.bot_data.get("app_context")
        if not app_context:
            settings = context.application.bot_data.get("settings")
            openai_client = context.application.bot_data.get("openai_client")
        else:
            settings = getattr(app_context, "settings", None)
            openai_client = getattr(app_context, "openai_client", None)

        active_model = context.application.bot_data.get("active_model_id") or (
            settings.nine_router_model_id if settings else ""
        )

        if openai_client:
            from src.services.mutation_extractor import extract_mutation_delta
            from src.services.tape_parser import build_tape_columns

            draft = pending_orders[active_draft_id]
            try:
                delta = await run_with_typing(
                    update.message.chat,
                    extract_mutation_delta(
                        client=openai_client,
                        model_id=active_model,
                        text=text,
                        current_order=draft,
                    ),
                )
            except Exception:
                logger.exception("Failed to extract mutation delta for active draft")
                delta = None

            if delta:
                if delta.new_customer_name:
                    draft["customer_name"] = delta.new_customer_name
                if delta.new_customer_phone:
                    draft["customer_phone"] = delta.new_customer_phone
                if delta.new_shipping_address:
                    draft["shipping_address"] = delta.new_shipping_address
                    draft["address_auto_filled"] = False
                if delta.new_items_text:
                    draft["items_text"] = delta.new_items_text
                    cols = build_tape_columns(
                        items_text=delta.new_items_text,
                        llm_tapes=delta.new_tapes,
                        llm_genres=delta.new_tape_genres,
                        llm_artists=delta.new_tape_artists,
                    )
                    draft["tape_quantity"] = cols.quantity
                    draft["tapes"] = json.loads(cols.tapes_json)
                    draft["tape_genres"] = json.loads(cols.genres_json)
                    draft["tape_artists"] = json.loads(cols.artists_json)
                elif delta.new_tapes:
                    cols = build_tape_columns(
                        items_text=draft.get("items_text") or "",
                        llm_tapes=delta.new_tapes,
                        llm_genres=delta.new_tape_genres or draft.get("tape_genres"),
                        llm_artists=delta.new_tape_artists or draft.get("tape_artists"),
                    )
                    draft["tape_quantity"] = cols.quantity
                    draft["tapes"] = json.loads(cols.tapes_json)
                    if cols.genres_json != "[]":
                        draft["tape_genres"] = json.loads(cols.genres_json)
                    if cols.artists_json != "[]":
                        draft["tape_artists"] = json.loads(cols.artists_json)
                if delta.new_total_amount is not None:
                    draft["total_amount"] = delta.new_total_amount
                if delta.new_cod_amount is not None:
                    draft["cod_amount"] = delta.new_cod_amount
                if delta.new_notes:
                    draft["notes"] = delta.new_notes
                if delta.clear_reminder:
                    draft["reminder_at"] = None
                    draft["reminder_note"] = None
                elif delta.new_reminder_at:
                    draft["reminder_at"] = delta.new_reminder_at
                    if delta.new_reminder_note:
                        draft["reminder_note"] = delta.new_reminder_note

            preview_text, reply_markup = render_preview_card(draft, draft.get("stats"))
            await update.message.reply_text(
                text=f"✏️ <b>ĐÃ CẬP NHẬT THEO YÊU CẦU CỦA BÁC:</b>\n\n{preview_text}",
                reply_markup=reply_markup,
                parse_mode="HTML",
            )
            return

    # 3-Way Intent Routing (CREATE vs SEARCH vs MUTATE) per MUT-01..MUT-05, D-01..D-05
    app_context = context.application.bot_data.get("app_context")
    if not app_context:
        settings = context.application.bot_data.get("settings")
        openai_client = context.application.bot_data.get("openai_client")
    else:
        settings = getattr(app_context, "settings", None)
        openai_client = getattr(app_context, "openai_client", None)

    active_model = context.application.bot_data.get("active_model_id") or (
        settings.nine_router_model_id if settings else ""
    )

    reply_msg = update.message.reply_to_message
    reply_text = (reply_msg.text or reply_msg.caption) if reply_msg else None
    reply_order_id = extract_order_id_from_reply(reply_text)

    intent = await run_with_typing(
        update.message.chat,
        classify_intent(
            text=text,
            client=openai_client,
            model_id=active_model,
            has_reply_order=bool(reply_order_id),
        ),
    )

    if intent == IntentType.MUTATE:
        from src.bot.handlers.mutation import handle_mutation_flow

        await handle_mutation_flow(update, context, text)
        return

    # Check for search_state or search_intent per D-01, D-02, D-03
    search_state = context.user_data.get("search_state")
    if search_state:
        if time.time() <= search_state.get("expires_at", 0):
            from src.bot.handlers.search import process_search_query

            await process_search_query(update, context, text)
            return
        context.user_data.pop("search_state", None)

    if intent == IntentType.SEARCH or is_search_intent(text):
        from src.bot.handlers.search import process_search_query

        await process_search_query(update, context, text)
        return

    if not openai_client or not settings:
        logger.error("OpenAI client or settings missing from application data")
        await update.message.reply_text(
            "⚠️ Hệ thống bóc tách đang bận hoặc gián đoạn kết nối. Bác vui lòng thử gửi lại tin nhắn sau giây lát nhé!"
        )
        return

    try:
        extracted = await run_with_typing(
            update.message.chat,
            extract_order_from_text(
                client=openai_client,
                model_id=active_model,
                text=text,
            ),
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


async def _extract_and_process_photo_order(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    caption: str,
    photo_file_ids: list[str],
) -> None:
    """Extract order info from photo caption and reply with preview card."""
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

    active_model = (
        context.application.bot_data.get("active_model_id") or settings.nine_router_model_id
    )
    try:
        extracted = await run_with_typing(
            update.message.chat,
            extract_order_from_text(
                client=openai_client,
                model_id=active_model,
                text=caption,
            ),
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


async def _finalize_media_group(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    media_group_id: str,
) -> None:
    """Wait out the album debounce then process the collected photos (runs in the background)."""
    try:
        await asyncio.sleep(MEDIA_GROUP_DEBOUNCE_SECONDS)

        buf = _MEDIA_GROUP_BUFFERS.get(media_group_id)
        if not buf:
            return

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
    except Exception:
        # Background task: log instead of dying silently or taking down sibling tasks.
        logger.exception("Failed to finalize media group %s", media_group_id)
    finally:
        _MEDIA_GROUP_BUFFERS.pop(media_group_id, None)
        _PROCESSED_MEDIA_GROUPS[media_group_id] = time.time()


def _spawn_finalizer(context: ContextTypes.DEFAULT_TYPE, coro) -> asyncio.Task:
    """Schedule the debounce finalizer without blocking the sequential update pump."""
    application = getattr(context, "application", None)
    if isinstance(application, Application):
        return application.create_task(coro)
    return asyncio.create_task(coro)


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

    # First photo in album: initialize buffer and schedule the debounce finalizer in the
    # background so the sequential update pump keeps draining photos 2..N immediately.
    buf = {
        "photos": [photo_file_id],
        "caption": caption,
        "caption_update": update if caption else None,
        "first_update": update,
        "task": None,
    }
    _MEDIA_GROUP_BUFFERS[media_group_id] = buf
    buf["task"] = _spawn_finalizer(context, _finalize_media_group(update, context, media_group_id))
