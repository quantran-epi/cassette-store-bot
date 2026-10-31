import html
import logging
import time
import uuid
from contextlib import nullcontext
from math import ceil

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.error import BadRequest
from telegram.ext import ContextTypes

from src.bot.handlers.base import run_with_typing
from src.bot.keyboards import (
    DIVIDER,
    build_search_empty_keyboard,
    build_search_multi_keyboard,
    build_search_prompt_keyboard,
    build_search_single_order_keyboard,
    render_customer_detail_card,
    render_search_empty_card,
    render_search_multi_card,
    render_search_single_order_card,
)
from src.db.connection import get_db_connection
from src.db.customers import get_customer_by_id, is_customer_search, search_customers
from src.db.orders import (
    count_orders_by_customer_id,
    get_customer_order_stats,
    get_orders_by_customer_id,
)
from src.models.customer import Customer
from src.models.mutation import IntentType
from src.models.order import Order
from src.services.order_search import (
    SearchResult,
    SearchResultType,
    fetch_customer_search_page,
    fetch_search_page,
    run_order_search,
)

logger = logging.getLogger(__name__)


def _get_active_db_context(context: ContextTypes.DEFAULT_TYPE):
    """Resolve active database connection or create context connection per G-04-3."""
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


def _summary_prefix(result: SearchResult) -> str:
    """Escape aggregate summary so it can be prepended to a HTML list card (MIXED only)."""
    if not result.summary_text:
        return ""
    return html.escape(result.summary_text).strip() + "\n\n"


def _has_db_pagination(result: SearchResult) -> bool:
    """True when the snapshot carries a validated list SQL and a known total count."""
    return isinstance(result.list_sql, str) and isinstance(result.total_count, int)


def _total_pages(result: SearchResult) -> int:
    """Page count for a paginated result, clamped to at least one page."""
    total = result.total_count if isinstance(result.total_count, int) else len(result.orders)
    page_size = (
        result.page_size if isinstance(result.page_size, int) and result.page_size > 0 else 5
    )
    return max(1, ceil(total / page_size))


def _clamp_page(result: SearchResult, page: int) -> int:
    """Keep a requested page inside the current result range."""
    return min(max(page, 1), _total_pages(result))


async def _safe_edit(query, text: str, reply_markup=None) -> None:
    """Edit a callback message, ignoring Telegram's 'message is not modified' rejection."""
    try:
        await query.edit_message_text(text=text, reply_markup=reply_markup, parse_mode="HTML")
    except BadRequest as e:
        if "Message is not modified" not in str(e):
            raise


async def _load_page_orders(
    context: ContextTypes.DEFAULT_TYPE, result: SearchResult, page: int
) -> list[Order] | None:
    """Fetch a page of orders from the DB using the stored list SQL, or None for legacy snapshots."""
    if not _has_db_pagination(result):
        return None
    db_ctx = _get_active_db_context(context)
    async with db_ctx as active_db:
        if not active_db:
            return None
        return await fetch_search_page(active_db, result.list_sql, page, result.page_size)


def _render_list_view(
    result: SearchResult,
    query_text: str,
    search_id: str,
    page: int,
    page_orders: list[Order],
) -> tuple[str, InlineKeyboardMarkup]:
    """Render empty/single/multi list card plus prefix for MIXED results."""
    total = result.total_count if isinstance(result.total_count, int) else len(result.orders)
    total_pages = _total_pages(result)
    page = min(max(page, 1), total_pages)
    prefix = _summary_prefix(result) if result.result_type == SearchResultType.MIXED else ""
    purpose = result.list_purpose if isinstance(getattr(result, "list_purpose", None), str) else None

    if total == 0:
        return (
            prefix + render_search_empty_card(query_text, purpose=purpose),
            build_search_empty_keyboard(),
        )
    if total == 1 and page_orders and page_orders[0].id is not None:
        return (
            prefix + render_search_single_order_card(page_orders[0], query_text, purpose=purpose),
            build_search_single_order_keyboard(page_orders[0].id, search_id),
        )

    return (
        prefix
        + render_search_multi_card(
            orders=page_orders,
            query=query_text,
            page=page,
            total_pages=total_pages,
            total_orders=total,
            purpose=purpose,
        ),
        build_search_multi_keyboard(
            orders=page_orders,
            search_id=search_id,
            page=page,
            total_pages=total_pages,
        ),
    )


async def handle_search_menu_reply(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle '[🔍 Tra cứu đơn]' button click by setting 300s search state and sending guide per D-01, D-03."""
    context.user_data["search_state"] = {"expires_at": time.time() + 300}
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


CUSTOMER_PAGE_SIZE = 5


def _render_customer_empty_card(query: str) -> tuple[str, InlineKeyboardMarkup]:
    """Friendly empty customer lookup card."""
    esc_query = html.escape(query.strip())
    text = (
        f"👤 <b>TÌM KHÁCH HÀNG</b>\n"
        f"<i>(Tìm theo: '{esc_query}')</i>\n\n"
        f"Dạ em tìm trong sổ khách không thấy ai như bác tả rồi!\n\n"
        f"💡 <b>Bác có thể tìm theo:</b>\n"
        f"• Tên khách: <code>tìm khách anh Tuấn</code>\n"
        f"• Số điện thoại: <code>tìm khách 0903626566</code>\n"
        f"• Địa chỉ: <code>tìm khách Hà Nội</code>"
    )
    return text, InlineKeyboardMarkup(
        [[InlineKeyboardButton("🔍 Thử tìm lại", callback_data="sch_new")]]
    )


def _render_customer_chooser(
    customers: list[Customer],
    search_id: str,
    page: int = 1,
    total_pages: int = 1,
    total_customers: int | None = None,
    prefix: str = "",
) -> tuple[str, InlineKeyboardMarkup]:
    """Compact chooser: one button per matched customer with pagination."""
    total = total_customers if total_customers is not None else len(customers)
    page_suffix = f" <i>(Trang {page}/{total_pages})</i>" if total_pages > 1 else ""
    lines = [
        "👤 <b>TÌM THẤY NHIỀU KHÁCH HÀNG</b>",
        f"Dạ em tìm thấy <b>{total} khách</b>, bác chọn đúng người nhé:{page_suffix}",
        DIVIDER,
    ]
    buttons: list[list[InlineKeyboardButton]] = []
    for c in customers:
        phone = c.phones[0] if c.phones else "Chưa có SĐT"
        addr_text = f" ({html.escape(c.addresses[0])})" if c.addresses else ""
        label = f"👤 {c.name} - {phone}"
        if len(label) > 60:
            label = label[:57] + "..."
        lines.append(f"• <b>{html.escape(c.name)}</b> - <code>{html.escape(phone)}</code>{addr_text}")
        buttons.append([InlineKeyboardButton(label, callback_data=f"cus_v:{c.id}:{search_id}")])

    if total_pages > 1:
        nav_row: list[InlineKeyboardButton] = []
        if page > 1:
            nav_row.append(
                InlineKeyboardButton(
                    "◀️ Trước",
                    callback_data=f"cus_ls_pg:{search_id}:{page - 1}",
                )
            )
        nav_row.append(
            InlineKeyboardButton(f"Trang {page}/{total_pages}", callback_data="ord_noop")
        )
        if page < total_pages:
            nav_row.append(
                InlineKeyboardButton(
                    "Sau ➡️",
                    callback_data=f"cus_ls_pg:{search_id}:{page + 1}",
                )
            )
        buttons.append(nav_row)

    buttons.append([InlineKeyboardButton("❌ Huỷ", callback_data="sch_cancel")])
    return prefix + "\n".join(lines), InlineKeyboardMarkup(buttons)


async def _render_customer_detail(
    context: ContextTypes.DEFAULT_TYPE, customer_id: int, page: int, search_id: str
) -> tuple[str, InlineKeyboardMarkup] | None:
    """Load one customer profile + stats + one history page and render the detail card."""
    db_ctx = _get_active_db_context(context)
    async with db_ctx as active_db:
        if not active_db:
            return None
        customer = await get_customer_by_id(active_db, customer_id)
        if not customer:
            return None
        stats = await get_customer_order_stats(active_db, customer_id)
        total_orders = await count_orders_by_customer_id(active_db, customer_id)
        total_pages = max(1, ceil(total_orders / CUSTOMER_PAGE_SIZE))
        page = max(1, min(page, total_pages))
        orders = await get_orders_by_customer_id(
            active_db,
            customer_id,
            limit=CUSTOMER_PAGE_SIZE,
            offset=(page - 1) * CUSTOMER_PAGE_SIZE,
        )
    return render_customer_detail_card(
        customer=customer,
        stats=stats,
        orders=orders,
        page=page,
        total_pages=total_pages,
        draft_id=None,
        nav_callback=lambda p: f"cus_pg:{customer_id}:{p}",
        back_callback=f"cus_bk:{search_id}",
    )


async def process_search_query(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    query_text: str,
    *,
    intent: IntentType | None = None,
    bulk: bool = False,
) -> None:
    """Process one centrally-routed customer or order query."""
    if intent is None:
        intent = (
            IntentType.CUSTOMER_PROFILE
            if is_customer_search(query_text)
            else IntentType.ORDER_SEARCH
        )
    # Clear search state upon receiving query
    context.user_data.pop("search_state", None)

    app_context = context.application.bot_data.get("app_context")
    if not app_context:
        settings = context.application.bot_data.get("settings")
        openai_client = context.application.bot_data.get("openai_client")
    else:
        settings = getattr(app_context, "settings", None)
        openai_client = getattr(app_context, "openai_client", None)

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

            if not openai_client or not settings:
                if intent == IntentType.CUSTOMER_PROFILE:
                    matches = await search_customers(active_db, query_text)
                    search_id = uuid.uuid4().hex[:8]
                    context.user_data.setdefault("customer_searches", {})[search_id] = {
                        "query": query_text,
                        "ids": [c.id for c in matches],
                    }
                    if len(matches) == 1:
                        rendered = await _render_customer_detail(context, matches[0].id, 1, search_id)
                        text, kb = rendered or _render_customer_empty_card(query_text)
                    elif matches:
                        text, kb = _render_customer_chooser(matches, search_id)
                    else:
                        text, kb = _render_customer_empty_card(query_text)
                    if update.effective_message:
                        await update.effective_message.reply_text(
                            text=text, reply_markup=kb, parse_mode="HTML"
                        )
                    return
                logger.error("OpenAI client or settings missing from application data")
                if update.effective_message:
                    await update.effective_message.reply_text(
                        "⚠️ Hệ thống tra cứu đang bận hoặc gián đoạn kết nối. Bác vui lòng thử lại sau giây lát nhé!"
                    )
                return

            bot_data = (
                context.application.bot_data
                if getattr(context, "application", None)
                and isinstance(getattr(context.application, "bot_data", None), dict)
                else getattr(context, "bot_data", {})
            )
            active_model = (
                bot_data.get("active_model_id") if isinstance(bot_data, dict) else None
            ) or settings.nine_router_model_id

            if chat:
                result = await run_with_typing(
                    chat,
                    run_order_search(
                        client=openai_client,
                        model_id=active_model,
                        db=active_db,
                        query=query_text,
                    ),
                )
            else:
                result = await run_order_search(
                    client=openai_client,
                    model_id=active_model,
                    db=active_db,
                    query=query_text,
                )
    except Exception:
        logger.exception("Natural language search failed")
        if intent == IntentType.CUSTOMER_PROFILE:
            try:
                db_ctx = _get_active_db_context(context)
                async with db_ctx as active_db:
                    if active_db:
                        matches = await search_customers(active_db, query_text)
                        search_id = uuid.uuid4().hex[:8]
                        context.user_data.setdefault("customer_searches", {})[search_id] = {
                            "query": query_text,
                            "ids": [c.id for c in matches],
                        }
                        if len(matches) == 1:
                            rendered = await _render_customer_detail(context, matches[0].id, 1, search_id)
                            text, kb = rendered or _render_customer_empty_card(query_text)
                        elif matches:
                            text, kb = _render_customer_chooser(matches, search_id)
                        else:
                            text, kb = _render_customer_empty_card(query_text)
                        if update.effective_message:
                            await update.effective_message.reply_text(
                                text=text, reply_markup=kb, parse_mode="HTML"
                            )
                        return
            except Exception:
                pass
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

    # Handle CUSTOMERS result
    if result.result_type == SearchResultType.CUSTOMERS:
        matches = result.customers
        total = result.total_count if isinstance(result.total_count, int) else len(matches)
        page_size = result.page_size if result.page_size > 0 else 5
        total_pages = max(1, ceil(total / page_size))
        prefix = _summary_prefix(result)
        context.user_data.setdefault("customer_searches", {})[search_id] = {
            "query": query_text,
            "ids": [c.id for c in matches],
            "result": result,
            "page": 1,
            "total_pages": total_pages,
            "total_count": total,
        }
        if total == 1 and matches:
            rendered = await _render_customer_detail(context, matches[0].id, 1, search_id)
            if rendered:
                text, kb = prefix + rendered[0], rendered[1]
            else:
                card_text, kb = _render_customer_empty_card(query_text)
                text = prefix + card_text
        elif total > 1 and matches:
            # If multiple entities matched, disambiguate before showing aggregate calculations
            disambiguation_prefix = (
                prefix
                + "⚠️ <b>CẦN LÀM RÕ THỰC THỂ:</b>\n"
                + "Dạ câu hỏi của bác có thể áp dụng cho nhiều khách hàng khác nhau.\n\n"
                if result.summary_text
                else prefix
            )
            text, kb = _render_customer_chooser(
                customers=matches,
                search_id=search_id,
                page=1,
                total_pages=total_pages,
                total_customers=total,
                prefix=disambiguation_prefix,
            )
        else:
            card_text, kb = _render_customer_empty_card(query_text)
            text = prefix + card_text
        if update.effective_message:
            await update.effective_message.reply_text(
                text=text, reply_markup=kb, parse_mode="HTML"
            )
        return

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

    # Handle ORDERS and MIXED results per D-08, D-09, D-10 with DB-backed pagination
    if bulk:
        from src.bot.handlers.bulk_status import render_and_store_bulk_picker

        await render_and_store_bulk_picker(
            update=update,
            context=context,
            result=result,
            query_display=query_text,
        )
        return

    card_text, kb = _render_list_view(
        result=result,
        query_text=query_text,
        search_id=search_id,
        page=1,
        page_orders=result.orders,
    )
    if update.effective_message:
        await update.effective_message.reply_text(
            text=card_text,
            reply_markup=kb,
            parse_mode="HTML",
        )


async def handle_customer_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle cus_v / cus_pg / cus_bk callbacks from customer search cards."""
    query = update.callback_query
    if not query or not query.data:
        return
    await query.answer()

    parts = query.data.split(":")
    action = parts[0]

    if action == "cus_v" and len(parts) >= 3:
        try:
            customer_id = int(parts[1])
        except ValueError:
            return
        search_id = parts[2]
        context.user_data["customer_search_active"] = search_id
        rendered = await _render_customer_detail(context, customer_id, 1, search_id)
        if not rendered:
            await _safe_edit(query, "⚠️ Không tìm thấy hồ sơ khách hàng này.")
            return
        await _safe_edit(query, rendered[0], rendered[1])
        return

    if action == "cus_pg" and len(parts) >= 3:
        try:
            customer_id, page = int(parts[1]), int(parts[2])
        except ValueError:
            return
        search_id = context.user_data.get("customer_search_active", "")
        rendered = await _render_customer_detail(context, customer_id, page, search_id)
        if not rendered:
            await _safe_edit(query, "⚠️ Không tìm thấy hồ sơ khách hàng này.")
            return
        await _safe_edit(query, rendered[0], rendered[1])
        return

    if action == "cus_ls_pg" and len(parts) >= 3:
        search_id = parts[1]
        try:
            target_page = int(parts[2])
        except ValueError:
            return
        snap = context.user_data.get("customer_searches", {}).get(search_id)
        if not snap:
            await _safe_edit(query, "⚠️ Kết quả tìm khách đã hết hạn. Bác hãy tìm lại nhé!")
            return
        result = snap.get("result")
        total_pages = snap.get("total_pages", 1)
        total_count = snap.get("total_count", len(snap.get("ids", [])))
        target_page = max(1, min(target_page, total_pages))
        snap["page"] = target_page

        prefix = _summary_prefix(result) if result else ""

        db_ctx = _get_active_db_context(context)
        async with db_ctx as active_db:
            if not active_db:
                await _safe_edit(query, "⚠️ Lỗi cơ sở dữ liệu. Bác vui lòng thử lại sau!")
                return
            if result and getattr(result, "list_sql", None):
                customers = await fetch_customer_search_page(
                    active_db, result.list_sql, target_page, result.page_size
                )
            else:
                ids = snap.get("ids", [])
                page_size = 5
                start = (target_page - 1) * page_size
                slice_ids = ids[start : start + page_size]
                customers = [
                    c for cid in slice_ids if (c := await get_customer_by_id(active_db, cid))
                ]
        text, kb = _render_customer_chooser(
            customers=customers,
            search_id=search_id,
            page=target_page,
            total_pages=total_pages,
            total_customers=total_count,
            prefix=prefix,
        )
        await _safe_edit(query, text, kb)
        return

    if action == "cus_bk" and len(parts) >= 2:
        search_id = parts[1]
        snap = context.user_data.get("customer_searches", {}).get(search_id)
        if not snap:
            await _safe_edit(query, "⚠️ Kết quả tìm khách đã hết hạn. Bác hãy tìm lại nhé!")
            return
        result = snap.get("result")
        page = snap.get("page", 1)
        total_pages = snap.get("total_pages", 1)
        total_count = snap.get("total_count", len(snap.get("ids", [])))
        prefix = _summary_prefix(result) if result else ""

        db_ctx = _get_active_db_context(context)
        async with db_ctx as active_db:
            if not active_db:
                await _safe_edit(query, "⚠️ Lỗi cơ sở dữ liệu. Bác vui lòng thử lại sau!")
                return
            if result and getattr(result, "list_sql", None):
                customers = await fetch_customer_search_page(
                    active_db, result.list_sql, page, result.page_size
                )
            else:
                ids = snap.get("ids", [])
                page_size = 5
                start = (page - 1) * page_size
                slice_ids = ids[start : start + page_size]
                customers = [
                    c for cid in slice_ids if (c := await get_customer_by_id(active_db, cid))
                ]
        text, kb = _render_customer_chooser(
            customers=customers,
            search_id=search_id,
            page=page,
            total_pages=total_pages,
            total_customers=total_count,
            prefix=prefix,
        )
        await _safe_edit(query, text, kb)
        return


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
        context.user_data["search_state"] = {"expires_at": time.time() + 300}
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

        result = snap["result"]
        orders = result.orders
        query_text = snap["query"]

        if _has_db_pagination(result):
            target_page = _clamp_page(result, target_page)
            if target_page == 1:
                # Page 1 is already in the snapshot; avoid a redundant DB round-trip.
                page_orders = orders
            else:
                try:
                    page_orders = await _load_page_orders(context, result, target_page)
                except Exception:
                    logger.exception("Failed to fetch search results page from DB")
                    page_orders = None
                if page_orders is None:
                    await _safe_edit(query, "⚠️ Lỗi cơ sở dữ liệu. Bác vui lòng thử lại sau!")
                    return
            snap["page"] = target_page
            card_text, kb = _render_list_view(
                result=result,
                query_text=query_text,
                search_id=search_id,
                page=target_page,
                page_orders=page_orders,
            )
        else:
            # Legacy in-memory snapshot pagination (no list_sql)
            total = len(orders)
            page_size = result.page_size if result.page_size > 0 else 5
            total_pages = max(1, ceil(total / page_size))

            if target_page < 1:
                target_page = 1
            elif target_page > total_pages:
                target_page = total_pages

            snap["page"] = target_page
            start_idx = (target_page - 1) * page_size
            page_orders = orders[start_idx : start_idx + page_size]

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
            try:
                await query.edit_message_text(text=summary, reply_markup=kb)
            except BadRequest as e:
                if "Message is not modified" not in str(e):
                    raise
            return

        # ORDERS and MIXED restore saved page (DB-backed when list_sql available)
        page = _clamp_page(result, snap.get("page", 1))
        orders = result.orders
        page_orders = orders

        if _has_db_pagination(result):
            if page > 1:
                try:
                    loaded = await _load_page_orders(context, result, page)
                except Exception:
                    logger.exception("Failed to restore search results page from DB")
                    loaded = None
                if loaded is None:
                    await _safe_edit(query, "⚠️ Lỗi cơ sở dữ liệu. Bác vui lòng thử lại sau!")
                    return
                page_orders = loaded
        else:
            page_size = result.page_size if result.page_size > 0 else 5
            start_idx = (page - 1) * page_size
            page_orders = orders[start_idx : start_idx + page_size]

        card_text, kb = _render_list_view(
            result=result,
            query_text=query_text,
            search_id=search_id,
            page=page,
            page_orders=page_orders,
        )
        try:
            await query.edit_message_text(text=card_text, reply_markup=kb, parse_mode="HTML")
        except BadRequest as e:
            if "Message is not modified" not in str(e):
                raise
        return

    if data.startswith("sch_v:"):
        # sch_v:{search_id}:{order_id} -> handled in Task 3 for detail card navigation
        from src.bot.keyboards import (
            build_order_detail_keyboard,
            render_order_detail_card,
        )
        from src.db.orders import get_order_by_id

        parts = data.split(":")
        search_id = parts[1] if len(parts) > 1 else ""
        try:
            order_id = int(parts[2])
        except (IndexError, ValueError):
            await _safe_edit(query, "⚠️ Không xác định được đơn hàng. Bác hãy tìm lại nhé!")
            return

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
            back_cb = f"sch_bk:{search_id}"
            if context.user_data is not None:
                context.user_data[f"ord_back_{order_id}"] = back_cb
            detail_kb = build_order_detail_keyboard(
                order=order,
                date_str="search",
                page=1,
                back_callback_data=back_cb,
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
