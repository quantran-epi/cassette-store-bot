import logging
import time
from typing import Any

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.error import BadRequest
from telegram.ext import ContextTypes

from src.bot.handlers.admin import _get_active_db_context
from src.bot.handlers.base import run_with_typing
from src.bot.handlers.order_actions import parse_vnd_amount
from src.bot.keyboards import (
    DIVIDER,
    build_milestone_condition_keyboard,
    build_milestone_confirm_delete_keyboard,
    build_milestone_detail_keyboard,
    build_milestone_list_keyboard,
    build_milestone_period_keyboard,
    build_milestone_target_type_keyboard,
    build_milestone_template_choice_keyboard,
    build_milestone_value_shortcuts_keyboard,
)
from src.bot.security import UserRole, require_role
from src.db.milestones import (
    create_milestone_rule,
    delete_milestone_rule,
    get_current_period_key,
    get_milestone_metric_value,
    get_milestone_rule_by_id,
    has_milestone_triggered,
    list_milestone_rules,
    toggle_milestone_rule_active,
    update_milestone_rule,
)
from src.models.milestone import MilestonePeriod, MilestoneRule, MilestoneTargetType
from src.services.milestones import (
    compute_milestone_pace_and_deadline,
    format_amount_vnd,
    format_milestone_broadcast_message,
    get_default_milestone_template,
    suggest_milestone_template,
)

logger = logging.getLogger(__name__)

PERIOD_NAMES: dict[MilestonePeriod, str] = {
    MilestonePeriod.WEEK: "Theo Tuần",
    MilestonePeriod.MONTH: "Theo Tháng",
    MilestonePeriod.YEAR: "Theo Năm",
    MilestonePeriod.ALL_TIME: "Toàn bộ shop",
}


def render_milestone_list_card(rules: list[MilestoneRule]) -> str:
    """Render milestone rules list header and brief instructions."""
    lines = [
        "🎯 <b>CẤU HÌNH MỐC CHÚC MỪNG & PHÁO HOA</b>",
        f"{DIVIDER}",
        "Tự động gửi thông báo chúc mừng kèm pháo hoa tới Whitelist khi shop cán mốc kỷ lục.",
        "",
        f"<b>Tổng số mốc hiện có:</b> {len(rules)} mốc",
        "",
        "<i>Chú thích biểu tượng:</i>",
        "• 🟢 Đang bật | ⚪ Đang tạm dừng",
        "• ✅ Chỉ tính đơn thành công | 📦 Mọi đơn đặt (trừ bom)",
        "• 🎆 Bật hiệu ứng pháo hoa Telegram",
        f"{DIVIDER}",
        "Bấm vào mốc bên dưới để xem chi tiết hoặc chỉnh sửa:",
    ]
    return "\n".join(lines)


async def render_milestone_detail_card(
    db: Any, rule: MilestoneRule
) -> str:
    """Render single milestone rule details and current progress."""
    p_name = PERIOD_NAMES.get(rule.period, rule.period.value)
    type_name = (
        "Số lượng đơn hàng"
        if rule.target_type == MilestoneTargetType.ORDER_COUNT
        else "Doanh số tiền (VNĐ)"
    )
    val_str = (
        f"{rule.target_value:,} đơn".replace(",", ".")
        if rule.target_type == MilestoneTargetType.ORDER_COUNT
        else format_amount_vnd(rule.target_value)
    )
    cond_str = (
        "Chỉ tính đơn giao thành công (DA_GIAO)"
        if rule.only_delivered
        else "Tính mọi đơn đặt (trừ bom hàng / huỷ)"
    )
    st_str = "🟢 Đang hoạt động" if rule.is_active else "⚪ Đang tạm dừng"
    effect_str = "🎆 Bật pháo hoa" if rule.effect_enabled else "Tắt hiệu ứng"

    # Current metric value
    curr_val = await get_milestone_metric_value(
        db, rule.period, rule.target_type, rule.only_delivered
    )
    curr_str = (
        f"{curr_val:,} đơn".replace(",", ".")
        if rule.target_type == MilestoneTargetType.ORDER_COUNT
        else format_amount_vnd(curr_val)
    )

    # Trigger status for current cycle
    cycle_key = get_current_period_key(rule.period)
    already_fired = await has_milestone_triggered(db, rule.id, cycle_key) if rule.id else False
    fired_str = (
        f"✅ Đã đạt & bắn tin trong chu kỳ ({cycle_key})"
        if already_fired
        else f"⏳ Chưa kích hoạt chu kỳ này ({cycle_key})"
    )

    preview_msg = format_milestone_broadcast_message(rule, curr_val or rule.target_value)

    pct = (
        min(100, int((curr_val / rule.target_value) * 100))
        if rule.target_value > 0
        else 100
    )
    filled_blocks = pct // 10
    progress_bar = f"[{'■' * filled_blocks}{'□' * (10 - filled_blocks)}] {pct}%"

    pace_info = compute_milestone_pace_and_deadline(
        rule.period, rule.target_type, rule.target_value, curr_val
    )

    lines = [
        f"🎯 <b>CHI TIẾT MỐC #{rule.id}</b>",
        f"{DIVIDER}",
        f"• <b>Chu kỳ:</b> {p_name}",
        f"• <b>Chỉ tiêu:</b> {type_name} ➔ <b>{val_str}</b>",
        f"• <b>Điều kiện:</b> {cond_str}",
        f"• <b>Trạng thái:</b> {st_str}",
        f"• <b>Hiệu ứng:</b> {effect_str}",
        f"• <b>Tiến độ:</b> {progress_bar} (<b>{curr_str}</b> / {val_str})",
    ]

    if pace_info["remaining"] > 0:
        rem_str = (
            f"{pace_info['remaining']:,} đơn".replace(",", ".")
            if rule.target_type == MilestoneTargetType.ORDER_COUNT
            else format_amount_vnd(pace_info["remaining"])
        )
        lines.append(f"• <b>Còn thiếu:</b> <b>{rem_str}</b>")

        if pace_info["days_left"] is not None and pace_info["deadline_date"] is not None:
            deadline_fmt = pace_info["deadline_date"].strftime("%d/%m/%Y")
            days_cnt = pace_info["days_left"]
            day_word = "hôm nay là ngày cuối" if days_cnt == 1 else f"còn {days_cnt} ngày"
            lines.append(f"• <b>Thời hạn:</b> {day_word} (hết ngày {deadline_fmt})")

            if rule.target_type == MilestoneTargetType.ORDER_COUNT:
                pace_val = pace_info["pace"]
                pace_fmt = f"{pace_val:.1f}".rstrip("0").rstrip(".")
                lines.append(
                    f"• <b>Tốc độ cần đạt:</b> Cần trung bình <b>~{pace_fmt} đơn/ngày</b> để kịp mốc!"
                )
            else:
                pace_val = int(pace_info["pace"])
                pace_fmt = format_amount_vnd(pace_val)
                lines.append(
                    f"• <b>Tốc độ cần đạt:</b> Cần trung bình <b>~{pace_fmt}/ngày</b> để kịp mốc!"
                )
    else:
        lines.append("• <b>Mục tiêu:</b> 🏆 <b>ĐÃ HOÀN THÀNH MỐC NÀY!</b>")

    lines.extend([
        f"• <b>Kỳ này:</b> {fired_str}",
        f"{DIVIDER}",
        "📜 <b>Nội dung thông báo (Xem trước):</b>",
        preview_msg,
    ])
    return "\n".join(lines)


@require_role(UserRole.ADMIN)
async def handle_milestone_callback(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """Callback router for adm:ms:* namespace."""
    query = update.callback_query
    if not query:
        return
    await query.answer()

    data = query.data or ""
    parts = data.split(":")
    if len(parts) < 3:
        return
    action = parts[2]

    async with _get_active_db_context(context) as db:
        if not db:
            await query.edit_message_text("❌ Không thể kết nối cơ sở dữ liệu.")
            return

        if action == "list":
            rules = list(await list_milestone_rules(db))
            card = render_milestone_list_card(rules)
            kb = build_milestone_list_keyboard(rules)
            await query.edit_message_text(card, reply_markup=kb, parse_mode="HTML")
            return

        if action == "view" and len(parts) > 3:
            rule_id = int(parts[3])
            rule = await get_milestone_rule_by_id(db, rule_id)
            if not rule:
                await query.edit_message_text("❌ Không tìm thấy mốc này.")
                return
            card = await render_milestone_detail_card(db, rule)
            kb = build_milestone_detail_keyboard(rule)
            await query.edit_message_text(card, reply_markup=kb, parse_mode="HTML")
            return

        if action == "toggle" and len(parts) > 3:
            rule_id = int(parts[3])
            await toggle_milestone_rule_active(db, rule_id)
            rule = await get_milestone_rule_by_id(db, rule_id)
            if rule:
                card = await render_milestone_detail_card(db, rule)
                kb = build_milestone_detail_keyboard(rule)
                await query.edit_message_text(card, reply_markup=kb, parse_mode="HTML")
            return

        if action == "effect" and len(parts) > 3:
            rule_id = int(parts[3])
            rule = await get_milestone_rule_by_id(db, rule_id)
            if rule:
                rule.effect_enabled = not rule.effect_enabled
                await update_milestone_rule(db, rule)
                card = await render_milestone_detail_card(db, rule)
                kb = build_milestone_detail_keyboard(rule)
                await query.edit_message_text(card, reply_markup=kb, parse_mode="HTML")
            return

        if action == "delprompt" and len(parts) > 3:
            rule_id = int(parts[3])
            kb = build_milestone_confirm_delete_keyboard(rule_id)
            await query.edit_message_text(
                f"⚠️ <b>Bạn có chắc chắn muốn xoá mốc #{rule_id}?</b>\n"
                f"{DIVIDER}\n"
                "Toàn bộ lịch sử kích hoạt của mốc này cũng sẽ bị xoá.",
                reply_markup=kb,
                parse_mode="HTML",
            )
            return

        if action == "delconfirm" and len(parts) > 3:
            rule_id = int(parts[3])
            await delete_milestone_rule(db, rule_id)
            rules = list(await list_milestone_rules(db))
            card = render_milestone_list_card(rules)
            kb = build_milestone_list_keyboard(rules)
            await query.edit_message_text(
                f"✅ Đã xoá mốc #{rule_id}.\n\n" + card,
                reply_markup=kb,
                parse_mode="HTML",
            )
            return

        if action == "edittpl" and len(parts) > 3:
            rule_id = int(parts[3])
            rule = await get_milestone_rule_by_id(db, rule_id)
            if not rule:
                return
            context.user_data["action_state"] = {
                "action": "await_milestone_edit_tpl",
                "rule_id": rule_id,
                "expires_at": time.time() + 300,
            }
            cancel_kb = InlineKeyboardMarkup(
                [[InlineKeyboardButton("❌ Huỷ sửa", callback_data=f"adm:ms:view:{rule_id}")]]
            )
            await query.edit_message_text(
                f"✏️ <b>SỬA NỘI DUNG LỜI CHÚC CHO MỐC #{rule_id}</b>\n"
                f"{DIVIDER}\n"
                f"<i>Nội dung hiện tại:</i>\n{rule.message_template}\n\n"
                "👉 <b>Mời bác gõ gửi tin nhắn nội dung mới:</b>\n"
                "(Mẹo: Dùng <code>{current_value}</code> để bot tự điền số thực tế khi đạt mốc)",
                reply_markup=cancel_kb,
                parse_mode="HTML",
            )
            return

        # ------------------- WIZARD FLOW -------------------
        if action == "add" and len(parts) > 3 and parts[3] == "period":
            context.user_data["milestone_draft"] = {}
            kb = build_milestone_period_keyboard()
            await query.edit_message_text(
                "🎯 <b>TẠO MỐC CHÚC MỪNG MỚI (Bước 1/4)</b>\n"
                f"{DIVIDER}\n"
                "Bác muốn thiết lập mốc này tính theo chu kỳ nào?",
                reply_markup=kb,
                parse_mode="HTML",
            )
            return

        if action == "wiz":
            sub = parts[3] if len(parts) > 3 else ""
            val = parts[4] if len(parts) > 4 else ""
            draft = context.user_data.setdefault("milestone_draft", {})

            if sub == "period":
                draft["period"] = MilestonePeriod(val)
                kb = build_milestone_target_type_keyboard()
                await query.edit_message_text(
                    "🎯 <b>TẠO MỐC CHÚC MỪNG MỚI (Bước 2/4)</b>\n"
                    f"{DIVIDER}\n"
                    f"• Chu kỳ: <b>{PERIOD_NAMES.get(draft['period'], val)}</b>\n\n"
                    "Bác muốn đặt chỉ tiêu theo <b>Số lượng đơn</b> hay <b>Doanh thu tiền</b>?",
                    reply_markup=kb,
                    parse_mode="HTML",
                )
                return

            if sub == "type":
                draft["target_type"] = MilestoneTargetType(val)
                kb = build_milestone_condition_keyboard()
                t_label = (
                    "Số lượng đơn"
                    if draft["target_type"] == MilestoneTargetType.ORDER_COUNT
                    else "Doanh thu tiền"
                )
                await query.edit_message_text(
                    "🎯 <b>TẠO MỐC CHÚC MỪNG MỚI (Bước 3/4)</b>\n"
                    f"{DIVIDER}\n"
                    f"• Chu kỳ: <b>{PERIOD_NAMES.get(draft.get('period'), '')}</b>\n"
                    f"• Chỉ tiêu: <b>{t_label}</b>\n\n"
                    "Bác muốn tính theo đơn nào?",
                    reply_markup=kb,
                    parse_mode="HTML",
                )
                return

            if sub == "cond":
                if val == "back":
                    kb = build_milestone_target_type_keyboard()
                    await query.edit_message_text(
                        "🎯 <b>TẠO MỐC CHÚC MỪNG MỚI (Bước 2/4)</b>\n"
                        f"{DIVIDER}\n"
                        "Bác muốn đặt chỉ tiêu theo <b>Số lượng đơn</b> hay <b>Doanh thu tiền</b>?",
                        reply_markup=kb,
                        parse_mode="HTML",
                    )
                    return

                draft["only_delivered"] = val == "delivered"
                t_type = draft.get("target_type", MilestoneTargetType.ORDER_COUNT)
                kb = build_milestone_value_shortcuts_keyboard(t_type)

                # Set action_state so admin can also type a number in chat
                context.user_data["action_state"] = {
                    "action": "await_milestone_val",
                    "expires_at": time.time() + 300,
                }

                type_desc = (
                    "số đơn (VD: 50, 100)"
                    if t_type == MilestoneTargetType.ORDER_COUNT
                    else "số tiền (VD: 10tr, 50.000.000)"
                )
                await query.edit_message_text(
                    "🎯 <b>TẠO MỐC CHÚC MỪNG MỚI (Bước 4/4)</b>\n"
                    f"{DIVIDER}\n"
                    f"Bác hãy chọn nhanh con số bên dưới, hoặc <b>gõ chat trực tiếp</b> {type_desc}:",
                    reply_markup=kb,
                    parse_mode="HTML",
                )
                return

            if sub == "val":
                if val == "back":
                    kb = build_milestone_condition_keyboard()
                    await query.edit_message_text(
                        "🎯 <b>TẠO MỐC CHÚC MỪNG MỚI (Bước 3/4)</b>\n"
                        f"{DIVIDER}\n"
                        "Bác muốn tính theo đơn nào?",
                        reply_markup=kb,
                        parse_mode="HTML",
                    )
                    return

                draft["target_value"] = int(val)
                context.user_data.pop("action_state", None)

                # Prepare template suggestion with typing and instant feedback
                await _show_wizard_template_choice(
                    query, context, draft, chat=update.effective_chat
                )
                return

            if sub == "ai_retry":
                await _show_wizard_template_choice(
                    query, context, draft, chat=update.effective_chat, force_ai=True
                )
                return

            if sub == "custom_tpl":
                context.user_data["action_state"] = {
                    "action": "await_milestone_tpl",
                    "expires_at": time.time() + 300,
                }
                cancel_kb = InlineKeyboardMarkup(
                    [[InlineKeyboardButton("❌ Huỷ", callback_data="adm:ms:list")]]
                )
                await query.edit_message_text(
                    "✏️ <b>TỰ SOẠN LỜI CHÚC CHO MỐC NÀY</b>\n"
                    f"{DIVIDER}\n"
                    "👉 <b>Mời bác gõ nội dung lời chúc vào chat:</b>\n"
                    "(Dùng <code>{current_value}</code> để bot tự điền số khi đạt mốc)",
                    reply_markup=cancel_kb,
                    parse_mode="HTML",
                )
                return

            if sub == "save":
                template = draft.get("template") or get_default_milestone_template(
                    draft["period"],
                    draft["target_type"],
                    draft["target_value"],
                    draft["only_delivered"],
                )
                new_rule = MilestoneRule(
                    period=draft["period"],
                    target_type=draft["target_type"],
                    target_value=draft["target_value"],
                    only_delivered=draft["only_delivered"],
                    message_template=template,
                    effect_enabled=True,
                    is_active=True,
                )
                rule_id = await create_milestone_rule(db, new_rule)
                context.user_data.pop("milestone_draft", None)
                context.user_data.pop("action_state", None)

                created_rule = await get_milestone_rule_by_id(db, rule_id)
                card = (
                    f"🎉 <b>ĐÃ TẠO THÀNH CÔNG MỐC #{rule_id}!</b>\n\n"
                    + (await render_milestone_detail_card(db, created_rule) if created_rule else "")
                )
                kb = build_milestone_detail_keyboard(created_rule) if created_rule else build_milestone_list_keyboard([])
                await query.edit_message_text(card, reply_markup=kb, parse_mode="HTML")
                return


def _resolve_llm_client_and_model(context: ContextTypes.DEFAULT_TYPE) -> tuple[Any, str]:
    """Resolve OpenAI/9router client and active model ID across bot contexts."""
    bot_data = getattr(context, "bot_data", None)
    if not isinstance(bot_data, dict) and hasattr(context, "application"):
        bot_data = getattr(context.application, "bot_data", None)
    if not isinstance(bot_data, dict):
        bot_data = {}

    client = bot_data.get("openai_client")
    if not client:
        app_context = bot_data.get("app_context")
        if app_context:
            client = getattr(app_context, "openai_client", None)

    settings = bot_data.get("settings")
    active_model = bot_data.get("active_model_id") or (
        getattr(settings, "nine_router_model_id", "gpt-4o-mini") if settings else "gpt-4o-mini"
    )
    return client, active_model


async def _show_wizard_template_choice(
    query: Any,
    context: ContextTypes.DEFAULT_TYPE,
    draft: dict,
    chat: Any = None,
    force_ai: bool = False,
) -> None:
    """Generate or retrieve template suggestion and display to admin with typing feedback."""
    if query:
        try:
            await query.edit_message_text(
                "⏳ <b>Đang soạn thảo lời chúc mừng...</b>\n<i>Vui lòng đợi giây lát...</i>",
                parse_mode="HTML",
            )
        except Exception:
            pass

    period = draft.get("period", MilestonePeriod.WEEK)
    t_type = draft.get("target_type", MilestoneTargetType.ORDER_COUNT)
    t_val = draft.get("target_value", 50)
    only_del = draft.get("only_delivered", False)

    retry_count = draft.get("retry_count", 0)
    if force_ai:
        retry_count += 1
        draft["retry_count"] = retry_count

    client, model = _resolve_llm_client_and_model(context)

    coro = suggest_milestone_template(
        period=period,
        target_type=t_type,
        target_value=t_val,
        only_delivered=only_del,
        client=client,
        model=model,
        variant=retry_count,
    )
    if chat:
        tpl = await run_with_typing(chat, coro)
    else:
        tpl = await coro
    draft["template"] = tpl

    # Preview with actual value
    sample_rule = MilestoneRule(
        period=period,
        target_type=t_type,
        target_value=t_val,
        only_delivered=only_del,
        message_template=tpl,
    )
    preview = format_milestone_broadcast_message(sample_rule, t_val)

    kb = build_milestone_template_choice_keyboard()
    text = (
        "📜 <b>XÁC NHẬN LỜI CHÚC MỪNG</b>\n"
        f"{DIVIDER}\n"
        f"Bot đã soạn sẵn lời chúc cho mốc này:\n\n"
        f"{preview}\n\n"
        f"{DIVIDER}\n"
        "Bác muốn dùng luôn mẫu này hay tự chỉnh sửa?"
    )
    if query:
        try:
            await query.edit_message_text(text, reply_markup=kb, parse_mode="HTML")
            if force_ai:
                await query.answer("✨ Đã tạo mẫu lời chúc mới!", show_alert=False)
        except BadRequest as e:
            if "Message is not modified" in str(e):
                await query.answer("✨ Đã làm mới lời chúc!", show_alert=False)
            else:
                raise


async def handle_milestone_text_input(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> bool:
    """Handle text input when admin is in milestone creation or edit mode."""
    action_state = context.user_data.get("action_state")
    if not action_state or not update.message or not update.message.text:
        return False

    action = action_state.get("action")
    raw_text = update.message.text.strip()

    if action == "await_milestone_val":
        draft = context.user_data.get("milestone_draft")
        if not draft:
            context.user_data.pop("action_state", None)
            return False

        t_type = draft.get("target_type", MilestoneTargetType.ORDER_COUNT)
        if t_type == MilestoneTargetType.ORDER_COUNT:
            try:
                clean_num = int("".join(filter(str.isdigit, raw_text)))
                if clean_num <= 0:
                    raise ValueError
                val = clean_num
            except Exception:
                await update.message.reply_text("⚠️ Số đơn không hợp lệ. Vui lòng nhập số nguyên (VD: 50, 100).")
                return True
        else:
            parsed = parse_vnd_amount(raw_text)
            if not parsed or parsed <= 0:
                await update.message.reply_text("⚠️ Số tiền không hợp lệ. Vui lòng nhập rõ (VD: 10tr, 50.000.000).")
                return True
            val = parsed

        draft["target_value"] = val
        context.user_data.pop("action_state", None)

        status_msg = await update.message.reply_text(
            "⏳ <b>Đang soạn thảo lời chúc mừng...</b>\n<i>Vui lòng đợi giây lát...</i>",
            parse_mode="HTML",
        )

        # Send next step
        period = draft.get("period", MilestonePeriod.WEEK)
        only_del = draft.get("only_delivered", False)
        client, model = _resolve_llm_client_and_model(context)

        coro = suggest_milestone_template(
            period=period,
            target_type=t_type,
            target_value=val,
            only_delivered=only_del,
            client=client,
            model=model,
            variant=draft.get("retry_count", 0),
        )
        if update.effective_chat:
            tpl = await run_with_typing(update.effective_chat, coro)
        else:
            tpl = await coro
        draft["template"] = tpl

        sample_rule = MilestoneRule(
            period=period,
            target_type=t_type,
            target_value=val,
            only_delivered=only_del,
            message_template=tpl,
        )
        preview = format_milestone_broadcast_message(sample_rule, val)

        kb = build_milestone_template_choice_keyboard()
        text = (
            "📜 <b>XÁC NHẬN LỜI CHÚC MỪNG</b>\n"
            f"{DIVIDER}\n"
            f"Bot đã soạn sẵn lời chúc cho mốc này:\n\n"
            f"{preview}\n\n"
            f"{DIVIDER}\n"
            "Bác muốn dùng luôn mẫu này hay tự chỉnh sửa?"
        )
        await status_msg.edit_text(text, reply_markup=kb, parse_mode="HTML")
        return True

    if action == "await_milestone_tpl":
        draft = context.user_data.get("milestone_draft")
        if not draft:
            context.user_data.pop("action_state", None)
            return False

        draft["template"] = raw_text
        context.user_data.pop("action_state", None)

        async with _get_active_db_context(context) as db:
            if not db:
                await update.message.reply_text("❌ Không thể kết nối cơ sở dữ liệu.")
                return True
            new_rule = MilestoneRule(
                period=draft["period"],
                target_type=draft["target_type"],
                target_value=draft["target_value"],
                only_delivered=draft["only_delivered"],
                message_template=raw_text,
                effect_enabled=True,
                is_active=True,
            )
            rule_id = await create_milestone_rule(db, new_rule)
            context.user_data.pop("milestone_draft", None)

            created_rule = await get_milestone_rule_by_id(db, rule_id)
            card = (
                f"🎉 <b>ĐÃ TẠO THÀNH CÔNG MỐC #{rule_id}!</b>\n\n"
                + (await render_milestone_detail_card(db, created_rule) if created_rule else "")
            )
            kb = build_milestone_detail_keyboard(created_rule) if created_rule else build_milestone_list_keyboard([])
            await update.message.reply_text(card, reply_markup=kb, parse_mode="HTML")
            return True

    if action == "await_milestone_edit_tpl":
        rule_id = action_state.get("rule_id")
        context.user_data.pop("action_state", None)
        if not rule_id:
            return False

        async with _get_active_db_context(context) as db:
            if not db:
                await update.message.reply_text("❌ Không thể kết nối cơ sở dữ liệu.")
                return True
            rule = await get_milestone_rule_by_id(db, rule_id)
            if not rule:
                await update.message.reply_text("❌ Không tìm thấy mốc.")
                return True
            rule.message_template = raw_text
            await update_milestone_rule(db, rule)

            card = (
                f"✅ <b>Đã cập nhật lời chúc cho mốc #{rule_id}!</b>\n\n"
                + (await render_milestone_detail_card(db, rule))
            )
            kb = build_milestone_detail_keyboard(rule)
            await update.message.reply_text(card, reply_markup=kb, parse_mode="HTML")
            return True

    return False
