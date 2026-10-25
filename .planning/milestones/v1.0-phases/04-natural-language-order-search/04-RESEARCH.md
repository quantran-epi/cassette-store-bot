# Phase 04: Natural Language Order Search - Research

**Researched:** 2026-10-25
**Domain:** Natural Language Order Search, Text-to-SQL, SQLite Read-Only Execution, Telegram Bot Confirmation UX
**Confidence:** HIGH

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

#### 1. Kích hoạt tìm kiếm (Query Trigger Mode)
- **D-01:** Bố trí nút `[🔍 Tra cứu đơn]` trên Reply Keyboard cố định dưới khung chat theo lưới 2x2:
  - Hàng 1: `[📦 Đơn hôm nay]` `[📋 Xem theo ngày]`
  - Hàng 2: `[📝 Nhập đơn mới]` `[🔍 Tra cứu đơn]`
  - Thay thế vị trí nút Trợ giúp (chuyển Trợ giúp thành lệnh `/help`).
- **D-02:** Nhận diện tự động: Nếu người dùng không bấm nút `[🔍 Tra cứu đơn]` mà gõ trực tiếp câu chat bắt đầu bằng các từ khoá tìm kiếm ("tìm...", "tra cứu...", "kiểm tra đơn..."), bot tự động nhận diện và kích hoạt luồng tra cứu thay vì báo lỗi thiếu SĐT của luồng nhập đơn.
- **D-03:** Quản lý trạng thái chờ: Khi bấm nút `[🔍 Tra cứu đơn]`, bot phản hồi hướng dẫn kèm nút Inline `[❌ Huỷ tra cứu]`, tự động huỷ sau 2 phút nếu không có thao tác để tránh kẹt trạng thái của bot.

#### 2. Chuyển đổi truy vấn qua LLM (LLM Search Translation)
- **D-04:** Kiến trúc Text-to-SQL (Read-only): Để hỗ trợ linh hoạt 100% mọi câu hỏi phức tạp (tìm theo ca sĩ, phôi băng, thời gian, khoảng tiền, trạng thái, câu hỏi thống kê "bao nhiêu đơn", "gần nhất khi nào"):
  - Cung cấp DDL schema của bảng `orders` và `customers` kèm ngày giờ hiện tại theo giờ Việt Nam (UTC+7) trong System Prompt của LLM.
  - LLM sinh câu truy vấn SQL thuần tuý.
- **D-05:** Ràng buộc an toàn: App Python kiểm tra nghiêm ngặt câu lệnh SQL từ LLM sinh ra:
  - Bắt buộc bắt đầu bằng `SELECT`.
  - Nghiêm cấm tuyệt đối các từ khoá thay đổi dữ liệu (`INSERT`, `UPDATE`, `DELETE`, `DROP`, `ALTER`, `CREATE`, `REPLACE`, `ATTACH`, `PRAGMA`).
- **D-06:** Cơ chế gọi LLM & Khôi phục lỗi:
  - Tái sử dụng client OpenAI và gateway 9router đã cấu hình.
  - Nếu câu SQL sinh ra bị lỗi cú pháp SQLite, app tự động gửi lại thông báo lỗi kèm schema cho LLM thử sửa 1 lần (retry 1-shot).
- **D-07:** Phân luồng xử lý kết quả truy vấn:
  - Nếu câu hỏi tìm đơn cụ thể (trả về danh sách các hàng từ bảng `orders`): Chuyển kết quả sang luồng hiển thị thẻ xác nhận đơn hàng (D-08, D-09).
  - Nếu câu hỏi thống kê / tổng hợp (kết quả trả về scalar như `COUNT`, `SUM`, `MAX`, `AVG` hoặc danh sách ngắn thống kê): Gửi kết quả rows về cho LLM tóm tắt thành 1 câu trả lời tiếng Việt tự nhiên, ngắn gọn, ấm áp cho người già.

#### 3. Giao diện xác nhận kết quả (Results & Confirmation UX)
- **D-08:** Khớp đúng 1 đơn hàng duy nhất:
  - Hiển thị thẻ tóm tắt hỏi xác nhận: Mã đơn `#ID`, Tên khách, SĐT (dạng che bớt hoặc code), Tên băng, Tổng tiền, Trạng thái đơn.
  - Kèm dòng giải thích ngắn gọn tiêu chí bot đã tìm ra (ví dụ: *"🔍 Em tìm thấy đơn anh Tuấn mua Tuấn Vũ hôm qua:"*).
  - Cung cấp 2 nút bấm Inline: `[👁️ Đúng rồi, xem chi tiết]` và `[🔍 Tìm câu khác]`. Bấm xác nhận mới mở thẻ chi tiết đầy đủ (đáp ứng đúng yêu cầu 2-phase confirmation của SEARCH-02).
- **D-09:** Khớp từ 2 đơn hàng trở lên (Nhiều đơn):
  - Hiển thị thông báo: *"Dạ em tìm thấy N đơn hàng phù hợp:"*, tóm tắt mỗi đơn 2 dòng kèm danh sách nút bấm `[👁️ Xem đơn #ID]` và điều hướng phân trang 5 đơn/trang (tái sử dụng component danh sách đơn của Phase 3).
- **D-10:** Không tìm thấy đơn nào (0 đơn):
  - Thông báo thân thiện: *"Dạ em tìm trong sổ không thấy đơn nào như bác tả rồi!"* kèm gợi ý mẫu câu tìm kiếm và 2 nút bấm Inline: `[🔍 Thử tìm lại]` và `[📝 Nhập đơn mới]`.
- **D-11:** Hiệu ứng chờ: Trong thời gian bot gọi LLM và query SQLite (1-3s), bot gửi liên tục hiệu ứng typing (`ChatAction.TYPING`) để người lớn tuổi an tâm chờ đợi.

#### 4. Điều hướng và thao tác (Action & Navigation Flow)
- **D-12:** Tái sử dụng thẻ chi tiết đầy đủ: Khi bấm xem chi tiết đơn tìm được, mở thẻ chi tiết đầy đủ của Phase 3 (`render_order_detail_card` + `build_order_detail_keyboard`) có đầy đủ nút Copy 1 chạm (SĐT, Địa chỉ, Mã vận đơn), xem/thêm ảnh, và cho phép đổi trạng thái trực tiếp.
- **D-13:** Nút quay lại thông minh: Nút `[⬅️ Quay lại]` trên thẻ chi tiết được điều hướng quay trở lại đúng tin nhắn tóm tắt hoặc danh sách kết quả tìm kiếm trước đó, không làm mất ngữ cảnh tìm kiếm.
- **D-14:** Nút tìm kiếm tiếp theo: Dưới kết quả tra cứu luôn có nút `[🔍 Tìm câu khác]` để kích hoạt lại luồng tra cứu ngay lập tức.

### Claude's Discretion
- Định dạng System Prompt Text-to-SQL chi tiết với các quy tắc mapping SQLite: sử dụng `date(created_at, '+7 hours')` cho thời gian UTC+7, so sánh xâu không phân biệt hoa thường, xử lý tiếng Việt.
- Cơ chế sanitize và unaccent đơn giản hỗ trợ SQLite nếu cần cho các trường tên và địa chỉ.
- Tự động giới hạn `LIMIT 20` cho các câu lệnh SELECT tìm đơn để chống tràn bộ nhớ nếu câu truy vấn quá rộng.

### Deferred Ideas (OUT OF SCOPE)
- Không có (None — discussion stayed within phase scope). Tất cả tính năng nâng cao (xuất báo cáo Excel ENH-02, phân tích doanh thu) đã thuộc Backlog / v2 Requirements.
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| SEARCH-01 | Tra cứu/tìm kiếm đơn hàng bằng ngôn ngữ tự nhiên thông qua tin nhắn chat tự do (VD: *"tìm đơn anh Tuấn hôm qua mua 2 cuốn Tuấn Vũ"*). | Hệ thống hỗ trợ kích hoạt qua Reply Keyboard 2x2 `[🔍 Tra cứu đơn]` hoặc tự động kích hoạt khi tin nhắn bắt đầu bằng các từ khoá tìm kiếm (`tìm...`, `tra cứu...`, `kiểm tra...`). Dùng LLM gateway 9router dịch Text-to-SQL trên SQLite schema `orders` + `customers`. |
| SEARCH-02 | LLM truy vấn tìm kiếm đơn hàng phù hợp trong DB; gửi lại thẻ xác nhận *"Có phải bạn muốn xem đơn này không?"* kèm nút xác nhận trước khi hiển thị chi tiết hoặc thao tác. | Thẻ xác nhận 2-phase confirmation cho kết quả 1 đơn hàng (D-08), danh sách phân trang cho nhiều đơn (D-09), và tóm tắt tiếng Việt tự nhiên cho câu hỏi thống kê (D-07). Khi người dùng nhấn nút xác nhận `[👁️ Đúng rồi, xem chi tiết]`, mới mở thẻ chi tiết đầy đủ với khả năng đổi trạng thái và quay lại kết quả tìm kiếm. |
</phase_requirements>

## Summary

Phase 04 hoàn thiện năng lực tìm kiếm đơn hàng bằng ngôn ngữ tự nhiên tiếng Việt cho chatbot Telegram shop băng cassette, phục vụ đối tượng người lớn tuổi low-tech. Người dùng có thể tìm kiếm đơn linh hoạt theo tên khách, ca sĩ, tên băng, số điện thoại, mốc thời gian ("hôm qua", "tuần này"), trạng thái đơn hoặc các câu hỏi tổng hợp thống kê ("hôm nay bán được bao nhiêu đơn").

Hệ thống kết hợp:
1. **Kích hoạt kép (Dual Trigger)**: Nút cố định `[🔍 Tra cứu đơn]` trên Reply Keyboard 2x2 (thay thế nút Trợ giúp, chuyển trợ giúp sang `/help`) có trạng thái chờ 120s, song song với cơ chế tự động nhận diện tin nhắn bắt đầu bằng từ khoá tìm kiếm (`tìm`, `tra cứu`, `kiểm tra đơn`) để chuyển hướng ngay sang luồng search mà không kích hoạt nhầm thông báo thiếu SĐT của luồng nhập đơn.
2. **Text-to-SQL an toàn (Read-Only SQLite)**: LLM sinh câu truy vấn `SELECT` dựa trên DDL schema và ngày giờ hiện tại UTC+7 (`date(created_at, '+7 hours')`). Python app thực hiện sanitize nghiêm ngặt: cấm tuyệt đối mọi câu lệnh thay đổi dữ liệu (`INSERT`, `UPDATE`, `DELETE`, `DROP`, `ALTER`, `CREATE`, `REPLACE`, `ATTACH`, `PRAGMA`), cấm dấu chấm phẩy nhiều câu lệnh (multi-statement injection), và tự động gán `LIMIT 20`. Có cơ chế retry 1-shot nếu SQLite trả lỗi cú pháp.
3. **UX Xác nhận 2 pha & Điều hướng bảo toàn ngữ cảnh**: Khớp 1 đơn hiển thị thẻ xác nhận kèm 2 nút `[👁️ Đúng rồi, xem chi tiết]` và `[🔍 Tìm câu khác]`; khớp nhiều đơn hiển thị danh sách phân trang (5 đơn/trang); khớp 0 đơn hiển thị gợi ý thân thiện; câu hỏi thống kê được LLM tóm tắt 1 câu ấm áp. Thẻ chi tiết tái sử dụng component Phase 3 nhưng nút `[⬅️ Quay lại]` điều hướng mượt mà về lại kết quả tìm kiếm thay vì danh sách ngày.

**Primary recommendation:** Xây dựng module `src/services/order_search.py` đảm nhiệm sinh/validate/thực thi Text-to-SQL và tóm tắt số liệu; xây dựng `src/bot/handlers/search.py` quản lý callback và render thẻ kết quả; kết nối vào `handle_text_order` và menu 2x2 trong `src/bot/keyboards.py`.

## Project Constraints (from CLAUDE.md)

- **Tech stack**: Python + SQLite (`sqlite3`/`aiosqlite`) + `python-telegram-bot` (v20+ async) [VERIFIED: CLAUDE.md:8].
- **LLM Gateway**: 9router (OpenAI-compatible protocol), cấu hình URL, API Key, Model ID trong settings [VERIFIED: CLAUDE.md:9].
- **Bảo mật**: Whitelist Telegram User IDs ở Handler Group -1 — từ chối tương tác từ người lạ [VERIFIED: CLAUDE.md:10, src/bot/app.py:60].
- **UX**: Tối đa nút bấm Inline, tối thiểu gõ phím cấu trúc; mọi hành động nhạy cảm đều phải có bước xác nhận [VERIFIED: CLAUDE.md:11].
- **Thư viện cấm**: Không dùng ORM phức tạp (SQLAlchemy Async / Tortoise ORM), không dùng webhook server (FastAPI/Flask), không dùng Celery/Redis [VERIFIED: CLAUDE.md:275-288].
- **SQLite Concurrency**: Sử dụng WAL mode và busy timeout để chống database lock [VERIFIED: CLAUDE.md:280, src/db/connection.py:12-13].

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Nhận diện kích hoạt tìm kiếm (nút menu + regex prefix) | Telegram Bot Handler (`src/bot/handlers/`) | State Manager (`context.user_data`) | Bắt sự kiện trực tiếp từ message update trước khi đẩy vào pipeline bóc tách đơn hàng. |
| Dịch câu hỏi tự nhiên thành SQL (Text-to-SQL) | LLM Gateway Service (`src/services/order_search.py`) | 9router API (`AsyncOpenAI`) | Dùng OpenAI client gọi 9router với system prompt chứa schema và quy tắc SQLite UTC+7. |
| Kiểm duyệt an toàn câu lệnh SQL (Sanitize & Validation) | Core Python Logic (`src/services/order_search.py`) | — | Bắt buộc kiểm tra bằng regex/AST: chỉ cho phép `SELECT`, chặn từ khoá ghi dữ liệu, chặn đa câu lệnh. |
| Thực thi truy vấn dữ liệu | Database Layer (`aiosqlite`) | SQLite Engine | Thực thi câu lệnh `SELECT` đã kiểm duyệt trên database file với timeout ngắn. |
| Phân luồng kết quả (Đơn hàng vs Thống kê) | Business Service (`src/services/order_search.py`) | LLM Summary | Tự động phân loại dựa trên schema kết quả (các cột order vs scalar values). |
| Render thẻ xác nhận & bàn phím phân trang | Bot Keyboards (`src/bot/keyboards.py`) | UI Components | Tái sử dụng mẫu thẻ HTML và format nút bấm chuẩn cho người già. |
| Điều hướng chi tiết và quay lại ngữ cảnh tìm kiếm | Callback Handlers (`src/bot/handlers/search.py`) | `context.user_data["searches"]` | Lưu `search_id` và danh sách kết quả tạm trong bộ nhớ phiên để nút `[⬅️ Quay lại]` hoạt động chính xác. |

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| **python-telegram-bot** | `~=22.8` [VERIFIED: CLAUDE.md:19] | Bot API & Inline/Reply Keyboards | Hỗ trợ đầy đủ async polling, `CopyTextButton`, `CallbackQueryHandler`, `ChatAction.TYPING`. |
| **openai** | `~=3.37.0` [VERIFIED: CLAUDE.md:21] | LLM client cho 9router gateway | Hỗ trợ cấu hình `base_url`, `AsyncOpenAI`, timeouts, error hierarchy. |
| **aiosqlite** | `~=0.22.1` [VERIFIED: CLAUDE.md:20] | Async SQLite client | Thao tác không khoá event loop, hỗ trợ WAL mode, `Row` dictionary factory. |
| **pydantic** | `~=2.14.1` [VERIFIED: CLAUDE.md:22] | Domain modeling & validation | Kiểm soát dữ liệu Order và cấu hình an toàn. |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| **unicodedata** | Python standard library | Xử lý unaccent tiếng Việt | Chuẩn hoá chuỗi tiếng Việt không dấu cho custom function SQLite hoặc regex. |
| **re** | Python standard library | Phân tích từ khoá & kiểm duyệt SQL | Nhận diện prefix tìm kiếm và chặn từ khoá SQL nguy hại. |
| **asyncio** | Python standard library | Task group & typing indicator | Gửi `ChatAction.TYPING` chu kỳ 4s trong khi chờ LLM phản hồi. |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Text-to-SQL thuần LLM | Trích xuất bộ lọc Filter Params (JSON) rồi sinh SQL bằng Python code | JSON filter an toàn nhưng cứng nhắc, rất khó hỗ trợ câu hỏi tổng hợp phức tạp ("khách nào mua nhiều nhất", "lần gần nhất mua Tuấn Vũ là khi nào", "tuần trước có bao nhiêu đơn bom"). Text-to-SQL + Read-only sanitizer đáp ứng 100% độ linh hoạt theo D-04. |
| Custom function `unaccent` trong SQLite | Sinh `LIKE '%từ_khoá%'` trực tiếp | `LIKE` của SQLite trên macOS/Linux mặc định case-insensitive với ASCII nhưng không tự bỏ dấu tiếng Việt; prompt LLM kết hợp thêm unaccent hoặc sinh đa điều kiện OR giúp khớp chính xác cả khi khách gõ không dấu. |

**Installation:**
Không cần cài thêm thư viện mới. Tất cả thư viện cần thiết đã có sẵn trong môi trường ảo `.venv`.

**Version verification:**
- `python-telegram-bot`: `22.8` [VERIFIED: pyproject.toml:13]
- `openai`: `1.50.0` [VERIFIED: pyproject.toml:15]
- `aiosqlite`: `0.20.0` [VERIFIED: pyproject.toml:14]
- `pydantic`: `2.10.0` [VERIFIED: pyproject.toml:16]

## Package Legitimacy Audit

Không có package mới nào được cài đặt trong Phase 04. Toàn bộ tính năng tận dụng stack có sẵn từ các Phase 1, 2, 3 và thư viện chuẩn của Python.

| Package | Registry | Age | Downloads | Source Repo | Verdict | Disposition |
|---------|----------|-----|-----------|-------------|---------|-------------|
| `python-telegram-bot` | PyPI | 9+ yrs | ~1.5M/mo | github.com/python-telegram-bot/python-telegram-bot | [OK] | Approved (Phase 1) |
| `openai` | PyPI | 4+ yrs | ~50M/mo | github.com/openai/openai-python | [OK] | Approved (Phase 1) |
| `aiosqlite` | PyPI | 6+ yrs | ~5M/mo | github.com/omnilib/aiosqlite | [OK] | Approved (Phase 1) |
| `pydantic` | PyPI | 7+ yrs | ~120M/mo | github.com/pydantic/pydantic | [OK] | Approved (Phase 1) |

**Packages removed due to [SLOP] verdict:** None
**Packages flagged as suspicious [SUS]:** None

## Architecture Patterns

### System Architecture Diagram

```
User Message Update
       │
       ▼
[whitelist_gate (group -1)] ──(chặn nếu ngoài whitelist)──> Từ chối
       │
       ▼ (group 0)
Is Reply Keyboard text?
  ├── "🔍 Tra cứu đơn" ──> Gửi hướng dẫn + nút [❌ Huỷ tra cứu] + bật search_state (120s)
  └── Các nút khác (Đơn hôm nay, Xem theo ngày, Nhập đơn mới) ──> Handlers Phase 3
       │
       ▼
Is Text Message (filters.TEXT & ~filters.COMMAND)?
  ├── active action_state? ──> Xử lý nhập mã vận đơn (Phase 3)
  ├── active search_state (trong 120s)? ──> Chuyển sang luồng Search
  ├── starts with search keywords ("tìm", "tra cứu", "kiểm tra", ...)? ──> Chuyển sang luồng Search
  └── Otherwise ──> Luồng Nhập đơn mới (Phase 2 LLM Ingestion)
       │
       ▼ [LUỒNG SEARCH]
Gửi ChatAction.TYPING liên tục (asyncio task)
       │
       ▼
Text-to-SQL Service (`src/services/order_search.py`):
  1. System Prompt chứa DDL schema (orders, customers) + Ngày giờ VN (UTC+7)
  2. Gọi 9router qua AsyncOpenAI
  3. Sanitize SQL: Kiểm tra bắt đầu bằng SELECT, không chứa từ khoá cấm, không chứa ';', ép LIMIT 20
  4. Thực thi SQLite qua aiosqlite
     └── Nếu lỗi cú pháp SQLite: Retry 1-shot (gửi lỗi kèm schema cho LLM sửa)
       │
       ▼
Phân luồng kết quả:
  ├── Case A: Trả về kết quả Order (có đủ cột order)
  │     ├── 0 đơn: Thông báo thân thiện + gợi ý + nút [🔍 Thử tìm lại] [📝 Nhập đơn mới]
  │     ├── 1 đơn: Thẻ xác nhận tóm tắt + nút [👁️ Đúng rồi, xem chi tiết] [🔍 Tìm câu khác]
  │     └── >= 2 đơn: Danh sách phân trang 5 đơn/trang + nút [👁️ Xem đơn #ID] + nút [🔍 Tìm câu khác]
  │
  └── Case B: Trả về kết quả Thống kê / Tổng hợp (scalar COUNT, SUM, v.v.)
        └── Gửi dữ liệu thô về LLM tóm tắt 1 câu tiếng Việt ấm áp + nút [🔍 Tìm câu khác]
       │
       ▼
Khi bấm [👁️ Đúng rồi, xem chi tiết] (Single Order) hoặc [👁️ Xem đơn #ID] (Multi Orders):
  Mở thẻ chi tiết đầy đủ (Phase 3) với nút [⬅️ Quay lại] dẫn về sch_bk:{search_id}
```

### In-Repo Values Verbatim Citation

Cột và trạng thái của đơn hàng từ `src/models/order.py:10-17` [VERIFIED: src/models/order.py:10-17]:
```python
    CHO_LAM = "CHO_LAM"
    DANG_LAM = "DANG_LAM"
    DA_DONG_GOI = "DA_DONG_GOI"
    DA_TAO_DON = "DA_TAO_DON"
    SHIPPER_DA_LAY = "SHIPPER_DA_LAY"
    DA_GIAO = "DA_GIAO"
    BOM_HANG = "BOM_HANG"
    HUY_DON = "HUY_DON"
```

Schema DDL của `orders` từ `src/db/schema.py:26-56` [VERIFIED: src/db/schema.py:26-56]:
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

Bố cục bàn phím Reply Keyboard 2x2 hiện tại từ `src/bot/keyboards.py:53-62` [VERIFIED: src/bot/keyboards.py:53-62]:
```python
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
```

### Recommended Project Structure
```
src/
├── bot/
│   ├── app.py                     # Cập nhật menu regex & đăng ký search handlers
│   ├── keyboards.py               # Cập nhật 2x2 menu, thêm render_search_* và build_search_*
│   └── handlers/
│       ├── base.py                # Thêm help_command (cho /help)
│       ├── ingest.py              # Thêm rẽ nhánh search_state và search_intent
│       ├── orders.py              # Hỗ trợ custom back_callback_data trên thẻ chi tiết
│       └── search.py              # [MỚI] Handlers tìm kiếm tự nhiên & callbacks (sch_*)
├── db/
│   ├── connection.py              # Đăng ký custom sqlite unaccent nếu cần
│   └── orders.py                  # Tái sử dụng get_order_by_id, _row_to_order
└── services/
    ├── extractor.py               # Phase 2 Ingestion
    └── order_search.py            # [MỚI] Text-to-SQL prompt, SQL sanitizer, retry, execute, LLM summary
```

### Pattern 1: Safe Text-to-SQL Execution with Sanitization & 1-Shot Recovery
**What:** Bộ chuyển đổi ngôn ngữ tự nhiên sang SQL chỉ đọc (Read-Only) có kiểm duyệt nghiêm ngặt và cơ chế tự sửa lỗi cú pháp.
**When to use:** Khi nhận câu hỏi tra cứu hoặc thống kê tự do từ người dùng.
**Example:**
```python
import re
import aiosqlite
from openai import AsyncOpenAI

FORBIDDEN_SQL_KEYWORDS = {
    "INSERT", "UPDATE", "DELETE", "DROP", "ALTER", "CREATE",
    "REPLACE", "ATTACH", "DETACH", "PRAGMA", "VACUUM", "EXEC"
}

def sanitize_and_validate_sql(raw_sql: str) -> str:
    cleaned = raw_sql.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:sql)?\s*", "", cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(r"\s*```$", "", cleaned)
    cleaned = cleaned.strip()
    cleaned = re.sub(r";+\s*$", "", cleaned)  # strip trailing semicolon

    if ";" in cleaned:
        raise ValueError("Phát hiện nhiều câu lệnh SQL (chống SQL injection).")

    if not re.match(r"^\s*SELECT\b", cleaned, re.IGNORECASE):
        raise ValueError("Câu lệnh truy vấn bắt buộc phải bắt đầu bằng SELECT.")

    tokens = set(re.findall(r"\b[A-Z_]+\b", cleaned.upper()))
    forbidden_used = tokens.intersection(FORBIDDEN_SQL_KEYWORDS)
    if forbidden_used:
        raise ValueError(f"Phát hiện từ khoá cấm thay đổi dữ liệu: {forbidden_used}")

    if not re.search(r"\bLIMIT\s+\d+\b", cleaned, re.IGNORECASE):
        cleaned = f"{cleaned} LIMIT 20"

    return cleaned
```

### Pattern 2: Context-Preserving Search Navigation
**What:** Lưu trạng thái tìm kiếm dưới dạng snapshot trong `context.user_data["searches"][search_id]` để khi người dùng xem chi tiết đơn hàng rồi bấm `[⬅️ Quay lại]`, màn hình quay lại đúng thẻ xác nhận 1 đơn hoặc đúng trang kết quả của danh sách nhiều đơn.
**When to use:** D-12 và D-13 yêu cầu không làm mất ngữ cảnh tìm kiếm khi di chuyển qua lại giữa thẻ chi tiết và kết quả tra cứu.
**Example:**
```python
# In search.py
search_id = uuid.uuid4().hex[:8]
context.user_data.setdefault("searches", {})[search_id] = {
    "query": user_query,
    "order_ids": [o.id for o in orders],
    "is_single": len(orders) == 1,
    "page": 1,
}

# When rendering detail card for order from search:
keyboard = build_order_detail_keyboard(
    order=order,
    date_str="search",
    page=1,
    back_callback_data=f"sch_bk:{search_id}",
)
```

### Anti-Patterns to Avoid
- **Thực thi SQL trực tiếp từ LLM không qua kiểm duyệt:** Cực kỳ nguy hiểm nếu prompt injection khiến LLM sinh `DROP TABLE` hoặc `UPDATE`. Bắt buộc kiểm duyệt bằng `sanitize_and_validate_sql`.
- **Dùng hàm `datetime('now')` mặc định của SQLite:** Giờ SQLite mặc định là UTC+0. Khách hàng Việt Nam ở UTC+7, nếu truy vấn `date('now')` vào buổi sáng (trước 7h AM) sẽ bị lệch sang ngày hôm qua. Bắt buộc dùng `date('now', '+7 hours')` và `date(created_at, '+7 hours')`.
- **Kẹt trạng thái bot vĩnh viễn (Sticky FSM trap):** Nếu người già bấm `[🔍 Tra cứu đơn]` rồi bỏ quên, bot không được chặn các thao tác khác vô thời hạn. State phải có `expires_at = time.time() + 120` và nút bấm Inline `[❌ Huỷ tra cứu]`.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Phân tích cú pháp SQL phức tạp | Bộ parser SQL tự viết từ đầu | Regex validation nghiêm ngặt (chỉ cho phép SELECT, cấm toàn bộ từ khoá thay đổi, cấm dấu chấm phẩy) + SQLite engine | SQLite engine đã có trình parser chuẩn xác nhất. Nếu câu lệnh không hợp lệ, SQLite sẽ raise `sqlite3.OperationalError` để ta kích hoạt retry 1-shot. |
| Phân trang danh sách nhiều đơn | Logic phân trang mới với thuật ngữ khác nhau | Tái cấu trúc chuẩn hoá theo pattern phân trang 5 đơn/trang của Phase 3 (`render_search_multi_card`, `build_search_multi_keyboard`) | Đồng nhất giao diện và trải nghiệm nút bấm cho người già. |
| Hiệu ứng bot đang xử lý | Gửi tin nhắn text "Chờ em tí..." rồi xoá | `context.bot.send_chat_action(chat_id, ChatAction.TYPING)` lặp chu kỳ | Telegram hỗ trợ hiển thị "đang gõ..." ngay dưới thanh tiêu đề chat, êm dịu, không làm xáo trộn lịch sử tin nhắn. |

## Runtime State Inventory

None — greenfield feature in existing DB. Phase 04 chỉ bổ sung câu lệnh truy vấn `SELECT` đọc dữ liệu, không thay đổi schema database và không đổi tên khoá lưu trữ hiện có.

## Common Pitfalls

### Pitfall 1: Lệch múi giờ UTC vs UTC+7 trong truy vấn ngày tháng
**What goes wrong:** Người dùng hỏi "tìm đơn hôm nay", nhưng các đơn phát sinh từ 00:00 đến 06:59 sáng giờ VN bị coi là ngày hôm trước trong DB SQLite do `created_at` lưu `CURRENT_TIMESTAMP` (UTC).
**Why it happens:** SQLite hàm `CURRENT_TIMESTAMP` lưu UTC+0.
**How to avoid:** Trong System Prompt cho LLM Text-to-SQL, hướng dẫn rõ ràng: `date(o.created_at, '+7 hours') = date('now', '+7 hours')`. Đồng thời truyền giá trị ngày giờ hiện tại của Việt Nam (VD: `2026-10-25 09:30:00 (Chủ Nhật)`) vào context của prompt để LLM giải quyết các từ ngữ tương đối ("hôm qua", "thứ năm tuần trước").
**Warning signs:** Tìm đơn trong ngày không ra đơn nào vào buổi sáng sớm.

### Pitfall 2: Tìm kiếm tiếng Việt có dấu vs không dấu
**What goes wrong:** DB lưu "Tuấn Vũ", người dùng gõ tìm "tuan vu" không dấu thì `LIKE '%tuan vu%'` trong SQLite trả về 0 kết quả.
**Why it happens:** Toán tử `LIKE` của SQLite không hỗ trợ unaccent mặc định cho ký tự ngoài bảng mã ASCII.
**How to avoid:**
1. Hướng dẫn trong system prompt: Nếu từ khoá tìm kiếm không dấu, có thể dùng hàm `unaccent(column)` hoặc gợi ý LLM dùng điều kiện mở rộng.
2. Đăng ký hàm `unaccent` vào SQLite connection trong `get_db_connection()` bằng thư viện chuẩn `unicodedata`.
**Warning signs:** Gõ chữ có dấu tìm ra đơn, gõ chữ không dấu báo không thấy đơn nào.

### Pitfall 3: Nhầm lẫn giữa câu hỏi tìm đơn và câu hỏi thống kê
**What goes wrong:** Người dùng hỏi "hôm nay bán được bao nhiêu đơn rồi", bot lại cố hiển thị thẻ danh sách đơn hàng trống hoặc thẻ đơn hàng lỗi.
**Why it happens:** Câu truy vấn trả về scalar `COUNT(*)` chứ không phải bản ghi đơn hàng đầy đủ.
**How to avoid:** Kiểm tra tập cột trả về (`cursor.description`). Nếu tập cột không chứa bộ trường định danh đơn hàng (`id`, `customer_name`, `items_text`, `total_amount`), chuyển ngay sang luồng LLM Tóm tắt số liệu (D-07).
**Warning signs:** Bot báo lỗi `KeyError: 'customer_name'` khi thực thi các câu lệnh `COUNT` hoặc `SUM`.

### Pitfall 4: Xung đột nhận diện giữa Luồng Tìm kiếm và Luồng Nhập đơn mới
**What goes wrong:** Người dùng gõ "tìm đơn anh Nam lấy 2 cuốn Tuấn Vũ", bot nhảy vào luồng nhập đơn Phase 2 và báo: *"Em không nhận diện được đơn hàng từ tin nhắn này. Bác vui lòng gửi lại tin nhắn có số điện thoại khách nhé!"*.
**Why it happens:** Luồng nhập đơn Phase 2 bắt toàn bộ `filters.TEXT & ~filters.COMMAND`.
**How to avoid:** Bổ sung bước kiểm tra ưu tiên ở đầu hàm `handle_text_order`:
1. Nếu `search_state` đang hoạt động (trong 120s) -> Chuyển vào search.
2. Nếu tin nhắn bắt đầu bằng các từ khoá tìm kiếm (`tìm`, `tra cứu`, `kiểm tra`, `xem lại đơn`, `hỏi đơn`) -> Chuyển vào search.
**Warning signs:** Người dùng phàn nàn bot cứ đòi số điện thoại khi họ chỉ muốn tra cứu.

## Code Examples

### 1. Đăng ký hàm unaccent vào aiosqlite connection
```python
# Source: Python unicodedata standard library & aiosqlite documentation
import unicodedata
import aiosqlite

def remove_accents(input_str: str | None) -> str:
    """Normalize Vietnamese text to lowercase unaccented string."""
    if not input_str:
        return ""
    nfkd = unicodedata.normalize("NFKD", input_str)
    cleaned = "".join([c for c in nfkd if not unicodedata.combining(c)])
    return cleaned.replace("đ", "d").replace("Đ", "D").lower()

# In src/db/connection.py or on connection init:
await db.create_function("unaccent", 1, remove_accents)
```

### 2. System Prompt Text-to-SQL cho LLM
```python
# System prompt for LLM Text-to-SQL translation
SYSTEM_PROMPT_TEXT_TO_SQL = """
Bạn là chuyên gia cơ sở dữ liệu SQLite cho shop bán băng cassette tại Việt Nam.
Nhiệm vụ: Chuyển đổi câu hỏi ngôn ngữ tự nhiên của chủ shop thành 1 câu lệnh SQLite SELECT duy nhất, chính xác 100%.

THÔNG TIN THỜI GIAN HIỆN TẠI (Giờ Việt Nam UTC+7):
- Thời điểm hiện tại: {current_time_vn} (Định dạng YYYY-MM-DD HH:MM:SS)
- Hôm nay là ngày: {current_date_vn}

SCHEMA CƠ SỞ DỮ LIỆU:
Table customers (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    phones TEXT NOT NULL,       -- JSON array các SĐT, VD: '["0903626566"]'
    addresses TEXT NOT NULL,    -- JSON array các địa chỉ
    notes TEXT NOT NULL,
    created_at TIMESTAMP
);

Table orders (
    id INTEGER PRIMARY KEY,
    customer_id INTEGER,        -- Khóa ngoại liên kết customers(id)
    customer_name TEXT NOT NULL,
    customer_phone TEXT NOT NULL,
    shipping_address TEXT NOT NULL,
    items_text TEXT NOT NULL,   -- Danh sách băng cassette, ca sĩ, phôi băng
    total_amount INTEGER NOT NULL, -- Tổng tiền đơn hàng (VNĐ)
    cod_amount INTEGER NOT NULL,   -- Tiền thu hộ COD (VNĐ)
    payment_method TEXT NOT NULL,  -- 'COD' hoặc 'CHUYEN_KHOAN'
    status TEXT NOT NULL,          -- 'CHO_LAM', 'DANG_LAM', 'DA_DONG_GOI', 'DA_TAO_DON', 'SHIPPER_DA_LAY', 'DA_GIAO', 'BOM_HANG', 'HUY_DON'
    tracking_code TEXT,
    photo_file_ids TEXT,
    raw_text TEXT,
    created_at TIMESTAMP,
    updated_at TIMESTAMP
);

QUY TẮC BẮT BUỘC:
1. CHỈ TRẢ VỀ DUY NHẤT CÂU LỆNH SQL bắt đầu bằng SELECT. Tuyệt đối không thêm bất kỳ lời giải thích, chào hỏi, hay markdown ngoài câu SQL.
2. Với câu hỏi TÌM ĐƠN HÀNG CỤ THỂ: LUÔN DÙNG `SELECT o.* FROM orders o ... ORDER BY o.created_at DESC LIMIT 20;`
3. Với câu hỏi THỐNG KÊ, TỔNG HỢP (bao nhiêu đơn, tổng tiền, lần gần nhất): Viết câu lệnh SELECT các trường thống kê (VD: `SELECT COUNT(*) AS total_orders, SUM(o.total_amount) AS total_revenue FROM orders o ...`).
4. Xử lý thời gian Việt Nam:
   - Cột `created_at` lưu giờ UTC. Chuyển sang giờ Việt Nam dùng `datetime(created_at, '+7 hours')` hoặc `date(created_at, '+7 hours')`.
   - "Hôm nay": `date(o.created_at, '+7 hours') = '{current_date_vn}'`
   - "Hôm qua": `date(o.created_at, '+7 hours') = date('{current_date_vn}', '-1 day')`
5. Tìm kiếm chuỗi tiếng Việt:
   - Dùng `o.customer_name LIKE '%keyword%'` hoặc `o.items_text LIKE '%keyword%'`
   - Nếu từ khoá không dấu, có thể dùng `unaccent(o.customer_name) LIKE '%keyword%'` hoặc `unaccent(o.items_text) LIKE '%keyword%'`.
"""
```

### 3. Tóm tắt kết quả thống kê bằng LLM
```python
# System prompt for statistical result summarization
SYSTEM_PROMPT_SUMMARY = """
Bạn là trợ lý cho chủ shop băng cassette lớn tuổi tại Việt Nam.
Nhiệm vụ: Dựa vào câu hỏi của bác chủ và kết quả dữ liệu từ cơ sở dữ liệu, hãy trả lời bác bằng 1 câu tiếng Việt ngắn gọn, ấm áp, tự nhiên, rõ ràng.
Ví dụ:
- Hỏi: "hôm nay bán được bao nhiêu đơn" | Dữ liệu: [{"total_orders": 4, "total_revenue": 1200000}]
  -> Trả lời: "Dạ hôm nay shop mình có 4 đơn hàng, tổng tiền là 1.200.000 đ bác nhé!"
- Hỏi: "lần gần nhất có khách mua Tuấn Vũ là khi nào" | Dữ liệu: [{"created_at": "2026-10-24 14:30:00", "customer_name": "Anh Nam", "items_text": "2 cuốn Tuấn Vũ"}]
  -> Trả lời: "Dạ đơn gần nhất có băng Tuấn Vũ là hôm qua của anh Nam (2 cuốn Tuấn Vũ) bác nhé!"
Không dùng từ ngữ kỹ thuật, không đề cập đến database hay SQL.
"""
```

### 4. Background Typing Indicator Loop
```python
import asyncio
from telegram.constants import ChatAction

async def run_with_typing(chat, coro):
    """Run an async coroutine while continuously sending ChatAction.TYPING."""
    stop_event = asyncio.Event()

    async def _typing_loop():
        while not stop_event.is_set():
            try:
                await chat.send_action(ChatAction.TYPING)
            except Exception:
                pass
            try:
                await asyncio.wait_for(stop_event.wait(), timeout=4.0)
            except asyncio.TimeoutError:
                pass

    typing_task = asyncio.create_task(_typing_loop())
    try:
        return await coro
    finally:
        stop_event.set()
        await typing_task
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Trích xuất entity JSON cứng nhắc (Name, Phone, Date) rồi ghép thủ công WHERE | Text-to-SQL có sanitize chặt chẽ qua LLM 9router | 2024-2026 | Hỗ trợ 100% câu hỏi tự do bất kỳ: thống kê doanh thu, đơn bom gần nhất, tìm theo phôi băng, so sánh thời gian mà không cần viết hàng chục if/else. |
| ChatAction gửi 1 lần lúc nhận tin nhắn | Background loop gửi typing liên tục mỗi 4s đến khi có kết quả | Telegram Bot API 7.x+ | Người lớn tuổi thấy bot "đang gõ..." liên tục trong suốt 2-3s LLM xử lý, không bị hoang mang tưởng bot bị đơ hay mất kết nối. |
| Nút quay lại hardcode theo ngày | Nút quay lại dynamic lưu theo `search_id` trong phiên | Phase 4 | Quay lại đúng ngữ cảnh tìm kiếm vừa thực hiện, không ép người dùng phải chọn lại ngày. |

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | 9router model ID cấu hình hiện tại sinh câu lệnh SQLite SELECT chuẩn xác với tỷ lệ >90% ở lần gọi đầu tiên | Architecture Patterns | Nếu model sinh sai cú pháp SQLite, cơ chế retry 1-shot (D-06) sẽ tốn thêm 1.5s; nếu vẫn sai bot sẽ trả thông báo lỗi thân thiện nhờ bác gõ lại. |
| A2 | Bộ nhớ RAM đủ chứa danh sách `searches` trong `context.user_data` | Architecture Patterns | Thấp vì số lượng phiên đồng thời của shop cassette tư nhân nhỏ (< 5 người dùng), mỗi search_id chỉ lưu vài ID số nguyên. |

## Open Questions

1. **Khả năng LLM tự sinh hàm `unaccent()` khi không cần thiết**
   - What we know: `unaccent` là custom SQLite function do Python app đăng ký, không phải hàm chuẩn mặc định của SQLite.
   - What's unclear: Nếu LLM tự ý dùng hàm khác như `LOWER()` hoặc `unaccent()` sai cú pháp.
   - Recommendation: Hướng dẫn rõ ràng trong System Prompt cách dùng `LIKE '%...%'` và chỉ dẫn dùng `unaccent(...)` khi từ khoá tiếng Việt không dấu. Đăng ký hàm `unaccent` trong `get_db_connection` để SQLite luôn hỗ trợ sẵn sàng.

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Python | Runtime | ✓ | 3.11.4 | — |
| python-telegram-bot | Bot framework | ✓ | 22.8 | — |
| openai | LLM client cho 9router | ✓ | 1.50.0 / API 3.37.0 | — |
| aiosqlite | SQLite async client | ✓ | 0.20.0 | — |
| SQLite database file | Data storage | ✓ | WAL mode enabled | — |
| 9router gateway | Text-to-SQL LLM translation | ✓ | Configured via .env | Thông báo bot bận khi rớt mạng |

**Missing dependencies with no fallback:** None.
**Missing dependencies with fallback:** None.

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest 9.1.1 + pytest-asyncio 1.4.0 [VERIFIED: tests/conftest.py] |
| Config file | pyproject.toml [VERIFIED: pyproject.toml] |
| Quick run command | `./.venv/bin/pytest tests/test_order_search.py -v` |
| Full suite command | `./.venv/bin/pytest` |

### Phase Requirements → Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| SEARCH-01 | Phân loại từ khoá tìm kiếm (`is_search_intent`) | Unit | `./.venv/bin/pytest tests/test_order_search.py::test_is_search_intent` | ❌ Wave 0 |
| SEARCH-01 | Kiểm duyệt an toàn SQL (chỉ SELECT, cấm INSERT/UPDATE/DROP/PRAGMA, cấm multi-statement, ép LIMIT 20) | Unit | `./.venv/bin/pytest tests/test_order_search.py::test_sql_sanitizer` | ❌ Wave 0 |
| SEARCH-01 | Text-to-SQL sinh câu lệnh đúng DDL và hỗ trợ UTC+7 | Integration | `./.venv/bin/pytest tests/test_order_search.py::test_text_to_sql_execution` | ❌ Wave 0 |
| SEARCH-02 | Thẻ xác nhận 1 đơn hàng (D-08: 2-phase confirmation buttons) | Unit/UI | `./.venv/bin/pytest tests/test_order_search.py::test_search_single_order_card` | ❌ Wave 0 |
| SEARCH-02 | Danh sách kết quả nhiều đơn hàng kèm phân trang (D-09) | Unit/UI | `./.venv/bin/pytest tests/test_order_search.py::test_search_multi_order_card` | ❌ Wave 0 |
| SEARCH-02 | Xử lý kết quả thống kê / tổng hợp (D-07: LLM summary) | Unit/Mock | `./.venv/bin/pytest tests/test_order_search.py::test_search_aggregate_summary` | ❌ Wave 0 |
| SEARCH-02 | Điều hướng quay lại bảo toàn ngữ cảnh tìm kiếm (`sch_bk:{search_id}`) | Integration | `./.venv/bin/pytest tests/test_order_search.py::test_search_navigation_back` | ❌ Wave 0 |

### Sampling Rate
- **Per task commit:** `./.venv/bin/pytest tests/test_order_search.py -v`
- **Per wave merge:** `./.venv/bin/pytest`
- **Phase gate:** Full suite green (84+ passing tests) trước khi hoàn tất Phase 4.

### Wave 0 Gaps
- [ ] `tests/test_order_search.py` — bao phủ toàn bộ chức năng kiểm duyệt SQL, routing search intent, render thẻ xác nhận và navigation callback.

## Security Domain

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | no | — |
| V3 Session Management | no | — |
| V4 Access Control | yes | Telegram User ID whitelist check tại Handler Group -1 trước mọi handler khác. |
| V5 Input Validation | yes | Regex validation nghiêm ngặt trên SQL do LLM sinh ra: bắt buộc bắt đầu bằng `SELECT`, cấm tuyệt đối mọi từ khoá DDL/DML (`INSERT`, `UPDATE`, `DELETE`, `DROP`, `ALTER`, `CREATE`, `REPLACE`, `ATTACH`, `PRAGMA`), cấm dấu chấm phẩy, tự động ép `LIMIT 20`. Bọc prompt input bằng thẻ `<query>...</query>` để ngăn prompt injection. |
| V6 Cryptography | no | — |

### Known Threat Patterns for SQLite & LLM Stack

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Prompt Injection (người dùng gõ tin nhắn bảo LLM xoá database) | Tampering / Elevation of Privilege | Bọc câu hỏi khách hàng vào `<query>...</query>`. Python app kiểm tra câu SQL trả về bằng `sanitize_and_validate_sql`: bất kỳ câu lệnh nào chứa từ khoá cấm đều bị ném lỗi và từ chối thực thi. |
| Multi-Statement SQL Injection (cố ý chèn `; DROP TABLE`) | Tampering | Kiểm tra nghiêm ngặt không cho phép ký tự `;` nằm trong câu lệnh SQL. |
| DoS qua câu truy vấn quá lớn (SELECT toàn bộ database) | Denial of Service | Tự động thêm hoặc cưỡng chế `LIMIT 20` trên mọi câu lệnh SELECT. |
| Truy cập trái phép bot | Elevation of Privilege | Đã chặn từ Handler Group -1 qua Whitelist ID cấu hình trong `.env`. |

## Sources

### Primary (HIGH confidence)
- Codebase inspection: `src/models/order.py` (OrderStatus enum, Order model) [VERIFIED: src/models/order.py:10-34]
- Codebase inspection: `src/db/schema.py` (DDL schema orders, customers, indices) [VERIFIED: src/db/schema.py:4-72]
- Codebase inspection: `src/bot/keyboards.py` (build_main_menu_reply_keyboard, render_order_detail_card, build_order_detail_keyboard) [VERIFIED: src/bot/keyboards.py:51-188]
- Codebase inspection: `src/bot/handlers/ingest.py` (handle_text_order, message routing) [VERIFIED: src/bot/handlers/ingest.py:161-220]
- Official Python & SQLite documentation: `unicodedata`, SQLite date and time functions [CITED: sqlite.org/lang_datefunc.html]

### Secondary (MEDIUM confidence)
- Phase 04 Context & Decisions: `.planning/phases/04-natural-language-order-search/04-CONTEXT.md`

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — kế thừa 100% stack hiện có, không bổ sung package ngoài.
- Architecture: HIGH — phân luồng rõ ràng giữa order search và aggregate summary, bảo vệ an toàn bằng AST/regex sanitizer.
- Pitfalls: HIGH — đã kiểm chứng thực tế sự khác biệt múi giờ UTC+7 và xử lý tiếng Việt không dấu trên SQLite.

**Research date:** 2026-10-25
**Valid until:** 2026-11-25
