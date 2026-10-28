import html
import logging
import re
import time
import uuid
from contextlib import nullcontext

from telegram import Update
from telegram.ext import ContextTypes

from src.bot.handlers.base import run_with_typing
from src.bot.keyboards import (
    DIVIDER,
    STATUS_NAMES,
    build_mutation_confirm_keyboard,
    build_mutation_disambiguation_keyboard,
    build_mutation_status_keyboard,
    render_mutation_diff_card,
    render_mutation_disambiguation_card,
)
from src.db.connection import get_db_connection
from src.db.orders import (
    ACTIVE_MUTATION_STATUSES,
    find_orders_for_mutation,
    get_order_by_id,
    hydrate_customer_stats,
)
from src.models.order import Order, OrderStatus
from src.services.intent_router import extract_order_id_from_reply, parse_fast_path_status
from src.services.mutation_extractor import (
    extract_mutation_delta,
    search_target_orders_for_mutation,
)
from src.services.order_search import PHONE_PATTERN, execute_natural_language_search

logger = logging.getLogger(__name__)


def _get_active_db_context(context: ContextTypes.DEFAULT_TYPE):
    """Resolve active database connection or create context connection."""
    app_context = context.application.bot_data.get("app_context")
    db = getattr(app_context, "db", None) if app_context else context.application.bot_data.get("db")
    settings = (
        getattr(app_context, "settings", None)
        if app_context
        else context.application.bot_data.get("settings")
    )
    db_path = (
        getattr(settings, "sqlite_db_path", "cassette_store.db")
        if settings
        else "cassette_store.db"
    )
    return nullcontext(db) if db else get_db_connection(db_path)


async def handle_mutation_flow(
    update: Update, context: ContextTypes.DEFAULT_TYPE, text: str
) -> None:
    """Entry point for natural language order mutation queries (MUT-01..MUT-05, D-05..D-13)."""
    if not update.message:
        return

    db_ctx = _get_active_db_context(context)

    # 1. Reply context extraction (D-05)
    reply_msg = update.message.reply_to_message
    reply_order_id = (
        extract_order_id_from_reply(reply_msg.text or reply_msg.caption) if reply_msg else None
    )

    # 2. Fast-path status regex check in 0ms without LLM (D-06)
    fast_path = parse_fast_path_status(text)
    if fast_path:
        target_oid, new_status = fast_path
        async with db_ctx as db:
            target_order = await get_order_by_id(db, target_oid) if db else None

        if target_order:
            draft_id = uuid.uuid4().hex[:8]
            delta_dict = {"status": new_status}
            pending_mutations = context.user_data.setdefault("pending_mutations", {})
            pending_mutations[draft_id] = {
                "draft_id": draft_id,
                "order_id": target_order.id,
                "expected_updated_at": str(target_order.updated_at),
                "delta": delta_dict,
                "expires_at": time.time() + 180,
            }
            card_text = render_mutation_diff_card(target_order, delta_dict)
            kb = build_mutation_confirm_keyboard(draft_id)
            await update.message.reply_text(card_text, reply_markup=kb, parse_mode="HTML")
            return

    # Check for direct order ID in text (e.g. "sửa đơn 12", "đơn #15")
    explicit_match = re.search(r"\b(?:đơn|mã)\s*(?:#|số)?\s*(\d+)\b", text, re.IGNORECASE)
    explicit_order_id = int(explicit_match.group(1)) if explicit_match else None
    effective_order_id = reply_order_id or explicit_order_id

    app_context = context.application.bot_data.get("app_context")
    openai_client = (
        getattr(app_context, "openai_client", None)
        if app_context
        else context.application.bot_data.get("openai_client")
    )
    settings = (
        getattr(app_context, "settings", None)
        if app_context
        else context.application.bot_data.get("settings")
    )

    if not openai_client or not settings:
        await update.message.reply_text(
            "⚠️ Hệ thống bóc tách đang bận hoặc gián đoạn kết nối. Bác vui lòng thử gửi lại câu lệnh sửa đơn sau giây lát nhé!"
        )
        return

    active_model = (
        context.application.bot_data.get("active_model_id") or settings.nine_router_model_id
    )

    # 3. PHASE 1: FIND TARGET ORDER(S)
    matches: list[Order] = []
    delta_pre = None

    async with db_ctx as db:
        if not db:
            await update.message.reply_text("⚠️ Lỗi cơ sở dữ liệu. Bác vui lòng thử lại sau!")
            return

        if effective_order_id:
            ord_obj = await get_order_by_id(db, effective_order_id)
            if ord_obj:
                matches = [ord_obj]
        else:
            # 3a. Try LLM Text-to-SQL search to isolate target order accurately
            try:
                matches = await run_with_typing(
                    update.message.chat,
                    search_target_orders_for_mutation(openai_client, active_model, db, text),
                )
            except Exception:
                logger.exception("Text-to-SQL search for mutation failed")
                matches = []

            # 3b. Fallback: try keyword/delta extraction
            if not matches:
                try:
                    delta_pre = await run_with_typing(
                        update.message.chat,
                        extract_mutation_delta(openai_client, active_model, text),
                    )
                except Exception:
                    logger.exception("Fallback delta extraction failed")
                    delta_pre = None

                kw = delta_pre.target_customer_keyword if delta_pre else None
                phone_match = PHONE_PATTERN.search(text)
                phone_str = phone_match.group(0) if phone_match else None

                if kw:
                    matches = await find_orders_for_mutation(
                        db,
                        keyword=kw,
                        limit=5,
                    )
                elif phone_str:
                    matches = await find_orders_for_mutation(
                        db,
                        phone=phone_str,
                        limit=5,
                    )

                if not matches and kw and openai_client:
                    try:
                        scoped_query = f"{kw} đang xử lý hoặc chưa giao"
                        _, raw_rows = await run_with_typing(
                            update.message.chat,
                            execute_natural_language_search(
                                client=openai_client,
                                model_id=active_model,
                                db=db,
                                query=scoped_query,
                            ),
                        )
                        if raw_rows:
                            active_matches: list[Order] = []
                            terminal_matches: list[Order] = []
                            for row in raw_rows:
                                oid = row.get("id") or row.get("order_id")
                                if oid is not None:
                                    try:
                                        oid_int = int(oid)
                                    except (ValueError, TypeError):
                                        continue
                                    ord_obj = await get_order_by_id(db, oid_int)
                                    if ord_obj:
                                        if ord_obj.status.value in ACTIVE_MUTATION_STATUSES:
                                            active_matches.append(ord_obj)
                                        else:
                                            terminal_matches.append(ord_obj)
                            matches = (active_matches + terminal_matches)[:5]
                    except Exception:
                        logger.exception("Text-to-SQL fallback failed during mutation lookup")

        await hydrate_customer_stats(db, matches)

    # 4. Handle matching counts
    # 4a. 0 found: friendly empty guidance
    if not matches:
        search_kw = ""
        if delta_pre and delta_pre.target_customer_keyword:
            search_kw = delta_pre.target_customer_keyword
        kw_display = html.escape(search_kw or str(effective_order_id or "này"))
        empty_msg = (
            f"🔍 <b>KHÔNG TÌM THẤY ĐƠN HÀNG CẦN SỬA</b>\n\n"
            f"Dạ em tìm trong sổ không thấy đơn hàng nào của <b>{kw_display}</b> để sửa!\n\n"
            f"💡 <b>Bác thử lại bằng cách:</b>\n"
            f"• Nhắn kèm Số điện thoại khách: <code>sửa địa chỉ đơn 0912345678</code>\n"
            f"• Hoặc nhắn Mã đơn cụ thể: <code>sửa đơn 12</code>\n"
            f"• Hoặc bấm giữ (Reply) vào tin nhắn đơn cũ rồi nhắn nội dung cần đổi."
        )
        await update.message.reply_text(empty_msg, parse_mode="HTML")
        return

    draft_id = uuid.uuid4().hex[:8]

    # 4b. 2 to 5 found: disambiguation keyboard
    if len(matches) > 1 and not effective_order_id:
        pending_mutations = context.user_data.setdefault("pending_mutations", {})
        pending_mutations[draft_id] = {
            "draft_id": draft_id,
            "original_text": text,
            "matched_order_ids": [o.id for o in matches],
            "expires_at": time.time() + 180,
        }
        kw_for_card = delta_pre.target_customer_keyword if delta_pre else None
        dis_text = render_mutation_disambiguation_card(matches, kw_for_card)
        kb = build_mutation_disambiguation_keyboard(matches, draft_id)
        await update.message.reply_text(dis_text, reply_markup=kb, parse_mode="HTML")
        return

    # 4c. Exactly 1 order found -> PHASE 2: CONTEXT-AWARE DELTA EXTRACTION
    target_order = matches[0]
    delta = None
    try:
        delta = await run_with_typing(
            update.message.chat,
            extract_mutation_delta(
                openai_client,
                active_model,
                text,
                current_order=target_order.model_dump(),
            ),
        )
    except Exception:
        logger.exception("Failed to extract context-aware mutation delta")
        delta = None

    if not delta and delta_pre:
        delta = delta_pre

    if not delta:
        await update.message.reply_text(
            "⚠️ Hệ thống bóc tách đang bận hoặc gián đoạn kết nối. Bác vui lòng thử gửi lại câu lệnh sửa đơn sau giây lát nhé!"
        )
        return

    delta_dict = delta.model_dump(exclude_unset=True, exclude_none=True)
    delta_dict.pop("target_order_id", None)
    delta_dict.pop("target_customer_keyword", None)

    pending_mutations = context.user_data.setdefault("pending_mutations", {})
    pending_mutations[draft_id] = {
        "draft_id": draft_id,
        "order_id": target_order.id,
        "expected_updated_at": str(target_order.updated_at),
        "delta": delta_dict,
        "expires_at": time.time() + 180,
    }

    # If status disambiguation is explicitly needed (MUT-05, D-13)
    if delta.status_disambiguation_needed:
        st_label = STATUS_NAMES.get(target_order.status, str(target_order.status.value))
        status_prompt_text = (
            f"🔄 <b>CHỌN TRẠNG THÁI TIẾP THEO</b>\n"
            f"📦 <b>Đơn hàng #{target_order.id}</b> - {html.escape(target_order.customer_name)}\n"
            f"Hiện tại: <b>{st_label}</b>\n"
            f"{DIVIDER}\n"
            f"Bác muốn chuyển đơn này sang bước nào ạ:"
        )
        kb = build_mutation_status_keyboard(draft_id, target_order.id, target_order.status)
        await update.message.reply_text(status_prompt_text, reply_markup=kb, parse_mode="HTML")
        return

    diff_card_text = render_mutation_diff_card(target_order, delta_dict)
    kb = build_mutation_confirm_keyboard(draft_id)
    await update.message.reply_text(diff_card_text, reply_markup=kb, parse_mode="HTML")


async def handle_mutation_selection(
    update: Update, context: ContextTypes.DEFAULT_TYPE, draft_id: str, order_id: int
) -> None:
    """Handle order selection from disambiguation keyboard (D-10)."""
    query = update.callback_query
    if not query:
        return

    pending_mutations = context.user_data.get("pending_mutations", {})
    draft = pending_mutations.get(draft_id)
    if not draft:
        await query.edit_message_text("Thao tác hết hạn, bác vui lòng gửi lại yêu cầu nhé!")
        return

    db_ctx = _get_active_db_context(context)
    async with db_ctx as db:
        target_order = await get_order_by_id(db, order_id) if db else None

    if not target_order:
        await query.edit_message_text("⚠️ Đơn hàng không tồn tại.")
        return

    original_text = draft.get("original_text", "")
    delta_dict = draft.get("delta")

    # If delta was not yet extracted with context of the selected order:
    if (
        not delta_dict or delta_dict.get("shipping_address") or delta_dict.get("items_text")
    ) and original_text:
        app_context = context.application.bot_data.get("app_context")
        openai_client = (
            getattr(app_context, "openai_client", None)
            if app_context
            else context.application.bot_data.get("openai_client")
        )
        settings = (
            getattr(app_context, "settings", None)
            if app_context
            else context.application.bot_data.get("settings")
        )
        active_model = context.application.bot_data.get("active_model_id") or (
            settings.nine_router_model_id if settings else "gpt-4o-mini"
        )
        if openai_client:
            try:
                delta = await extract_mutation_delta(
                    openai_client,
                    active_model,
                    original_text,
                    current_order=target_order.model_dump(),
                )
                if delta:
                    delta_dict = delta.model_dump(exclude_unset=True, exclude_none=True)
                    delta_dict.pop("target_order_id", None)
                    delta_dict.pop("target_customer_keyword", None)
            except Exception:
                logger.exception("Failed to extract context-aware delta upon selection")

    if not delta_dict:
        delta_dict = draft.get("delta") or {}

    draft["order_id"] = target_order.id
    draft["delta"] = delta_dict
    draft["expected_updated_at"] = str(target_order.updated_at)
    draft["expires_at"] = time.time() + 180

    # If status disambiguation needed
    if delta_dict.get("status_disambiguation_needed"):
        st_label = STATUS_NAMES.get(target_order.status, str(target_order.status.value))
        status_prompt_text = (
            f"🔄 <b>CHỌN TRẠNG THÁI TIẾP THEO</b>\n"
            f"📦 <b>Đơn hàng #{target_order.id}</b> - {html.escape(target_order.customer_name)}\n"
            f"Hiện tại: <b>{st_label}</b>\n"
            f"{DIVIDER}\n"
            f"Bác muốn chuyển đơn này sang bước nào ạ:"
        )
        kb = build_mutation_status_keyboard(draft_id, target_order.id, target_order.status)
        await query.edit_message_text(status_prompt_text, reply_markup=kb, parse_mode="HTML")
        return

    diff_card_text = render_mutation_diff_card(target_order, delta_dict)
    kb = build_mutation_confirm_keyboard(draft_id)
    await query.edit_message_text(diff_card_text, reply_markup=kb, parse_mode="HTML")


async def handle_status_suggestion_selection(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    draft_id: str,
    order_id: int,
    status_str: str,
) -> None:
    """Handle status selection from suggestion keyboard (Screen 3 -> Screen 2)."""
    query = update.callback_query
    if not query:
        return

    pending_mutations = context.user_data.get("pending_mutations", {})
    draft = pending_mutations.get(draft_id)
    if not draft:
        await query.edit_message_text("Thao tác hết hạn, bác vui lòng gửi lại yêu cầu nhé!")
        return

    db_ctx = _get_active_db_context(context)
    async with db_ctx as db:
        target_order = await get_order_by_id(db, order_id) if db else None

    if not target_order:
        await query.edit_message_text("⚠️ Đơn hàng không tồn tại.")
        return

    new_st = OrderStatus(status_str)
    draft["delta"]["status"] = new_st
    draft["delta"].pop("status_disambiguation_needed", None)
    draft["expected_updated_at"] = str(target_order.updated_at)
    draft["expires_at"] = time.time() + 120

    diff_card_text = render_mutation_diff_card(target_order, draft["delta"])
    kb = build_mutation_confirm_keyboard(draft_id)
    await query.edit_message_text(diff_card_text, reply_markup=kb, parse_mode="HTML")
