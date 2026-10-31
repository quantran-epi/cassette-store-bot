import html
import json
import re
from collections.abc import Callable, Sequence
from datetime import datetime, timedelta, timezone
from typing import Any

from telegram import (
    CopyTextButton,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardMarkup,
)

from src.bot.security import UserRole
from src.models.customer import Customer
from src.models.order import Order, OrderStatus
from src.services.tape_parser import (
    build_tape_columns,
    format_artist_summary,
    format_tape_summary,
)

# Timezone Vietnam UTC+7
TZ_VN = timezone(timedelta(hours=7))

DIVIDER = "••••••••••••••••"  # 16 bullet dots divider
ITEM_DIVIDER = "────────"  # Short divider between order list items

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
    """Build persistent Reply Keyboard for elderly-friendly navigation."""
    keyboard = [
        [
            KeyboardButton("📦 Đơn hôm nay"),
            KeyboardButton("⏳ Đơn chờ làm"),
        ],
        [
            KeyboardButton("📋 Xem theo ngày"),
            KeyboardButton("✏️ Sửa đơn"),
        ],
        [
            KeyboardButton("🔍 Tra cứu đơn"),
            KeyboardButton("🔄 Đổi trạng thái"),
        ],
    ]
    return ReplyKeyboardMarkup(
        keyboard,
        resize_keyboard=True,
        is_persistent=True,
    )


def format_customer_classification(completed_orders: int, completed_spend: int) -> str:
    """Format delivered-order frequency and spend as separate Telegram HTML labels."""
    completed_orders = max(0, completed_orders)
    completed_spend = max(0, completed_spend)

    if completed_orders == 0:
        frequency_marker, frequency = "🆕", "KHÁCH VÃNG LAI"
    elif completed_orders == 1:
        frequency_marker, frequency = "🛍️", "KHÁCH MUA 1 LẦN"
    elif completed_orders < 5:
        frequency_marker, frequency = "🔁", "KHÁCH QUEN"
    else:
        frequency_marker, frequency = "⭐", "KHÁCH THÂN THIẾT"

    if completed_spend < 1_000_000:
        spend_marker = "🪙"
    elif completed_spend < 3_000_000:
        spend_marker = "🥉"
    elif completed_spend < 10_000_000:
        spend_marker = "🥈"
    else:
        spend_marker = "🥇"
    spend = f"{completed_spend:,} đ".replace(",", ".")
    return (
        f"{frequency_marker} <b>TẦN SUẤT:</b> <b>{frequency}</b> ({completed_orders} đơn hoàn thành)\n"
        f"{spend_marker} <b>CHI TIÊU:</b> <b>{spend}</b>"
    )


def _returning_marker(order: Order) -> str:
    """Icon for a customer with any prior order in the system (any status, not just delivered)."""
    count = order.customer_any_order_count
    return " 🔂" if isinstance(count, int) and count >= 2 else ""

def _order_classification(order: Order) -> str:
    if isinstance(order.customer_completed_orders, int) and isinstance(
        order.customer_completed_spend, int
    ):
        return format_customer_classification(
            order.customer_completed_orders, order.customer_completed_spend
        )
    return ""


def render_order_detail_card(
    order: Order,
    reminders: Any = None,
) -> str:
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
    notes_line = f"📝 <b>GHI CHÚ:</b> {html.escape(order.notes)}\n" if order.notes else ""
    classification = _order_classification(order)
    classification_line = f"{classification}\n" if classification else ""

    # Reminder display
    reminder_line = ""
    if reminders:
        r_list = [reminders] if not isinstance(reminders, (list, tuple)) else reminders
        r_strs = []
        for r in r_list:
            if hasattr(r, "remind_at") and hasattr(r, "reminder_text"):
                r_strs.append(f"<code>{r.remind_at}</code> ({html.escape(r.reminder_text)})")
            elif isinstance(r, dict):
                r_strs.append(
                    f"<code>{r.get('remind_at')}</code> ({html.escape(str(r.get('reminder_text') or ''))})"
                )
            else:
                r_strs.append(html.escape(str(r)))
        if r_strs:
            reminder_line = f"⏰ <b>LỊCH NHẮC:</b> {', '.join(r_strs)}\n"

    vn_created_at = (
        to_vn_datetime(order.created_at) if isinstance(order.created_at, datetime) else None
    )
    created_str = (
        vn_created_at.strftime("%d/%m/%Y %H:%M") if vn_created_at else str(order.created_at or "")
    )
    created_line = ""
    if created_str:
        creator_tag = (
            f" (bởi {html.escape(order.created_by_name)})" if order.created_by_name else ""
        )
        created_line = f"🕒 <b>THỜI GIAN TẠO:</b> {created_str}{creator_tag}\n"
    elif order.created_by_name:
        created_line = f"🕒 <b>NGƯỜI TẠO:</b> {html.escape(order.created_by_name)}\n"

    return (
        f"📦 <b>CHI TIẾT ĐƠN HÀNG #{order.id}</b>\n"
        f"🔄 <b>TRẠNG THÁI:</b> <b>{status_label}</b>\n"
        f"{DIVIDER}\n"
        f"👤 <b>KHÁCH:</b> {html.escape(order.customer_name)}{_returning_marker(order)}\n"
        f"{classification_line}"
        f"📞 <b>SĐT:</b> <code>{html.escape(order.customer_phone)}</code> <i>(chạm để copy)</i>\n"
        f"📍 <b>ĐỊA CHỈ:</b> <code>{html.escape(order.shipping_address)}</code>\n"
        f"📼 <b>BĂNG CASSETTE:</b> {html.escape(order.items_text)}\n"
        f"📼 <b>PHÔI BĂNG:</b> {html.escape(format_tape_summary(order.tape_quantity, order.tapes))}\n"
        f"🎤 <b>CA SĨ:</b> {html.escape(format_artist_summary(order.tape_artists))}\n"
        f"💰 <b>TỔNG TIỀN:</b> <b>{total_fmt}</b>\n"
        f"💵 <b>TIỀN COD THU:</b> <b>{cod_fmt}</b>\n"
        f"🚚 <b>MÃ VẬN ĐƠN:</b> {tracking_str}\n"
        f"📷 <b>ẢNH ĐÍNH KÈM:</b> {photo_str}\n"
        f"{notes_line}"
        f"{reminder_line}"
        f"{created_line}"
        f"{DIVIDER}"
    )


def build_order_detail_keyboard(
    order: Order,
    date_str: str = "",
    page: int = 1,
    back_callback_data: str | None = None,
    has_reminder: bool = False,
    expanded: bool = False,
    show_back: bool | None = None,
) -> InlineKeyboardMarkup:
    """Build multi-row inline keyboard with 1-tap CopyTextButtons and actions."""
    buttons: list[list[InlineKeyboardButton]] = []

    back_cb = back_callback_data or (f"ord_bk:{date_str}:{page}" if date_str else None)
    if show_back is None:
        show_back = bool(back_callback_data or date_str)

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

    if not expanded:
        # Collapsed mode: only essential buttons
        # 2. Photos row (ONLY if order has photos)
        if order.photo_file_ids:
            buttons.append(
                [
                    InlineKeyboardButton(
                        f"🖼️ Xem {len(order.photo_file_ids)} ảnh",
                        callback_data=f"ord_act:view_photo:{order.id}",
                    )
                ]
            )

        # 3. Shipping helper row (1-tap dispatch copy for carrier apps)
        buttons.append(
            [
                InlineKeyboardButton(
                    "🚚 Tạo đơn vận chuyển",
                    callback_data=f"ord_act:ship_helper:{order.id}",
                )
            ]
        )

        # 4. Expand / more actions button
        buttons.append(
            [
                InlineKeyboardButton(
                    "⚙️ Thao tác khác ▾",
                    callback_data=f"ord_act:more:{order.id}",
                )
            ]
        )

        # 5. Back navigation (only if from list)
        if show_back and back_cb:
            buttons.append(
                [
                    InlineKeyboardButton(
                        "⬅️ Quay lại",
                        callback_data=back_cb,
                    )
                ]
            )

        return InlineKeyboardMarkup(buttons)

    # Expanded mode: full actions

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

    # 5. Reminder row
    remind_label = "⏰ Sửa/Xem lịch nhắc" if has_reminder else "⏰ Thêm nhắc lịch"
    buttons.append(
        [
            InlineKeyboardButton(
                remind_label,
                callback_data=f"ord_act:remind:{order.id}",
            )
        ]
    )

    # 6. Shipping helper row (1-tap dispatch copy for carrier apps)
    buttons.append(
        [
            InlineKeyboardButton(
                "🚚 Tạo đơn vận chuyển",
                callback_data=f"ord_act:ship_helper:{order.id}",
            )
        ]
    )

    # 7. Edit order info & Change status menu
    buttons.append(
        [
            InlineKeyboardButton(
                "✏️ Sửa thông tin",
                callback_data=f"ord_act:edit_menu:{order.id}",
            ),
            InlineKeyboardButton(
                "🔄 Đổi trạng thái khác",
                callback_data=f"ord_st_menu:{order.id}",
            ),
        ]
    )

    # 8. Delete order
    buttons.append(
        [
            InlineKeyboardButton(
                "🗑️ Xoá đơn",
                callback_data=f"ord_act:del_prompt:{order.id}",
            ),
        ]
    )

    # 9. Collapse button
    buttons.append(
        [
            InlineKeyboardButton(
                "🔼 Thu gọn",
                callback_data=f"ord_act:less:{order.id}",
            )
        ]
    )

    # 10. Back navigation (only if from list)
    if show_back and back_cb:
        buttons.append(
            [
                InlineKeyboardButton(
                    "⬅️ Quay lại",
                    callback_data=back_cb,
                )
            ]
        )

    return InlineKeyboardMarkup(buttons)


def build_order_edit_menu_keyboard(order_id: int) -> InlineKeyboardMarkup:
    """Build keyboard for static field-by-field order editing."""
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    "👤 Tên khách", callback_data=f"ord_act:edit_fld:{order_id}:customer_name"
                ),
                InlineKeyboardButton(
                    "📞 SĐT", callback_data=f"ord_act:edit_fld:{order_id}:customer_phone"
                ),
            ],
            [
                InlineKeyboardButton(
                    "📍 Địa chỉ nhận hàng",
                    callback_data=f"ord_act:edit_fld:{order_id}:shipping_address",
                ),
            ],
            [
                InlineKeyboardButton(
                    "💰 Tổng tiền", callback_data=f"ord_act:edit_fld:{order_id}:total_amount"
                ),
                InlineKeyboardButton(
                    "💵 Tiền COD", callback_data=f"ord_act:edit_fld:{order_id}:cod_amount"
                ),
            ],
            [
                InlineKeyboardButton(
                    "📼 Danh sách băng", callback_data=f"ord_act:edit_fld:{order_id}:items_text"
                ),
                InlineKeyboardButton(
                    "📝 Ghi chú", callback_data=f"ord_act:edit_fld:{order_id}:notes"
                ),
            ],
            [
                InlineKeyboardButton("⬅️ Quay lại thẻ đơn", callback_data=f"ord_v_cur:{order_id}"),
            ],
        ]
    )


def build_shipping_helper_card(order: Order) -> str:
    """Render shipping dispatch helper card with copyable info for carrier apps."""
    cust_name = html.escape(order.customer_name)
    phone = html.escape(order.customer_phone) if order.customer_phone else "(Chưa có SĐT)"
    addr = html.escape(order.shipping_address) if order.shipping_address else "(Chưa có địa chỉ)"
    cod_fmt = f"{order.cod_amount:,} đ".replace(",", ".")
    is_cod = order.payment_method.upper() == "COD" or order.cod_amount > 0
    shipping_note = "Cho xem hàng, KHÔNG DÙNG THỬ" if is_cod else "Cho xem hàng"

    lines = [
        f"🚚 <b>HỖ TRỢ TẠO ĐƠN VẬN CHUYỂN #{order.id}</b>",
        DIVIDER,
        f"👤 <b>Khách hàng:</b> {cust_name}",
        f"📞 <b>Số điện thoại:</b> <code>{phone}</code>",
        f"📍 <b>Địa chỉ:</b> <code>{addr}</code>",
        "📦 <b>Tên hàng hoá:</b> <code>băng cát sét</code>",
        f"💰 <b>Tiền COD:</b> <b>{cod_fmt}</b>",
        f"📝 <b>Ghi chú giao hàng:</b> <code>{html.escape(shipping_note)}</code>",
    ]
    if order.tracking_code:
        lines.append(
            f"🚚 <b>Mã vận đơn hiện tại:</b> <code>{html.escape(order.tracking_code)}</code>"
        )
    lines.append(DIVIDER)
    lines.append(
        "<i>Bác chạm vào từng nút bên dưới để sao chép nhanh và dán sang app vận chuyển nhé:</i>"
    )
    return "\n".join(lines)


def build_shipping_helper_keyboard(order: Order) -> InlineKeyboardMarkup:
    """Build keyboard with 1-tap copy buttons and tracking action for carrier dispatch."""
    safe_name = (order.customer_name or "").strip()[:256] or "Khách hàng"
    safe_phone = (order.customer_phone or "").strip()[:256] or ""
    safe_addr = (order.shipping_address or "").strip()[:256] or ""
    is_cod = order.payment_method.upper() == "COD" or order.cod_amount > 0
    shipping_note = "Cho xem hàng, KHÔNG DÙNG THỬ" if is_cod else "Cho xem hàng"
    cod_raw = str(order.cod_amount)
    cod_fmt = f"{order.cod_amount:,} đ".replace(",", ".")

    buttons: list[list[InlineKeyboardButton]] = [
        [
            InlineKeyboardButton("👤 Copy Tên khách", copy_text=CopyTextButton(text=safe_name)),
            InlineKeyboardButton("📞 Copy SĐT", copy_text=CopyTextButton(text=safe_phone)),
        ],
        [
            InlineKeyboardButton("📍 Copy Địa chỉ", copy_text=CopyTextButton(text=safe_addr)),
        ],
        [
            InlineKeyboardButton(
                "📦 Copy Hàng hoá (băng cát sét)", copy_text=CopyTextButton(text="băng cát sét")
            ),
        ],
        [
            InlineKeyboardButton(
                f"💰 Copy Tiền COD ({cod_fmt})", copy_text=CopyTextButton(text=cod_raw)
            ),
        ],
        [
            InlineKeyboardButton(
                "📝 Copy Ghi chú giao hàng", copy_text=CopyTextButton(text=shipping_note)
            ),
        ],
    ]

    track_row: list[InlineKeyboardButton] = []
    if order.tracking_code:
        track_row.append(
            InlineKeyboardButton(
                "🚚 Copy Mã vận đơn",
                copy_text=CopyTextButton(text=order.tracking_code.strip()[:256]),
            )
        )
    track_row.append(
        InlineKeyboardButton(
            "🚚 Đổi mã vận đơn" if order.tracking_code else "🚚 Nhập mã vận đơn",
            callback_data=f"ord_act:track:{order.id}",
        )
    )
    buttons.append(track_row)

    buttons.append(
        [
            InlineKeyboardButton(
                "⬅️ Quay lại chi tiết đơn",
                callback_data=f"ord_v_cur:{order.id}",
            )
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


def format_order_item_summary(order: Order) -> str:
    """Format single order summary block for multi-order lists with high contrast and uppercase labels."""
    status_label = STATUS_NAMES.get(
        order.status,
        order.status.value if hasattr(order.status, "value") else str(order.status),
    )
    total_fmt = f"{order.total_amount:,} đ".replace(",", ".")
    cust_name = html.escape(order.customer_name)
    phone = (
        f"<code>{html.escape(order.customer_phone)}</code>"
        if order.customer_phone
        else "<i>(Chưa có SĐT)</i>"
    )
    addr = html.escape(order.shipping_address) if order.shipping_address else "<i>(Chưa có Đ/C)</i>"
    items_line = f"\n   📼 <b>BĂNG:</b> {html.escape(order.items_text)}" if order.items_text else ""
    classification = _order_classification(order)
    classification_line = f"   {classification.replace(chr(10), chr(10) + '   ')}\n" if classification else ""
    vn_created_at = (
        to_vn_datetime(order.created_at) if isinstance(order.created_at, datetime) else None
    )
    created_str = (
        vn_created_at.strftime("%d/%m/%Y %H:%M") if vn_created_at else str(order.created_at or "")
    )
    time_line = f"\n   🕒 <b>TẠO:</b> {created_str}" if created_str else ""
    return (
        f"📦 <b>#{order.id} — {cust_name}{_returning_marker(order)}</b>\n"
        f"{classification_line}"
        f"   📞 <b>SĐT:</b> {phone}\n"
        f"   📍 <b>Đ/C:</b> {addr}"
        f"{items_line}"
        f"{time_line}\n"
        f"   💰 <b>TIỀN:</b> <b>{total_fmt}</b> (<i>{status_label}</i>)"
    )


def render_order_list_card(
    orders: Sequence[Order],
    date_str: str,
    page: int,
    total_pages: int,
    total_orders: int,
) -> str:
    """Render paginated order list card (5 orders/page) or empty notice."""
    if total_orders == 0:
        return f"📅 <b>ĐƠN HÀNG NGÀY {date_str}</b>\n\nNgày này chưa có đơn hàng nào bác nhé!"

    # Convert YYYY-MM-DD to DD/MM/YYYY for friendly Vietnamese display
    try:
        dt = datetime.strptime(date_str, "%Y-%m-%d")
        display_date = dt.strftime("%d/%m/%Y")
    except ValueError:
        display_date = date_str

    lines = [
        f"📅 <b>ĐƠN HÀNG NGÀY {display_date}</b>",
        f"Tổng cộng: <b>{total_orders} đơn</b> (Trang {page}/{total_pages})",
        DIVIDER,
    ]

    order_blocks = [format_order_item_summary(order) for order in orders]
    if order_blocks:
        lines.append(f"\n{ITEM_DIVIDER}\n".join(order_blocks))

    lines.append(DIVIDER)
    lines.append("Bác chạm vào nút xem đơn bên dưới nhé:")
    return "\n".join(lines)


def format_order_compact_line(order: Order) -> str:
    """Compact order summary with classification when aggregate stats are hydrated."""
    total_fmt = f"{order.total_amount:,} đ".replace(",", ".")
    line = f"📦 <b>#{order.id}</b> · {html.escape(order.customer_name)}{_returning_marker(order)} · {total_fmt}"
    classification = _order_classification(order)
    return f"{line}\n   {classification.replace(chr(10), chr(10) + '   ')}" if classification else line


def _vn_date_label(created_at: Any) -> str:
    """Vietnam-time DD/MM/YYYY label, or a friendly fallback when unparseable."""
    dt: datetime | None = None
    if isinstance(created_at, datetime):
        dt = created_at
    elif isinstance(created_at, str) and created_at.strip():
        try:
            dt = datetime.fromisoformat(created_at.strip().replace("Z", "+00:00"))
        except ValueError:
            dt = None
    vn_dt = to_vn_datetime(dt)
    return vn_dt.strftime("%d/%m/%Y") if vn_dt else "Không rõ ngày"


def render_status_order_list_card(
    orders: Sequence[Order],
    status: OrderStatus,
    page: int,
    total_pages: int,
    total_orders: int,
) -> str:
    """Render status-filtered order list grouped by Vietnam creation date (D-4)."""
    status_label = STATUS_NAMES.get(status, status.value)
    header = (
        f"{status_label} — <b>DANH SÁCH ĐƠN</b>\n"
        f"Tổng cộng: <b>{total_orders} đơn</b> (Trang {page}/{total_pages})"
    )

    if total_orders == 0:
        return f"{header}\n\nChưa có đơn nào ở trạng thái này bác nhé!"

    # Group by VN date, preserving query order (created_at DESC). Never SQL GROUP BY.
    groups: dict[str, list[Order]] = {}
    for order in orders:
        groups.setdefault(_vn_date_label(order.created_at), []).append(order)

    blocks: list[str] = []
    for date_label, day_orders in groups.items():
        day_lines = [f"📅 <b>{date_label}</b> · {len(day_orders)} đơn"]
        day_lines.extend(format_order_compact_line(o) for o in day_orders)
        blocks.append("\n".join(day_lines))

    return "\n".join(
        [
            header,
            DIVIDER,
            "\n\n".join(blocks),
            DIVIDER,
            "Bác chạm vào nút xem đơn bên dưới nhé:",
        ]
    )


# Status chips shown at the bottom of every list card (D-3).
FILTER_CHIP_STATUSES: tuple[OrderStatus, ...] = (
    OrderStatus.CHO_LAM,
    OrderStatus.DANG_LAM,
    OrderStatus.DA_DONG_GOI,
)


def _build_status_filter_row(
    current_status: OrderStatus | None = None,
    current_page: int = 1,
) -> list[InlineKeyboardButton]:
    """Build the 3 status filter chips; keep the current page on the active chip."""
    row: list[InlineKeyboardButton] = []
    for st in FILTER_CHIP_STATUSES:
        page = current_page if st == current_status else 1
        row.append(
            InlineKeyboardButton(
                STATUS_NAMES[st],
                callback_data=f"ord_ls:{st.value}:{page}",
            )
        )
    return row


def build_status_order_list_keyboard(
    orders: Sequence[Order],
    status: OrderStatus,
    page: int,
    total_pages: int,
) -> InlineKeyboardMarkup:
    """Build keyboard for a status-filtered list: detail buttons, paging, filter chips."""
    buttons: list[list[InlineKeyboardButton]] = []

    for order in orders:
        btn_label = f"👁️ Xem đơn #{order.id} - {order.customer_name}"
        if len(btn_label) > 34:
            btn_label = btn_label[:31] + "..."
        buttons.append(
            [
                InlineKeyboardButton(
                    btn_label,
                    callback_data=f"ord_vls:{status.value}:{order.id}:{page}",
                )
            ]
        )

    if orders and total_pages > 1:
        nav_row: list[InlineKeyboardButton] = []
        if page > 1:
            nav_row.append(
                InlineKeyboardButton("⬅️ Trước", callback_data=f"ord_ls:{status.value}:{page - 1}")
            )
        nav_row.append(
            InlineKeyboardButton(f"Trang {page}/{total_pages}", callback_data="ord_noop")
        )
        if page < total_pages:
            nav_row.append(
                InlineKeyboardButton("Sau ➡️", callback_data=f"ord_ls:{status.value}:{page + 1}")
            )
        buttons.append(nav_row)

    return InlineKeyboardMarkup(buttons)


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
    nav_row.append(InlineKeyboardButton(f"Trang {page}/{total_pages}", callback_data="ord_noop"))
    if page < total_pages:
        nav_row.append(InlineKeyboardButton("Sau ➡️", callback_data=f"ord_pg:{date_str}:{page + 1}"))
    buttons.append(nav_row)

    # Pick another date bottom button per D-03
    buttons.append([InlineKeyboardButton("📋 Chọn ngày khác", callback_data="ord_act:pick_date")])

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


def render_search_single_order_card(order: Order, query: str, purpose: str | None = None) -> str:
    """Format single order confirmation preview card per D-08."""
    status_label = STATUS_NAMES.get(
        order.status,
        order.status.value if hasattr(order.status, "value") else str(order.status),
    )
    total_fmt = f"{order.total_amount:,} đ".replace(",", ".")
    cust_name = html.escape(order.customer_name)
    phone_display = (
        f"<code>{html.escape(order.customer_phone)}</code>"
        if order.customer_phone
        else "<i>Chưa có SĐT</i>"
    )
    addr = html.escape(order.shipping_address) if order.shipping_address else "<i>Chưa có Đ/C</i>"
    items = html.escape(order.items_text) if order.items_text else "<i>(Chưa có)</i>"
    esc_query = html.escape(query.strip())

    if purpose:
        heading = f"🔍 <b>{html.escape(purpose)}</b>\n{DIVIDER}\n"
    else:
        heading = (
            f"🔍 <b>KẾT QUẢ TÌM KIẾM ĐƠN HÀNG</b>\n<i>(Tìm theo: '{esc_query}')</i>\n{DIVIDER}\n"
        )

    classification = _order_classification(order)
    classification_line = f"{classification}\n" if classification else ""
    return (
        heading + f"📦 <b>Đơn #{order.id}</b> - {cust_name}{_returning_marker(order)}\n"
        f"{classification_line}"
        f"📞 <b>SĐT:</b> {phone_display}\n"
        f"📍 <b>ĐỊA CHỈ:</b> {addr}\n"
        f"📼 <b>BĂNG CASSETTE:</b> {items}\n"
        f"💰 <b>TỔNG TIỀN:</b> <b>{total_fmt}</b> | 🔄 <b>TRẠNG THÁI:</b> <b>{status_label}</b>\n"
        f"{DIVIDER}\n"
        f"Có phải bác muốn xem đơn này không?"
    )


def build_search_single_order_keyboard(order_id: int, search_id: str) -> InlineKeyboardMarkup:
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


def render_search_empty_card(query: str, purpose: str | None = None) -> str:
    """Format friendly empty search result card per D-10."""
    esc_query = html.escape(query.strip())
    if purpose:
        return (
            f"🔍 <b>{html.escape(purpose)}</b>\n\n"
            f"Dạ em tìm trong sổ không thấy đơn nào phù hợp với mục này!"
        )
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
    purpose: str | None = None,
) -> str:
    """Render paginated multi-order search result preview card per D-09."""
    esc_query = html.escape(query.strip())
    if purpose:
        lines = [
            f"🔍 <b>{html.escape(purpose)}</b>",
            f"Dạ em tìm thấy <b>{total_orders} đơn hàng</b> phù hợp (Trang {page}/{total_pages}):",
            DIVIDER,
        ]
    else:
        lines = [
            "🔍 <b>KẾT QUẢ TÌM KIẾM ĐƠN HÀNG</b>",
            f"<i>(Tìm theo: '{esc_query}')</i>",
            f"Dạ em tìm thấy <b>{total_orders} đơn hàng</b> phù hợp (Trang {page}/{total_pages}):",
            DIVIDER,
        ]

    order_blocks = [format_order_item_summary(order) for order in orders]
    if order_blocks:
        lines.append(f"\n{ITEM_DIVIDER}\n".join(order_blocks))

    lines.append(DIVIDER)
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

    # Pagination navigation row: [◀️ Trang trước] [Trang X/Y] [Xem thêm ➡️]
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
                    "Xem thêm ➡️",
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
    maintenance_mode: bool = False,
) -> InlineKeyboardMarkup:
    """Build 2-column admin suite navigation grid per D-03 and UI-SPEC."""
    rows: list[list[InlineKeyboardButton]] = [
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
    ]

    if user_role == UserRole.SUPER_ADMIN:
        maint_label = (
            "🚧 Tắt bảo trì (Đang dừng)" if maintenance_mode else "🟢 Bật bảo trì (Tạm dừng chat)"
        )
        rows.append(
            [
                InlineKeyboardButton(maint_label, callback_data="adm:maint:toggle"),
            ]
        )

    rows.append(
        [
            InlineKeyboardButton("❌ Đóng menu", callback_data="adm:dash:close"),
        ]
    )
    return InlineKeyboardMarkup(rows)


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
        user_buttons.append(InlineKeyboardButton(label, callback_data=f"adm:wl:view:{uid}"))

    # 2 buttons per row
    for i in range(0, len(user_buttons), 2):
        buttons.append(user_buttons[i : i + 2])

    # Pagination if total_pages > 1
    if total_pages > 1:
        nav_row: list[InlineKeyboardButton] = []
        if current_page > 1:
            nav_row.append(
                InlineKeyboardButton("⬅️ Trước", callback_data=f"adm:wl:list:{current_page - 1}")
            )
        nav_row.append(
            InlineKeyboardButton(f"Trang {current_page}/{total_pages}", callback_data="adm:noop")
        )
        if current_page < total_pages:
            nav_row.append(
                InlineKeyboardButton("Sau ➡️", callback_data=f"adm:wl:list:{current_page + 1}")
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
                [InlineKeyboardButton("🛡️ Root Super Admin (Bảo vệ)", callback_data="adm:noop")],
                [
                    InlineKeyboardButton(
                        "✏️ Đổi tên", callback_data=f"adm:wl:rename_prompt:{target_id}"
                    )
                ],
                [InlineKeyboardButton("⬅️ Quay lại danh sách", callback_data="adm:wl:list:1")],
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

    # Action row: Rename & Remove
    buttons.append(
        [
            InlineKeyboardButton(
                "✏️ Đổi tên",
                callback_data=f"adm:wl:rename_prompt:{target_id}",
            ),
            InlineKeyboardButton(
                "🗑️ Xoá khỏi Whitelist",
                callback_data=f"adm:wl:rm_req:{target_id}",
            ),
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
                InlineKeyboardButton("⚠️ Xác nhận xoá", callback_data=f"adm:wl:rm_cf:{target_id}"),
            ],
            [
                InlineKeyboardButton("Quay lại", callback_data=f"adm:wl:view:{target_id}"),
            ],
        ]
    )


def build_model_switcher_keyboard(
    available_models: list[str], active_model: str
) -> InlineKeyboardMarkup:
    """Build model switcher keyboard with active indicator, custom input, and delete option per D-17."""
    buttons: list[list[InlineKeyboardButton]] = []
    model_buttons: list[InlineKeyboardButton] = []

    for m in available_models:
        label = f"[✓] {m}" if m == active_model else m
        model_buttons.append(InlineKeyboardButton(label, callback_data=f"adm:mdl:sel:{m}"))

    # 2 buttons per row
    for i in range(0, len(model_buttons), 2):
        buttons.append(model_buttons[i : i + 2])

    action_row = [
        InlineKeyboardButton("✏️ Nhập tên model khác", callback_data="adm:mdl:input_prompt")
    ]
    # Show delete button if there are models other than the active model
    other_models = [m for m in available_models if m != active_model]
    if other_models:
        action_row.append(InlineKeyboardButton("🗑️ Xoá model", callback_data="adm:mdl:del_menu"))
    buttons.append(action_row)

    buttons.append(
        [
            InlineKeyboardButton("⬅️ Quay lại", callback_data="adm:dash:refresh"),
            InlineKeyboardButton("❌ Đóng", callback_data="adm:dash:close"),
        ]
    )

    return InlineKeyboardMarkup(buttons)


def build_model_delete_keyboard(models: list[str], active_model: str) -> InlineKeyboardMarkup:
    """Build keyboard to delete non-active models per D-17."""
    deletable = [m for m in models if m != active_model]
    buttons: list[list[InlineKeyboardButton]] = []

    for m in deletable:
        buttons.append([InlineKeyboardButton(f"🗑️ {m}", callback_data=f"adm:mdl:del:{m}")])

    buttons.append([InlineKeyboardButton("⬅️ Quay lại", callback_data="adm:mdl:menu")])
    return InlineKeyboardMarkup(buttons)


def build_logs_keyboard(current_limit: int = 25, errors_only: bool = False) -> InlineKeyboardMarkup:
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


def get_suggested_next_statuses(
    current_status: OrderStatus,
) -> list[tuple[OrderStatus, str]]:
    """Return contextually sensible forward transitions and cancellation based on lifecycle per MUT-05 and D-13."""
    suggestions: dict[OrderStatus, list[tuple[OrderStatus, str]]] = {
        OrderStatus.CHO_LAM: [
            (OrderStatus.DANG_LAM, "▶️ Bắt đầu làm"),
            (OrderStatus.HUY_DON, "❌ Huỷ đơn này"),
        ],
        OrderStatus.DANG_LAM: [
            (OrderStatus.DA_DONG_GOI, "📦 Đã đóng gói xong"),
            (OrderStatus.DA_TAO_DON, "📑 Đã tạo đơn ship"),
            (OrderStatus.HUY_DON, "❌ Huỷ đơn này"),
        ],
        OrderStatus.DA_DONG_GOI: [
            (OrderStatus.DA_TAO_DON, "📑 Đã tạo đơn ship"),
            (OrderStatus.SHIPPER_DA_LAY, "🚚 Shipper đã lấy"),
            (OrderStatus.HUY_DON, "❌ Huỷ đơn này"),
        ],
        OrderStatus.DA_TAO_DON: [
            (OrderStatus.SHIPPER_DA_LAY, "🚚 Shipper đã lấy"),
            (OrderStatus.DA_GIAO, "✅ Đã giao thành công"),
            (OrderStatus.HUY_DON, "❌ Huỷ đơn này"),
        ],
        OrderStatus.SHIPPER_DA_LAY: [
            (OrderStatus.DA_GIAO, "✅ Đã giao thành công"),
            (OrderStatus.BOM_HANG, "🚫 Đánh dấu bom hàng"),
            (OrderStatus.HUY_DON, "❌ Huỷ đơn này"),
        ],
        OrderStatus.DA_GIAO: [
            (OrderStatus.CHO_LAM, "⏳ Mở lại đơn (Chờ làm)"),
        ],
        OrderStatus.BOM_HANG: [
            (OrderStatus.CHO_LAM, "⏳ Mở lại đơn (Chờ làm)"),
        ],
        OrderStatus.HUY_DON: [
            (OrderStatus.CHO_LAM, "⏳ Mở lại đơn (Chờ làm)"),
        ],
    }
    return suggestions.get(
        current_status,
        [
            (OrderStatus.DANG_LAM, "▶️ Bắt đầu làm"),
            (OrderStatus.HUY_DON, "❌ Huỷ đơn"),
        ],
    )


def render_mutation_diff_card(order: Order, delta_dict: dict) -> str:
    """Format elderly-friendly Visual Diff card showing ONLY changed fields Before ➡️ After per D-11, D-19."""
    diff_lines: list[str] = []

    # 1. Status
    new_status = delta_dict.get("status") or delta_dict.get("new_status")
    if new_status and new_status != order.status:
        if isinstance(new_status, str):
            try:
                new_status = OrderStatus(new_status)
            except ValueError:
                pass
        old_lbl = STATUS_NAMES.get(
            order.status,
            str(order.status.value if hasattr(order.status, "value") else order.status),
        )
        new_lbl = STATUS_NAMES.get(
            new_status, str(new_status.value if hasattr(new_status, "value") else new_status)
        )
        diff_lines.append(f"🔄 <b>TRẠNG THÁI:</b> {old_lbl} ➡️ <b>{new_lbl}</b>")

    # 2. Phone
    new_phone = delta_dict.get("customer_phone") or delta_dict.get("new_customer_phone")
    if new_phone and new_phone != order.customer_phone:
        old_p = html.escape(order.customer_phone or "[Chưa có]")
        new_p = html.escape(str(new_phone))
        diff_lines.append(f"📞 <b>SĐT:</b> <code>{old_p}</code> ➡️ <code>{new_p}</code>")

    # 3. Address
    new_addr = delta_dict.get("shipping_address") or delta_dict.get("new_shipping_address")
    if new_addr and new_addr != order.shipping_address:
        old_a = html.escape(order.shipping_address or "[Chưa có]")
        new_a = html.escape(str(new_addr))
        diff_lines.append(f"📍 <b>ĐỊA CHỈ:</b>\n   [Cũ]: {old_a}\n   ➡️ [Mới]: <b>{new_a}</b>")

    # 4. Total Amount
    new_total = delta_dict.get("total_amount")
    if new_total is None:
        new_total = delta_dict.get("new_total_amount")
    if new_total is not None and new_total != order.total_amount:
        old_t = f"{order.total_amount:,} đ".replace(",", ".")
        new_t = f"{int(new_total):,} đ".replace(",", ".")
        diff_lines.append(f"💰 <b>TỔNG TIỀN:</b> {old_t} ➡️ <b>{new_t}</b>")

    # 5. COD Amount
    new_cod = delta_dict.get("cod_amount")
    if new_cod is None:
        new_cod = delta_dict.get("new_cod_amount")
    if new_cod is not None and new_cod != order.cod_amount:
        old_c = f"{order.cod_amount:,} đ".replace(",", ".")
        new_c = f"{int(new_cod):,} đ".replace(",", ".")
        diff_lines.append(f"💵 <b>TIỀN COD THU:</b> {old_c} ➡️ <b>{new_c}</b>")

    # 6. Tracking Code
    new_track = delta_dict.get("tracking_code") or delta_dict.get("new_tracking_code")
    if new_track and new_track != order.tracking_code:
        old_tr = html.escape(order.tracking_code or "(Chưa có)")
        new_tr = html.escape(str(new_track))
        diff_lines.append(f"🚚 <b>MÃ VẬN ĐƠN:</b> <code>{old_tr}</code> ➡️ <code>{new_tr}</code>")

    # 7. Items Text
    new_items = delta_dict.get("items_text") or delta_dict.get("new_items_text")
    if new_items and new_items != order.items_text:
        old_it = html.escape(order.items_text or "(Chưa có)")
        new_it = html.escape(str(new_items))
        diff_lines.append(f"📼 <b>BĂNG CASSETTE:</b> {old_it} ➡️ <b>{new_it}</b>")
        cols = build_tape_columns(
            str(new_items),
            delta_dict.get("new_tapes") or delta_dict.get("tapes"),
            delta_dict.get("new_tape_genres") or delta_dict.get("tape_genres"),
            delta_dict.get("new_tape_artists") or delta_dict.get("tape_artists"),
        )
        old_display = order.tape_quantity if order.tape_quantity is not None else "—"
        diff_lines.append(f"📼 <b>SỐ BĂNG:</b> {old_display} ➡️ <b>{cols.quantity}</b>")
        new_artists = json.loads(cols.artists_json)
        diff_lines.append(
            f"🎤 <b>CA SĨ:</b> {html.escape(format_artist_summary(order.tape_artists))} "
            f"➡️ <b>{html.escape(format_artist_summary(new_artists))}</b>"
        )

    # 8. Notes
    new_notes = delta_dict.get("notes") or delta_dict.get("new_notes")
    if new_notes:
        diff_lines.append(f"📝 <b>GHI CHÚ MỚI:</b> {html.escape(str(new_notes))}")

    # Fallback if no specific diff lines
    diff_text = "\n\n".join(diff_lines) if diff_lines else "<i>Không phát hiện thay đổi cụ thể.</i>"

    cust_name = html.escape(order.customer_name or "[Khách]")
    return (
        f"📝 <b>XÁC NHẬN SỬA ĐƠN HÀNG #{order.id}</b>\n"
        f"👤 <b>KHÁCH:</b> {cust_name}\n"
        f"{DIVIDER}\n"
        f"<b>Các nội dung thay đổi:</b>\n\n"
        f"{diff_text}\n"
        f"{DIVIDER}\n"
        f"Bác kiểm tra lại thông tin rồi bấm nút bên dưới nhé (hết hạn sau 5 phút):"
    )


def build_mutation_confirm_keyboard(draft_id: str) -> InlineKeyboardMarkup:
    """Build confirmation keyboard with [✅ Xác nhận sửa] and [❌ Huỷ] per D-11."""
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("✅ Xác nhận sửa", callback_data=f"ord_mut_cf:{draft_id}"),
                InlineKeyboardButton("❌ Huỷ", callback_data=f"ord_mut_ca:{draft_id}"),
            ]
        ]
    )


def render_mutation_disambiguation_card(orders: Sequence[Order], keyword: str | None) -> str:
    """Render disambiguation list card for multiple matched orders in mutation."""
    kw_display = html.escape(keyword or "khách")
    lines = [
        "🔍 <b>CHỌN ĐƠN HÀNG CẦN SỬA</b>",
        f"<i>(Tìm thấy {len(orders)} đơn hàng của '{kw_display}')</i>",
        DIVIDER,
    ]
    order_blocks = [format_order_item_summary(order) for order in orders]
    if order_blocks:
        lines.append(f"\n{ITEM_DIVIDER}\n".join(order_blocks))

    lines.append(DIVIDER)
    lines.append("Bác bấm chọn đúng đơn cần sửa bên dưới nhé:")
    return "\n".join(lines)


def build_mutation_disambiguation_keyboard(
    orders: list[Order], draft_id: str
) -> InlineKeyboardMarkup:
    """Build 1-button-per-row disambiguation keyboard for 2-5 matching orders per D-08."""
    buttons: list[list[InlineKeyboardButton]] = []
    for o in orders[:5]:
        status_label = STATUS_NAMES.get(
            o.status, str(o.status.value if hasattr(o.status, "value") else o.status)
        )
        total_str = f"{o.total_amount:,} đ".replace(",", ".")
        cust_name = o.customer_name[:12] if len(o.customer_name) > 12 else o.customer_name
        label = f"📦 Đơn #{o.id} - {cust_name} - {total_str} - {status_label}"
        if len(label) > 38:
            label = label[:35] + "..."
        buttons.append(
            [InlineKeyboardButton(label, callback_data=f"ord_mut_sel:{draft_id}:{o.id}")]
        )

    buttons.append([InlineKeyboardButton("❌ Huỷ", callback_data=f"ord_mut_ca:{draft_id}")])
    return InlineKeyboardMarkup(buttons)


def build_mutation_status_keyboard(
    draft_id: str, order_id: int, current_status: OrderStatus
) -> InlineKeyboardMarkup:
    """Build status selection suggestions keyboard per MUT-05 and D-13."""
    suggestions = get_suggested_next_statuses(current_status)
    buttons: list[list[InlineKeyboardButton]] = []

    for status_val, label in suggestions:
        buttons.append(
            [
                InlineKeyboardButton(
                    label,
                    callback_data=f"ord_mut_st:{draft_id}:{order_id}:{status_val.value}",
                )
            ]
        )

    buttons.append(
        [
            InlineKeyboardButton(
                "❌ Huỷ bỏ",
                callback_data=f"ord_mut_ca:{draft_id}",
            )
        ]
    )
    return InlineKeyboardMarkup(buttons)


def render_customer_detail_card(
    customer: Customer,
    stats: dict,
    orders: Sequence[Order],
    page: int,
    total_pages: int,
    draft_id: str | None = None,
    *,
    nav_callback: Callable[[int], str] | None = None,
    back_callback: str | None = None,
) -> tuple[str, InlineKeyboardMarkup]:
    """Render customer profile and paginated order history card with navigation keyboard.

    ``nav_callback`` overrides the draft-based paging callbacks; ``back_callback`` replaces the
    "back to draft" button. Defaults keep the original draft-flow behaviour intact.
    """
    cust_name = html.escape(customer.name or "Khách hàng")
    phones_str = (
        ", ".join(f"<code>{html.escape(p)}</code>" for p in customer.phones)
        if customer.phones
        else "<i>Chưa có</i>"
    )

    if customer.addresses:
        addr_lines = "\n".join(
            f"  {idx + 1}. {html.escape(a)}" for idx, a in enumerate(customer.addresses)
        )
        addr_block = f"📍 <b>Địa chỉ ({len(customer.addresses)}):</b>\n{addr_lines}"
    else:
        addr_block = "📍 <b>Địa chỉ:</b> <i>Chưa có</i>"

    classification = format_customer_classification(
        stats.get("total_orders", 0), stats.get("total_spent", 0)
    )
    bom_count = stats.get("bom_count", 0)
    warning_line = (
        f"\n⚠️ <b>CẢNH BÁO: Khách từng có {bom_count} đơn BOM HÀNG!</b>" if bom_count > 0 else ""
    )

    notes_line = f"\n📝 <b>Ghi chú:</b> {html.escape(customer.notes)}" if customer.notes else ""

    order_blocks: list[str] = []
    for o in orders:
        st_name = STATUS_NAMES.get(
            o.status,
            o.status.value if hasattr(o.status, "value") else str(o.status),
        )
        tot = f"{o.total_amount:,} đ".replace(",", ".")
        cod = f"{o.cod_amount:,} đ".replace(",", ".")
        items = html.escape(o.items_text or "(Chưa có băng)")
        created_str = ""
        if o.created_at:
            vn_dt = to_vn_datetime(o.created_at) if isinstance(o.created_at, datetime) else None
            created_str = f" ({vn_dt.strftime('%d/%m/%Y')})" if vn_dt else ""

        order_blocks.append(
            f"• <b>#DH{o.id}</b>{created_str} - {st_name}\n  📼 {items}\n  💰 {tot} (COD: {cod})"
        )

    if order_blocks:
        history_content = "\n\n".join(order_blocks)
    else:
        history_content = "<i>(Chưa có đơn hàng nào)</i>"

    text = (
        f"👤 <b>HỒ SƠ KHÁCH HÀNG: {cust_name.upper()}</b>\n"
        f"📞 <b>SĐT:</b> {phones_str}\n"
        f"{addr_block}\n"
        f"{classification}"
        f"{warning_line}"
        f"{notes_line}\n"
        f"{DIVIDER}\n"
        f"📦 <b>LỊCH SỬ ĐƠN HÀNG (Trang {page}/{total_pages}):</b>\n\n"
        f"{history_content}\n"
        f"{DIVIDER}\n"
        f"Bác bấm nút bên dưới để xem thêm hoặc quay lại:"
    )

    keyboard: list[list[InlineKeyboardButton]] = []
    safe_draft_id = draft_id or "00000000"

    def _page_cb(target_page: int) -> str:
        return (
            nav_callback(target_page) if nav_callback else f"ord:cs:{safe_draft_id}:{target_page}"
        )

    # Pagination row
    if total_pages > 1:
        nav_row: list[InlineKeyboardButton] = []
        if page > 1:
            nav_row.append(InlineKeyboardButton("⬅️ Trước", callback_data=_page_cb(page - 1)))
        nav_row.append(
            InlineKeyboardButton(
                f"Trang {page}/{total_pages}",
                callback_data=f"ord:noop:{safe_draft_id}",
            )
        )
        if page < total_pages:
            nav_row.append(InlineKeyboardButton("Sau ➡️", callback_data=_page_cb(page + 1)))
        keyboard.append(nav_row)

    # Back button: custom target for customer search, or the draft preview as before.
    if back_callback:
        keyboard.append([InlineKeyboardButton("🔙 Quay lại kết quả", callback_data=back_callback)])
    elif draft_id:
        keyboard.append(
            [InlineKeyboardButton("◀️ Quay lại đơn đang tạo", callback_data=f"ord:bk:{draft_id}")]
        )

    return text, InlineKeyboardMarkup(keyboard)


# ============================================================================
# BULK STATUS CHANGE KEYBOARDS & CARDS
# ============================================================================


def _status_short_emoji(st: OrderStatus) -> str:
    """Compact status icon for button labels."""
    mapping = {
        OrderStatus.CHO_LAM: "⏳",
        OrderStatus.DANG_LAM: "🛠️",
        OrderStatus.DA_DONG_GOI: "📦",
        OrderStatus.DA_TAO_DON: "📑",
        OrderStatus.SHIPPER_DA_LAY: "🚚",
        OrderStatus.DA_GIAO: "✅",
        OrderStatus.BOM_HANG: "🚫",
        OrderStatus.HUY_DON: "❌",
    }
    return mapping.get(st, "•")


def _format_bulk_button_label(order: Order, checked: bool) -> str:
    """Format single-order checkbox button per user requirement:
    name, 4 last digits of phone, status icon, and tracking code if present."""
    mark = "☑" if checked else "☐"
    name = (order.customer_name or "Khách").strip()
    if len(name) > 10:
        name = name[:9] + "…"

    phone = re.sub(r"\D", "", order.customer_phone or "")
    phone_part = phone[-4:] if len(phone) >= 4 else (phone or "")

    st_ico = _status_short_emoji(order.status)
    track = (order.tracking_code or "").strip()
    track_part = f" · {track[-6:]}" if track else ""

    phone_str = f" · {phone_part}" if phone_part else ""
    label = f"{mark} #{order.id} {name}{phone_str}{track_part} {st_ico}"
    # Telegram button text limit safe guard (64 chars)
    return label[:48]


def render_bulk_intro_card() -> str:
    """Render step 1/3 intro card."""
    return (
        "🔄 <b>ĐỔI TRẠNG THÁI HÀNG LOẠT</b>\n"
        "<i>Bước 1/3 — Chọn đơn cần đổi</i>\n"
        f"{DIVIDER}\n"
        "Bác chọn đơn theo 1 trong 2 cách:\n\n"
        "• Bấm <b>🔍 Tìm đơn</b> rồi gõ tên khách, SĐT hoặc ngày như bình thường.\n"
        "• Hoặc bấm <b>📋 Dán mã vận đơn</b> rồi dán 1 loạt mã (mỗi mã 1 dòng) vào ô chat.\n\n"
        "Mỗi đơn sẽ có nút bật/tắt (☐/☑) và nút 👁️ để xem chi tiết."
    )


def build_bulk_intro_keyboard() -> InlineKeyboardMarkup:
    """Build step 1/3 entry keyboard."""
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("🔍 Tìm đơn", callback_data="bs:search")],
            [InlineKeyboardButton("📋 Dán mã vận đơn", callback_data="bs:paste")],
            [InlineKeyboardButton("❌ Huỷ", callback_data="bs:cancel")],
        ]
    )


def render_bulk_paste_prompt_card() -> str:
    """Render prompt asking user to paste tracking codes."""
    return (
        "🔄 <b>ĐỔI TRẠNG THÁI HÀNG LOẠT</b>\n"
        "📋 <b>DÁN MÃ VẬN ĐƠN</b>\n"
        f"{DIVIDER}\n"
        "Bác hãy dán danh sách mã vận đơn vào ô chat, mỗi mã một dòng.\n\n"
        "Ví dụ:\n"
        "<code>GHN123456</code>\n"
        "<code>VN987654321</code>\n\n"
        "<i>(Hết hạn sau 5 phút)</i>"
    )


def build_bulk_paste_prompt_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("⬅️ Quay lại", callback_data="bs:start"),
                InlineKeyboardButton("❌ Huỷ", callback_data="bs:cancel"),
            ]
        ]
    )


def render_bulk_pick_card(
    orders: Sequence[Order],
    selected_ids: set[int],
    page: int,
    total_pages: int,
    total_orders: int,
    query_display: str | None = None,
    missing_codes: Sequence[str] | None = None,
) -> str:
    """Render paginated order picker card with detailed summaries."""
    q_str = f"Tìm theo: '{html.escape(query_display)}' — " if query_display else ""
    lines = [
        "🔄 <b>ĐỔI TRẠNG THÁI HÀNG LOẠT</b>",
        f"<i>Bước 1/3 — {q_str}{total_orders} đơn (Trang {page}/{total_pages})</i>",
        DIVIDER,
    ]

    if missing_codes:
        esc_missing = ", ".join(f"<code>{html.escape(c)}</code>" for c in missing_codes[:5])
        extra = f" (+{len(missing_codes) - 5} mã khác)" if len(missing_codes) > 5 else ""
        lines.append(f"⚠️ <b>Không tìm thấy mã:</b> {esc_missing}{extra}\n")

    if not orders:
        lines.append("<i>Không có đơn nào để hiển thị.</i>")
    else:
        for o in orders:
            mark = "☑" if o.id in selected_ids else "☐"
            st_label = STATUS_NAMES.get(o.status, o.status.value)
            tot = f"{o.total_amount:,} đ".replace(",", ".")
            phone = (
                f"<code>{html.escape(o.customer_phone)}</code>"
                if o.customer_phone
                else "<i>(Chưa có SĐT)</i>"
            )
            track = (
                f" · Mã: <code>{html.escape(o.tracking_code)}</code>"
                if o.tracking_code
                else ""
            )
            lines.append(
                f"{mark} <b>#{o.id} · {html.escape(o.customer_name)}{_returning_marker(o)}</b>\n"
                f"   📞 {phone} · 💰 {tot} · {st_label}{track}"
            )

    lines.append(DIVIDER)
    count = len(selected_ids)
    lines.append(f"Đã chọn: <b>{count} đơn</b> (tối đa 20)")
    lines.append("Bác bấm nút để chọn/bỏ chọn, hoặc bấm 👁️ để xem chi tiết:")
    return "\n".join(lines)


def build_bulk_pick_keyboard(
    orders: Sequence[Order],
    selected_ids: set[int],
    page: int,
    total_pages: int,
) -> InlineKeyboardMarkup:
    """Build picker keyboard with toggle + detail button per order."""
    buttons: list[list[InlineKeyboardButton]] = []

    for o in orders:
        if o.id is None:
            continue
        checked = o.id in selected_ids
        btn_label = _format_bulk_button_label(o, checked)
        buttons.append(
            [
                InlineKeyboardButton(btn_label, callback_data=f"bs:t:{o.id}"),
                InlineKeyboardButton("👁️", callback_data=f"bs:v:{o.id}"),
            ]
        )

    # Pagination row
    if total_pages > 1:
        nav_row: list[InlineKeyboardButton] = []
        if page > 1:
            nav_row.append(InlineKeyboardButton("⬅️ Trước", callback_data=f"bs:pg:{page - 1}"))
        nav_row.append(InlineKeyboardButton(f"{page}/{total_pages}", callback_data="ord_noop"))
        if page < total_pages:
            nav_row.append(InlineKeyboardButton("Sau ➡️", callback_data=f"bs:pg:{page + 1}"))
        buttons.append(nav_row)

    # Next action
    count = len(selected_ids)
    buttons.append(
        [
            InlineKeyboardButton(
                f"➡️ Tiếp tục ({count} đơn)",
                callback_data="bs:next",
            )
        ]
    )

    # Utilities
    buttons.append(
        [
            InlineKeyboardButton("🔍 Tìm lại", callback_data="bs:search"),
            InlineKeyboardButton("📋 Dán mã khác", callback_data="bs:paste"),
            InlineKeyboardButton("❌ Huỷ", callback_data="bs:cancel"),
        ]
    )
    return InlineKeyboardMarkup(buttons)


def render_bulk_status_card(selected_orders: Sequence[Order]) -> str:
    """Render step 2/3 status selection card."""
    count = len(selected_orders)
    id_list = ", ".join(f"#{o.id}" for o in selected_orders[:10])
    if count > 10:
        id_list += f" (+{count - 10} đơn nữa)"
    return (
        "🔄 <b>ĐỔI TRẠNG THÁI HÀNG LOẠT</b>\n"
        f"<i>Bước 2/3 — Chọn trạng thái MỚI cho {count} đơn ({id_list})</i>\n"
        f"{DIVIDER}\n"
        "Bác chạm vào trạng thái muốn chuyển sang:"
    )


def build_bulk_status_keyboard() -> InlineKeyboardMarkup:
    """Build step 2/3 status keyboard (8 statuses).
    First row has common end states, followed by 2-column lifecycle."""
    buttons: list[list[InlineKeyboardButton]] = [
        [
            InlineKeyboardButton("✅ Đã giao", callback_data=f"bs:st:{OrderStatus.DA_GIAO.value}"),
            InlineKeyboardButton("🚚 Shipper đã lấy", callback_data=f"bs:st:{OrderStatus.SHIPPER_DA_LAY.value}"),
        ],
        [
            InlineKeyboardButton("📦 Đã đóng gói", callback_data=f"bs:st:{OrderStatus.DA_DONG_GOI.value}"),
            InlineKeyboardButton("📑 Đã tạo đơn", callback_data=f"bs:st:{OrderStatus.DA_TAO_DON.value}"),
        ],
        [
            InlineKeyboardButton("⏳ Chờ làm", callback_data=f"bs:st:{OrderStatus.CHO_LAM.value}"),
            InlineKeyboardButton("🛠️ Đang làm", callback_data=f"bs:st:{OrderStatus.DANG_LAM.value}"),
        ],
        [
            InlineKeyboardButton("🚫 Bom hàng", callback_data=f"bs:st:{OrderStatus.BOM_HANG.value}"),
            InlineKeyboardButton("❌ Huỷ đơn", callback_data=f"bs:st:{OrderStatus.HUY_DON.value}"),
        ],
        [
            InlineKeyboardButton("⬅️ Quay lại chọn đơn", callback_data="bs:back:1"),
            InlineKeyboardButton("❌ Huỷ", callback_data="bs:cancel"),
        ],
    ]
    return InlineKeyboardMarkup(buttons)


def render_bulk_confirm_card(
    orders: Sequence[Order],
    target_status: OrderStatus,
) -> str:
    """Render step 3/3 confirmation card."""
    target_label = STATUS_NAMES.get(target_status, target_status.value)
    lines = [
        "🔄 <b>ĐỔI TRẠNG THÁI HÀNG LOẠT</b>",
        f"<i>Bước 3/3 — Xác nhận đổi {len(orders)} đơn</i>",
        DIVIDER,
        f"➡️ <b>TRẠNG THÁI MỚI:</b> <b>{target_label}</b>\n",
        "<b>Danh sách đơn sẽ đổi:</b>",
    ]
    for o in orders[:15]:
        cur_label = STATUS_NAMES.get(o.status, o.status.value)
        lines.append(
            f"• <b>#{o.id}</b> · {html.escape(o.customer_name)}: {cur_label} → <b>{target_label}</b>"
        )
    if len(orders) > 15:
        lines.append(f"• <i>...và {len(orders) - 15} đơn khác nữa</i>")

    lines.append(DIVIDER)
    lines.append("⚠️ Bác kiểm tra kỹ rồi bấm <b>Xác nhận</b> nhé (không tự hoàn tác được).")
    return "\n".join(lines)


def build_bulk_confirm_keyboard() -> InlineKeyboardMarkup:
    """Build step 3/3 confirmation keyboard."""
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("✅ Xác nhận đổi", callback_data="bs:cf"),
            ],
            [
                InlineKeyboardButton("⬅️ Chọn trạng thái khác", callback_data="bs:back:2"),
                InlineKeyboardButton("❌ Huỷ", callback_data="bs:cancel"),
            ],
        ]
    )


def render_bulk_done_card(
    orders: Sequence[Order],
    target_status: OrderStatus,
) -> str:
    """Render completion card."""
    target_label = STATUS_NAMES.get(target_status, target_status.value)
    lines = [
        f"✅ <b>ĐÃ ĐỔI XONG {len(orders)} ĐƠN</b>",
        f"Trạng thái mới: <b>{target_label}</b>",
        DIVIDER,
    ]
    for o in orders[:15]:
        lines.append(f"• <b>#{o.id}</b> · {html.escape(o.customer_name)}")
    if len(orders) > 15:
        lines.append(f"• <i>...và {len(orders) - 15} đơn khác</i>")
    lines.append(DIVIDER)
    lines.append("Bác có thể tiếp tục công việc bình thường nhé!")
    return "\n".join(lines)


def build_bulk_done_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("🔄 Đổi đợt khác", callback_data="bs:start"),
            ]
        ]
    )

