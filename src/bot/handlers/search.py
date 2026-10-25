import asyncio
import logging
import time
import uuid
from contextlib import nullcontext
from math import ceil
from typing import Any, Coroutine

from telegram import Chat, InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.constants import ChatAction
from telegram.error import BadRequest
from telegram.ext import ContextTypes

from src.bot.keyboards import (
    build_search_empty_keyboard,
    build_search_multi_keyboard,
    build_search_prompt_keyboard,
    build_search_single_order_keyboard,
    render_search_empty_card,
    render_search_multi_card,
    render_search_single_order_card,
)
from src.db.connection import get_db_connection
from src.services.order_search import SearchResultType, run_order_search

logger = logging.getLogger(__name__)


def _get_active_db_context(context: ContextTypes.DEFAULT_TYPE):
    """Resolve active database connection or create context connection per G-04-3."""
    app_context = context.application.bot_data.get("app_context")
    db = getattr(app_context, "db", None) if app_context else context.application.bot_data.get("db")
    settings = getattr(app_context, "settings", None) if app_context else context.application.bot_data.get("settings")
    db_path = getattr(settings, "sqlite_db_path", "cassette_store.db") if settings else "cassette_store.db"
    return nullcontext(db) if db else get_db_connection(db_path)


async def run_with_typing(chat: Chat, coro: Coroutine[Any, Any, Any]) -> Any:
    """Run an async coroutine while periodically sending ChatAction.TYPING every 4s per D-11."""
    stop_event = asyncio.Event()

    async def _keep_typing() -> None:
        while not stop_event.is_set():
            try:
                await chat.send_action(ChatAction.TYPING)
            except Exception as e:
                logger.debug("Failed to send typing chat action: %s", e)
            try:
                await asyncio.wait_for(stop_event.wait(), timeout=4.0)
            except asyncio.TimeoutError:
                pass

    typing_task = asyncio.create_task(_keep_typing())
    try:
        return await coro
    finally:
        stop_event.set()
        typing_task.cancel()
        try:
            await typing_task
        except asyncio.CancelledError:
            pass


async def handle_search_menu_reply(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle '[🔍 Tra cứu đơn]' button click by setting 120s search state and sending guide per D-01, D-03."""
    context.user_data["search_state"] = {"expires_at": time.time() + 120}
    text = (
        "🔍 <b>TRA CỨU ĐƠN HÀNG TỰ NHIÊN</b>\n\n"
        "Bác muốn tìm đơn nào cứ gõ tự nhiên vào đây nhé (ví dụ: 'tìm đơn anh Tuấn hôm qua' "
        "hoặc 'hôm nay bán bao nhiêu đơn')."
    )
    keyboard = build_search_prompt_keyboard()
    if update.effective_message:
        await update.effective_message.reply_text(
            text=text,
            reply_markup=keyboard,
            parse_mode="HTML",
        )


async def handle_search_cancel_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle '[❌ Huỷ tra cứu]' inline button click per D-03."""
    query = update.callback_query
    if query:
        await query.answer()
    context.user_data.pop("search_state", None)

    msg = "Đã huỷ tìm kiếm. Bác có thể tiếp tục công việc bình thường nhé!"
    if query:
        try:
            await query.edit_message_text(text=msg)
        except BadRequest as e:
            if "Message is not modified" not in str(e):
                raise
    elif update.effective_message:
        await update.effective_message.reply_text(text=msg)


async def process_search_query(update: Update, context: ContextTypes.DEFAULT_TYPE, query_text: str) -> None:
    """Process natural language search query and reply with confirmation/result card per D-04..D-11."""
    # Clear search state upon receiving query
    context.user_data.pop("search_state", None)

    app_context = context.application.bot_data.get("app_context")
    if not app_context:
        settings = context.application.bot_data.get("settings")
        openai_client = context.application.bot_data.get("openai_client")
    else:
        settings = getattr(app_context, "settings", None)
        openai_client = getattr(app_context, "openai_client", None)

    if not openai_client or not settings:
        logger.error("OpenAI client or settings missing from application data")
        if update.effective_message:
            await update.effective_message.reply_text(
                "⚠️ Hệ thống tra cứu đang bận hoặc gián đoạn kết nối. Bác vui lòng thử lại sau giây lát nhé!"
            )
        return

    chat = update.effective_chat
    try:
        db_ctx = _get_active_db_context(context)
        async with db_ctx as active_db:
            if not active_db:
                logger.error("Database connection unavailable for process_search_query")
                if update.effective_message:
                    await update.effective_message.reply_text(
                        "⚠️ Hệ thống tra cứu đang bận hoặc gián đoạn kết nối. Bác vui lòng thử lại sau giây lát nhé!"
                    )
                return

            if chat:
                result = await run_with_typing(
                    chat,
                    run_order_search(
                        client=openai_client,
                        model_id=settings.nine_router_model_id,
                        db=active_db,
                        query=query_text,
                    ),
                )
            else:
                result = await run_order_search(
                    client=openai_client,
                    model_id=settings.nine_router_model_id,
                    db=active_db,
                    query=query_text,
                )
    except Exception:
        logger.exception("Natural language order search failed")
        if update.effective_message:
            await update.effective_message.reply_text(
                "⚠️ Hệ thống chưa hiểu được câu hỏi này hoặc bị gián đoạn. Bác thử tìm lại với từ khoá đơn giản hơn nhé!"
            )
        return

    search_id = uuid.uuid4().hex[:8]
    searches = context.user_data.setdefault("searches", {})
    searches[search_id] = {
        "query": query_text,
        "result": result,
        "page": 1,
    }

    # Handle AGGREGATE result per D-07
    if result.result_type == SearchResultType.AGGREGATE:
        summary = result.summary_text or "Dạ em đã tra cứu xong thông tin cho bác rồi ạ!"
        kb = InlineKeyboardMarkup(
            [[InlineKeyboardButton("🔍 Tìm câu khác", callback_data="sch_new")]]
        )
        if update.effective_message:
            await update.effective_message.reply_text(
                text=summary,
                reply_markup=kb,
            )
        return

    # Handle ORDERS result per D-08, D-09, D-10
    orders = result.orders
    if len(orders) == 0:
        empty_card = render_search_empty_card(query_text)
        empty_kb = build_search_empty_keyboard()
        if update.effective_message:
            await update.effective_message.reply_text(
                text=empty_card,
                reply_markup=empty_kb,
                parse_mode="HTML",
            )
    elif len(orders) == 1:
        single_card = render_search_single_order_card(orders[0], query_text)
        single_kb = build_search_single_order_keyboard(orders[0].id, search_id)
        if update.effective_message:
            await update.effective_message.reply_text(
                text=single_card,
                reply_markup=single_kb,
                parse_mode="HTML",
            )
    else:
        # Multiple orders: 5 orders per page
        total = len(orders)
        total_pages = max(1, ceil(total / 5))
        page_orders = orders[0:5]
        multi_card = render_search_multi_card(
            orders=page_orders,
            query=query_text,
            page=1,
            total_pages=total_pages,
            total_orders=total,
        )
        multi_kb = build_search_multi_keyboard(
            orders=page_orders,
            search_id=search_id,
            page=1,
            total_pages=total_pages,
        )
        if update.effective_message:
            await update.effective_message.reply_text(
                text=multi_card,
                reply_markup=multi_kb,
                parse_mode="HTML",
            )


async def handle_search_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle all 'sch_' prefixed callback queries per D-03, D-08, D-09, D-12, D-13, D-14."""
    query = update.callback_query
    if not query or not query.data:
        return

    await query.answer()
    data = query.data

    if data == "sch_cancel":
        await handle_search_cancel_callback(update, context)
        return

    if data == "sch_new":
        context.user_data["search_state"] = {"expires_at": time.time() + 120}
        prompt_text = (
            "🔍 <b>TRA CỨU ĐƠN HÀNG TỰ NHIÊN</b>\n\n"
            "Bác hãy gõ câu hỏi tìm kiếm mới vào ô chat bên dưới nhé!"
        )
        kb = build_search_prompt_keyboard()
        try:
            await query.edit_message_text(
                text=prompt_text,
                reply_markup=kb,
                parse_mode="HTML",
            )
        except BadRequest as e:
            if "Message is not modified" not in str(e):
                raise
        return

    if data.startswith("sch_pg:"):
        # sch_pg:{search_id}:{page}
        parts = data.split(":")
        search_id = parts[1]
        target_page = int(parts[2]) if len(parts) > 2 else 1

        searches = context.user_data.get("searches", {})
        snap = searches.get(search_id)
        if not snap:
            await query.edit_message_text("⚠️ Kết quả tìm kiếm đã hết hạn. Bác hãy thử tìm lại nhé!")
            return

        orders = snap["result"].orders
        query_text = snap["query"]
        total = len(orders)
        total_pages = max(1, ceil(total / 5))

        if target_page < 1:
            target_page = 1
        elif target_page > total_pages:
            target_page = total_pages

        snap["page"] = target_page
        start_idx = (target_page - 1) * 5
        page_orders = orders[start_idx : start_idx + 5]

        card_text = render_search_multi_card(
            orders=page_orders,
            query=query_text,
            page=target_page,
            total_pages=total_pages,
            total_orders=total,
        )
        kb = build_search_multi_keyboard(
            orders=page_orders,
            search_id=search_id,
            page=target_page,
            total_pages=total_pages,
        )
        try:
            await query.edit_message_text(
                text=card_text,
                reply_markup=kb,
                parse_mode="HTML",
            )
        except BadRequest as e:
            if "Message is not modified" not in str(e):
                raise
        return

    if data.startswith("sch_bk:"):
        # sch_bk:{search_id} -> return to search snapshot view (single or multi page) per D-13
        parts = data.split(":")
        search_id = parts[1]

        searches = context.user_data.get("searches", {})
        snap = searches.get(search_id)
        if not snap:
            await query.edit_message_text("⚠️ Kết quả tìm kiếm đã hết hạn. Bác hãy thử tìm lại nhé!")
            return

        result = snap["result"]
        query_text = snap["query"]

        if result.result_type == SearchResultType.AGGREGATE:
            summary = result.summary_text or "Dạ em đã tra cứu xong thông tin cho bác rồi ạ!"
            kb = InlineKeyboardMarkup(
                [[InlineKeyboardButton("🔍 Tìm câu khác", callback_data="sch_new")]]
            )
            await query.edit_message_text(text=summary, reply_markup=kb)
            return

        orders = result.orders
        if len(orders) == 1:
            card_text = render_search_single_order_card(orders[0], query_text)
            kb = build_search_single_order_keyboard(orders[0].id, search_id)
            await query.edit_message_text(text=card_text, reply_markup=kb, parse_mode="HTML")
            return

        # Multi-orders: restore saved page
        page = snap.get("page", 1)
        total = len(orders)
        total_pages = max(1, ceil(total / 5))
        start_idx = (page - 1) * 5
        page_orders = orders[start_idx : start_idx + 5]

        card_text = render_search_multi_card(
            orders=page_orders,
            query=query_text,
            page=page,
            total_pages=total_pages,
            total_orders=total,
        )
        kb = build_search_multi_keyboard(
            orders=page_orders,
            search_id=search_id,
            page=page,
            total_pages=total_pages,
        )
        await query.edit_message_text(text=card_text, reply_markup=kb, parse_mode="HTML")
        return

    if data.startswith("sch_v:"):
        # sch_v:{search_id}:{order_id} -> handled in Task 3 for detail card navigation
        from src.bot.keyboards import (
            build_order_detail_keyboard,
            render_order_detail_card,
        )
        from src.db.orders import get_order_by_id

        parts = data.split(":")
        search_id = parts[1]
        order_id = int(parts[2])

        db_ctx = _get_active_db_context(context)
        async with db_ctx as active_db:
            if not active_db:
                await query.edit_message_text("⚠️ Lỗi cơ sở dữ liệu. Bác vui lòng thử lại sau!")
                return

            order = await get_order_by_id(active_db, order_id)
            if not order:
                await query.edit_message_text("⚠️ Đơn hàng không tồn tại hoặc đã bị xoá.")
                return

            card_text = render_order_detail_card(order)
            detail_kb = build_order_detail_keyboard(
                order=order,
                date_str="search",
                page=1,
                back_callback_data=f"sch_bk:{search_id}",
            )
            try:
                await query.edit_message_text(
                    text=card_text,
                    reply_markup=detail_kb,
                    parse_mode="HTML",
                )
            except BadRequest as e:
                if "Message is not modified" not in str(e):
                    raise
            return
