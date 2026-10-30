"""Static tutorial content for elderly-friendly bot help.

Pure data + render module: no handler or DB imports (avoids import cycles).
"""

from telegram import InlineKeyboardButton, InlineKeyboardMarkup

from src.bot.keyboards import DIVIDER

TUTORIAL_PAGES: list[dict] = [
    {
        "title": "❓ <b>HƯỚNG DẪN SỬ DỤNG BOT</b>",
        "body": (
            "Bác chỉ cần chạm vào các nút to trên màn hình.\n"
            "1. 📦 Đơn hôm nay - xem đơn trong ngày.\n"
            "2. ⏳ Đơn chờ làm - xem đơn đang chờ làm.\n"
            "3. 📋 Xem theo ngày - xem đơn ngày trước.\n"
            "4. ✏️ Sửa đơn - sửa đơn bằng câu nói thường.\n"
            "5. 🔍 Tra cứu đơn - tìm đơn bằng câu nói thường.\n"
            "6. Gửi tin nhắn đặt hàng bất kỳ - bot tự nhận là đơn mới."
        ),
        "try_kind": None,
    },
    {
        "title": "⏳ <b>ĐƠN CHỜ LÀM</b>",
        "body": (
            "1. Bấm nút ⏳ Đơn chờ làm.\n"
            "2. Bot hiện danh sách đơn chờ làm, gom theo ngày tạo.\n"
            "3. Chạm chip ⏳/🛠️/📦 ở cuối để lọc trạng thái khác."
        ),
        "try_kind": "pending_orders",
    },
    {
        "title": "📦 <b>XEM ĐƠN HÔM NAY</b>",
        "body": (
            "1. Bấm nút 📦 Đơn hôm nay.\n"
            "2. Bot hiện danh sách đơn trong ngày.\n"
            "3. Chạm nút 👁️ Xem đơn #... để xem chi tiết."
        ),
        "try_kind": "today_orders",
    },
    {
        "title": "📋 <b>XEM ĐƠN NGÀY KHÁC</b>",
        "body": (
            "1. Bấm nút 📋 Xem theo ngày.\n"
            "2. Chọn Hôm qua hoặc một ngày trong danh sách.\n"
            "3. Chạm nút xem đơn để xem chi tiết."
        ),
        "try_kind": "date_picker",
    },
    {
        "title": "🔍 <b>TRA CỨU ĐƠN</b>",
        "body": (
            "1. Bấm nút 🔍 Tra cứu đơn.\n"
            "2. Gõ câu tự nhiên, ví dụ: tìm đơn anh Tuấn.\n"
            "3. Bấm nút xem đơn trong kết quả."
        ),
        "try_kind": "search",
    },
    {
        "title": "📋 <b>CHẠM ĐỂ COPY</b>",
        "body": (
            "1. Mở chi tiết một đơn hàng.\n"
            "2. Chạm nút 📋 Copy SĐT hoặc 📍 Copy Địa chỉ.\n"
            "3. Dán sang app vận chuyển."
        ),
        "try_kind": None,
    },
]

PAGE_COUNT = len(TUTORIAL_PAGES)


def _clamp_page(page: int) -> int:
    """Keep a requested page inside the valid range."""
    return min(max(page, 0), PAGE_COUNT - 1)


def build_tutorial_keyboard(page: int) -> InlineKeyboardMarkup:
    """Build one-button-per-row navigation keyboard for easy tapping."""
    idx = _clamp_page(page)
    try_kind = TUTORIAL_PAGES[idx]["try_kind"]

    rows: list[list[InlineKeyboardButton]] = []
    if try_kind:
        rows.append(
            [InlineKeyboardButton("▶️ Thử ngay", callback_data=f"help:try:{try_kind}")]
        )
    if idx > 0:
        rows.append(
            [InlineKeyboardButton("⬅️ Quay lại", callback_data=f"help:page:{idx - 1}")]
        )
    rows.append(
        [InlineKeyboardButton(f"Trang {idx + 1}/{PAGE_COUNT}", callback_data="help:noop")]
    )
    if idx < PAGE_COUNT - 1:
        rows.append(
            [InlineKeyboardButton("Tiếp ➡️", callback_data=f"help:page:{idx + 1}")]
        )
    return InlineKeyboardMarkup(rows)


def render_tutorial_page(page: int) -> tuple[str, InlineKeyboardMarkup]:
    """Render one tutorial page (text is static, no user input interpolated)."""
    idx = _clamp_page(page)
    item = TUTORIAL_PAGES[idx]
    hint = (
        "Bác bấm Tiếp để xem bước sau nhé."
        if idx < PAGE_COUNT - 1
        else "Hết hướng dẫn. Bác bấm Thử ngay để làm luôn nhé!"
    )
    text = (
        f"{item['title']}\n"
        f"Trang {idx + 1}/{PAGE_COUNT}\n"
        f"{DIVIDER}\n"
        f"{item['body']}\n"
        f"{DIVIDER}\n"
        f"{hint}"
    )
    return text, build_tutorial_keyboard(idx)
