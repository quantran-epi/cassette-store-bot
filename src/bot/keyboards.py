import html
import re
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


def extract_province_or_city(address: str) -> str:
    """Extract province or city name from the end of a comma-separated address."""
    if not address:
        return ""
    parts = [p.strip() for p in address.split(",") if p.strip()]
    if not parts:
        return ""
    last = parts[-1]
    cleaned = re.sub(r"^(TP\.?|Thành phố|Tỉnh)\s+", "", last, flags=re.IGNORECASE).strip()
    return cleaned or last

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


def build_date_picker_keyboard(
    base_date: datetime | None = None,
) -> InlineKeyboardMarkup:
    """Build fast inline date selection keyboard (Today, Yesterday, and 3 previous days)."""
    if base_date is None:
        now_vn = datetime.now(TZ_VN)
    else:
        now_vn = base_date if base_date.tzinfo else base_date.replace(tzinfo=TZ_VN)

    today = now_vn.date()
    yesterday = today - timedelta(days=1)

    keyboard: list[list[InlineKeyboardButton]] = [
        [
            InlineKeyboardButton("Hôm nay", callback_data=f"ord_dt:{today.isoformat()}"),
            InlineKeyboardButton("Hôm qua", callback_data=f"ord_dt:{yesterday.isoformat()}"),
        ]
    ]

    # Vietnamese day of week names: Monday=0 -> Thứ Hai, etc.
    weekday_names = {
        0: "Thứ Hai",
        1: "Thứ Ba",
        2: "Thứ Tư",
        3: "Thứ Năm",
        4: "Thứ Sáu",
        5: "Thứ Bảy",
        6: "Chủ Nhật",
    }

    # 3 prior days
    prior_row: list[InlineKeyboardButton] = []
    for i in range(2, 5):
        d = today - timedelta(days=i)
        wd = weekday_names[d.weekday()]
        label = f"{wd}, {d.strftime('%d/%m')}"
        prior_row.append(InlineKeyboardButton(label, callback_data=f"ord_dt:{d.isoformat()}"))

    # Split prior days into 2 rows for clean layout (2 buttons + 1 button) or 1 row each
    # For elderly users, 1 button per row or 2-column makes it easy to tap
    keyboard.append([prior_row[0]])
    keyboard.append([prior_row[1], prior_row[2]])

    return InlineKeyboardMarkup(keyboard)


def render_order_list_card(
    orders: Sequence[Order],
    date_str: str,
    page: int,
    total_pages: int,
    total_orders: int,
) -> str:
    """Render paginated order list card (5 orders/page) or empty notice."""
    if total_orders == 0:
        return (
            f"📅 <b>ĐƠN HÀNG NGÀY {date_str}</b>\n\n"
            f"Ngày này chưa có đơn hàng nào bác nhé!"
        )

    # Convert YYYY-MM-DD to DD/MM/YYYY for friendly Vietnamese display
    try:
        dt = datetime.strptime(date_str, "%Y-%m-%d")
        display_date = dt.strftime("%d/%m/%Y")
    except ValueError:
        display_date = date_str

    lines = [
        f"📅 <b>ĐƠN HÀNG NGÀY {display_date}</b>",
        f"Tổng cộng: <b>{total_orders} đơn</b> (Trang {page}/{total_pages})",
        "────────────────────",
    ]

    for order in orders:
        status_label = STATUS_NAMES.get(order.status, order.status.value)
        total_fmt = f"{order.total_amount:,} đ".replace(",", ".")
        cust_name = html.escape(order.customer_name)
        addr = html.escape(order.shipping_address) if order.shipping_address else "<i>Chưa có Đ/C</i>"
        lines.append(f"📦 <b>Đơn #{order.id}</b> - {cust_name}")
        lines.append(f"   📍 {addr}")
        lines.append(f"   💰 {total_fmt} | {status_label}")

    lines.append("────────────────────")
    lines.append("Bác chạm vào nút xem đơn bên dưới nhé:")
    return "\n".join(lines)


def build_order_list_keyboard(
    orders: Sequence[Order],
    date_str: str,
    page: int,
    total_pages: int,
) -> InlineKeyboardMarkup:
    """Build list keyboard with order detail buttons and pagination navigation."""
    buttons: list[list[InlineKeyboardButton]] = []

    if not orders:
        # Empty state per D-04
        buttons.append(
            [
                InlineKeyboardButton("📝 Nhập đơn mới", callback_data="ord_act:new"),
                InlineKeyboardButton("📋 Chọn ngày khác", callback_data="ord_act:pick_date"),
            ]
        )
        return InlineKeyboardMarkup(buttons)

    # 1 button per order for detail view
    for order in orders:
        btn_label = f"👁️ Xem đơn #{order.id} - {order.customer_name}"
        # Truncate label if too long for a single button
        if len(btn_label) > 34:
            btn_label = btn_label[:31] + "..."
        buttons.append(
            [
                InlineKeyboardButton(
                    btn_label,
                    callback_data=f"ord_v:{order.id}:{date_str}:{page}",
                )
            ]
        )

    # Pagination navigation row: [⬅️ Trước] [Trang X/Y] [Sau ➡️]
    nav_row: list[InlineKeyboardButton] = []
    if page > 1:
        nav_row.append(
            InlineKeyboardButton("⬅️ Trước", callback_data=f"ord_pg:{date_str}:{page - 1}")
        )
    nav_row.append(
        InlineKeyboardButton(f"Trang {page}/{total_pages}", callback_data="ord_noop")
    )
    if page < total_pages:
        nav_row.append(
            InlineKeyboardButton("Sau ➡️", callback_data=f"ord_pg:{date_str}:{page + 1}")
        )
    buttons.append(nav_row)

    # Pick another date bottom button per D-03
    buttons.append(
        [
            InlineKeyboardButton("📋 Chọn ngày khác", callback_data="ord_act:pick_date")
        ]
    )

    return InlineKeyboardMarkup(buttons)


def build_status_selection_keyboard(
    order_id: int,
    current_status: OrderStatus,
) -> InlineKeyboardMarkup:
    """Build 8-status selection keyboard with (Hiện tại) mark and back button."""
    buttons: list[list[InlineKeyboardButton]] = []
    all_statuses = list(OrderStatus)

    # 2 buttons per row
    for i in range(0, len(all_statuses), 2):
        row: list[InlineKeyboardButton] = []
        for st in all_statuses[i : i + 2]:
            label = STATUS_NAMES.get(st, st.value)
            if st == current_status:
                label = f"{label} (Hiện tại)"
            row.append(
                InlineKeyboardButton(
                    label,
                    callback_data=f"ord_st:{order_id}:{st.value}",
                )
            )
        buttons.append(row)

    # Back to order detail card
    buttons.append(
        [
            InlineKeyboardButton(
                "⬅️ Quay lại thẻ đơn",
                callback_data=f"ord_v_cur:{order_id}",
            )
        ]
    )
    return InlineKeyboardMarkup(buttons)

