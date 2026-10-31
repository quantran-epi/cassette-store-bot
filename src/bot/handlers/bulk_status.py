"""Handler for bulk order status change flow (3 steps)."""

import logging
import re
import time
from math import ceil
from typing import Any

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.error import BadRequest
from telegram.ext import ContextTypes

from src.bot.handlers.search import (
    _get_active_db_context,
    _load_page_orders,
    _safe_edit,
    _total_pages,
)
from src.bot.keyboards import (
    DIVIDER,
    build_bulk_confirm_keyboard,
    build_bulk_done_keyboard,
    build_bulk_intro_keyboard,
    build_bulk_paste_prompt_keyboard,
    build_bulk_pick_keyboard,
    build_bulk_status_keyboard,
    render_bulk_confirm_card,
    render_bulk_done_card,
    render_bulk_intro_card,
    render_bulk_paste_prompt_card,
    render_bulk_pick_card,
    render_bulk_status_card,
    render_order_detail_card,
)
from src.db.orders import (
    bulk_update_order_status,
    find_orders_by_tracking_codes,
    get_order_by_id,
)
from src.db.reminders import get_reminders_by_order_id
from src.models.order import Order, OrderStatus
from src.services.order_search import SearchResult

logger = logging.getLogger(__name__)

BULK_STATE_TTL_SECONDS: float = 300.0  # 5 minutes per session
MAX_BULK_SELECT: int = 20


def _init_bulk_state(context: ContextTypes.DEFAULT_TYPE) -> dict[str, Any]:
    state: dict[str, Any] = {
        "step": 1,
        "selected": set(),  # set of int order_ids
        "cached_orders": {},  # int -> Order
        "page_order_ids": [],  # order ids on current page
        "result": None,  # SearchResult if DB-paginated
        "query_display": None,
        "missing_codes": [],
        "page": 1,
        "total_pages": 1,
        "total_orders": 0,
        "target_status": None,
        "awaiting_codes": False,
        "awaiting_query": False,
        "expires_at": time.time() + BULK_STATE_TTL_SECONDS,
    }
    context.user_data["bulk_status"] = state
    return state


def _get_bulk_state(context: ContextTypes.DEFAULT_TYPE) -> dict[str, Any] | None:
    state = context.user_data.get("bulk_status")
    if not state:
        return None
    if time.time() > state.get("expires_at", 0):
        context.user_data.pop("bulk_status", None)
        return None
    # Refresh TTL on each interaction
    state["expires_at"] = time.time() + BULK_STATE_TTL_SECONDS
    return state


async def start_bulk_status(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle menu reply '🔄 Đổi trạng thái': start flow step 1."""
    _init_bulk_state(context)
    card = render_bulk_intro_card()
    kb = build_bulk_intro_keyboard()
    if update.effective_message:
        await update.effective_message.reply_text(
            text=card,
            reply_markup=kb,
            parse_mode="HTML",
        )


async def render_and_store_bulk_picker(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    result: SearchResult,
    query_display: str,
) -> None:
    """Store natural language search result into bulk state and render picker card."""
    state = _get_bulk_state(context) or _init_bulk_state(context)
    state["step"] = 1
    state["result"] = result
    state["query_display"] = query_display
    state["page"] = 1
    total = result.total_count if isinstance(result.total_count, int) else len(result.orders)
    state["total_orders"] = total
    state["total_pages"] = _total_pages(result)

    page_orders = result.orders
    for o in page_orders:
        if o.id is not None:
            state["cached_orders"][o.id] = o
    state["page_order_ids"] = [o.id for o in page_orders if o.id is not None]

    selected: set[int] = state.get("selected", set())
    text = render_bulk_pick_card(
        orders=page_orders,
        selected_ids=selected,
        page=1,
        total_pages=state["total_pages"],
        total_orders=total,
        query_display=query_display,
    )
    kb = build_bulk_pick_keyboard(
        orders=page_orders,
        selected_ids=selected,
        page=1,
        total_pages=state["total_pages"],
    )

    if update.effective_message:
        await update.effective_message.reply_text(text=text, reply_markup=kb, parse_mode="HTML")


async def handle_bulk_codes_text(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    raw_text: str,
) -> None:
    """Parse pasted tracking codes and render picker card."""
    state = _get_bulk_state(context) or _init_bulk_state(context)
    state["awaiting_codes"] = False

    # Extract non-empty lines / tokens
    tokens = [re.sub(r"[,\s]", "", line).strip() for line in raw_text.splitlines()]
    codes = [t for t in tokens if t]
    if not codes:
        # Fallback to whitespace splitting
        codes = [t.strip() for t in raw_text.split() if t.strip()]

    if not codes:
        if update.effective_message:
            await update.effective_message.reply_text(
                "Dạ em chưa nhận diện được mã vận đơn nào. Bác kiểm tra lại nhé!",
            )
        return

    db_ctx = _get_active_db_context(context)
    async with db_ctx as active_db:
        if not active_db:
            if update.effective_message:
                await update.effective_message.reply_text("⚠️ Lỗi cơ sở dữ liệu.")
            return
        orders = await find_orders_by_tracking_codes(active_db, codes)

    found_codes_upper = {
        (o.tracking_code or "").strip().upper() for o in orders if o.tracking_code
    }
    missing = [c for c in codes if c.strip().upper() not in found_codes_upper]

    state["step"] = 1
    state["result"] = None
    state["query_display"] = f"Dán {len(codes)} mã"
    state["missing_codes"] = missing
    state["page"] = 1
    page_size = 5
    total = len(orders)
    state["total_orders"] = total
    state["total_pages"] = max(1, ceil(total / page_size))

    # Cache all found orders
    for o in orders:
        if o.id is not None:
            state["cached_orders"][o.id] = o

    # Auto-select all found orders up to MAX_BULK_SELECT
    new_selected = set(state.get("selected", set()))
    for o in orders:
        if o.id is not None and len(new_selected) < MAX_BULK_SELECT:
            new_selected.add(o.id)
    state["selected"] = new_selected

    # Store full list in state for simple manual pagination
    state["manual_order_list"] = orders
    first_page_orders = orders[:page_size]
    state["page_order_ids"] = [o.id for o in first_page_orders if o.id is not None]

    text = render_bulk_pick_card(
        orders=first_page_orders,
        selected_ids=new_selected,
        page=1,
        total_pages=state["total_pages"],
        total_orders=total,
        query_display=state["query_display"],
        missing_codes=missing,
    )
    kb = build_bulk_pick_keyboard(
        orders=first_page_orders,
        selected_ids=new_selected,
        page=1,
        total_pages=state["total_pages"],
    )

    if update.effective_message:
        await update.effective_message.reply_text(text=text, reply_markup=kb, parse_mode="HTML")


async def _resolve_selected_orders(
    context: ContextTypes.DEFAULT_TYPE,
    state: dict[str, Any],
) -> list[Order]:
    """Retrieve full Order objects for all selected IDs, fetching missing from DB."""
    selected_ids = list(state.get("selected", set()))
    if not selected_ids:
        return []
    cached = state.get("cached_orders", {})
    resolved: list[Order] = []
    missing_ids: list[int] = []

    for oid in selected_ids:
        if oid in cached:
            resolved.append(cached[oid])
        else:
            missing_ids.append(oid)

    if missing_ids:
        db_ctx = _get_active_db_context(context)
        async with db_ctx as active_db:
            if active_db:
                for oid in missing_ids:
                    ord_obj = await get_order_by_id(active_db, oid)
                    if ord_obj:
                        cached[oid] = ord_obj
                        resolved.append(ord_obj)

    # Sort resolved by id
    resolved.sort(key=lambda o: o.id or 0)
    return resolved


async def handle_bulk_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle all bs:* callback actions."""
    query = update.callback_query
    if not query or not query.data:
        return

    data = query.data
    parts = data.split(":")
    action = parts[1] if len(parts) > 1 else ""

    # bs:close: delete detached detail view message
    if action == "close":
        await query.answer()
        try:
            await query.message.delete()
        except BadRequest:
            pass
        return

    # bs:cancel: cancel entire flow
    if action == "cancel":
        await query.answer(text="Đã huỷ thao tác")
        context.user_data.pop("bulk_status", None)
        await _safe_edit(
            query,
            "Đã huỷ đổi trạng thái hàng loạt. Bác có thể tiếp tục công việc bình thường nhé!",
        )
        return

    # Check active state for all other actions
    state = _get_bulk_state(context)
    if not state and action != "start":
        await query.answer(text="Phiên làm việc đã hết hạn!", show_alert=True)
        await _safe_edit(
            query,
            "⚠️ Phiên làm việc đã hết hạn. Bác vui lòng bấm lại menu <b>🔄 Đổi trạng thái</b> nhé!",
        )
        return

    # bs:start: re-enter intro
    if action == "start":
        await query.answer()
        state = _init_bulk_state(context)
        await _safe_edit(query, render_bulk_intro_card(), build_bulk_intro_keyboard())
        return

    # bs:search: prompt user to type natural query
    if action == "search":
        await query.answer()
        state["awaiting_query"] = True
        state["awaiting_codes"] = False
        kb = InlineKeyboardMarkup(
            [
                [
                    InlineKeyboardButton("⬅️ Quay lại", callback_data="bs:start"),
                    InlineKeyboardButton("❌ Huỷ", callback_data="bs:cancel"),
                ]
            ]
        )
        await _safe_edit(
            query,
            f"🔍 <b>TÌM ĐƠN ĐỂ ĐỔI TRẠNG THÁI</b>\n"
            f"{DIVIDER}\n"
            f"Bác gõ tên khách, số điện thoại, hoặc từ khoá vào ô chat (ví dụ: 'đơn hôm nay' hoặc 'tìm anh Tuấn').\n\n"
            f"Bot sẽ trả về danh sách có nút chọn cho bác tick!",
            kb,
        )
        return

    # bs:paste: prompt user to paste tracking codes
    if action == "paste":
        await query.answer()
        state["awaiting_codes"] = True
        state["awaiting_query"] = False
        await _safe_edit(
            query,
            render_bulk_paste_prompt_card(),
            build_bulk_paste_prompt_keyboard(),
        )
        return

    # bs:t:<order_id>: toggle selection checkbox
    if action == "t" and len(parts) >= 3:
        try:
            order_id = int(parts[2])
        except ValueError:
            await query.answer()
            return
        selected: set[int] = state.setdefault("selected", set())
        if order_id in selected:
            selected.remove(order_id)
            await query.answer(text=f"Đã bỏ chọn #{order_id}")
        else:
            if len(selected) >= MAX_BULK_SELECT:
                await query.answer(
                    text=f"Bác chỉ chọn tối đa {MAX_BULK_SELECT} đơn một lần thôi nhé!",
                    show_alert=True,
                )
                return
            selected.add(order_id)
            await query.answer(text=f"Đã chọn #{order_id}")

        # Re-render current picker page
        await _rerender_current_picker_page(query, context, state)
        return

    # bs:v:<order_id>: view order detail as detached message
    if action == "v" and len(parts) >= 3:
        await query.answer()
        try:
            order_id = int(parts[2])
        except ValueError:
            return

        db_ctx = _get_active_db_context(context)
        async with db_ctx as active_db:
            if not active_db:
                return
            order = await get_order_by_id(active_db, order_id)
            if not order:
                return
            reminders = await get_reminders_by_order_id(active_db, order_id)

        card_text = render_order_detail_card(order, reminders=reminders)
        kb = InlineKeyboardMarkup(
            [[InlineKeyboardButton("⬅️ Đóng chi tiết", callback_data="bs:close")]]
        )
        if query.message:
            await query.message.reply_text(
                text=card_text,
                reply_markup=kb,
                parse_mode="HTML",
            )
        return

    # bs:pg:<page>: paginate picker
    if action == "pg" and len(parts) >= 3:
        await query.answer()
        try:
            target_page = int(parts[2])
        except ValueError:
            return
        state["page"] = max(1, min(target_page, state.get("total_pages", 1)))
        await _rerender_current_picker_page(query, context, state)
        return

    # bs:next: proceed from step 1 to step 2 (choose target status)
    if action == "next":
        selected = state.get("selected", set())
        if not selected:
            await query.answer(
                text="Bác chưa chọn đơn nào cả! Hãy chạm vào đơn muốn đổi nhé.",
                show_alert=True,
            )
            return
        await query.answer()
        state["step"] = 2
        selected_orders = await _resolve_selected_orders(context, state)
        card_text = render_bulk_status_card(selected_orders)
        kb = build_bulk_status_keyboard()
        await _safe_edit(query, card_text, kb)
        return

    # bs:st:<STATUS>: chosen target status, proceed to step 3 (confirmation)
    if action == "st" and len(parts) >= 3:
        status_str = parts[2]
        try:
            target_st = OrderStatus(status_str)
        except ValueError:
            await query.answer(text="Trạng thái không hợp lệ!", show_alert=True)
            return
        await query.answer()
        state["target_status"] = target_st.value
        state["step"] = 3
        selected_orders = await _resolve_selected_orders(context, state)
        card_text = render_bulk_confirm_card(selected_orders, target_st)
        kb = build_bulk_confirm_keyboard()
        await _safe_edit(query, card_text, kb)
        return

    # bs:back:<step>: return to a previous step
    if action == "back" and len(parts) >= 3:
        await query.answer()
        target_step = parts[2]
        if target_step == "1":
            state["step"] = 1
            await _rerender_current_picker_page(query, context, state)
            return
        if target_step == "2":
            state["step"] = 2
            selected_orders = await _resolve_selected_orders(context, state)
            await _safe_edit(
                query,
                render_bulk_status_card(selected_orders),
                build_bulk_status_keyboard(),
            )
            return
        return

    # bs:cf: confirm bulk execution
    if action == "cf":
        target_val = state.get("target_status")
        if not target_val:
            await query.answer(text="Chưa chọn trạng thái đích!", show_alert=True)
            return
        target_status = OrderStatus(target_val)
        selected_ids = list(state.get("selected", set()))
        if not selected_ids:
            await query.answer(text="Không có đơn nào được chọn!", show_alert=True)
            return

        db_ctx = _get_active_db_context(context)
        async with db_ctx as active_db:
            if not active_db:
                await query.answer(text="Lỗi kết nối cơ sở dữ liệu!", show_alert=True)
                return

            user = query.from_user
            updated_ids = await bulk_update_order_status(
                db=active_db,
                order_ids=selected_ids,
                new_status=target_status,
                user_id=user.id if user else None,
                user_name=user.full_name if user else None,
            )

        await query.answer(
            text=f"✅ Đã đổi xong {len(updated_ids)} đơn!",
            show_alert=False,
        )

        selected_orders = await _resolve_selected_orders(context, state)
        # Filter to successfully updated ones
        done_orders = [o for o in selected_orders if o.id in set(updated_ids)]

        card_text = render_bulk_done_card(done_orders, target_status)
        kb = build_bulk_done_keyboard()
        context.user_data.pop("bulk_status", None)
        await _safe_edit(query, card_text, kb)
        return


async def _rerender_current_picker_page(
    query,
    context: ContextTypes.DEFAULT_TYPE,
    state: dict[str, Any],
) -> None:
    """Render the picker card for the current page in state."""
    page = state.get("page", 1)
    page_size = 5
    result: SearchResult | None = state.get("result")

    if result and getattr(result, "list_sql", None):
        page_orders = await _load_page_orders(context, result, page)
        if not page_orders:
            page_orders = result.orders
    elif "manual_order_list" in state:
        all_orders: list[Order] = state["manual_order_list"]
        start = (page - 1) * page_size
        page_orders = all_orders[start : start + page_size]
    else:
        cached = state.get("cached_orders", {})
        oids = state.get("page_order_ids", [])
        page_orders = [cached[oid] for oid in oids if oid in cached]

    # Cache any resolved orders
    for o in page_orders:
        if o.id is not None:
            state["cached_orders"][o.id] = o
    state["page_order_ids"] = [o.id for o in page_orders if o.id is not None]

    selected: set[int] = state.get("selected", set())
    text = render_bulk_pick_card(
        orders=page_orders,
        selected_ids=selected,
        page=page,
        total_pages=state.get("total_pages", 1),
        total_orders=state.get("total_orders", len(page_orders)),
        query_display=state.get("query_display"),
        missing_codes=state.get("missing_codes"),
    )
    kb = build_bulk_pick_keyboard(
        orders=page_orders,
        selected_ids=selected,
        page=page,
        total_pages=state.get("total_pages", 1),
    )
    await _safe_edit(query, text, kb)
