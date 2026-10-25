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

from src.bot.security import UserRole
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


def to_vn_datetime(dt: datetime | None) -> datetime | None:
    """Convert naive or UTC datetime to Vietnam local timezone (UTC+7)."""
    if not dt:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(TZ_VN)

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
            KeyboardButton("🔍 Tra cứu đơn"),
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

    vn_created_at = to_vn_datetime(order.created_at) if isinstance(order.created_at, datetime) else None
    created_str = (
        vn_created_at.strftime("%d/%m/%Y %H:%M")
        if vn_created_at
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
    order: Order,
    date_str: str,
    page: int,
    back_callback_data: str | None = None,
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
    safe_phone = (order.customer_phone or "").strip()[:256] or "Chưa có SĐT"
    safe_address = (order.shipping_address or "").strip()[:256] or "Chưa có địa chỉ"
    buttons.append(
        [
            InlineKeyboardButton(
                "📋 Copy SĐT",
                copy_text=CopyTextButton(text=safe_phone),
            ),
            InlineKeyboardButton(
                "📍 Copy Địa chỉ",
                copy_text=CopyTextButton(text=safe_address),
            ),
        ]
    )

    # 3. Tracking code row (Copy if exists, otherwise or in addition input/edit)
    track_row: list[InlineKeyboardButton] = []
    if order.tracking_code:
        safe_track = (order.tracking_code or "").strip()[:256]
        if safe_track:
            track_row.append(
                InlineKeyboardButton(
                    "🚚 Copy Mã vận đơn",
                    copy_text=CopyTextButton(text=safe_track),
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
    back_cb = back_callback_data or f"ord_bk:{date_str}:{page}"
    buttons.append(
        [
            InlineKeyboardButton(
                "🔄 Đổi trạng thái khác",
                callback_data=f"ord_st_menu:{order.id}",
            ),
            InlineKeyboardButton(
                "⬅️ Quay lại",
                callback_data=back_cb,
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


def render_search_single_order_card(order: Order, query: str) -> str:
    """Format single order confirmation preview card per D-08."""
    status_label = STATUS_NAMES.get(order.status, order.status.value)
    total_fmt = f"{order.total_amount:,} đ".replace(",", ".")
    cust_name = html.escape(order.customer_name)
    phone = html.escape(order.customer_phone)
    items = html.escape(order.items_text)
    esc_query = html.escape(query.strip())

    return (
        f"🔍 <b>KẾT QUẢ TÌM KIẾM ĐƠN HÀNG</b>\n"
        f"<i>(Tìm theo: '{esc_query}')</i>\n"
        f"────────────────────\n"
        f"📦 <b>Đơn #{order.id}</b> - {cust_name}\n"
        f"📞 <b>SĐT:</b> <code>{phone}</code>\n"
        f"📼 <b>Băng:</b> {items}\n"
        f"💰 <b>Tổng tiền:</b> {total_fmt} | <b>Trạng thái:</b> {status_label}\n"
        f"────────────────────\n"
        f"Có phải bác muốn xem đơn này không?"
    )


def build_search_single_order_keyboard(
    order_id: int, search_id: str
) -> InlineKeyboardMarkup:
    """Build inline keyboard for single order confirmation per D-08, D-14."""
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    "👁️ Đúng rồi, xem chi tiết",
                    callback_data=f"sch_v:{search_id}:{order_id}",
                )
            ],
            [
                InlineKeyboardButton(
                    "🔍 Tìm câu khác",
                    callback_data="sch_new",
                )
            ],
        ]
    )


def render_search_empty_card(query: str) -> str:
    """Format friendly empty search result card per D-10."""
    esc_query = html.escape(query.strip())
    return (
        f"🔍 <b>KẾT QUẢ TÌM KIẾM</b>\n"
        f"<i>(Tìm theo: '{esc_query}')</i>\n\n"
        f"Dạ em tìm trong sổ không thấy đơn nào như bác tả rồi!\n\n"
        f"💡 <b>Mẹo tìm kiếm:</b>\n"
        f"• Bác có thể tìm theo tên khách: <code>tìm đơn anh Tuấn</code>\n"
        f"• Tìm theo tên băng/ca sĩ: <code>tìm đơn Tuấn Vũ</code>\n"
        f"• Hoặc tìm theo ngày: <code>tìm đơn hôm qua</code>"
    )


def build_search_empty_keyboard() -> InlineKeyboardMarkup:
    """Build inline keyboard for empty search result per D-10."""
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    "🔍 Thử tìm lại",
                    callback_data="sch_new",
                )
            ],
            [
                InlineKeyboardButton(
                    "📝 Nhập đơn mới",
                    callback_data="ord_act:new",
                )
            ],
        ]
    )


def render_search_multi_card(
    orders: Sequence[Order],
    query: str,
    page: int,
    total_pages: int,
    total_orders: int,
) -> str:
    """Render paginated multi-order search result preview card per D-09."""
    esc_query = html.escape(query.strip())
    lines = [
        "🔍 <b>KẾT QUẢ TÌM KIẾM ĐƠN HÀNG</b>",
        f"<i>(Tìm theo: '{esc_query}')</i>",
        f"Dạ em tìm thấy <b>{total_orders} đơn hàng</b> phù hợp (Trang {page}/{total_pages}):",
        "────────────────────",
    ]

    for order in orders:
        status_label = STATUS_NAMES.get(order.status, order.status.value)
        total_fmt = f"{order.total_amount:,} đ".replace(",", ".")
        cust_name = html.escape(order.customer_name)
        items = html.escape(order.items_text)
        lines.append(f"📦 <b>Đơn #{order.id}</b> - {cust_name}")
        lines.append(f"   📼 {items}")
        lines.append(f"   💰 {total_fmt} | {status_label}")

    lines.append("────────────────────")
    lines.append("Bác chạm vào nút xem đơn bên dưới nhé:")
    return "\n".join(lines)


def build_search_multi_keyboard(
    orders: Sequence[Order],
    search_id: str,
    page: int,
    total_pages: int,
) -> InlineKeyboardMarkup:
    """Build multi-order search list keyboard with order detail buttons and pagination per D-09."""
    buttons: list[list[InlineKeyboardButton]] = []

    for order in orders:
        btn_label = f"👁️ Xem đơn #{order.id} - {order.customer_name}"
        if len(btn_label) > 34:
            btn_label = btn_label[:31] + "..."
        buttons.append(
            [
                InlineKeyboardButton(
                    btn_label,
                    callback_data=f"sch_v:{search_id}:{order.id}",
                )
            ]
        )

    # Pagination navigation row: [◀️ Trang trước] [Trang X/Y] [Trang sau ▶️]
    if total_pages > 1:
        nav_row: list[InlineKeyboardButton] = []
        if page > 1:
            nav_row.append(
                InlineKeyboardButton(
                    "◀️ Trang trước",
                    callback_data=f"sch_pg:{search_id}:{page - 1}",
                )
            )
        nav_row.append(
            InlineKeyboardButton(f"Trang {page}/{total_pages}", callback_data="ord_noop")
        )
        if page < total_pages:
            nav_row.append(
                InlineKeyboardButton(
                    "Trang sau ▶️",
                    callback_data=f"sch_pg:{search_id}:{page + 1}",
                )
            )
        buttons.append(nav_row)

    # Bottom action: new query
    buttons.append(
        [
            InlineKeyboardButton(
                "🔍 Tìm câu khác",
                callback_data="sch_new",
            )
        ]
    )

    return InlineKeyboardMarkup(buttons)


def build_search_prompt_keyboard() -> InlineKeyboardMarkup:
    """Build inline keyboard for search mode prompt per D-03."""
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    "❌ Huỷ tra cứu",
                    callback_data="sch_cancel",
                )
            ]
        ]
    )


def build_admin_main_keyboard(
    user_role: UserRole = UserRole.ADMIN,
) -> InlineKeyboardMarkup:
    """Build 2-column admin suite navigation grid per D-03 and UI-SPEC."""
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("👥 Quản lý Whitelist", callback_data="adm:wl:list:1"),
                InlineKeyboardButton("🤖 Đổi Model LLM", callback_data="adm:mdl:menu"),
            ],
            [
                InlineKeyboardButton("📜 Xem Logs", callback_data="adm:log:view:25:all"),
                InlineKeyboardButton("💾 Sao lưu DB", callback_data="adm:bkp:trigger"),
            ],
            [
                InlineKeyboardButton("⏰ Đặt giờ sao lưu", callback_data="adm:bkp:menu"),
                InlineKeyboardButton("🔄 Làm mới", callback_data="adm:dash:refresh"),
            ],
            [
                InlineKeyboardButton("❌ Đóng menu", callback_data="adm:dash:close"),
            ],
        ]
    )


def build_whitelist_keyboard(
    users: list[dict], current_page: int = 1, total_pages: int = 1
) -> InlineKeyboardMarkup:
    """Build whitelist users listing keyboard with 2 columns and action buttons."""
    buttons: list[list[InlineKeyboardButton]] = []
    user_buttons: list[InlineKeyboardButton] = []

    for u in users:
        uid = u["telegram_id"]
        role = u.get("role", "STAFF")
        name = u.get("name", "") or str(uid)
        icon = "👑" if role == "SUPER_ADMIN" else ("🛡️" if role == "ADMIN" else "👤")
        label = f"{icon} {name}"
        if len(label) > 20:
            label = label[:17] + "..."
        user_buttons.append(
            InlineKeyboardButton(label, callback_data=f"adm:wl:view:{uid}")
        )

    # 2 buttons per row
    for i in range(0, len(user_buttons), 2):
        buttons.append(user_buttons[i : i + 2])

    # Pagination if total_pages > 1
    if total_pages > 1:
        nav_row: list[InlineKeyboardButton] = []
        if current_page > 1:
            nav_row.append(
                InlineKeyboardButton(
                    "⬅️ Trước", callback_data=f"adm:wl:list:{current_page - 1}"
                )
            )
        nav_row.append(
            InlineKeyboardButton(
                f"Trang {current_page}/{total_pages}", callback_data="adm:noop"
            )
        )
        if current_page < total_pages:
            nav_row.append(
                InlineKeyboardButton(
                    "Sau ➡️", callback_data=f"adm:wl:list:{current_page + 1}"
                )
            )
        buttons.append(nav_row)

    # Add user button
    buttons.append(
        [
            InlineKeyboardButton("➕ Thêm tài khoản", callback_data="adm:wl:add_prompt"),
        ]
    )

    # Navigation row
    buttons.append(
        [
            InlineKeyboardButton("⬅️ Quay lại", callback_data="adm:dash:refresh"),
            InlineKeyboardButton("❌ Đóng", callback_data="adm:dash:close"),
        ]
    )

    return InlineKeyboardMarkup(buttons)


def build_whitelist_user_detail_keyboard(
    target_user: dict, is_root: bool = False
) -> InlineKeyboardMarkup:
    """Build detail and action keyboard for a whitelist user."""
    target_id = target_user["telegram_id"]
    current_role = target_user.get("role", "STAFF")

    if is_root:
        return InlineKeyboardMarkup(
            [
                [
                    InlineKeyboardButton(
                        "🛡️ Root Super Admin (Bảo vệ)", callback_data="adm:noop"
                    )
                ],
                [
                    InlineKeyboardButton(
                        "⬅️ Quay lại danh sách", callback_data="adm:wl:list:1"
                    )
                ],
            ]
        )

    buttons: list[list[InlineKeyboardButton]] = []
    # Role toggle buttons
    role_row: list[InlineKeyboardButton] = []
    if current_role == "ADMIN":
        role_row.append(
            InlineKeyboardButton(
                "👤 Đổi: NHÂN VIÊN",
                callback_data=f"adm:wl:role:{target_id}:STAFF",
            )
        )
    else:
        role_row.append(
            InlineKeyboardButton(
                "🛡️ Đổi vai trò: ADMIN",
                callback_data=f"adm:wl:role:{target_id}:ADMIN",
            )
        )
    buttons.append(role_row)

    # Remove button
    buttons.append(
        [
            InlineKeyboardButton(
                "🗑️ Xoá khỏi Whitelist",
                callback_data=f"adm:wl:rm_req:{target_id}",
            )
        ]
    )

    # Back button
    buttons.append(
        [
            InlineKeyboardButton(
                "⬅️ Quay lại danh sách",
                callback_data="adm:wl:list:1",
            )
        ]
    )

    return InlineKeyboardMarkup(buttons)


def build_whitelist_confirm_delete_keyboard(target_id: int) -> InlineKeyboardMarkup:
    """Build 2-step confirmation modal for whitelist removal per D-07."""
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    "⚠️ Xác nhận xoá", callback_data=f"adm:wl:rm_cf:{target_id}"
                ),
            ],
            [
                InlineKeyboardButton(
                    "Quay lại", callback_data=f"adm:wl:view:{target_id}"
                ),
            ],
        ]
    )


def build_model_switcher_keyboard(
    available_models: list[str], active_model: str
) -> InlineKeyboardMarkup:
    """Build model switcher keyboard with active indicator and custom input option."""
    buttons: list[list[InlineKeyboardButton]] = []
    model_buttons: list[InlineKeyboardButton] = []

    for m in available_models:
        label = f"[✓] {m}" if m == active_model else m
        model_buttons.append(
            InlineKeyboardButton(label, callback_data=f"adm:mdl:sel:{m}")
        )

    # 2 buttons per row
    for i in range(0, len(model_buttons), 2):
        buttons.append(model_buttons[i : i + 2])

    buttons.append(
        [
            InlineKeyboardButton(
                "✏️ Nhập tên model khác", callback_data="adm:mdl:input_prompt"
            )
        ]
    )
    buttons.append(
        [
            InlineKeyboardButton("⬅️ Quay lại", callback_data="adm:dash:refresh"),
            InlineKeyboardButton("❌ Đóng", callback_data="adm:dash:close"),
        ]
    )

    return InlineKeyboardMarkup(buttons)


def build_logs_keyboard(
    current_limit: int = 25, errors_only: bool = False
) -> InlineKeyboardMarkup:
    """Build logs viewer keyboard with limit, error filter, and refresh actions."""
    filter_val = "errors" if errors_only else "all"
    toggle_filter = "all" if errors_only else "errors"
    toggle_label = "📋 Tất cả" if errors_only else "⚠️ Chỉ Lỗi"

    filter_row = [
        InlineKeyboardButton(
            f"{'• ' if current_limit == 25 else ''}25 dòng",
            callback_data=f"adm:log:view:25:{filter_val}",
        ),
        InlineKeyboardButton(
            f"{'• ' if current_limit == 50 else ''}50 dòng",
            callback_data=f"adm:log:view:50:{filter_val}",
        ),
        InlineKeyboardButton(
            toggle_label,
            callback_data=f"adm:log:view:{current_limit}:{toggle_filter}",
        ),
        InlineKeyboardButton("🔄 Làm mới", callback_data="adm:log:refresh"),
    ]

    return InlineKeyboardMarkup(
        [
            filter_row,
            [
                InlineKeyboardButton("⬅️ Menu Quản trị", callback_data="adm:dash:refresh"),
                InlineKeyboardButton("❌ Đóng", callback_data="adm:dash:close"),
            ],
        ]
    )


def build_backup_schedule_keyboard(current_time: str) -> InlineKeyboardMarkup:
    """Build backup schedule time picker with presets and custom input per D-15."""
    presets = ["01:00", "02:00", "03:00", "04:00"]
    preset_buttons = [
        InlineKeyboardButton(
            f"[✓] {p}" if p == current_time else p,
            callback_data=f"adm:bkp:set:{p}",
        )
        for p in presets
    ]
    return InlineKeyboardMarkup(
        [
            preset_buttons[:2],
            preset_buttons[2:],
            [InlineKeyboardButton("✏️ Nhập giờ khác", callback_data="adm:bkp:custom_prompt")],
            [InlineKeyboardButton("⬅️ Quay lại", callback_data="adm:dash:refresh")],
        ]
    )




