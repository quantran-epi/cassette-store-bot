# Phase 3: Ergonomic Order Management & Low-Tech Actions - Research

**Researched:** 2026-10-24
**Domain:** Telegram Bot UI/UX (Reply & Inline Keyboards), CopyTextButton API, Order Lifecycle FSM, Async SQLite Pagination
**Confidence:** HIGH

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

- **D-01: Reply Keyboard cố định dưới màn hình bố trí 2x2 nút to, dễ bấm cho người già:**
  - Hàng 1: `[📦 Đơn hôm nay]` `[📋 Xem theo ngày]`
  - Hàng 2: `[📝 Nhập đơn mới]` `[❓ Trợ giúp]`
  - Người dùng bấm nút là kích hoạt ngay, không bắt buộc nhớ hay gõ các lệnh slash `/`.
- **D-02: Xem đơn theo ngày:**
  - Khi bấm `[📋 Xem theo ngày]`, bot phản hồi bằng tin nhắn kèm các nút Inline bấm nhanh: `[Hôm nay]`, `[Hôm qua]`, và danh sách 3-5 ngày gần nhất để chạm chọn ngày xem ngay mà không phải gõ cú pháp ngày tháng phức tạp.
- **D-03: Phân trang danh sách đơn hàng:**
  - Hiển thị gọn 5 đơn/trang. Mỗi đơn tóm tắt 2-3 dòng (Mã đơn `#ID`, Tên khách, Tổng tiền, Trạng thái đơn) kèm nút Inline `[Xem đơn #ID]` ngay dưới để mở thẻ chi tiết.
  - Hàng nút điều hướng phân trang ở cuối tin nhắn: `[⬅️ Trước]` `[Trang X/Y]` `[Sau ➡️]`.
- **D-04: Xử lý danh sách đơn trống:**
  - Khi ngày được chọn không có đơn hàng nào, bot thông báo thân thiện: *"Ngày này chưa có đơn hàng nào bác nhé!"* kèm nút bấm nhanh `[📝 Nhập đơn mới]`.
- **D-05: Cơ chế sao chép 1 chạm thông tin khách để dán vào app ship (GHTK/GHN/ViettelPost):**
  - Kết hợp 2 tầng:
    1. Bọc Số điện thoại, Địa chỉ nhận hàng, Mã vận đơn trong thẻ HTML `<code>...</code>` (người dùng chạm tay vào chữ trên điện thoại là copy ngay vào clipboard).
    2. Cung cấp các nút Inline chuyên dụng sử dụng `CopyTextButton` của Telegram Bot API 7.3+ (ví dụ: `[📋 Copy SĐT]`, `[📍 Copy Địa chỉ]`, `[🚚 Copy Mã vận đơn]`) để người già dễ bấm.
- **D-06: Bố cục đổi trạng thái vòng đời đơn:**
  - Dưới thẻ chi tiết hiển thị 1 nút to nổi bật gợi ý bước kế tiếp tự nhiên theo luồng (ví dụ: đang ở `CHO_LAM` -> gợi ý nút `[▶️ Bắt đầu làm]`).
  - Kèm 1 nút phụ `[🔄 Đổi trạng thái khác]` để mở rộng menu chọn bất kỳ trạng thái nào trong 8 trạng thái.
- **D-07: Xác nhận với trạng thái nhạy cảm:**
  - Các trạng thái thông thường (`DANG_LAM`, `DA_DONG_GOI`, `DA_TAO_DON`, `SHIPPER_DA_LAY`, `DA_GIAO`) đổi ngay tức thì 1 chạm.
  - Riêng 2 trạng thái nhạy cảm/kết thúc đơn có tổn thất (`BOM_HANG`, `HUY_DON`): Bot hiển thị bước hỏi xác nhận kèm 2 nút `[⚠️ Xác nhận]` và `[Quay lại]` để tránh người già chạm nhầm.
- **D-08: Phản hồi khi đổi trạng thái:**
  - Chỉnh sửa trực tiếp tin nhắn thẻ hiện tại (`edit_message_text`), không gửi tin nhắn mới làm trôi màn hình.
  - Hiển thị popup toast alert ngắn gọn trên Telegram (`query.answer(text="✅ Đã chuyển sang: ...")`) và bọc try/catch chống lỗi `telegram.error.BadRequest: Message is not modified`.
- **D-09: Quy trình nhập mã vận đơn đối tác ship:**
  - Trên thẻ chi tiết có nút `[🚚 Nhập/Đổi mã vận đơn]`. Khi bấm, bot gửi tin nhắn hướng dẫn: *"Bác gửi mã vận đơn (hoặc dán ảnh biên lai ship) cho đơn này nhé:"* kèm nút Inline `[❌ Huỷ bỏ]`.
  - Bot chờ tin nhắn text từ người dùng, cập nhật `tracking_code` vào DB cho đơn hàng đó và cập nhật lại thẻ chi tiết.
- **D-10: Xem lại ảnh đính kèm:**
  - Thẻ chi tiết hiển thị dòng: `📷 Ảnh đính kèm: N ảnh`.
  - Nếu có ảnh, hiển thị nút Inline `[🖼️ Xem N ảnh]`. Khi bấm, bot gửi Album ảnh bằng `send_media_group` (sử dụng các `file_id` Telegram đã lưu trong DB) kèm nút `[Quay lại thẻ đơn]`.
- **D-11: Bổ sung ảnh cho đơn đã lưu:**
  - Trên thẻ chi tiết có nút `[➕ Gửi thêm ảnh]`. Khi bấm, bot kích hoạt trạng thái chờ ảnh. Người dùng gửi 1 hoặc nhiều ảnh, bot tự động lấy `photo.file_id` append vào `photo_file_ids` của đơn trong DB via `append_order_photos()`.
- **D-12: Thoát trạng thái chờ (Cancel & Timeout):**
  - Mọi trạng thái chờ nhập (chờ mã vận đơn, chờ gửi ảnh) luôn đi kèm nút Inline `[❌ Huỷ bỏ thao tác]` trong tin nhắn hướng dẫn và tự động hủy sau 2 phút nếu không có thao tác để tránh kẹt bot.

### Claude's Discretion

- Định dạng thẻ chi tiết đơn hàng HTML thoáng mắt, font số điện thoại/địa chỉ rõ ràng, emoji tương ứng từng trường.
- Mapping tiếng Việt chuẩn cho 8 trạng thái enum `OrderStatus`:
  - `CHO_LAM`: ⏳ Chờ làm
  - `DANG_LAM`: 🛠️ Đang làm
  - `DA_DONG_GOI`: 📦 Đã đóng gói
  - `DA_TAO_DON`: 📑 Đã tạo đơn ship
  - `SHIPPER_DA_LAY`: 🚚 Shipper đã lấy
  - `DA_GIAO`: ✅ Đã giao thành công
  - `BOM_HANG`: 🚫 Bom hàng
  - `HUY_DON`: ❌ Đã huỷ đơn

### Deferred Ideas (OUT OF SCOPE)

- Tra cứu đơn hàng bằng câu chat tự nhiên tiếng Việt (VD: *"tìm đơn của anh Tuấn ở Hà Nội"*): Thuộc phạm vi của Phase 4 (Yêu cầu SEARCH-01, SEARCH-02).
- Tự động đồng bộ trạng thái đơn từ webhook/API của hãng ship GHTK/GHN: Thuộc v2.
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| **DATA-05** | Nhập và cập nhật mã vận đơn cho đơn hàng cụ thể. | `src/db/orders.py:93-107` đã có `update_order_tracking()`. Handler quản lý trạng thái chờ nhập mã vận đơn, kiểm tra timeout 120s, và cập nhật DB. |
| **UI-01** | 100% tính năng vận hành trên giao diện chat Telegram thông qua Inline Buttons và Reply Keyboard. | Bố trí 2 tầng bàn phím: Reply Keyboard 2x2 cố định dưới màn hình và Inline Keyboards điều hướng phân trang, xem chi tiết, đổi trạng thái. |
| **UI-02** | Menu phím bấm to, cố định dưới khung chat (Reply Keyboard) cho các thao tác chính: Đơn hôm nay, Xem theo ngày, Nhập đơn mới, Trợ giúp. | `ReplyKeyboardMarkup` với `resize_keyboard=True` và `is_persistent=True` gửi kèm `/start` và cập nhật sau các thao tác. |
| **UI-03** | Liệt kê danh sách đơn theo ngày: Hôm nay, Hôm qua, hoặc ngày cụ thể tuỳ chọn bằng nút bấm. | Thêm `list_orders_by_date()` và `count_orders_by_date()` trong SQLite dùng hàm `date(created_at, '+7 hours') = ?` chuẩn giờ Việt Nam; bàn phím chọn ngày Inline nhanh. |
| **UI-04** | Thẻ chi tiết đơn hàng cung cấp các nút bấm Inline "Sao chép nhanh" 1 chạm (`CopyTextButton` / định dạng code mono) để copy SĐT, Địa chỉ, Mã vận đơn. | Kết hợp thẻ `<code>...</code>` và `InlineKeyboardButton(..., copy_text=CopyTextButton(text=...))` của Telegram Bot API 7.3+ (PTB 22.8). |
| **UI-05** | Đổi trạng thái đơn hàng trực tiếp bằng 1 chạm thông qua danh sách nút bấm Inline trạng thái tương ứng. | Gợi ý bước kế tiếp 1 chạm + menu đầy đủ 8 trạng thái; modal xác nhận 2 bước cho trạng thái nhạy cảm `BOM_HANG` và `HUY_DON`; `edit_message_text` kèm toast alert. |
| **UI-06** | Xem lại danh sách ảnh đã đính kèm của đơn hàng trong Telegram chat (dưới dạng media group hoặc từng ảnh) và nút thêm ảnh mới cho đơn. | Dùng `send_media_group` (khi có 2-10 ảnh) hoặc `send_photo` (khi 1 ảnh) từ `file_id` lưu trong DB; hỗ trợ gửi thêm ảnh via `append_order_photos()`. |
</phase_requirements>

## Summary

Phase 3 hoàn thiện toàn bộ tầng quản trị đơn hàng hàng ngày dành riêng cho người lớn tuổi / low-tech. 100% trải nghiệm diễn ra qua các nút bấm kích thước lớn trên Telegram mà không đòi hỏi người dùng gõ lệnh hay biểu mẫu phức tạp.

Hệ thống kết hợp:
1. **Reply Keyboard cố định (2x2)** ghim sát bàn phím điện thoại để truy cập nhanh: `[📦 Đơn hôm nay]`, `[📋 Xem theo ngày]`, `[📝 Nhập đơn mới]`, `[❓ Trợ giúp]`.
2. **Inline Pagination (5 đơn/trang)** hiển thị đơn theo ngày giờ Việt Nam (UTC+7).
3. **Thẻ chi tiết đơn hàng tích hợp 1-Tap Copy** qua `CopyTextButton` và HTML `<code>` mono text để dán sang app ship GHTK/GHN/ViettelPost.
4. **Vòng đời đơn hàng 8 trạng thái** với nút gợi ý bước tiếp theo và cơ chế xác nhận chống bấm nhầm cho `BOM_HANG` / `HUY_DON`.
5. **Quản lý mã vận đơn và xem/bổ sung album ảnh** qua cơ chế state timeout 120s an toàn không gây nghẽn bot.

**Primary recommendation:** Sử dụng cơ chế routing tin nhắn Reply Keyboard tách biệt trước bộ phân giải LLM, áp dụng tính toán múi giờ Việt Nam `date(created_at, '+7 hours')` trực tiếp trong SQLite, và dùng `context.user_data["action_state"]` kèm timestamp hết hạn 120s để xử lý nhập tracking/ảnh mượt mà, không gặp rủi ro cảnh báo/xung đột của `ConversationHandler`.

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Reply Keyboard 2x2 | Telegram UI Client | Bot Dispatcher (`src/bot/keyboards.py`) | Reply keyboard được client render cố định; bot gửi markup qua `/start` hoặc phản hồi. |
| Ingestion Message Routing | Bot Dispatcher (`src/bot/app.py`) | Ingest Handler (`src/bot/handlers/ingest.py`) | Regex filter phân loại các nút Reply Keyboard (`📦 Đơn hôm nay`, v.v.) trước khi gửi tới LLM extractor. |
| Date Query & Pagination | Database Tier (`src/db/orders.py`) | Order Handler (`src/bot/handlers/orders.py`) | SQLite thực hiện lọc ngày giờ VN (UTC+7) và `LIMIT 5 OFFSET ?`, bot render inline pagination. |
| 1-Tap Copy UX | Telegram Native API | Bot Formatter (`src/bot/keyboards.py`) | `CopyTextButton` (Telegram Bot API 7.3+) copy thẳng vào clipboard trên client mà không cần bot xử lý thêm. |
| Order Lifecycle FSM | Business Logic (`src/models/order.py`) | Action Handler (`src/bot/handlers/order_actions.py`) | Kiểm tra chuyển trạng thái hợp lệ, phân loại trạng thái nhạy cảm cần xác nhận 2 bước. |
| Photo Album Presentation | Telegram Media API | Action Handler (`src/bot/handlers/order_actions.py`) | Sử dụng `send_media_group` cho 2-10 ảnh hoặc `send_photo` cho 1 ảnh qua `file_id` đã lưu. |

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| **python-telegram-bot** | `22.8` | Telegram Bot Framework | [VERIFIED: in-repo .venv] Đã cài đặt, hỗ trợ native `CopyTextButton`, `send_media_group`, `InputMediaPhoto`, async `edit_message_text`. |
| **aiosqlite** | `0.22.1` | Async SQLite database | [VERIFIED: in-repo .venv] Đã cài đặt, hỗ trợ WAL mode, query `date(created_at, '+7 hours')`. |
| **pydantic** | `2.14.1` | Domain validation | [VERIFIED: in-repo .venv] Đã cài đặt, quản lý model `Order` và `OrderStatus`. |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| **datetime** (stdlib) | `3.11+` | Xử lý ngày tháng và múi giờ | Dùng `datetime.timezone(timedelta(hours=7))` để tính ngày hiện tại tại Việt Nam mà không cần cài thêm `pytz`. |
| **html** (stdlib) | `3.11+` | Escape text an toàn | Escape tên khách, địa chỉ, hàng hoá trước khi chèn vào HTML message. |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| `context.user_data["action_state"]` | `ConversationHandler` | `ConversationHandler` phát sinh `PTBUserWarning: If per_message=False...` khi kết hợp CallbackQuery entry point với MessageHandler, và có nguy cơ kẹt bot nếu người dùng bấm nút Reply Keyboard ngoài menu. Dùng `action_state` với timestamp hết hạn 120s đơn giản hơn, dễ test hơn, không bị kẹt. |
| SQLite `date(created_at, '+7 hours')` | Python-side date filtering | Filter phía Python phải đọc toàn bộ record vào RAM rồi mới lọc, gây chậm khi DB có hàng nghìn đơn. SQLite index và hàm date xử lý ngay trên đĩa cực nhanh. |

**Installation:**
Không cần cài thêm thư viện ngoài nào. Tất cả dependencies cần thiết đã có sẵn trong virtual environment của dự án.

## Package Legitimacy Audit

Không có package mới nào được cài đặt trong Phase 3. 100% chức năng dựa trên các thư viện đã được cài đặt và kiểm tra từ Phase 1 và 2.

| Package | Registry | Age | Downloads | Source Repo | Verdict | Disposition |
|---------|----------|-----|-----------|-------------|---------|-------------|
| `python-telegram-bot` | PyPI | > 8 yrs | verified in Phase 1 | github.com/python-telegram-bot/python-telegram-bot | [OK] | Đã cài (`22.8`) |
| `aiosqlite` | PyPI | > 5 yrs | verified in Phase 1 | github.com/omnilib/aiosqlite | [OK] | Đã cài (`0.22.1`) |
| `pydantic` | PyPI | > 7 yrs | verified in Phase 1 | github.com/pydantic/pydantic | [OK] | Đã cài (`2.14.1`) |

**Packages removed due to [SLOP] verdict:** none
**Packages flagged as suspicious [SUS]:** none

## Architecture Patterns

### System Architecture Diagram

```
[User on Telegram Mobile / Desktop]
     │
     ├── 1. Click Reply Keyboard Button [📦 Đơn hôm nay / 📋 Xem theo ngày]
     │       │
     │       ▼
     │   [src/bot/handlers/orders.py] ◄── Router intercepts menu labels
     │       │
     │       ├── Query orders by VN date (UTC+7) ──► [src/db/orders.py] ──► SQLite DB
     │       │
     │       ▼
     │   Reply with Order List Card (5 orders/page) + Inline Navigation [⬅️ X/Y ➡️]
     │
     ├── 2. Click Inline Button [Xem đơn #ID]
     │       │
     │       ▼
     │   [src/bot/handlers/orders.py]
     │       │
     │       ▼
     │   Render Detail Card with:
     │   - Mono HTML <code> tags
     │   - Telegram Bot API 7.3+ CopyTextButtons (SĐT, Địa chỉ, Mã vận đơn)
     │   - Natural Next Step Button (e.g. [▶️ Bắt đầu làm])
     │   - Action Buttons ([🚚 Nhập Vận Đơn], [🖼️ Xem N ảnh], [➕ Thêm ảnh], [🔄 Đổi trạng thái])
     │
     ├── 3. Click [▶️ Đổi trạng thái] / [🔄 Menu trạng thái]
     │       │
     │       ▼
     │   [src/bot/handlers/order_actions.py]
     │       │
     │       ├── Normal status (1-tap): update DB, edit_message_text, query.answer() toast
     │       └── Sensitive status (BOM_HANG / HUY_DON): prompt confirm modal [⚠️ Xác nhận] / [Quay lại]
     │
     └── 4. Click [🚚 Nhập mã vận đơn] or [➕ Thêm ảnh]
             │
             ▼
         Set context.user_data["action_state"] (expires in 120s)
             │
             ├── User sends Text ──► Update tracking_code in DB ──► Refresh Detail Card
             ├── User sends Photo ─► Append photo_file_id in DB ──► Confirm to user
             └── User clicks [❌ Huỷ bỏ] or Timeout 120s ──────────► Clear action_state
```

### Recommended Project Structure
```
src/
├── bot/
│   ├── app.py                 # Registration & handler pipeline ordering
│   ├── keyboards.py           # Reply & Inline keyboard builders (CopyTextButton, Pagination, Status)
│   ├── handlers/
│   │   ├── base.py            # /start (sends 2x2 Reply Keyboard), /ping
│   │   ├── callbacks.py       # Phase 2 order draft confirmation callbacks
│   │   ├── ingest.py          # LLM ingestion handlers (checks action_state before LLM)
│   │   ├── orders.py          # NEW: Today orders, date picker, paginated list, detail card
│   │   └── order_actions.py   # NEW: Status changes, tracking input, photo view/add, cancels
├── db/
│   ├── orders.py              # NEW QUERIES: list_orders_by_date, count_orders_by_date
│   └── schema.py              # Existing schema (verified)
└── models/
    └── order.py               # Order domain model & OrderStatus enum (verified)
```

### Pattern 1: Reply Keyboard Interception Before LLM Extractor
**What:** Khi người già bấm nút Reply Keyboard (`[📦 Đơn hôm nay]`), Telegram gửi text `"📦 Đơn hôm nay"`. Nếu để `MessageHandler(filters.TEXT & ~filters.COMMAND)` bắt tự do, text này sẽ bị đẩy vào LLM extractor gây lãng phí token và hiểu sai thành đơn hàng.
**When to use:** Luôn luôn đăng ký MessageHandler với Regex filter cho menu trước handler nhận tin nhắn đặt hàng.
**Example:**
```python
# In src/bot/app.py
from telegram.ext import MessageHandler, filters

MENU_BUTTON_REGEX = r"^(📦 Đơn hôm nay|📋 Xem theo ngày|📝 Nhập đơn mới|❓ Trợ giúp)$"

# Register BEFORE general text order handler:
app.add_handler(
    MessageHandler(filters.Regex(MENU_BUTTON_REGEX), handle_main_menu_text),
    group=0,
)
app.add_handler(
    MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text_order),
    group=0,
)
```

### Pattern 2: Dual-Tier 1-Tap Copy UX for Elderly Users
**What:** Người già thường run tay hoặc khó thao tác bôi đen chọn chữ trên màn hình cảm ứng. Kết hợp thẻ HTML `<code>` (chạm vào chữ để copy trên Telegram mobile) và nút Inline `CopyTextButton` (1 chạm to rõ ràng).
**When to use:** Thẻ chi tiết đơn hàng cho SĐT, Địa chỉ, Mã vận đơn.
**Example:**
```python
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, CopyTextButton

# 1. In HTML text:
# 📞 <b>SĐT:</b> <code>0912345678</code> (chạm số để copy)
# 📍 <b>Địa chỉ:</b> <code>123 Lê Lợi, P. Bến Thành, Q.1</code>

# 2. In InlineKeyboardMarkup:
keyboard = [
    [
        InlineKeyboardButton("📋 Copy SĐT", copy_text=CopyTextButton(text=order.customer_phone)),
        InlineKeyboardButton("📍 Copy Địa chỉ", copy_text=CopyTextButton(text=order.shipping_address)),
    ]
]
if order.tracking_code:
    keyboard.append([
        InlineKeyboardButton("🚚 Copy Mã vận đơn", copy_text=CopyTextButton(text=order.tracking_code))
    ])
```

### Pattern 3: Sensitive Lifecycle Confirmation
**What:** Chuyển trạng thái thông thường chỉ cần 1 chạm. Trạng thái `BOM_HANG` (bom hàng) và `HUY_DON` (huỷ đơn) là các trạng thái kết thúc gây tổn thất hoặc huỷ bỏ doanh thu, cần xác nhận tránh chạm nhầm.
**When to use:** Khi người dùng chọn trạng thái `BOM_HANG` hoặc `HUY_DON`.
**Example:**
```python
SENSITIVE_STATUSES = {OrderStatus.BOM_HANG, OrderStatus.HUY_DON}

# In status callback:
if target_status in SENSITIVE_STATUSES and not is_confirmed:
    # Render confirmation prompt
    confirm_kb = InlineKeyboardMarkup([
        [
            InlineKeyboardButton(f"⚠️ Xác nhận {STATUS_LABELS[target_status]}", callback_data=f"ord_st_cf:{order_id}:{target_status.value}"),
            InlineKeyboardButton("Quay lại", callback_data=f"ord_v:{order_id}:{date_str}:{page}"),
        ]
    ])
    await query.edit_message_text(
        f"⚠️ <b>XÁC NHẬN CHUYỂN TRẠNG THÁI</b>\n\n"
        f"Bác có chắc chắn muốn chuyển đơn <b>#{order_id}</b> sang trạng thái "
        f"<b>{STATUS_LABELS[target_status]}</b> không?",
        reply_markup=confirm_kb,
        parse_mode="HTML",
    )
    return
```

### Anti-Patterns to Avoid
- **Lồng `ConversationHandler` phức tạp với `CallbackQueryHandler` entry-point:** Dễ phát sinh `PTBUserWarning`, khó unit test và khiến người dùng bị kẹt trạng thái nếu họ nhấn nút menu Reply Keyboard. Dùng `action_state` trong `context.user_data` với expiration check đơn giản, linh hoạt và triệt để hơn.
- **Gửi tin nhắn mới thay vì `edit_message_text`:** Làm trôi màn hình chat, người già phải cuộn tìm lại thẻ đơn cũ rất bất tiện.
- **Không bắt lỗi `Message is not modified`:** Khi người dùng bấm 2 lần liên tiếp vào nút trạng thái hiện tại, Telegram bắn exception làm bot gián đoạn nếu không try/except.
- **Truyền 1 ảnh vào `send_media_group`:** Telegram Bot API quy định `sendMediaGroup` phải có 2-10 items. Nếu có đúng 1 ảnh mà gọi `send_media_group` sẽ bị lỗi `BadRequest`. Phải gọi `send_photo` cho trường hợp 1 ảnh.

## In-Repo Values Verbatim Quotation

Tuân thủ quy tắc In-repo value provenance:

1. **`OrderStatus` enum:** [VERIFIED: src/models/order.py:7-17]
```python
class OrderStatus(str, Enum):
    """Order lifecycle status enum (8 states)."""

    CHO_LAM = "CHO_LAM"
    DANG_LAM = "DANG_LAM"
    DA_DONG_GOI = "DA_DONG_GOI"
    DA_TAO_DON = "DA_TAO_DON"
    SHIPPER_DA_LAY = "SHIPPER_DA_LAY"
    DA_GIAO = "DA_GIAO"
    BOM_HANG = "BOM_HANG"
    HUY_DON = "HUY_DON"
```

2. **`Order` model:** [VERIFIED: src/models/order.py:20-37]
```python
class Order(BaseModel):
    """Order domain model storing customer snapshot, items text, and lifecycle status."""

    id: int | None = None
    customer_id: int | None = None
    customer_name: str
    customer_phone: str
    shipping_address: str
    items_text: str
    total_amount: int = 0
    cod_amount: int = 0
    payment_method: str = "COD"
    status: OrderStatus = OrderStatus.CHO_LAM
    tracking_code: str | None = None
    photo_file_ids: list[str] = Field(default_factory=list)
    raw_text: str = ""
    created_at: datetime | None = None
    updated_at: datetime | None = None
```

3. **`orders` table schema:** [VERIFIED: src/db/schema.py:26-55]
```sql
        CREATE TABLE IF NOT EXISTS orders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            customer_id INTEGER,
            customer_name TEXT NOT NULL,
            customer_phone TEXT NOT NULL,
            shipping_address TEXT NOT NULL,
            items_text TEXT NOT NULL,
            total_amount INTEGER NOT NULL DEFAULT 0,
            cod_amount INTEGER NOT NULL DEFAULT 0,
            payment_method TEXT NOT NULL DEFAULT 'COD',
            status TEXT NOT NULL DEFAULT 'CHO_LAM' CHECK (
                status IN (
                    'CHO_LAM',
                    'DANG_LAM',
                    'DA_DONG_GOI',
                    'DA_TAO_DON',
                    'SHIPPER_DA_LAY',
                    'DA_GIAO',
                    'BOM_HANG',
                    'HUY_DON'
                )
            ),
            tracking_code TEXT,
            photo_file_ids TEXT NOT NULL DEFAULT '[]',
            raw_text TEXT NOT NULL DEFAULT '',
            created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (customer_id) REFERENCES customers(id) ON DELETE SET NULL
        );
```

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Copy text vào clipboard trên điện thoại | Bắt người dùng bôi đen hoặc gửi tin nhắn riêng chứa số điện thoại | `CopyTextButton` (Telegram Bot API 7.3+) và thẻ `<code>` | Telegram client tự động copy khi bấm/chạm, không cần thêm code xử lý callback phía bot. |
| Timezone conversion phức tạp | Cài đặt `pytz` hoặc `zoneinfo` với dependency tzdata bên ngoài | `datetime.timezone(timedelta(hours=7))` của Python stdlib | Việt Nam có múi giờ cố định UTC+7 không có Daylight Saving Time. Stdlib xử lý gọn nhẹ và chính xác 100%. |
| Lọc ngày theo giờ Việt Nam | Đọc toàn bộ đơn vào Python rồi dùng `datetime.strptime` để filter | SQLite `WHERE date(created_at, '+7 hours') = ?` | Tận dụng SQLite engine tối ưu với index `idx_orders_created_at`, cực nhanh và không tốn RAM. |
| Popup thông báo kết quả | Gửi một tin nhắn riêng rồi xoá sau 3 giây | `await query.answer(text="...", show_alert=False)` | Telegram hiển thị toast alert nhỏ gọn ở đỉnh màn hình, tự biến mất, không làm trôi lịch sử chat. |

## Common Pitfalls

### Pitfall 1: Bấm nút Reply Keyboard bị LLM nuốt mất
**What goes wrong:** Người già bấm `[📦 Đơn hôm nay]`, bot không hiện danh sách đơn mà phản hồi: *"Em không nhận diện được đơn hàng từ tin nhắn này. Bác vui lòng gửi lại..."*.
**Why it happens:** Reply Keyboard trong Telegram thực chất gửi tin nhắn văn bản mang nhãn của nút. Nếu `handle_text_order` được đăng ký trước hoặc dùng `filters.TEXT & ~filters.COMMAND`, nó sẽ chặn toàn bộ text và chuyển sang LLM.
**How to avoid:** Đăng ký handler bắt các nhãn Reply Keyboard với `filters.Regex(r"^(📦 Đơn hôm nay|📋 Xem theo ngày|📝 Nhập đơn mới|❓ Trợ giúp)$")` ở vị trí ưu tiên trước `handle_text_order`.
**Warning signs:** Bấm nút menu bot lại gọi OpenAI API.

### Pitfall 2: Callback Data vượt quá giới hạn 64 bytes của Telegram
**What goes wrong:** Telegram API trả về lỗi `BadRequest: Button_data_invalid` khi render keyboard.
**Why it happens:** Telegram giới hạn `callback_data` tối đa 64 bytes UTF-8. Nếu nhét format dài như `order_action:view_order_detail_by_id:12345:2026-10-24:page_1`, độ dài vượt quá 64 bytes.
**How to avoid:** Dùng tiền tố ngắn gọn chuẩn hóa:
- `ord_dt:YYYY-MM-DD` (17 bytes)
- `ord_pg:YYYY-MM-DD:PAGE` (20 bytes)
- `ord_v:ID:YYYY-MM-DD:PAGE` (25 bytes)
- `ord_st:ID:STATUS` (20 bytes)
- `ord_st_cf:ID:STATUS` (23 bytes)
- `ord_act:track:ID` (17 bytes)
- `ord_act:add_photo:ID` (21 bytes)
- `ord_act:view_photo:ID` (22 bytes)
- `ord_act:cancel` (14 bytes)

### Pitfall 3: Lỗi Telegram `BadRequest: Message is not modified`
**What goes wrong:** Khi cập nhật lại thẻ đơn nhưng nội dung text và bàn phím không có gì thay đổi (ví dụ người dùng chạm 2 lần vào cùng 1 trạng thái), bot crash hoặc log lỗi exception.
**Why it happens:** Telegram API bắt buộc nội dung chỉnh sửa phải khác nội dung hiện tại.
**How to avoid:** Bọc lệnh `edit_message_text` trong khối try/except:
```python
from telegram.error import BadRequest

try:
    await query.edit_message_text(text=text, reply_markup=keyboard, parse_mode="HTML")
except BadRequest as e:
    if "Message is not modified" not in str(e):
        raise
```

### Pitfall 4: Gọi `send_media_group` với 1 ảnh duy nhất
**What goes wrong:** Khi đơn hàng chỉ có 1 ảnh đính kèm, người dùng bấm `[🖼️ Xem 1 ảnh]`, bot văng lỗi `BadRequest: Field "media" must contain 2-10 items`.
**Why it happens:** Đặc tả của Telegram Bot API yêu cầu `sendMediaGroup` phải chứa từ 2 đến 10 `InputMedia`.
**How to avoid:**
```python
if len(photo_ids) == 1:
    await context.bot.send_photo(
        chat_id=chat_id,
        photo=photo_ids[0],
        caption=f"📷 Ảnh đính kèm đơn #{order_id}",
    )
else:
    # Send in chunks of 10
    for chunk in [photo_ids[i:i+10] for i in range(0, len(photo_ids), 10)]:
        media = [InputMediaPhoto(media=fid) for fid in chunk]
        await context.bot.send_media_group(chat_id=chat_id, media=media)
```

### Pitfall 5: Lệch múi giờ UTC vs Giờ Việt Nam khi xem đơn hôm nay
**What goes wrong:** Khách tạo đơn lúc 8h sáng ngày 24/10 tại Việt Nam (tương đương 1h sáng UTC ngày 24/10) hoặc lúc 1h sáng ngày 24/10 tại Việt Nam (tương đương 18h ngày 23/10 UTC). Nếu truy vấn `date(created_at) = '2026-10-24'` trên SQLite sẽ bị sót đơn tạo lúc rạng sáng.
**Why it happens:** SQLite `CURRENT_TIMESTAMP` lưu theo UTC.
**How to avoid:** Luôn dùng `date(created_at, '+7 hours') = ?` trong SQL và lấy ngày hôm nay theo `datetime.now(timezone(timedelta(hours=7))).strftime("%Y-%m-%d")`.

## Code Examples

### 1. Database Queries Theo Ngày (aiosqlite)
```python
# In src/db/orders.py
from collections.abc import Sequence
import aiosqlite
from src.models.order import Order

async def list_orders_by_date(
    db: aiosqlite.Connection,
    date_str: str,
    limit: int = 5,
    offset: int = 0,
) -> Sequence[Order]:
    """Retrieve orders created on a specific Vietnam date (UTC+7)."""
    query = """
        SELECT * FROM orders
        WHERE date(created_at, '+7 hours') = ?
        ORDER BY created_at DESC, id DESC
        LIMIT ? OFFSET ?
    """
    async with db.execute(query, (date_str, limit, offset)) as cursor:
        rows = await cursor.fetchall()
        return [_row_to_order(row) for row in rows]


async def count_orders_by_date(db: aiosqlite.Connection, date_str: str) -> int:
    """Count total orders created on a specific Vietnam date (UTC+7)."""
    query = """
        SELECT COUNT(*) FROM orders
        WHERE date(created_at, '+7 hours') = ?
    """
    async with db.execute(query, (date_str,)) as cursor:
        row = await cursor.fetchone()
        return row[0] if row else 0
```

### 2. Format Thẻ Chi Tiết Đơn Hàng & CopyTextButtons
```python
# In src/bot/keyboards.py
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, CopyTextButton
from src.models.order import Order, OrderStatus

STATUS_NAMES = {
    OrderStatus.CHO_LAM: "⏳ Chờ làm",
    OrderStatus.DANG_LAM: "🛠️ Đang làm",
    OrderStatus.DA_DONG_GOI: "📦 Đã đóng gói",
    OrderStatus.DA_TAO_DON: "📑 Đã tạo đơn ship",
    OrderStatus.SHIPPER_DA_LAY: "🚚 Shipper đã lấy",
    OrderStatus.DA_GIAO: "✅ Đã giao thành công",
    OrderStatus.BOM_HANG: "🚫 Bom hàng",
    OrderStatus.HUY_DON: "❌ Đã huỷ đơn",
}

NEXT_STATUS_MAP = {
    OrderStatus.CHO_LAM: (OrderStatus.DANG_LAM, "▶️ Bắt đầu làm"),
    OrderStatus.DANG_LAM: (OrderStatus.DA_DONG_GOI, "📦 Đã đóng gói xong"),
    OrderStatus.DA_DONG_GOI: (OrderStatus.DA_TAO_DON, "📑 Đã tạo đơn ship"),
    OrderStatus.DA_TAO_DON: (OrderStatus.SHIPPER_DA_LAY, "🚚 Shipper đã lấy"),
    OrderStatus.SHIPPER_DA_LAY: (OrderStatus.DA_GIAO, "✅ Đã giao thành công"),
}

def render_order_detail_card(order: Order) -> str:
    status_label = STATUS_NAMES.get(order.status, order.status.value)
    total_fmt = f"{order.total_amount:,} đ".replace(",", ".")
    cod_fmt = f"{order.cod_amount:,} đ".replace(",", ".")
    tracking_str = f"<code>{order.tracking_code}</code>" if order.tracking_code else "<i>(Chưa có)</i>"
    photo_str = f"{len(order.photo_file_ids)} ảnh" if order.photo_file_ids else "Không có"

    return (
        f"📦 <b>CHI TIẾT ĐƠN HÀNG #{order.id}</b>\n"
        f"Trạng thái: <b>{status_label}</b>\n"
        f"────────────────────\n"
        f"👤 <b>Khách:</b> {html.escape(order.customer_name)}\n"
        f"📞 <b>SĐT:</b> <code>{order.customer_phone}</code> <i>(chạm để copy)</i>\n"
        f"📍 <b>Địa chỉ:</b> <code>{html.escape(order.shipping_address)}</code>\n"
        f"📼 <b>Băng:</b> {html.escape(order.items_text)}\n"
        f"💰 <b>Tổng tiền:</b> {total_fmt}\n"
        f"💵 <b>Tiền COD thu:</b> {cod_fmt}\n"
        f"🚚 <b>Mã vận đơn:</b> {tracking_str}\n"
        f"📷 <b>Ảnh đính kèm:</b> {photo_str}\n"
        f"────────────────────"
    )

def build_order_detail_keyboard(order: Order, date_str: str, page: int) -> InlineKeyboardMarkup:
    buttons: list[list[InlineKeyboardButton]] = []

    # Row 1: Next lifecycle step (if not terminal)
    if order.status in NEXT_STATUS_MAP:
        next_st, label = NEXT_STATUS_MAP[order.status]
        buttons.append([
            InlineKeyboardButton(label, callback_data=f"ord_st:{order.id}:{next_st.value}")
        ])

    # Row 2: 1-Tap Copy Buttons
    copy_row = [
        InlineKeyboardButton("📋 Copy SĐT", copy_text=CopyTextButton(text=order.customer_phone)),
        InlineKeyboardButton("📍 Copy Địa chỉ", copy_text=CopyTextButton(text=order.shipping_address)),
    ]
    buttons.append(copy_row)

    # Row 3: Tracking code action & copy
    track_row = []
    if order.tracking_code:
        track_row.append(InlineKeyboardButton("🚚 Copy Vận đơn", copy_text=CopyTextButton(text=order.tracking_code)))
        track_row.append(InlineKeyboardButton("✏️ Đổi mã VĐ", callback_data=f"ord_act:track:{order.id}"))
    else:
        track_row.append(InlineKeyboardButton("🚚 Nhập mã vận đơn", callback_data=f"ord_act:track:{order.id}"))
    buttons.append(track_row)

    # Row 4: Photos
    photo_row = []
    if order.photo_file_ids:
        photo_row.append(InlineKeyboardButton(f"🖼️ Xem {len(order.photo_file_ids)} ảnh", callback_data=f"ord_act:view_photo:{order.id}"))
    photo_row.append(InlineKeyboardButton("➕ Thêm ảnh", callback_data=f"ord_act:add_photo:{order.id}"))
    buttons.append(photo_row)

    # Row 5: Change status menu & Back to list
    buttons.append([
        InlineKeyboardButton("🔄 Đổi trạng thái", callback_data=f"ord_st_menu:{order.id}"),
        InlineKeyboardButton("⬅️ Quay lại danh sách", callback_data=f"ord_bk:{date_str}:{page}"),
    ])

    return InlineKeyboardMarkup(buttons)
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Gõ lệnh text `/don_hom_nay` hoặc slash command | Reply Keyboard cố định dưới màn hình 2x2 | Telegram Bot API 2.0+ | Người già không cần gõ bàn phím, chỉ chạm 1 nút to là kích hoạt. |
| Bôi đen số điện thoại / địa chỉ để copy vào app ship | `CopyTextButton` + thẻ `<code>` | Telegram Bot API 7.3+ (PTB 22.8) | 1 chạm là copy chính xác 100%, không bị bôi nhầm ký tự thừa. |
| Gửi tin nhắn mới cho mỗi lần đổi trạng thái | `edit_message_text` kèm toast alert (`query.answer(text=...)`) | PTB 20+ async | Tránh spam tin nhắn, không làm trôi hội thoại, phản hồi mượt mà. |
| Session state phức tạp lưu Redis / DB | `context.user_data["action_state"]` có TTL | PTB async built-in | Zero infra phụ trợ, tự dọn dẹp sau 120s, không lo kẹt bot. |

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | Thời gian chờ nhập mã vận đơn / gửi ảnh là 2 phút (120s) | User Constraints D-12 | Thấp. Nếu người già thao tác chậm hơn 2 phút, có thể tăng lên 3-5 phút hoặc cấu hình được. |

## Open Questions

Không có. Mọi yêu cầu và quyết định kỹ thuật từ CONTEXT.md và REQUIREMENTS.md đều rõ ràng và đã được kiểm chứng tương thích với code base hiện tại.

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Python | Runtime | ✓ | 3.11.4 (`.venv`) | — |
| python-telegram-bot | Bot framework | ✓ | 22.8 | — |
| aiosqlite | SQLite client | ✓ | 0.22.1 | — |
| pydantic | Data validation | ✓ | 2.14.1 | — |
| pytest & pytest-asyncio | Test suite | ✓ | pytest-9.1.1, asyncio-1.4.0 | — |

**Missing dependencies with no fallback:** None.
**Missing dependencies with fallback:** None.

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest 9.1.1 + pytest-asyncio 1.4.0 |
| Config file | `pyproject.toml` |
| Quick run command | `./.venv/bin/pytest tests/test_orders_ui.py -x` |
| Full suite command | `./.venv/bin/pytest` |

### Phase Requirements → Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| **DATA-05** | Cập nhật mã vận đơn thành công vào DB và hiển thị trên thẻ | Unit / Integration | `./.venv/bin/pytest tests/test_db_orders.py -k test_update_order_tracking` | ✅ (cần bổ sung test handler) |
| **UI-01** | Khởi động bot gửi kèm Reply Keyboard cố định | Integration | `./.venv/bin/pytest tests/test_orders_ui.py -k test_start_command_reply_keyboard` | ❌ Wave 0 |
| **UI-02** | Xử lý bấm các nút trên Reply Keyboard 2x2 | Integration | `./.venv/bin/pytest tests/test_orders_ui.py -k test_main_menu_routing` | ❌ Wave 0 |
| **UI-03** | Lọc đơn theo ngày (hôm nay, hôm qua, chọn ngày) và phân trang 5 đơn/trang | Unit / DB | `./.venv/bin/pytest tests/test_db_orders.py -k test_list_orders_by_date` | ❌ Wave 0 |
| **UI-04** | Thẻ chi tiết sinh đúng HTML `<code>` và các nút `CopyTextButton` cho SĐT, Địa chỉ, Vận đơn | Unit | `./.venv/bin/pytest tests/test_orders_ui.py -k test_copy_buttons_rendering` | ❌ Wave 0 |
| **UI-05** | Đổi trạng thái 1 chạm và modal xác nhận 2 bước cho `BOM_HANG`/`HUY_DON` | Integration | `./.venv/bin/pytest tests/test_orders_ui.py -k test_status_transition_and_confirmation` | ❌ Wave 0 |
| **UI-06** | Xem ảnh đính kèm (send_photo vs send_media_group) và thêm ảnh vào đơn | Integration | `./.venv/bin/pytest tests/test_orders_ui.py -k test_photo_view_and_append` | ❌ Wave 0 |

### Sampling Rate
- **Per task commit:** `./.venv/bin/pytest tests/test_orders_ui.py -x`
- **Per wave merge:** `./.venv/bin/pytest`
- **Phase gate:** Full suite green (59 passing tests + new UI tests) trước khi hoàn thành phase.

### Wave 0 Gaps
- [ ] `tests/test_orders_ui.py` — kiểm thử bàn phím Reply Keyboard, phân trang danh sách đơn, format thẻ chi tiết kèm `CopyTextButton`, logic đổi trạng thái và modal xác nhận, quy trình nhập tracking code và album ảnh.
- [ ] `tests/test_db_orders.py` — bổ sung tests cho `list_orders_by_date()` và `count_orders_by_date()`.

## Security Domain

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | No | N/A (Telegram User ID whitelist) |
| V3 Session Management | No | N/A |
| V4 Access Control | Yes | Tất cả các handler mới đều được bảo vệ bởi `whitelist_gate` ở `group=-1` (đã có từ Phase 1). Người lạ không thể xem đơn hay đổi trạng thái. |
| V5 Input Validation | Yes | Validate độ dài mã vận đơn (`tracking_code.strip()`), kiểm tra `order_id` tồn tại trong DB trước khi cập nhật, kiểm tra `date_str` đúng định dạng `YYYY-MM-DD`. |
| V6 Cryptography | No | N/A |

### Known Threat Patterns for Stack

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Insecure Direct Object Reference (IDOR) | Elevation of Privilege | Chỉ người dùng nằm trong `telegram_whitelist_user_ids` mới vượt qua `whitelist_gate`. Trong phạm vi cửa hàng nội bộ, whitelist bảo vệ toàn diện. |
| Malformed `callback_data` Injection | Tampering | Sử dụng regex chặt chẽ để parse `callback_data` (ví dụ `^ord_st:(\d+):([A-Z_]+)$`) và validate enum trước khi thao tác. |
| Callback Query Flood / Double-click | Denial of Service | Gọi `await query.answer()` ngay lập tức để huỷ spinner, bọc `edit_message_text` trong try/except `BadRequest` chống crash khi user bấm nhanh 2 lần. |
| Callback State Hijacking / Stale State | Tampering | Kiểm tra `order is not None` trước khi cập nhật trạng thái; kiểm tra timestamp hết hạn 120s cho `action_state`. |

## Sources

### Primary (HIGH confidence)
- In-repo source code: `src/models/order.py:7-37`, `src/db/orders.py:1-174`, `src/db/schema.py:26-55`, `src/bot/app.py:1-75`
- Telegram Bot API 7.3+ Documentation — `CopyTextButton` specification & constraints
- python-telegram-bot v22.8 runtime check in `.venv` — verified `CopyTextButton`, `send_media_group`, `InputMediaPhoto`

### Secondary (MEDIUM confidence)
- SQLite Documentation — `date(timestring, modifier)` syntax and UTC offset calculation

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - 100% thư viện đã có sẵn trong `.venv`, đã kiểm chứng chạy thực tế.
- Architecture: HIGH - Tách bạch rõ giữa `keyboards.py`, `orders.py`, `order_actions.py` và `src/db/orders.py`.
- Pitfalls: HIGH - Xác định rõ 5 cạm bẫy thực tế (Regex routing trước LLM, callback_data 64 bytes limit, send_media_group 1-item bug, message not modified, timezone offset).

**Research date:** 2026-10-24
**Valid until:** 2026-11-24 (30 days)
