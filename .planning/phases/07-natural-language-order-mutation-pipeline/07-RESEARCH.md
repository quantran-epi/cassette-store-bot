# Phase 7: Natural Language Order Mutation Pipeline - Research

**Researched:** 2026-10-25
**Domain:** Natural Language Processing (Intent Routing, Delta Extraction, Visual Diff UX, SQLite Optimistic Locking, Audit Trail)
**Confidence:** HIGH

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

#### Routing ý định 3 chiều (3-Way Intent Router)
- **D-01:** Cơ chế nhận diện ý định Sửa đơn: Dùng regex từ khoá nhanh ("sửa", "đổi", "huỷ", "cập nhật", "thay địa chỉ"...) trước. Nếu không khớp regex mới dùng LLM fallback phân loại. Nhanh 0ms, tiết kiệm token.
- **D-02:** Xử lý câu mơ hồ (vừa có dấu hiệu tạo mới vừa có dấu hiệu sửa): Ưu tiên tìm đơn cũ để sửa trước; nếu không tìm thấy đơn cũ mới hỏi bác muốn tạo mới hay sửa.
- **D-03:** Kiến trúc router: Đóng gói thành 1 router hàm hợp nhất `classify_intent(text) -> CREATE | SEARCH | MUTATE` trong codebase để gom logic điều hướng, tránh if-else chồng chéo trong `ingest.py`.
- **D-04:** LLM fallback phân loại ý định: Khi regex không chắc chắn, gọi prompt phân loại nhẹ (10-20 token output trả về nhãn intent).
- **D-05:** Ngữ cảnh Reply: Khi người dùng Reply trực tiếp vào tin nhắn bot hiển thị đơn hàng trước đó, router tự động trích xuất Order ID từ tin nhắn gốc mà không cần tìm kiếm lại theo từ khoá.
- **D-06:** Fast-path sửa trạng thái: Với câu chat ngắn có cú pháp trạng thái rõ ràng (ví dụ: "huỷ đơn 12", "đơn 12 đã giao"), Router chuyển thẳng thành delta trạng thái mà không cần gọi LLM bóc tách, hiện ngay thẻ xác nhận 1-chạm.

#### Phạm vi & Chọn đơn khớp (Scope & Disambiguation)
- **D-07:** Phạm vi tìm kiếm đơn cần sửa: Ưu tiên tìm các đơn đang active (`CHO_LAM`, `DANG_LAM`, `DA_DONG_GOI`, `DA_TAO_DON`, `SHIPPER_DA_LAY`). Nếu không thấy mới tìm trong các đơn đã hoàn tất (`DA_GIAO`, `BOM_HANG`, `HUY_DON`).
- **D-08:** Giao diện khi khớp nhiều đơn: Hiển thị tối đa 3-5 đơn gần nhất dưới dạng danh sách nút Inline 1-chạm: `[Đơn #12 - Nam - 250k - Chờ làm]` để người dùng bấm chọn ngay.
- **D-09:** Phản hồi khi không thấy đơn khớp: Báo "Không tìm thấy đơn hàng nào của [từ khoá]" kèm gợi ý gửi SĐT hoặc mã đơn để bot tìm lại; không tự động tạo đơn rác.
- **D-10:** Xử lý sau khi bấm chọn đơn từ danh sách gợi ý: Áp ngay delta đã bóc tách từ câu chat ban đầu (lưu tạm trong `user_data`) vào đơn đã chọn, lập tức hiển thị thẻ Diff Trước ➡️ Sau để xác nhận luôn.

#### Giao diện Thẻ Diff Trước/Sau (Visual Diff Card & UX)
- **D-11:** Định dạng thẻ Visual Diff: Tiêu đề hiển thị `[Mã đơn #12 - Khách: Nam]`, bên dưới chỉ hiển thị các trường có thay đổi dạng `📍 Địa chỉ: [Cũ] ➡️ [Mới]`. Không in lại toàn bộ đơn để giữ màn hình gọn gàng, người già nhìn phát hiểu ngay.
- **D-12:** Xử lý huỷ hoặc hết hạn 120s: Khi bấm `[❌ Huỷ]` hoặc quá 120s TTL, edit tin nhắn thẻ Diff thành `❌ Đã huỷ yêu cầu sửa đơn` / `⏰ Đã hết hạn 120s` và gỡ bỏ toàn bộ nút bấm inline để chống bấm nhầm lần 2.
- **D-13:** Gợi ý trạng thái đích chưa rõ (MUT-05): Dựa vào trạng thái hiện tại của đơn, chỉ gợi ý các bước kế tiếp hợp lý theo vòng đời đơn hàng (ví dụ: `DANG_LAM` gợi ý `DA_DONG_GOI`, `DA_TAO_DON`, `HUY_DON`), hiển thị 3-4 nút bấm trực quan.
- **D-14:** Phản hồi sau khi xác nhận sửa thành công: Sửa trực tiếp (edit) tin nhắn thẻ Diff thành thẻ đơn hàng đã cập nhật kèm thông báo `✅ Đã cập nhật thành công đơn #12!` và các nút hành động (Copy text, Đổi trạng thái). Giữ màn hình chat sạch sẽ.
- **D-19:** Rút ngắn divider và phân tách danh sách:
  - Đường kẻ phân cách (`divider`): rút ngắn từ 20 ký tự xuống 14 ký tự (`──────────────`) để chống vỡ dòng trên màn hình điện thoại nhỏ hoặc cỡ chữ lớn của người già.
  - Định dạng danh sách đơn (`order list card`): thêm 1 dòng trống giãn cách giữa các đơn liên tiếp trong danh sách để tách khối trực quan rõ ràng, chống dính chữ.

#### Khóa lạc quan & Lịch sử sửa đơn (Optimistic Locking & Audit Trail)
- **D-15:** Cơ chế khóa lạc quan: Sử dụng kiểm tra `WHERE id = ? AND updated_at = ?` khi thực hiện UPDATE. Nếu rowcount == 0 nghĩa là đã có xung đột xảy ra trong 120s chờ xác nhận.
- **D-16:** Lưu người tạo đơn & Lịch sử sửa đơn:
  - Bổ sung 2 cột `created_by_user_id` (INTEGER) và `created_by_name` (TEXT) vào bảng `orders`.
  - Luồng tạo đơn mới (`confirm_order_callback`): lưu `effective_user.id` và `effective_user.full_name` vào bản ghi đơn hàng mới, đồng thời ghi 1 bản ghi vào `order_history` (action `CREATE`).
  - Thẻ chi tiết đơn hàng (`render_order_detail_card`): hiển thị người tạo ngay tại dòng thời gian theo format `🕒 Thời gian: 25/10/2026 14:30 (bởi Quan Tran)`. Với đơn cũ không có dữ liệu người tạo thì không hiện đoạn `(bởi ...)`.
  - Tạo bảng `order_history (id, order_id, user_id, user_name, action, changes_json, created_at)` ghi nhận chi tiết mọi thao tác tạo mới và sửa đổi (ai thực hiện, lúc nào, thay đổi trường gì từ giá trị cũ sang giá trị mới).
- **D-17:** Xử lý và thông báo khi có xung đột: Khi phát hiện optimistic lock mismatch, bot đọc bản ghi mới nhất từ `order_history` và thông báo rõ: "⚠️ Đơn vừa được [Tên/ID] sửa nội dung [Chi tiết thay đổi] lúc [Giờ]!".
- **D-18:** Điều hướng sau xung đột: Hiển thị thông báo xung đột kèm thẻ chi tiết đơn mới nhất (kèm các nút thao tác) và dừng thao tác sửa cũ để tránh ghi đè nhầm lên thay đổi của người khác.

### Claude's Discretion
- Định dạng cụ thể của tin nhắn lỗi hoặc cảnh báo hết hạn TTL.
- Tên chính xác của các regex pattern và cấu trúc Pydantic schema cho OrderMutationDelta.
- Tối ưu hóa câu lệnh SQL migration bổ sung bảng `order_history` và cột `created_by_user_id`.

### Deferred Ideas (OUT OF SCOPE)
None — discussion stayed within phase scope.
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| **MUT-01** | User có thể nhắn tin tự do chứa ý định chỉnh sửa đơn hàng, hệ thống dùng 3-Way Intent Router tách biệt chính xác với Tạo đơn và Tìm kiếm | Regex prefix/keyword match + Reply message context + LLM lightweight 20-token classification router (`classify_intent`) |
| **MUT-02** | Hệ thống tìm đúng đơn hàng cần sửa dựa trên từ khoá (mã đơn, tên khách, số điện thoại, giá tiền), nếu khớp nhiều đơn thì hiển thị danh sách nút bấm để chọn | Active-first order resolver (`find_orders_for_mutation`) + multi-match inline disambiguation keyboard (3-5 buttons) |
| **MUT-03** | Hệ thống dùng LLM trích xuất delta thay đổi cho 5 nhóm trường: Trạng thái đơn (8 trạng thái), Mã vận đơn, Ghi chú, Tiền COD/tổng đơn, SĐT/địa chỉ nhận hàng | Pydantic schema `OrderMutationDelta` + 2-tier OpenAI parse extractor with JSON mode fallback + Fast-path status regex |
| **MUT-04** | Hệ thống hiển thị thẻ so sánh Trước ➡️ Sau (Visual Diff) kèm nút bấm Inline `[✅ Xác nhận sửa]` và `[❌ Huỷ]` (hết hạn sau 120s) | HTML Visual Diff card formatter + InlineKeyboard (`ord_mut_cf`, `ord_mut_ca`) + `context.user_data` TTL 120s expiry cleaner |
| **MUT-05** | Khi câu chat chưa chỉ định rõ trạng thái đích, hệ thống hiển thị danh sách nút bấm trạng thái gợi ý để người dùng chọn 1-chạm | Lifecycle status transition resolver (`get_suggested_next_statuses`) + 1-tap inline buttons (`ord_mut_st`) |
</phase_requirements>

## Project Constraints (from CLAUDE.md)
- **Tech stack**: Python 3.12+ / 3.13 + SQLite (sqlite3 / aiosqlite) + python-telegram-bot (v20+ async).
- **LLM Gateway**: 9router (OpenAI-compatible protocol), dual-mode client (structured output with JSON object fallback).
- **Security**: Whitelist Telegram User IDs — deny interactions from non-whitelisted users.
- **UX**: Maximum 1-tap Inline Keyboard Buttons, minimum long typed commands. All sensitive/mutation actions require 2-step confirmation with 120s TTL.
- **Architecture**: Asynchronous event loop (`aiosqlite` with WAL mode, no blocking synchronous sqlite3 calls in handlers).

## Summary

Phase 7 hoàn thiện mảnh ghép quan trọng bậc nhất trong nghiệp vụ bán lẻ của bác chủ shop băng cassette: cho phép chỉnh sửa thông tin đơn hàng đã tạo bằng tin nhắn tiếng Việt tự nhiên thay vì phải vào từng form menu phức tạp. Hệ thống xử lý thông suốt từ khâu phân loại ý định (3-Way Intent Router), tìm kiếm đơn mục tiêu (Active-first resolver), trích xuất delta thay đổi (LLM + Fast-path), trực quan hoá khác biệt (Visual Diff Card Trước ➡️ Sau), đến cập nhật nguyên tử có bảo vệ chống xung đột (Optimistic Locking & Audit Trail).

Trọng tâm thiết kế kỹ thuật là tối ưu tốc độ và sự đơn giản cho người lớn tuổi:
1. **Zero-latency Fast-path**: Những câu lệnh sửa trạng thái ngắn hoặc có mã đơn rõ ràng ("huỷ đơn 12", "đơn 12 đã giao") được giải quyết ngay lập tức bằng regex, không tốn token LLM và phản hồi tức thì dưới 50ms.
2. **Ngữ cảnh Reply thông minh**: Người dùng chỉ cần Reply vào tin nhắn đơn cũ của bot kèm lời dặn ("đổi địa chỉ sang Cầu Giấy nhé"), hệ thống tự động nhận diện mã đơn từ tin nhắn gốc mà không cần tra cứu lại.
3. **Thẻ Visual Diff tối giản**: Chỉ liệt kê những trường thực sự thay đổi theo định dạng `📍 Địa chỉ: [Cũ] ➡️ [Mới]` kèm đường kẻ phân cách ngắn 14 ký tự (`──────────────`) chống vỡ chữ trên điện thoại màn hình nhỏ.
4. **An toàn dữ liệu tuyệt đối**: Cơ chế khóa lạc quan `WHERE id = ? AND updated_at = ?` kết hợp bảng `order_history` ngăn chặn triệt để tình huống hai người cùng sửa một đơn gây mất dữ liệu.

**Primary recommendation:** Tận dụng 100% stack hiện có (`pydantic`, `aiosqlite`, `openai`, `python-telegram-bot`), không thêm bất kỳ thư viện ngoài nào; xây dựng module độc lập `src/services/intent_router.py`, `src/services/mutation_extractor.py`, `src/bot/handlers/mutation.py` và cắm gọn vào đầu `handle_text_order` trong `ingest.py`.

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Intent Classification (CREATE vs SEARCH vs MUTATE) | Services (`intent_router.py`) | Telegram Handler (`ingest.py`) | Router tách biệt hoàn toàn logic phân loại (regex + lightweight LLM) khỏi luồng nhận tin Telegram |
| Target Order Disambiguation | Database Service (`db/orders.py`) | Telegram Handler (`handlers/mutation.py`) | Truy vấn SQL tìm kiếm đơn active-first, handler render danh sách nút bấm 1-chạm nếu có nhiều đơn |
| Delta Extraction (5 field groups) | Services (`mutation_extractor.py`) | Models (`models/mutation.py`) | Schema Pydantic định nghĩa cấu trúc delta chuẩn hoá; extractor xử lý gọi OpenAI dual-tier |
| Visual Diff Card & Keyboard UI | Keyboards (`bot/keyboards.py`) | Telegram Handler (`handlers/mutation.py`) | Render chuỗi HTML Before ➡️ After và các nút bấm Inline 1-chạm |
| State & TTL Expiry (120s) | Memory State (`context.user_data`) | Handlers (`handlers/callbacks.py`) | Lưu tạm draft mutation trong RAM của bot process theo ID ngắn, tự huỷ sau 120s |
| Optimistic Locking & Audit Persistence | Database (`db/orders.py`, `db/schema.py`) | SQLite Engine | Đảm bảo tính nguyên tử của UPDATE và lưu vết lịch sử vào `order_history` |

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| `python-telegram-bot` | `22.8` [VERIFIED: pip index] | Bot framework & Inline Keyboards | Đã tích hợp sẵn, hỗ trợ native async, `InlineKeyboardMarkup`, `CopyTextButton`, và `CallbackQueryHandler` |
| `pydantic` | `2.14.1` [VERIFIED: pip index] | Schema validation for mutation delta | Chuẩn hoá kiểu dữ liệu, xác thực giá trị tiền, số điện thoại 10 chữ số, trạng thái hợp lệ |
| `openai` | `3.37.0` [VERIFIED: pip index] | 9router client | Gọi LLM trích xuất delta qua `beta.chat.completions.parse` và fallback `response_format={"type": "json_object"}` |
| `aiosqlite` | `0.22.1` [VERIFIED: pip index] | Async SQLite client | Thực thi câu lệnh SQL migration, optimistic locking update, và ghi chép audit trail an toàn |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| `python:3.13` (stdlib `re`) | stdlib | Regex intent matching & fast-paths | Nhận diện từ khoá sửa đơn, trích xuất Order ID từ reply message, fast-path trạng thái 0ms |
| `python:3.13` (stdlib `html`) | stdlib | HTML escaping for Telegram messages | Tránh lỗi vỡ parse HTML khi tên khách hoặc địa chỉ chứa ký tự đặc biệt (`<`, `>`, `&`) |
| `python:3.13` (stdlib `json`) | stdlib | Serializing `changes_json` in `order_history` | Lưu lại chi tiết các trường thay đổi dạng JSON string trong SQLite |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Regex + Lightweight LLM fallback | Pure LLM on every message | Tốn thêm 300-500ms mỗi tin nhắn và chi phí token gateway không cần thiết cho câu lệnh rõ ràng |
| Optimistic Locking (`WHERE id=? AND updated_at=?`) | Pessimistic Locking (`asyncio.Lock` per order) | Pessimistic lock trong bộ nhớ chỉ hoạt động trên 1 tiến trình và giữ lock quá lâu (120s TTL) gây nghẽn; optimistic lock bền vững và chuẩn cơ sở dữ liệu |
| In-memory `context.user_data` draft | SQLite temporary draft table | Draft chỉ tồn tại tối đa 120s chờ bấm nút; lưu trong `user_data` nhanh hơn, tự dọn dẹp khi restart, không rác DB |

**Installation:**
```bash
# Không cần cài thêm thư viện nào mới — tất cả thư viện đã có trong .venv
```

## Package Legitimacy Audit

Zero external packages installed in Phase 7. All requirements are implemented using already-installed, verified packages (`python-telegram-bot==22.8`, `openai==3.37.0`, `aiosqlite==0.22.1`, `pydantic==2.14.1`).

| Package | Registry | Age | Downloads | Source Repo | Verdict | Disposition |
|---------|----------|-----|-----------|-------------|---------|-------------|
| `python-telegram-bot` | PyPI | 9 yrs | 2M/mo | github.com/python-telegram-bot/python-telegram-bot | [OK] | Approved |
| `openai` | PyPI | 4 yrs | 40M/mo | github.com/openai/openai-python | [OK] | Approved |
| `aiosqlite` | PyPI | 6 yrs | 5M/mo | github.com/omnilib/aiosqlite | [OK] | Approved |
| `pydantic` | PyPI | 7 yrs | 150M/mo | github.com/pydantic/pydantic | [OK] | Approved |

**Packages removed due to [SLOP] verdict:** none
**Packages flagged as suspicious [SUS]:** none

## Architecture Patterns

### System Architecture Diagram

```
User Message (Text / Reply)
        │
        ▼
[Access Control Whitelist Gate] (security.py)
        │
        ▼
[handle_text_order] (ingest.py)
        │
        ├─► Reply to Order Card? ──(Yes)──► Extract Order ID from replied text (D-05)
        │                                         │
        ▼                                         ▼
[classify_intent] (intent_router.py)  ◄───────────┘
        │
        ├─► [Fast-path Status Regex] (D-06: "huỷ đơn 12", "đơn 12 đã giao")
        │         │ (Matched)
        │         └──────────────────────────────────────┐
        ├─► [Regex Keyword Rules] (D-01: "sửa", "đổi", "huỷ", "cập nhật"...)
        │         │ (Matched: MUTATE | SEARCH | CREATE)
        │         └──────────────────────────────────────┤
        └─► [LLM Lightweight Router] (D-04: 10-20 token classifier fallback)
                  │
                  ▼
          Intent Dispatch
        ┌─────────┼─────────┐
        ▼         ▼         ▼
    [CREATE]  [SEARCH]  [MUTATE]
    (existing)(existing)    │
                            ▼
        [find_orders_for_mutation] (db/orders.py, D-07)
        (Active orders first: CHO_LAM, DANG_LAM, DA_DONG_GOI...)
                            │
               ┌────────────┴────────────┐
               ▼                         ▼
         [0 matched]             [2-5 matched] (D-08)
         Show guide &            Inline Buttons: [Đơn #12 - Nam - 250k]
         prompt (D-09)                   │ (User taps button)
                                         ▼
                                 [1 order matched]
                                         │
                                         ▼
                        [extract_mutation_delta] (LLM 2-tier, MUT-03)
                                         │
                   ┌─────────────────────┴─────────────────────┐
                   ▼                                           ▼
         [Status unclear?] (MUT-05)                     [Delta ready]
         Show Next Status Buttons (D-13)                       │
                   │ (User selects)                            ▼
                   └─────────────────────────────────► Render Visual Diff Card (D-11)
                                                       [Mã đơn #12 - Khách: Nam]
                                                       📍 Địa chỉ: [Cũ] ➡️ [Mới]
                                                       [✅ Xác nhận sửa] [❌ Huỷ]
                                                       TTL: 120s (D-12)
                                                               │
                                         ┌─────────────────────┴─────────────────────┐
                                         ▼                                           ▼
                                 [❌ Huỷ / TTL Expired]                      [✅ Xác nhận sửa]
                                 Edit message: "Đã huỷ"                      Run UPDATE with
                                 Remove all buttons (D-12)                   Optimistic Lock (D-15)
                                                                             WHERE id=? AND updated_at=?
                                                                                     │
                                                                   ┌─────────────────┴─────────────────┐
                                                                   ▼                                   ▼
                                                             [rowcount == 0]                     [rowcount > 0]
                                                            Conflict detected!                  Success!
                                                            Read latest order_history           Insert order_history
                                                            Notify conflict details (D-17)      Edit message to
                                                            Show fresh order card (D-18)        Updated Order Card (D-14)
```

### Recommended Project Structure
```
src/
├── models/
│   ├── order.py              # Add created_by_user_id, created_by_name to Order model
│   └── mutation.py           # NEW: OrderMutationDelta, IntentType, PendingMutation schemas
├── db/
│   ├── schema.py             # Add order_history table and migration for orders columns
│   └── orders.py             # Add mutate_order_with_lock, find_orders_for_mutation, record_order_history
├── services/
│   ├── intent_router.py      # NEW: classify_intent, fast-path status extractor, reply ID extractor
│   └── mutation_extractor.py # NEW: 2-tier LLM extractor for mutation delta (5 field groups)
└── bot/
    ├── keyboards.py          # Visual diff card, 14-char divider, order list spacing, disambiguation buttons
    └── handlers/
        ├── ingest.py         # Route handle_text_order via classify_intent
        ├── mutation.py       # NEW: handle_mutation_flow, handle_mutation_selection
        └── callbacks.py      # Callback dispatch for ord_mut_cf, ord_mut_ca, ord_mut_sel, ord_mut_st
```

### Pattern 1: 3-Way Intent Router with Fast-Path & Context Preservation
**What:** Bộ phân loại 3 chiều kết hợp regex 0ms, context từ tin nhắn Reply, và LLM fallback nhẹ.
**When to use:** Ngay khi nhận được tin nhắn text không phải lệnh (`/`) trong `handle_text_order`.
**Example:**
```python
# Source: Internal architecture design per D-01, D-02, D-03, D-04, D-05, D-06
from enum import Enum
import re
from openai import AsyncOpenAI

class IntentType(str, Enum):
    CREATE = "CREATE"
    SEARCH = "SEARCH"
    MUTATE = "MUTATE"

MUTATION_PREFIXES = (
    "sửa", "đổi", "huỷ", "hủy", "cập nhật", "thay", "chuyển",
    "bỏ", "bớt", "thêm ghi chú", "mã vận đơn", "vận đơn là"
)

def extract_order_id_from_reply(reply_text: str | None) -> int | None:
    """Extract order ID if user replied to an order card message (D-05)."""
    if not reply_text:
        return None
    match = re.search(r"(?:CHI TIẾT ĐƠN HÀNG|Mã đơn:?)\s*#?(\d+)", reply_text)
    if match:
        return int(match.group(1))
    return None

async def classify_intent(
    text: str,
    client: AsyncOpenAI,
    model_id: str,
    has_reply_order: bool = False
) -> IntentType:
    trimmed = text.strip().lower()
    
    # If replied to an order card and message contains edit words or info
    if has_reply_order:
        return IntentType.MUTATE

    # Fast-path 1: Regex mutation keywords (D-01)
    if any(trimmed.startswith(prefix) for prefix in MUTATION_PREFIXES) or "đổi địa chỉ" in trimmed or "đổi sđt" in trimmed:
        return IntentType.MUTATE

    # Fast-path 2: Search intent check (existing order_search.is_search_intent)
    from src.services.order_search import is_search_intent
    if is_search_intent(text):
        return IntentType.SEARCH

    # Ambiguity check: if both phone/items and mutation cue exist, prioritize MUTATE (D-02)
    if any(cue in trimmed for cue in ("sửa", "đổi", "huỷ", "hủy")):
        return IntentType.MUTATE

    # Default to CREATE if phone number or heavy order signals present
    from src.services.order_search import PHONE_PATTERN
    if PHONE_PATTERN.search(text):
        return IntentType.CREATE

    # LLM Lightweight Fallback (D-04): 10-20 tokens
    prompt = (
        "Phân loại tin nhắn sau thành 1 trong 3 nhãn duy nhất: CREATE (tạo đơn mới), "
        "SEARCH (tìm kiếm/tra cứu đơn), MUTATE (chỉnh sửa/huỷ/đổi thông tin đơn cũ).\n"
        f"Tin nhắn: \"{text}\"\n"
        "Chỉ trả về duy nhất từ: CREATE, SEARCH hoặc MUTATE."
    )
    resp = await client.chat.completions.create(
        model=model_id,
        messages=[{"role": "user", "content": prompt}],
        max_tokens=5,
        temperature=0.0,
    )
    res_label = resp.choices[0].message.content.strip().upper()
    if "MUTATE" in res_label:
        return IntentType.MUTATE
    if "SEARCH" in res_label:
        return IntentType.SEARCH
    return IntentType.CREATE
```

### Pattern 2: Optimistic Locking with Audit Trail
**What:** Cập nhật đơn hàng an toàn với điều kiện `WHERE id = ? AND updated_at = ?` và ghi vết `order_history`.
**When to use:** Khi người dùng bấm `[✅ Xác nhận sửa]` trên thẻ Visual Diff.
**Example:**
```python
# Source: SQLite concurrency standard & D-15, D-16, D-17
import json
import aiosqlite
from datetime import datetime

async def mutate_order_with_lock(
    db: aiosqlite.Connection,
    order_id: int,
    expected_updated_at: str | datetime,
    delta: dict,
    user_id: int,
    user_name: str,
) -> tuple[bool, dict | None]:
    """Execute atomic update with optimistic lock and write to order_history."""
    # Convert datetime to string if needed to match SQLite format
    updated_str = str(expected_updated_at)
    
    # 1. Fetch current order
    async with db.execute("SELECT * FROM orders WHERE id = ?", (order_id,)) as cursor:
        current_row = await cursor.fetchone()
        if not current_row:
            return False, None

    # Compare updated_at
    if str(current_row["updated_at"]) != updated_str:
        # Conflict detected! Fetch latest history record per D-17
        async with db.execute(
            "SELECT * FROM order_history WHERE order_id = ? ORDER BY id DESC LIMIT 1",
            (order_id,)
        ) as h_cursor:
            last_change = await h_cursor.fetchone()
            return False, dict(last_change) if last_change else {}

    # Build dynamic UPDATE query based on delta
    fields = []
    params = []
    changes = {}
    for col, new_val in delta.items():
        if col in current_row.keys() and current_row[col] != new_val:
            fields.append(f"{col} = ?")
            params.append(new_val)
            changes[col] = {"old": current_row[col], "new": new_val}

    if not fields:
        return True, None  # No actual changes

    fields.append("updated_at = CURRENT_TIMESTAMP")
    sql = f"UPDATE orders SET {', '.join(fields)} WHERE id = ? AND updated_at = ?"
    params.extend([order_id, current_row["updated_at"]])

    cursor = await db.execute(sql, params)
    if cursor.rowcount == 0:
        # Concurrent modification happened right between fetch and update
        return False, {}

    # Insert into order_history
    await db.execute(
        """
        INSERT INTO order_history (order_id, user_id, user_name, action, changes_json)
        VALUES (?, ?, ?, 'MUTATE', ?)
        """,
        (order_id, user_id, user_name, json.dumps(changes, ensure_ascii=False))
    )
    await db.commit()
    return True, changes
```

### Anti-Patterns to Avoid
- **Blind UPDATE without lock:** Chạy `UPDATE orders SET ... WHERE id = ?` mà không kiểm tra `updated_at`. Nếu hai nhân viên cùng sửa cùng 1 đơn trong cửa sổ 120s, người bấm sau sẽ vô tình đè mất dữ liệu của người bấm trước mà không ai hay biết.
- **In lại toàn bộ đơn trong thẻ Diff:** In cả chục dòng thông tin cũ khi chỉ đổi 1 số điện thoại làm rối mắt người lớn tuổi. Chỉ hiển thị các trường có thay đổi dạng `📍 Địa chỉ: [Cũ] ➡️ [Mới]`.
- **Gọi LLM bóc tách cho câu lệnh trạng thái rõ ràng:** Người dùng chat "huỷ đơn 12" mà lại gọi LLM tốn 3-5 giây và vài trăm token là lãng phí. Phải dùng regex fast-path chuyển thẳng thành delta trạng thái `HUY_DON` trong 0ms.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Delta Validation & Typing | Custom dict checking with manual `if-else` | Pydantic `BaseModel` (`OrderMutationDelta`) | Tự động coerce kiểu, validate 10 chữ số SĐT, giới hạn 8 trạng thái `OrderStatus`, và loại bỏ các giá trị rác |
| Text-to-Intent Routing | Complex rule tree with 50+ nested `elif` | Dual-phase Router: Regex prefixes + 10-token LLM fallback | Regex bắt 90% trường hợp rõ ràng (0ms), LLM xử lý 10% các câu hành văn phức tạp hoặc tiếng địa phương |
| SQLite Concurrency Protection | Manual file locking or global application lock | Optimistic Locking (`WHERE id=? AND updated_at=?`) + SQLite WAL mode | Không phong toả toàn hệ thống, không gây nghẽn (deadlock), chuẩn quy chuẩn cơ sở dữ liệu quan hệ |
| Visual Diff Formatting | String concatenation with hardcoded lines | Pure functional renderer `render_mutation_diff_card(old_order, delta)` | Dễ unit test, dễ tái sử dụng, cô lập HTML escaping ngăn ngừa lỗi vỡ font Telegram |

## Common Pitfalls

### Pitfall 1: Format thời gian `updated_at` trong SQLite so với Python
**What goes wrong:** So sánh `updated_at` trong câu lệnh `WHERE id = ? AND updated_at = ?` luôn trả về `rowcount == 0` dù không có xung đột, làm bot luôn báo lỗi xung đột giả.
**Why it happens:** SQLite lưu `CURRENT_TIMESTAMP` dưới dạng chuỗi UTC `"YYYY-MM-DD HH:MM:SS"`. Nếu Python đọc qua `aiosqlite.Row` được chuyển đổi thành `datetime` object hoặc có múi giờ, khi truyền ngược lại vào câu truy vấn định dạng không khớp từng ký tự với bản ghi trong SQLite.
**How to avoid:** Khi lấy bản ghi để khóa lạc quan, luôn giữ nguyên giá trị `updated_at` dưới dạng chuỗi thô từ SQLite (hoặc format `strftime("%Y-%m-%d %H:%M:%S")`) trước khi đưa vào mệnh đề `WHERE`.
**Warning signs:** Test sửa đơn luôn bị báo "⚠️ Đơn vừa được sửa..." ngay lần thử đầu tiên.

### Pitfall 2: Bấm nút trên thẻ Diff sau khi đã hết hạn 120s hoặc đã huỷ
**What goes wrong:** Người dùng để màn hình điện thoại đó, 10 phút sau quay lại bấm `[✅ Xác nhận sửa]`. Nếu handler không kiểm tra trạng thái trong `user_data`, bot có thể crash vì `KeyError: draft_id` hoặc thực thi với dữ liệu rác.
**Why it happens:** Các nút bấm Inline trên Telegram không tự biến mất trừ khi bot chủ động edit tin nhắn gỡ bỏ `reply_markup`.
**How to avoid:**
1. Mỗi draft mutation trong `context.user_data["pending_mutations"]` lưu kèm `expires_at = time.time() + 120`.
2. Khi nhận callback `ord_mut_cf`, kiểm tra `if time.time() > expires_at`: lập tức gọi `query.edit_message_text("⏰ Yêu cầu sửa đơn đã hết hạn 120s...", reply_markup=None)`.
3. Khi bấm `[❌ Huỷ]`, edit tin nhắn thành `❌ Đã huỷ yêu cầu sửa đơn` và xoá ngay keyboard (D-12).

### Pitfall 3: Trùng lặp nhận diện giữa Tìm kiếm và Sửa đơn
**What goes wrong:** Người dùng gõ "kiểm tra đơn 12 để sửa địa chỉ" bị router điều hướng sang luồng Tìm kiếm (Text-to-SQL) thay vì Sửa đơn.
**Why it happens:** Câu chat chứa cả từ khoá tìm kiếm ("kiểm tra") và từ khoá sửa ("sửa địa chỉ").
**How to avoid:** Tuân thủ quy tắc D-02: Nếu câu chat có chứa cả hai hoặc có yếu tố thay đổi dữ liệu, ưu tiên tìm đơn cũ để sửa trước (`MUTATE`). Nếu tìm thấy đơn, hiện thẻ xác nhận sửa; nếu không thấy mới hỏi người dùng muốn tìm hay sửa.

### Pitfall 4: Lỗi vỡ giao diện trên điện thoại cỡ chữ to (D-19)
**What goes wrong:** Divider dài 20 ký tự (`────────────────────`) bị gãy thành 2 dòng trên màn hình điện thoại iPhone SE hoặc Android bật chế độ chữ lớn cho người già, tạo ra đường gạch đứt đoạn xấu xí.
**Why it happens:** Màn hình nhỏ + kích thước font hệ thống lớn làm chiều rộng cửa sổ chat thu hẹp dưới 20 ký tự đơn.
**How to avoid:** Áp dụng nghiêm ngặt D-19: rút ngắn toàn bộ divider thành 14 ký tự (`──────────────`), đồng thời thêm 1 dòng trống giãn cách giữa các đơn liên tiếp trong danh sách `render_order_list_card`.

## Code Examples

### 1. Pydantic Delta Schema (`src/models/mutation.py`)
```python
from enum import Enum
import re
from pydantic import BaseModel, Field, field_validator
from src.models.order import OrderStatus

VN_PHONE_REGEX = re.compile(r"^0[35789]\d{8}$")

class OrderMutationDelta(BaseModel):
    """Structured mutation delta for 5 field groups per MUT-03."""
    target_order_id: int | None = Field(default=None, description="Mã đơn hàng cần sửa nếu có")
    target_customer_keyword: str | None = Field(default=None, description="Tên khách hoặc từ khoá định danh đơn cũ")
    
    # Group 1: Trạng thái (8 trạng thái)
    new_status: OrderStatus | None = Field(default=None, description="Trạng thái đơn hàng mới")
    status_disambiguation_needed: bool = Field(default=False, description="True nếu muốn đổi trạng thái nhưng chưa rõ trạng thái đích")
    
    # Group 2: Mã vận đơn
    new_tracking_code: str | None = Field(default=None, description="Mã vận đơn mới")
    
    # Group 3: Ghi chú
    new_notes: str | None = Field(default=None, description="Ghi chú mới hoặc bổ sung")
    
    # Group 4: Tiền tệ
    new_total_amount: int | None = Field(default=None, ge=0, description="Tổng tiền mới")
    new_cod_amount: int | None = Field(default=None, ge=0, description="Tiền COD mới")
    
    # Group 5: Thông tin giao hàng & khách hàng
    new_customer_phone: str | None = Field(default=None, description="Số điện thoại nhận hàng mới")
    new_shipping_address: str | None = Field(default=None, description="Địa chỉ giao hàng mới")
    new_customer_name: str | None = Field(default=None, description="Tên khách hàng mới")
    
    # Optional items update
    new_items_text: str | None = Field(default=None, description="Danh sách băng mới nếu có thay đổi món")

    @field_validator("new_customer_phone", mode="before")
    @classmethod
    def validate_phone(cls, v: str | None) -> str | None:
        if not v or not isinstance(v, str):
            return None
        cleaned = re.sub(r"[\s.\-()]", "", v)
        if cleaned.startswith("+84"):
            cleaned = "0" + cleaned[3:]
        elif cleaned.startswith("84") and len(cleaned) == 11:
            cleaned = "0" + cleaned[2:]
        return cleaned if VN_PHONE_REGEX.match(cleaned) else None
```

### 2. Thẻ Visual Diff Trước ➡️ Sau (`src/bot/keyboards.py`)
```python
import html
from src.models.order import Order, OrderStatus
from src.bot.keyboards import STATUS_NAMES

DIVIDER = "──────────────"  # 14 chars per D-19

def render_mutation_diff_card(order: Order, delta: dict) -> str:
    """Format elderly-friendly Visual Diff card showing ONLY changed fields per D-11, D-19."""
    diff_lines = []
    
    # Status change
    if "status" in delta and delta["status"]:
        new_st = OrderStatus(delta["status"])
        if new_st != order.status:
            old_label = STATUS_NAMES.get(order.status, order.status.value)
            new_label = STATUS_NAMES.get(new_st, new_st.value)
            diff_lines.append(f"🔄 <b>Trạng thái:</b> {old_label} ➡️ <b>{new_label}</b>")
            
    # Phone change
    if "customer_phone" in delta and delta["customer_phone"]:
        new_phone = delta["customer_phone"]
        if new_phone != order.customer_phone:
            diff_lines.append(f"📞 <b>SĐT:</b> <code>{order.customer_phone}</code> ➡️ <code>{new_phone}</code>")
            
    # Address change
    if "shipping_address" in delta and delta["shipping_address"]:
        new_addr = delta["shipping_address"]
        if new_addr != order.shipping_address:
            diff_lines.append(f"📍 <b>Địa chỉ:</b>\n   [Cũ]: {html.escape(order.shipping_address)}\n   ➡️ [Mới]: <b>{html.escape(new_addr)}</b>")
            
    # Money change
    if "cod_amount" in delta and delta["cod_amount"] is not None:
        new_cod = delta["cod_amount"]
        if new_cod != order.cod_amount:
            old_fmt = f"{order.cod_amount:,} đ".replace(",", ".")
            new_fmt = f"{new_cod:,} đ".replace(",", ".")
            diff_lines.append(f"💵 <b>Tiền COD:</b> {old_fmt} ➡️ <b>{new_fmt}</b>")

    if "total_amount" in delta and delta["total_amount"] is not None:
        new_tot = delta["total_amount"]
        if new_tot != order.total_amount:
            old_fmt = f"{order.total_amount:,} đ".replace(",", ".")
            new_fmt = f"{new_tot:,} đ".replace(",", ".")
            diff_lines.append(f"💰 <b>Tổng tiền:</b> {old_fmt} ➡️ <b>{new_fmt}</b>")
            
    # Tracking change
    if "tracking_code" in delta and delta["tracking_code"]:
        new_tr = delta["tracking_code"]
        if new_tr != order.tracking_code:
            old_tr = order.tracking_code or "(Chưa có)"
            diff_lines.append(f"🚚 <b>Mã vận đơn:</b> <code>{old_tr}</code> ➡️ <code>{new_tr}</code>")
            
    # Items change
    if "items_text" in delta and delta["items_text"]:
        new_it = delta["items_text"]
        if new_it != order.items_text:
            diff_lines.append(f"📼 <b>Băng:</b> {html.escape(order.items_text)} ➡️ <b>{html.escape(new_it)}</b>")
            
    # Notes change
    if "notes" in delta and delta["notes"]:
        diff_lines.append(f"📝 <b>Ghi chú mới:</b> {html.escape(delta['notes'])}")

    diff_body = "\n\n".join(diff_lines) if diff_lines else "<i>Không phát hiện thay đổi cụ thể.</i>"

    return (
        f"📝 <b>XÁC NHẬN SỬA ĐƠN HÀNG #{order.id}</b>\n"
        f"👤 <b>Khách:</b> {html.escape(order.customer_name)}\n"
        f"{DIVIDER}\n"
        f"<b>Các nội dung thay đổi:</b>\n\n"
        f"{diff_body}\n"
        f"{DIVIDER}\n"
        f"Bác kiểm tra lại thông tin rồi bấm nút bên dưới nhé:"
    )
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Form / Menu sửa đơn thủ công nhiều bước | Chat tự nhiên tiếng Việt qua 3-Way Router + Visual Diff | 2026 (Phase 7) | Thao tác 1 bước thay vì 5 bước; phù hợp hoàn hảo với người dùng low-tech |
| Ghi đè trạng thái trực tiếp không kiểm tra xung đột | Khóa lạc quan (Optimistic Locking) + Bảng Audit Trail | 2026 (Phase 7) | Chống race condition khi nhiều admin/staff cùng vận hành bot, truy vết ai đã sửa lúc nào |
| In lại toàn bộ đơn hàng khi sửa | Chỉ in các trường có thay đổi Trước ➡️ Sau | 2026 (Phase 7) | Thẻ tin nhắn ngắn gọn, dễ đọc, không chiếm màn hình chat |
| Divider 20 ký tự cố định | Divider 14 ký tự chuẩn di động (`──────────────`) | 2026 (D-19) | Chống vỡ dòng trên màn hình nhỏ và người già để font chữ to |

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | Đơn hàng cần sửa chủ yếu nằm trong nhóm active (`CHO_LAM` -> `SHIPPER_DA_LAY`) | Scope & Disambiguation | Rất thấp: Nếu người dùng muốn sửa đơn đã giao/huỷ, hệ thống vẫn có fallback tìm trong terminal orders (D-07) |
| A2 | Cửa sổ 120s TTL cho xác nhận sửa đơn là đủ để bác chủ shop đọc và bấm nút | Giao diện Thẻ Diff & UX | Rất thấp: 120s là thời gian tiêu chuẩn đã áp dụng thành công ở Phase 3 và Phase 4 |

## Open Questions

1. **Khi người dùng chỉ ghi "sửa đơn Nam" nhưng anh Nam có 2 đơn đều đang `CHO_LAM`?**
   - Đã được giải quyết bởi D-08: Hệ thống hiển thị tối đa 3-5 đơn dưới dạng nút bấm Inline 1-chạm: `[Đơn #12 - Nam - 250k - Chờ làm]`, người dùng chạm chọn đơn nào thì áp delta vào đơn đó.
2. **Nếu tin nhắn ban đầu vừa bảo huỷ đơn 12 vừa bảo tạo đơn cho khách khác?**
   - Đã được giải quyết bởi D-02: Ưu tiên xử lý đơn cũ cần huỷ/sửa trước, sau khi xong bot có thể gợi ý tạo đơn tiếp theo.

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Python | Runtime | ✓ | 3.13.7 | — |
| python-telegram-bot | Telegram Bot & Keyboards | ✓ | 22.8 | — |
| aiosqlite | SQLite persistence & migrations | ✓ | 0.22.1 | — |
| openai | 9router LLM integration | ✓ | 3.37.0 | — |
| pydantic | Schema parsing & validation | ✓ | 2.14.1 | — |
| pytest & pytest-asyncio | Test suite | ✓ | 9.1.1 / 1.4.0 | — |

**Missing dependencies with no fallback:** None.
**Missing dependencies with fallback:** None.

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | `pytest` 9.1.1 + `pytest-asyncio` 1.4.0 |
| Config file | `pytest.ini` / `pyproject.toml` |
| Quick run command | `./.venv/bin/pytest tests/test_mutation*.py -v` |
| Full suite command | `./.venv/bin/pytest -v` |

### Phase Requirements → Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| **MUT-01** | 3-Way Intent Router tách biệt CREATE, SEARCH, MUTATE (regex, reply context, LLM fallback) | Unit / Integration | `./.venv/bin/pytest tests/test_intent_router.py -v` | ❌ Wave 0 |
| **MUT-02** | Tìm kiếm đơn theo từ khoá, ưu tiên active-first, disambiguation keyboard khi khớp nhiều | Unit / Integration | `./.venv/bin/pytest tests/test_order_mutation_search.py -v` | ❌ Wave 0 |
| **MUT-03** | LLM trích xuất delta cho 5 nhóm trường (Status, Tracking, Notes, Amounts, Address/Phone) + Fast-path status | Unit / Integration | `./.venv/bin/pytest tests/test_mutation_extractor.py -v` | ❌ Wave 0 |
| **MUT-04** | Render thẻ Visual Diff Trước ➡️ Sau, xác nhận sửa với TTL 120s, Optimistic Locking update | Unit / Integration | `./.venv/bin/pytest tests/test_mutation_card_and_lock.py -v` | ❌ Wave 0 |
| **MUT-05** | Gợi ý trạng thái đích khi chưa rõ (lifecycle transitions) qua nút bấm 1-chạm | Unit | `./.venv/bin/pytest tests/test_status_suggestions.py -v` | ❌ Wave 0 |
| **D-16** | Lưu `created_by_user_id`, `created_by_name` và ghi lịch sử `order_history` | Unit / DB | `./.venv/bin/pytest tests/test_order_audit_trail.py -v` | ❌ Wave 0 |

### Sampling Rate
- **Per task commit:** `./.venv/bin/pytest tests/test_mutation*.py` (dưới 2 giây)
- **Per wave merge:** `./.venv/bin/pytest` (toàn bộ 177+ test suite)
- **Phase gate:** Toàn bộ test suite xanh trước khi nghiệm thu Phase 7.

### Wave 0 Gaps
- [ ] `tests/test_intent_router.py`: Unit test phân loại 3 chiều (regex prefix, reply context, fallback)
- [ ] `tests/test_mutation_extractor.py`: Unit test bóc tách delta 5 nhóm trường và fast-path trạng thái
- [ ] `tests/test_mutation_card_and_lock.py`: Unit test format thẻ Visual Diff, divider 14 ký tự, và optimistic locking conflict
- [ ] `tests/test_order_audit_trail.py`: Unit test migration DB, lưu người tạo đơn và bảng `order_history`

## Security Domain

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | yes | Kiểm tra Telegram User ID qua Whitelist RBAC (`@require_role` / `is_user_whitelisted`) |
| V3 Session Management | yes | Quản lý draft mutation an toàn trong `context.user_data` với TTL cứng 120s |
| V4 Access Control | yes | Chặn các callback `ord_mut_*` từ người lạ không nằm trong danh sách whitelist |
| V5 Input Validation | yes | Pydantic validation cho SĐT 10 số, số tiền `>= 0`, và enum `OrderStatus` 8 trạng thái |
| V6 Cryptography | no | Không lưu trữ thẻ tín dụng hay mật khẩu trong hệ thống nội bộ |

### Known Threat Patterns for Order Mutation Pipeline

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Concurrent Overwrite (Race Condition) | Tampering | Optimistic locking `WHERE id = ? AND updated_at = ?` ngăn chặn ghi đè chéo giữa các admin |
| Replay Attack / Late Click | Tampering | Kiểm tra `expires_at` (120s TTL) và xoá draft ngay khi xác nhận/huỷ |
| Prompt Injection trong chat tự do | Elevation / Tampering | Bọc tin nhắn khách trong thẻ `<message>...</message>`, cấm LLM sinh câu lệnh thực thi |
| HTML Injection / Broken Markup | Denial of Service | Luôn dùng `html.escape()` cho toàn bộ dữ liệu người dùng trước khi gửi thẻ Telegram |

## Sources

### Primary (HIGH confidence)
- Codebase inspection: `src/bot/handlers/ingest.py`, `src/services/order_search.py`, `src/bot/keyboards.py`, `src/db/orders.py`, `src/db/schema.py`
- Official Documentation: Python Telegram Bot v22.8 API, SQLite Documentation (VACUUM INTO, WAL, Optimistic Concurrency)
- Context Decisions: `.planning/phases/07-natural-language-order-mutation-pipeline/07-CONTEXT.md`

### Secondary (MEDIUM confidence)
- Pip index verification for installed versions: `python-telegram-bot` 22.8, `openai` 3.37.0, `aiosqlite` 0.22.1, `pydantic` 2.14.1

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - Không thêm thư viện ngoài, dùng 100% stack đã kiểm chứng
- Architecture: HIGH - Tách biệt rõ ràng Intent Router, Extractor, Diff Card, Lock DB
- Pitfalls: HIGH - Đã dự phòng cẩn thận lệch định dạng datetime SQLite và vỡ layout font lớn

**Research date:** 2026-10-25
**Valid until:** 2026-11-25
