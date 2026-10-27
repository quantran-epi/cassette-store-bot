import asyncio
import html
import logging
import os
import shutil
import tempfile
import time

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.error import BadRequest
from telegram.ext import ContextTypes

from src.bot.handlers.admin import _get_active_db_context
from src.bot.security import UserRole, require_role
from src.services.backup import (
    RestoreApplyError,
    RestoreValidationError,
    apply_staged_restore,
    execute_backup,
    send_backup_document,
    stage_restore_archive,
)

logger = logging.getLogger(__name__)

RESTORE_CONFIRM_TTL = 300
MAX_UPLOAD_BYTES = 20 * 1024 * 1024


def _cleanup_restore_state(context: ContextTypes.DEFAULT_TYPE) -> None:
    """Drop pending restore state and its staging directory."""
    pending = context.user_data.pop("pending_restore", None)
    if pending and pending.get("temp_dir"):
        shutil.rmtree(pending["temp_dir"], ignore_errors=True)


def _prune_stale_restore_dirs(max_age: int = 3600) -> None:
    """Remove leftover restore_* staging dirs older than max_age seconds."""
    tmp_root = tempfile.gettempdir()
    cutoff = time.time() - max_age
    try:
        entries = os.listdir(tmp_root)
    except OSError:
        return
    for name in entries:
        if not name.startswith("restore_"):
            continue
        path = os.path.join(tmp_root, name)
        try:
            if os.path.isdir(path) and os.path.getmtime(path) < cutoff:
                shutil.rmtree(path, ignore_errors=True)
        except OSError:
            continue


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


@require_role(UserRole.SUPER_ADMIN)
async def handle_backup_document(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Stage a Super Admin's uploaded .sqlite3.gz backup and ask for confirmation."""
    message = update.effective_message
    doc = getattr(message, "document", None) if message else None
    if not message or not doc:
        return

    _cleanup_restore_state(context)
    _prune_stale_restore_dirs()

    file_size = getattr(doc, "file_size", None) or 0
    if file_size > MAX_UPLOAD_BYTES:
        await message.reply_text(
            f"❌ File quá lớn ({file_size / (1024*1024):.2f} MB). "
            f"Giới hạn {MAX_UPLOAD_BYTES // (1024*1024)} MB.",
        )
        return

    temp_dir = tempfile.mkdtemp(prefix="restore_")
    gz_path = os.path.join(temp_dir, "upload.gz")
    try:
        tg_file = await doc.get_file()
        await tg_file.download_to_drive(custom_path=gz_path)
        staged = await asyncio.to_thread(stage_restore_archive, gz_path, temp_dir)
    except Exception as e:
        logger.exception("Backup restore staging failed: %s", e)
        shutil.rmtree(temp_dir, ignore_errors=True)
        detail = (
            str(e)
            if isinstance(e, RestoreValidationError)
            else "xử lý file tải lên thất bại, vui lòng thử lại"
        )
        await message.reply_text(
            f"❌ File không hợp lệ: {html.escape(detail)}",
            parse_mode="HTML",
        )
        return
    finally:
        if os.path.exists(gz_path):
            try:
                os.remove(gz_path)
            except OSError:
                pass

    context.user_data["pending_restore"] = {
        "user_id": update.effective_user.id,
        "temp_dir": temp_dir,
        "staged_path": staged["staged_path"],
        "stats": staged,
        "expires_at": time.time() + RESTORE_CONFIRM_TTL,
    }

    keyboard = InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("✅ Xác nhận khôi phục", callback_data="adm:rst:ok")],
            [InlineKeyboardButton("❌ Huỷ", callback_data="adm:rst:cancel")],
        ]
    )
    file_name = html.escape(doc.file_name or "backup")
    gz_size_mb = file_size / (1024 * 1024)
    raw_size_mb = staged["raw_size"] / (1024 * 1024)
    text = (
        f"📥 <b>XÁC NHẬN KHÔI PHỤC DỮ LIỆU</b>\n"
        f"────────────────────\n"
        f"📄 <b>File:</b> {file_name}\n"
        f"📦 <b>Dung lượng:</b> {gz_size_mb:.2f} MB (nén) ➔ {raw_size_mb:.2f} MB\n"
        f"📊 <b>Dữ liệu trong file:</b> {staged['order_count']} đơn hàng | "
        f"{staged['customer_count']} khách hàng\n"
        f"────────────────────\n"
        f"⚠️ <b>CẢNH BÁO:</b> Xác nhận sẽ thay thế toàn bộ dữ liệu hiện tại "
        f"bằng dữ liệu trong file này. Một bản snapshot an toàn sẽ được tạo trước.\n"
        f"⏳ <i>Yêu cầu hết hạn sau {RESTORE_CONFIRM_TTL // 60} phút.</i>"
    )
    await message.reply_text(text, reply_markup=keyboard, parse_mode="HTML")


@require_role(UserRole.SUPER_ADMIN)
async def handle_restore_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Confirm or cancel a staged database restore."""
    query = update.callback_query
    if not query or not query.data:
        return

    data = query.data
    pending = context.user_data.get("pending_restore")

    if not pending or time.time() > pending.get("expires_at", 0):
        _cleanup_restore_state(context)
        await query.answer()
        await query.edit_message_text(
            "⌛ Yêu cầu khôi phục đã hết hạn. Vui lòng gửi lại file backup."
        )
        return

    if data == "adm:rst:cancel":
        await query.answer()
        _cleanup_restore_state(context)
        await query.edit_message_text(
            "❌ Đã huỷ khôi phục. Dữ liệu hiện tại được giữ nguyên."
        )
        return

    if data != "adm:rst:ok":
        return

    if pending["user_id"] != update.effective_user.id:
        await query.answer(
            "⛔ Chỉ người đã gửi file mới được xác nhận!",
            show_alert=True,
        )
        return

    settings = context.bot_data.get("settings")
    db_path = getattr(settings, "sqlite_db_path", None)
    if not db_path or db_path == ":memory:":
        await query.answer()
        _cleanup_restore_state(context)
        await query.edit_message_text(
            "❌ Không xác định được đường dẫn database để khôi phục."
        )
        return

    await query.answer()
    try:
        await query.edit_message_text("⏳ Đang khôi phục dữ liệu...")
    except BadRequest as e:
        if "Message is not modified" not in str(e):
            raise

    staged_path = pending["staged_path"]
    stats = pending.get("stats", {})
    try:
        result = await asyncio.to_thread(apply_staged_restore, staged_path, db_path)
    except RestoreApplyError as e:
        _cleanup_restore_state(context)
        detail = html.escape(str(e))
        await query.edit_message_text(
            f"❌ <b>KHÔI PHỤC THẤT BẠI</b>\n{detail}",
            parse_mode="HTML",
        )
        return
    except Exception as e:
        logger.exception("Restore apply failed: %s", e)
        _cleanup_restore_state(context)
        await query.edit_message_text(
            f"❌ <b>KHÔI PHỤC THẤT BẠI:</b> {html.escape(str(e))}\n"
            f"<i>Kiểm tra log hệ thống và thư mục backups để xác minh trạng thái dữ liệu.</i>",
            parse_mode="HTML",
        )
        return

    _cleanup_restore_state(context)

    # Bring the restored schema up to date and reload in-memory caches.
    try:
        from src.bot.app import startup_sync
        from src.db.connection import get_db_connection
        from src.db.schema import init_db

        async with get_db_connection(db_path) as db:
            await init_db(db)
        await startup_sync(context.application)
    except Exception as e:
        logger.exception("Post-restore synchronization failed: %s", e)
        await query.edit_message_text(
            f"✅ Đã khôi phục dữ liệu ({stats.get('order_count', 0)} đơn | "
            f"{stats.get('customer_count', 0)} khách) nhưng đồng bộ cấu hình thất bại: "
            f"{html.escape(str(e))}\n"
            f"⚠️ <b>Bot cần khởi động lại.</b>\n"
            f"💾 Snapshot trước khôi phục: <code>{html.escape(result['safety_path'])}</code>",
            parse_mode="HTML",
        )
        return

    await query.edit_message_text(
        f"✅ <b>KHÔI PHỤC THÀNH CÔNG</b>\n"
        f"────────────────────\n"
        f"📊 <b>Dữ liệu:</b> {stats.get('order_count', 0)} đơn hàng | "
        f"{stats.get('customer_count', 0)} khách hàng\n"
        f"💾 <b>Snapshot an toàn:</b> <code>{html.escape(result['safety_path'])}</code>\n"
        f"────────────────────\n"
        f"<i>Vui lòng kiểm tra lại danh sách truy cập (whitelist) và cấu hình.</i>",
        parse_mode="HTML",
    )
