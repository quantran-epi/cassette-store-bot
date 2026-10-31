import asyncio
import calendar
import logging
from collections.abc import Iterable
from datetime import datetime, timedelta, timezone
from typing import Any

import aiosqlite
from openai import AsyncOpenAI
from telegram import Bot

from src.bot.keyboards import DIVIDER
from src.db.milestones import (
    get_current_period_key,
    get_milestone_metric_value,
    has_milestone_triggered,
    list_milestone_rules,
    record_milestone_trigger,
)
from src.models.milestone import MilestonePeriod, MilestoneRule, MilestoneTargetType
from src.services.notifications import broadcast_to_whitelist

logger = logging.getLogger(__name__)

# Telegram Bot API 7.2 official celebration / party popper effect ID
FIREWORKS_EFFECT_ID = "5046509860389126442"

PERIOD_LABELS: dict[MilestonePeriod, str] = {
    MilestonePeriod.WEEK: "tuần này",
    MilestonePeriod.MONTH: "tháng này",
    MilestonePeriod.YEAR: "năm nay",
    MilestonePeriod.ALL_TIME: "từ trước đến nay",
}


def format_amount_vnd(amount: int) -> str:
    """Format currency in Vietnamese standard (100.000 đ)."""
    return f"{amount:,} đ".replace(",", ".")


def compute_milestone_pace_and_deadline(
    period: MilestonePeriod,
    target_type: MilestoneTargetType,
    target_value: int,
    current_value: int,
    dt: datetime | None = None,
) -> dict[str, Any]:
    """Compute remaining target, deadline date, remaining days, and required daily pace."""
    now_vn = dt if dt is not None else datetime.now(timezone(timedelta(hours=7)))
    today = now_vn.date()
    remaining = max(0, target_value - current_value)

    if period == MilestonePeriod.ALL_TIME:
        return {
            "remaining": remaining,
            "days_left": None,
            "deadline_date": None,
            "pace": None,
        }

    if period == MilestonePeriod.WEEK:
        days_until_sunday = 6 - today.weekday()
        deadline = today + timedelta(days=days_until_sunday)
        days_left = max(1, days_until_sunday + 1)
    elif period == MilestonePeriod.MONTH:
        _, last_day = calendar.monthrange(today.year, today.month)
        deadline = today.replace(day=last_day)
        days_left = max(1, (deadline - today).days + 1)
    elif period == MilestonePeriod.YEAR:
        deadline = today.replace(month=12, day=31)
        days_left = max(1, (deadline - today).days + 1)
    else:
        return {
            "remaining": remaining,
            "days_left": None,
            "deadline_date": None,
            "pace": None,
        }

    pace = 0.0 if remaining <= 0 else (remaining / days_left)

    return {
        "remaining": remaining,
        "days_left": days_left,
        "deadline_date": deadline,
        "pace": pace,
    }


def get_default_milestone_template(
    period: MilestonePeriod,
    target_type: MilestoneTargetType,
    target_value: int,
    only_delivered: bool,
) -> str:
    """Generate default lively celebration message template."""
    period_label = PERIOD_LABELS.get(period, "giai đoạn này")
    condition_label = "thành công" if only_delivered else "được đặt"

    if target_type == MilestoneTargetType.ORDER_COUNT:
        return (
            f"🎉 <b>KỶ LỤC MỚI: {target_value:,} ĐƠN HÀNG!</b> 🎉\n"
            f"{DIVIDER}\n"
            f"📻 Tiệm Băng Cassette vừa cán mốc <b>{{current_value}} đơn {condition_label}</b> {period_label}!\n"
            "🔥 Xin chúc mừng toàn thể shop buôn may bán đắt, âm nhạc ngập tràn!"
        )
    val_str = format_amount_vnd(target_value)
    return (
        f"🎉 <b>CÁN MỐC DOANH THU: {val_str}!</b> 🎉\n"
        f"{DIVIDER}\n"
        f"📻 Tiệm Băng Cassette vừa đạt doanh thu <b>{{current_value}}</b> {period_label}!\n"
        "🔥 Xin chúc mừng mốc doanh thu tuyệt vời! Tiếp tục phát huy nhé!"
    )


async def suggest_milestone_template(
    period: MilestonePeriod,
    target_type: MilestoneTargetType,
    target_value: int,
    only_delivered: bool,
    client: AsyncOpenAI | None = None,
    model: str = "gpt-4o-mini",
) -> str:
    """Generate or suggest celebratory template, using LLM if available."""
    default_tpl = get_default_milestone_template(
        period, target_type, target_value, only_delivered
    )
    if not client:
        return default_tpl

    period_label = PERIOD_LABELS.get(period, "giai đoạn này")
    metric_label = (
        f"{target_value} đơn hàng"
        if target_type == MilestoneTargetType.ORDER_COUNT
        else format_amount_vnd(target_value)
    )
    condition_desc = "đã giao thành công" if only_delivered else "đặt hàng (trừ đơn bom)"

    prompt = (
        f"Hãy viết một thông báo chúc mừng ngắn gọn (khoảng 2-3 câu), hào hứng, ấm áp bằng tiếng Việt "
        f"dành cho tiệm bán băng cassette cổ ('Tiệm Băng Cassette').\n"
        f"Chủ đề: Shop vừa đạt mốc kỷ lục {metric_label} ({condition_desc}) trong {period_label}.\n"
        f"Yêu cầu:\n"
        f"- Bắt đầu bằng dòng tiêu đề viết hoa kèm emoji (VD: 🎉 KỶ LỤC MỚI: ... 🎉).\n"
        f"- Trong phần thân, hãy dùng chính xác token '{{current_value}}' tại vị trí con số/số tiền đạt được "
        f"để hệ thống tự thay số thực tế vào.\n"
        f"- Dùng icon âm nhạc/băng cassette/pháo hoa (📻, 📼, 🎉, 🔥).\n"
        f"- Giữ phong cách cổ điển, thân tình, tràn đầy năng lượng.\n"
        f"- Chỉ xuất ra nội dung text thuần (cho phép thẻ b, i của HTML), không kèm lời giải thích."
    )

    try:
        response = await asyncio.wait_for(
            client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": "Bạn là trợ lý nội dung cho shop băng cassette."},
                    {"role": "user", "content": prompt},
                ],
                temperature=0.7,
                max_tokens=250,
            ),
            timeout=5.0,
        )
        content = (response.choices[0].message.content or "").strip()
        if content and "{current_value}" in content:
            # Insert divider after title line if not present
            lines = content.split("\n", 1)
            if len(lines) > 1 and DIVIDER not in content:
                return f"{lines[0]}\n{DIVIDER}\n{lines[1]}"
            return content
        if content:
            # Ensure {current_value} placeholder exists
            return f"{content}\n{DIVIDER}\n📻 Con số hiện tại: <b>{{current_value}}</b>"
    except Exception as e:
        logger.warning("LLM template suggestion failed, falling back to default: %s", e)

    return default_tpl


def format_milestone_broadcast_message(
    rule: MilestoneRule, current_value: int
) -> str:
    """Fill template variables with actual formatted numbers."""
    if rule.target_type == MilestoneTargetType.REVENUE:
        curr_str = format_amount_vnd(current_value)
        target_str = format_amount_vnd(rule.target_value)
    else:
        curr_str = f"{current_value:,}".replace(",", ".")
        target_str = f"{rule.target_value:,}".replace(",", ".")

    period_label = PERIOD_LABELS.get(rule.period, "giai đoạn này")

    # Replace placeholders safely
    text = rule.message_template
    text = text.replace("{current_value}", curr_str)
    text = text.replace("{target_value}", target_str)
    text = text.replace("{period_label}", period_label)

    return text


async def check_and_trigger_milestones(
    bot: Bot,
    db: aiosqlite.Connection,
    whitelist_ids: Iterable[int],
    trigger_point: str,  # "order_created" or "order_delivered"
    dt: datetime | None = None,
) -> list[tuple[MilestoneRule, int]]:
    """Scan active rules matching trigger point, broadcast celebration if threshold reached."""
    active_rules = await list_milestone_rules(db, active_only=True)
    if not active_rules:
        return []

    # Filter rules relevant to this trigger
    if trigger_point == "order_delivered":
        candidate_rules = [r for r in active_rules if r.only_delivered]
    else:  # "order_created"
        candidate_rules = [r for r in active_rules if not r.only_delivered]

    if not candidate_rules:
        return []

    triggered_results: list[tuple[MilestoneRule, int]] = []
    unique_whitelist = list(set(whitelist_ids))

    for rule in candidate_rules:
        if not rule.id:
            continue

        period_key = get_current_period_key(rule.period, dt=dt)
        already_triggered = await has_milestone_triggered(db, rule.id, period_key)
        if already_triggered:
            continue

        current_val = await get_milestone_metric_value(
            db, rule.period, rule.target_type, rule.only_delivered, dt=dt
        )

        if current_val >= rule.target_value:
            recorded = await record_milestone_trigger(
                db, rule.id, period_key, current_val
            )
            if not recorded:
                # Concurrent trigger already logged
                continue

            msg_text = format_milestone_broadcast_message(rule, current_val)
            effect_id = FIREWORKS_EFFECT_ID if rule.effect_enabled else None

            try:
                await broadcast_to_whitelist(
                    bot=bot,
                    whitelist_ids=unique_whitelist,
                    text=msg_text,
                    message_effect_id=effect_id,
                )
            except Exception as e:
                logger.error("Failed to broadcast milestone celebration: %s", e)

            triggered_results.append((rule, current_val))

    return triggered_results
