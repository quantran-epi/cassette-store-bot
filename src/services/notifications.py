import html
import logging
from collections.abc import Iterable

from telegram import Bot, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.error import TelegramError

from src.models.order import Order

logger = logging.getLogger(__name__)


def build_order_view_button(order_id: int) -> InlineKeyboardMarkup:
    """Build 1-tap view order detail button for broadcast messages."""
    return InlineKeyboardMarkup(
        [[InlineKeyboardButton("📦 Xem chi tiết đơn", callback_data=f"ord_v:{order_id}")]]
    )


async def broadcast_to_whitelist(
    bot: Bot,
    whitelist_ids: Iterable[int],
    text: str,
    reply_markup: InlineKeyboardMarkup | None = None,
    exclude_user_id: int | None = None,
    parse_mode: str = "HTML",
) -> int:
    """Broadcast a notification message to whitelisted users, excluding performer.

    Returns the count of successfully sent messages.
    """
    sent_count = 0
    unique_ids = set(whitelist_ids)
    for uid in unique_ids:
        if exclude_user_id is not None and uid == exclude_user_id:
            continue
        try:
            await bot.send_message(
                chat_id=uid,
                text=text,
                reply_markup=reply_markup,
                parse_mode=parse_mode,
            )
            sent_count += 1
        except TelegramError as e:
            logger.warning("Failed to broadcast message to user %s: %s", uid, e)
        except Exception as e:
            logger.exception("Unexpected error broadcasting to user %s: %s", uid, e)
    return sent_count


def format_maintenance_broadcast(is_enabled: bool) -> str:
    """Format maintenance mode change notification."""
    if is_enabled:
        return (
            "🚧 <b>THÔNG BÁO BẢO TRÌ HỆ THỐNG</b>\n"
            "────────────────────\n"
            "⚠️ Hệ thống tạm dừng tiếp nhận và xử lý tin nhắn để bảo trì.\n"
            "Quý khách và nhân viên vui lòng quay lại sau khi bảo trì hoàn tất."
        )
    return (
        "✅ <b>HỆ THỐNG ĐÃ HOẠT ĐỘNG TRỞ LẠI</b>\n"
        "────────────────────\n"
        "Bảo trì hệ thống đã hoàn tất. Bạn có thể tiếp tục sử dụng bot bình thường."
    )


def format_order_created_broadcast(order: Order) -> str:
    """Format notification when a new order is created."""
    total_fmt = f"{order.total_amount:,} đ".replace(",", ".")
    cod_fmt = f"{order.cod_amount:,} đ".replace(",", ".")
    notes_line = f"📝 <b>GHI CHÚ:</b> {html.escape(order.notes)}\n" if order.notes else ""
    creator = f" (bởi {html.escape(order.created_by_name)})" if order.created_by_name else ""

    return (
        f"🆕 <b>CÓ ĐƠN HÀNG MỚI TẠO</b> #{order.id}{creator}\n"
        f"────────────────────\n"
        f"👤 <b>KHÁCH:</b> {html.escape(order.customer_name)}\n"
        f"📞 <b>SĐT:</b> <code>{html.escape(order.customer_phone)}</code>\n"
        f"📍 <b>ĐỊA CHỈ:</b> <code>{html.escape(order.shipping_address)}</code>\n"
        f"📼 <b>BĂNG CASSETTE:</b> {html.escape(order.items_text)}\n"
        f"💰 <b>TỔNG TIỀN:</b> <b>{total_fmt}</b> | 💵 <b>COD:</b> <b>{cod_fmt}</b>\n"
        f"{notes_line}"
        f"────────────────────\n"
        f"🔄 <b>TRẠNG THÁI:</b> <i>⏳ Chờ làm</i>"
    )


def format_order_packed_broadcast(order: Order, operator_name: str | None = None) -> str:
    """Format notification when an order is packed (DA_DONG_GOI)."""
    operator = f" (bởi {html.escape(operator_name)})" if operator_name else ""
    return (
        f"📦 <b>ĐƠN HÀNG ĐÃ ĐÓNG GÓI</b> #{order.id}{operator}\n"
        f"────────────────────\n"
        f"👤 <b>KHÁCH:</b> {html.escape(order.customer_name)} ({html.escape(order.customer_phone)})\n"
        f"📼 <b>BĂNG CASSETTE:</b> {html.escape(order.items_text)}\n"
        f"📍 <b>ĐỊA CHỈ:</b> {html.escape(order.shipping_address)}\n"
        f"────────────────────\n"
        f"<i>Sẵn sàng tạo đơn vận chuyển / giao shipper!</i>"
    )


def format_order_shipping_label_broadcast(order: Order, operator_name: str | None = None) -> str:
    """Format notification when an order has created shipping label (DA_TAO_DON)."""
    operator = f" (bởi {html.escape(operator_name)})" if operator_name else ""
    track_str = (
        f"<code>{html.escape(order.tracking_code)}</code>"
        if order.tracking_code
        else "<i>(Chưa cập nhật mã)</i>"
    )
    return (
        f"🚚 <b>ĐƠN HÀNG ĐÃ TẠO ĐƠN VẬN CHUYỂN</b> #{order.id}{operator}\n"
        f"────────────────────\n"
        f"👤 <b>KHÁCH:</b> {html.escape(order.customer_name)} ({html.escape(order.customer_phone)})\n"
        f"🚚 <b>MÃ VẬN ĐƠN:</b> {track_str}\n"
        f"📍 <b>ĐỊA CHỈ:</b> {html.escape(order.shipping_address)}\n"
        f"────────────────────\n"
        f"<i>Chờ shipper lấy hàng!</i>"
    )


def format_reminder_broadcast(reminder_dict: dict) -> str:
    """Format notification when a reminder is due."""
    order_id = reminder_dict.get("order_id")
    cust_name = html.escape(str(reminder_dict.get("customer_name") or "Khách lẻ"))
    cust_phone = html.escape(str(reminder_dict.get("customer_phone") or ""))
    note_text = html.escape(str(reminder_dict.get("reminder_text") or ""))
    items = html.escape(str(reminder_dict.get("items_text") or ""))
    address = html.escape(str(reminder_dict.get("shipping_address") or ""))

    phone_part = f" ({cust_phone})" if cust_phone else ""
    items_line = f"📼 <b>BĂNG:</b> {items}\n" if items else ""
    addr_line = f"📍 <b>ĐỊA CHỈ:</b> {address}\n" if address else ""

    return (
        f"⏰ <b>NHẮC VIỆC ĐƠN HÀNG #{order_id}</b>\n"
        f"────────────────────\n"
        f"👤 <b>KHÁCH:</b> {cust_name}{phone_part}\n"
        f"📝 <b>NỘI DUNG NHẮC:</b> <b>{note_text}</b>\n"
        f"{items_line}"
        f"{addr_line}"
        f"────────────────────\n"
        f"<i>Bác và nhân viên lưu ý xử lý đơn đúng hẹn nhé!</i>"
    )
