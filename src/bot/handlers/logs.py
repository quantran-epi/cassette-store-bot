from datetime import datetime

from telegram import Update
from telegram.error import BadRequest
from telegram.ext import ContextTypes

from src.bot.keyboards import DIVIDER, TZ_VN, build_logs_keyboard
from src.bot.logging_handler import RingBufferLogHandler
from src.bot.security import UserRole, require_role


def _get_log_handler(context: ContextTypes.DEFAULT_TYPE) -> RingBufferLogHandler | None:
    """Retrieve RingBufferLogHandler instance from bot_data."""
    return context.bot_data.get("log_handler")


def _render_logs_card(
    log_handler: RingBufferLogHandler | None, limit: int = 25, errors_only: bool = False
) -> str:
    """Format HTML logs message card."""
    if log_handler:
        formatted_logs = log_handler.format_logs_for_telegram(limit=limit, errors_only=errors_only)
    else:
        formatted_logs = "(Không tìm thấy log handler)"

    now_str = datetime.now(TZ_VN).strftime("%H:%M:%S %d/%m/%Y")
    filter_label = "lỗi " if errors_only else ""

    return (
        f"📜 <b>NHẬT KÝ HỆ THỐNG GẦN NHẤT</b>\n"
        f"{DIVIDER}\n"
        f"<pre><code>{formatted_logs}</code></pre>\n"
        f"{DIVIDER}\n"
        f"<i>Hiển thị {limit} dòng {filter_label}gần nhất • Cập nhật lúc {now_str}</i>"
    )


@require_role(UserRole.SUPER_ADMIN)
async def logs_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Display system logs in-memory viewer for Super Admin via /logs."""
    if not update.effective_message:
        return

    log_handler = _get_log_handler(context)
    card_text = _render_logs_card(log_handler, limit=25, errors_only=False)
    keyboard = build_logs_keyboard(current_limit=25, errors_only=False)

    await update.effective_message.reply_text(
        card_text,
        reply_markup=keyboard,
        parse_mode="HTML",
    )


@require_role(UserRole.SUPER_ADMIN)
async def handle_logs_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle log viewer inline callbacks (limit, filter, refresh)."""
    query = update.callback_query
    if not query or not query.data:
        return

    data = query.data
    log_handler = _get_log_handler(context)

    limit = 25
    errors_only = False

    if data.startswith("adm:log:view:"):
        parts = data.split(":")
        limit = int(parts[3]) if len(parts) > 3 else 25
        errors_only = (parts[4] == "errors") if len(parts) > 4 else False
        await query.answer()

    elif data == "adm:log:refresh":
        await query.answer("Đã làm mới logs")

    card_text = _render_logs_card(log_handler, limit=limit, errors_only=errors_only)
    keyboard = build_logs_keyboard(current_limit=limit, errors_only=errors_only)

    try:
        await query.edit_message_text(card_text, reply_markup=keyboard, parse_mode="HTML")
    except BadRequest as e:
        if "Message is not modified" not in str(e):
            raise
