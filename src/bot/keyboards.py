import html
from collections.abc import Sequence
from datetime import datetime, timedelta, timezone

from telegram import (
    CopyTextButton,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardMarkup,
)

from src.models.order import Order, OrderStatus

# Timezone Vietnam UTC+7
TZ_VN = timezone(timedelta(hours=7))

STATUS_NAMES: dict[OrderStatus, str] = {
    OrderStatus.CHO_LAM: "⏳ Chờ làm",
    OrderStatus.DANG_LAM: "🛠️ Đang làm",
    OrderStatus.DA_DONG_GOI: "📦 Đã đóng gói",
    OrderStatus.DA_TAO_DON: "📑 Đã tạo đơn ship",
    OrderStatus.SHIPPER_DA_LAY: "🚚 Shipper đã lấy",
    OrderStatus.DA_GIAO: "✅ Đã giao thành công",
    OrderStatus.BOM_HANG: "🚫 Bom hàng",
    OrderStatus.HUY_DON: "❌ Đã huỷ đơn",
}

NEXT_STATUS_MAP: dict[OrderStatus, tuple[OrderStatus, str]] = {
    OrderStatus.CHO_LAM: (OrderStatus.DANG_LAM, "▶️ Bắt đầu làm"),
    OrderStatus.DANG_LAM: (OrderStatus.DA_DONG_GOI, "📦 Đã đóng gói xong"),
    OrderStatus.DA_DONG_GOI: (OrderStatus.DA_TAO_DON, "📑 Đã tạo đơn ship"),
    OrderStatus.DA_TAO_DON: (OrderStatus.SHIPPER_DA_LAY, "🚚 Shipper đã lấy"),
    OrderStatus.SHIPPER_DA_LAY: (OrderStatus.DA_GIAO, "✅ Đã giao thành công"),
}


def build_main_menu_reply_keyboard() -> ReplyKeyboardMarkup:
    """Build persistent 2x2 Reply Keyboard for elderly-friendly navigation."""
    keyboard = [
        [
            KeyboardButton("📦 Đơn hôm nay"),
            KeyboardButton("📋 Xem theo ngày"),
        ],
        [
            KeyboardButton("📝 Nhập đơn mới"),
            KeyboardButton("❓ Trợ giúp"),
        ],
    ]
    return ReplyKeyboardMarkup(
        keyboard,
        resize_keyboard=True,
        is_persistent=True,
    )


def render_order_detail_card(order: Order) -> str:
    """Format elderly-friendly HTML order detail card with mono copy fields."""
    status_label = STATUS_NAMES.get(order.status, order.status.value)
    total_fmt = f"{order.total_amount:,} đ".replace(",", ".")
    cod_fmt = f"{order.cod_amount:,} đ".replace(",", ".")

    tracking_str = (
        f"<code>{html.escape(order.tracking_code)}</code>"
        if order.tracking_code
        else "<i>(Chưa có)</i>"
    )
    photo_count = len(order.photo_file_ids)
    photo_str = f"{photo_count} ảnh" if photo_count > 0 else "Không có"

    created_str = (
        order.created_at.strftime("%d/%m/%Y %H:%M")
        if isinstance(order.created_at, datetime)
        else str(order.created_at or "")
    )
    created_line = f"🕒 <b>Thời gian:</b> {created_str}\n" if created_str else ""

    return (
        f"📦 <b>CHI TIẾT ĐƠN HÀNG #{order.id}</b>\n"
        f"Trạng thái: <b>{status_label}</b>\n"
        f"────────────────────\n"
        f"👤 <b>Khách:</b> {html.escape(order.customer_name)}\n"
        f"📞 <b>SĐT:</b> <code>{html.escape(order.customer_phone)}</code> <i>(chạm để copy)</i>\n"
        f"📍 <b>Địa chỉ:</b> <code>{html.escape(order.shipping_address)}</code>\n"
        f"📼 <b>Băng:</b> {html.escape(order.items_text)}\n"
        f"💰 <b>Tổng tiền:</b> {total_fmt}\n"
        f"💵 <b>Tiền COD thu:</b> {cod_fmt}\n"
        f"🚚 <b>Mã vận đơn:</b> {tracking_str}\n"
        f"📷 <b>Ảnh đính kèm:</b> {photo_str}\n"
        f"{created_line}"
        f"────────────────────"
    )


def build_order_detail_keyboard(
    order: Order, date_str: str, page: int
) -> InlineKeyboardMarkup:
    """Build multi-row inline keyboard with 1-tap CopyTextButtons and actions."""
    buttons: list[list[InlineKeyboardButton]] = []

    # 1. Natural next status suggestion row (D-06)
    if order.status in NEXT_STATUS_MAP:
        next_status, label = NEXT_STATUS_MAP[order.status]
        buttons.append(
            [
                InlineKeyboardButton(
                    label,
                    callback_data=f"ord_st:{order.id}:{next_status.value}",
                )
            ]
        )

    # 2. 1-Tap Copy buttons for Phone & Address (D-05, UI-04)
    buttons.append(
        [
            InlineKeyboardButton(
                "📋 Copy SĐT",
                copy_text=CopyTextButton(text=order.customer_phone),
            ),
            InlineKeyboardButton(
                "📍 Copy Địa chỉ",
                copy_text=CopyTextButton(text=order.shipping_address),
            ),
        ]
    )

    # 3. Tracking code row (Copy if exists, otherwise or in addition input/edit)
    track_row: list[InlineKeyboardButton] = []
    if order.tracking_code:
        track_row.append(
            InlineKeyboardButton(
                "🚚 Copy Mã vận đơn",
                copy_text=CopyTextButton(text=order.tracking_code),
            )
        )
    track_row.append(
        InlineKeyboardButton(
            "🚚 Nhập/Đổi mã" if order.tracking_code else "🚚 Nhập mã vận đơn",
            callback_data=f"ord_act:track:{order.id}",
        )
    )
    buttons.append(track_row)

    # 4. Photos row (View if has photos, always allow add)
    photo_row: list[InlineKeyboardButton] = []
    if order.photo_file_ids:
        photo_row.append(
            InlineKeyboardButton(
                f"🖼️ Xem {len(order.photo_file_ids)} ảnh",
                callback_data=f"ord_act:view_photo:{order.id}",
            )
        )
    photo_row.append(
        InlineKeyboardButton(
            "➕ Gửi thêm ảnh",
            callback_data=f"ord_act:add_photo:{order.id}",
        )
    )
    buttons.append(photo_row)

    # 5. Change status menu & Back navigation
    buttons.append(
        [
            InlineKeyboardButton(
                "🔄 Đổi trạng thái khác",
                callback_data=f"ord_st_menu:{order.id}",
            ),
            InlineKeyboardButton(
                "⬅️ Quay lại",
                callback_data=f"ord_bk:{date_str}:{page}",
            ),
        ]
    )

    return InlineKeyboardMarkup(buttons)
