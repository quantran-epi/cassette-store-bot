import html
import logging

from telegram import Update
from telegram.ext import ContextTypes

from src.bot.handlers.admin import _get_active_db_context
from src.bot.security import UserRole, require_role
from src.services.backup import execute_backup, send_backup_document

logger = logging.getLogger(__name__)


@require_role(UserRole.SUPER_ADMIN)
async def backup_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /backup manual trigger command for Super Admin."""
    if not update.effective_message or not update.effective_user:
        return

    progress_msg = await update.effective_message.reply_text(
        "⏳ <b>Đang tạo snapshot và nén dữ liệu cơ sở dữ liệu...</b>",
        parse_mode="HTML",
    )

    try:
        async with _get_active_db_context(context) as db:
            if not db:
                await progress_msg.edit_text("❌ Không thể kết nối cơ sở dữ liệu.")
                return
            stats = await execute_backup(db)

        if stats["is_oversized"]:
            await progress_msg.edit_text(
                f"⚠️ <b>CẢNH BÁO DUNG LƯỢNG VƯỢT QUÁ 48MB</b>\n"
                f"File nén: <code>{stats['gz_size'] / (1024*1024):.2f} MB</code> (Giới hạn Telegram: 50MB)\n"
                f"Đường dẫn file trên server: <code>{stats['gz_path']}</code>",
                parse_mode="HTML",
            )
            return

        reduction = (1 - (stats["gz_size"] / max(stats["raw_size"], 1))) * 100
        caption = (
            f"💾 <b>BẢN SAO LƯU HỆ THỐNG</b>\n"
            f"────────────────────\n"
            f"⏱️ <b>Thời gian:</b> {stats['timestamp_str']} (UTC+7)\n"
            f"📦 <b>Dung lượng:</b> {stats['raw_size'] / (1024*1024):.2f} MB ➔ {stats['gz_size'] / (1024*1024):.2f} MB (Giảm {reduction:.1f}%)\n"
            f"📊 <b>Dữ liệu:</b> {stats['order_count']} đơn hàng | {stats['customer_count']} khách hàng\n"
            f"────────────────────"
        )

        success = await send_backup_document(
            bot=context.bot,
            chat_id=update.effective_user.id,
            file_path=stats["gz_path"],
            caption=caption,
        )

        if success:
            await progress_msg.edit_text("✅ Đã tạo và gửi bản sao lưu thành công!")
        else:
            await progress_msg.edit_text(
                f"❌ Lỗi gửi file qua Telegram sau 3 lần thử.\n"
                f"Bản sao lưu đã được giữ lại trên máy chủ: <code>{stats['gz_path']}</code>",
                parse_mode="HTML",
            )
    except Exception as e:
        logger.exception("Manual backup failed: %s", e)
        await progress_msg.edit_text(f"❌ Quá trình sao lưu thất bại: {html.escape(str(e))}")
