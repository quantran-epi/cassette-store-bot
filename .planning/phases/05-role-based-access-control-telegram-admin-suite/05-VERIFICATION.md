---
phase: 05-role-based-access-control-telegram-admin-suite
verified: 2026-10-25T13:00:00Z
status: human_needed
score: 10/10 must-haves verified
overrides_applied: 0
human_verification:
  - test: "Mở menu /admin trên ứng dụng Telegram (di động hoặc desktop) của tài khoản ADMIN hoặc SUPER_ADMIN"
    expected: "Hiển thị Bảng điều khiển quản trị định dạng HTML với Uptime, kích thước DB/WAL, model LLM đang dùng, số đơn hôm nay và lưới bàn phím 2 cột: Quản lý Whitelist, Đổi Model LLM, Xem Logs, Sao lưu DB, Làm mới, Đóng menu."
    why_human: "Không thể tự động kiểm tra layout hiển thị và độ vừa vặn của nút bấm trên client Telegram thực tế."
  - test: "Vào menu Quản lý Whitelist -> Thêm tài khoản -> đợi quá 60 giây không nhập gì -> gửi tin nhắn đặt hàng mới"
    expected: "Trạng thái nhập ID admin hết hạn, tin nhắn được bot xử lý bình thường như đơn hàng thay vì bị nuốt hoặc báo lỗi nhập ID."
    why_human: "Cần kiểm tra cảm giác trải nghiệm thực tế và độ mượt mà khi hết hạn trạng thái chờ nhập trên ứng dụng người dùng."
---

# Phase 05: Role-Based Access Control & Telegram Admin Suite Verification Report

**Phase Goal:** Quản trị viên có thể phân quyền truy cập 2 cấp độ và quản trị vận hành bot trực tiếp từ Telegram với menu tương tác an toàn (trạng thái hệ thống, cấu hình model LLM, whitelist CRUD, xem log trực tiếp)
**Verified:** 2026-10-25T13:00:00Z
**Status:** human_needed
**Re-verification:** No — initial verification

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | Database persists admin_users with SUPER_ADMIN, ADMIN, and STAFF roles, and system_settings key-value entries | ✓ VERIFIED | `src/db/schema.py` định nghĩa bảng `admin_users` (ràng buộc CHECK vai trò) và `system_settings`. Kiểm thử tại `tests/test_admin_db.py`. |
| 2 | Root Super Admin ID configured in .env is automatically synchronized to SQLite and immutable against deletion or demotion | ✓ VERIFIED | `src/db/admin.py:delete_admin_user` và `sync_root_super_admin` chặn xóa/hạ quyền root ID với `PermissionError`. UI chi tiết ẩn nút xóa. |
| 3 | Security decorator @require_role blocks unauthorized users on both slash commands and callback queries, raising Telegram alert popups for callbacks | ✓ VERIFIED | `src/bot/security.py:require_role` gửi alert popup (`show_alert=True`) cho callbacks và HTML refusal cho commands. Đã kiểm thử đầy đủ các role. |
| 4 | In-memory RingBufferLogHandler intercepts log records up to fixed capacity (50-100), filters errors, and escapes HTML characters for safe Telegram display | ✓ VERIFIED | `src/bot/logging_handler.py:RingBufferLogHandler` dùng `collections.deque(maxlen=100)`, thoát ký tự HTML qua `html.escape`, giới hạn độ dài `< 3800` ký tự. |
| 5 | Admin user typing /admin opens the administrative dashboard displaying uptime, DB/WAL sizes, active LLM model, and today order count | ✓ VERIFIED | `src/bot/handlers/admin.py:admin_command` tính toán uptime, kích thước file `.db`/`-wal`, truy vấn số đơn hôm nay và trả về HTML dashboard kèm lưới 2 cột. |
| 6 | Admin can view available LLM models and switch models only after an automated 1-token reachability probe succeeds against 9router | ✓ VERIFIED | `src/services/llm_probe.py:probe_model_reachability` gửi 1-token test completion với 5s timeout. Chỉ lưu DB và bot_data khi probe thành công. |
| 7 | Admin can manage whitelist users with 60-second prompt timeout, view user details, change roles, and remove users with a 2-step confirmation modal | ✓ VERIFIED | `src/bot/handlers/admin.py` định tuyến `adm:wl:*`, xác nhận 2 bước `adm:wl:rm_req`/`rm_cf`, đồng bộ tức thì cả SQLite và `bot_data["whitelist_user_ids"]`. |
| 8 | Root Super Admin ID has delete/demote buttons hidden in the Telegram UI and cannot be removed | ✓ VERIFIED | `src/bot/keyboards.py:build_whitelist_user_detail_keyboard` ẩn nút khi `is_root=True`. Callback `adm:wl:role` và `adm:wl:rm_cf` đều chặn cứng. |
| 9 | Super Admin typing /logs views the 25-50 most recent log entries formatted inside HTML pre/code tags with filter buttons | ✓ VERIFIED | `src/bot/handlers/logs.py:logs_command` bảo vệ bằng `@require_role(UserRole.SUPER_ADMIN)`, hiển thị thẻ `<pre><code>` với các nút 25/50 dòng và lọc lỗi. |
| 10 | Application boot synchronizes .env root admin and whitelist IDs to SQLite and populates in-memory cache | ✓ VERIFIED | `src/bot/app.py:startup_sync` gọi `sync_root_super_admin`, nạp danh sách `admin_roles` và nạp model cấu hình nóng từ `system_settings`. |

**Score:** 10/10 truths verified

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `src/config.py` | Cấu hình `telegram_super_admin_id` | ✓ VERIFIED | Có trường `telegram_super_admin_id: int \| None = None`. |
| `src/db/schema.py` | DDL bảng `admin_users` và `system_settings` | ✓ VERIFIED | Chứa lệnh khởi tạo 2 bảng với ràng buộc vai trò. |
| `src/db/admin.py` | CRUD admin và bảo vệ root Super Admin | ✓ VERIFIED | Đầy đủ 5 hàm, raise `PermissionError` khi xóa root Super Admin. |
| `src/db/settings.py` | Lưu trữ cấu hình key-value / JSON | ✓ VERIFIED | Đầy đủ `get_setting`, `set_setting`, `get_json_setting`, `set_json_setting`. |
| `src/bot/security.py` | `UserRole`, `ROLE_HIERARCHY`, `@require_role` | ✓ VERIFIED | Dual-dispatch chuẩn xác cho cả Command và CallbackQuery. |
| `src/bot/logging_handler.py` | `RingBufferLogHandler` thread-safe in-memory | ✓ VERIFIED | `collections.deque(maxlen=capacity)`, `html.escape`, cắt bớt chuỗi an toàn. |
| `src/services/llm_probe.py` | Kiểm tra reachability probe 1 token | ✓ VERIFIED | Sử dụng `AsyncOpenAI`, max_tokens=1, timeout=5.0s. |
| `src/bot/keyboards.py` | Bộ bàn phím inline Admin Suite | ✓ VERIFIED | Đầy đủ 6 hàm bàn phím inline theo đúng UI-SPEC 2 cột. |
| `src/bot/handlers/admin.py` | Handlers dashboard, whitelist, model switcher | ✓ VERIFIED | Đầy đủ `admin_command`, `handle_admin_callback`, `handle_admin_text_input`. |
| `src/bot/handlers/logs.py` | Handlers lệnh `/logs` và callback nhật ký | ✓ VERIFIED | Đầy đủ `logs_command`, `handle_logs_callback` giới hạn cho Super Admin. |
| `src/bot/app.py` | Đăng ký handlers và đồng bộ khi khởi động | ✓ VERIFIED | Gắn `RingBufferLogHandler`, chạy `startup_sync`, đăng ký toàn bộ nhóm adm. |

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| `src/bot/security.py` | `context.bot_data` | Tra cứu `admin_roles` | ✓ WIRED | `get_user_role` đọc `context.bot_data.get("admin_roles", {})`. |
| `src/db/admin.py` | `src/config.py` | Kiểm tra bất biến root Super Admin | ✓ WIRED | `target_id == super_admin_id` ném `PermissionError`. |
| `src/bot/handlers/admin.py` | `src/services/llm_probe.py` | Probe trước khi đổi model | ✓ WIRED | Gọi `probe_model_reachability` trong cả chọn nhanh và nhập text. |
| `src/bot/handlers/admin.py` | `context.bot_data` | Đồng bộ whitelist & active model tức thì | ✓ WIRED | Cập nhật `whitelist_user_ids`, `admin_roles`, `active_model_id` ngay lập tức. |
| `src/bot/handlers/logs.py` | `src/bot/logging_handler.py` | Trích xuất log an toàn | ✓ WIRED | Gọi `log_handler.format_logs_for_telegram(limit, errors_only)`. |

### Data-Flow Trace (Level 4)

| Artifact | Data Variable | Source | Produces Real Data | Status |
|----------|---------------|--------|--------------------|--------|
| `render_dashboard_card` | `today_order_count`, `db_size_mb`, `uptime_str` | Truy vấn `count_orders_by_date` từ SQLite, `os.path.getsize`, `start_time` | Có, dữ liệu thực từ disk và SQLite DB | ✓ FLOWING |
| `adm:wl:list:` | `users` | Truy vấn `list_admin_users(db)` | Có, danh sách người dùng thực từ bảng `admin_users` | ✓ FLOWING |
| `adm:mdl:sel:` | `candidate_model` | Kết quả từ `probe_model_reachability` và cập nhật `system_settings` | Có, kiểm tra thực tế tới gateway và lưu SQLite | ✓ FLOWING |
| `logs_command` | `formatted_logs` | Bắt từ `logging.LogRecord` vào `RingBufferLogHandler` | Có, bắt log thực tế phát sinh trong tiến trình bot | ✓ FLOWING |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| Tạo schema, sync root, chặn xóa root super admin | `.venv/bin/python3 -c "import aiosqlite..."` | `ALL SPOT-CHECKS PASSED!` | ✓ PASS |
| RingBufferLogHandler HTML escape | `.venv/bin/python3 -c "import logging..."` | `<script>` thoát thành `&lt;script&gt;` | ✓ PASS |
| Toàn bộ test suite 152 bài kiểm thử | `.venv/bin/pytest -v` | `152 passed in 0.73s` | ✓ PASS |

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|-------------|-------------|--------|----------|
| **RBAC-01** | 05-01-PLAN | Bảng `admin_users` 2 cấp độ, neo cứng `SUPER_ADMIN_ID` gốc | ✓ SATISFIED | `src/config.py`, `src/db/schema.py`, `src/db/admin.py` đảm bảo không thể xóa root. |
| **RBAC-02** | 05-01-PLAN | Decorator `@require_role` kiểm soát lệnh và callback | ✓ SATISFIED | `src/bot/security.py:require_role` kiểm tra cấp bậc, chặn đứng trái quyền. |
| **RBAC-03** | 05-02-PLAN | Menu `/admin` xem trạng thái và đổi model 9router | ✓ SATISFIED | `src/bot/handlers/admin.py:admin_command` và `probe_model_reachability`. |
| **RBAC-04** | 05-02-PLAN | Quản lý whitelist tức thì trên Telegram | ✓ SATISFIED | Quản lý thêm/xóa/đổi vai trò, xác nhận 2 bước, đồng bộ SQLite + `bot_data`. |
| **RBAC-05** | 05-01-PLAN | Lệnh `/logs` xem 25-50 dòng log ring buffer HTML | ✓ SATISFIED | `src/bot/logging_handler.py` và `src/bot/handlers/logs.py:logs_command`. |

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| - | - | Không phát hiện anti-pattern hay debt marker nào | ℹ️ Info | Codebase sạch sẽ, không có TODO, FIXME hay stub chưa hoàn thiện |

### Human Verification Required

### 1. Telegram Inline UI Layout Rendering

**Test:** Mở menu `/admin` trên ứng dụng Telegram (di động hoặc desktop) của tài khoản ADMIN hoặc SUPER_ADMIN.
**Expected:** Hiển thị Bảng điều khiển quản trị định dạng HTML với Uptime, kích thước DB/WAL, model LLM đang dùng, số đơn hôm nay và lưới bàn phím 2 cột: `[👥 Quản lý Whitelist]` `[🤖 Đổi Model LLM]`, `[📜 Xem Logs]` `[💾 Sao lưu DB]`, `[🔄 Làm mới]` `[❌ Đóng menu]`.
**Why human:** Đảm bảo độ thẩm mỹ, không bị tràn viền nút bấm và căn chỉnh trực quan trên client Telegram của người dùng.

### 2. 60s Input Prompt Timeout UX

**Test:** Vào menu Quản lý Whitelist -> Thêm tài khoản -> đợi quá 60 giây không nhập gì -> gửi tin nhắn đặt hàng mới.
**Expected:** Trạng thái chờ nhập ID hết hạn nhẹ nhàng sau 60s, tin nhắn tiếp theo được bộ bóc tách đơn hàng nhận diện bình thường, không gây nghẽn bot.
**Why human:** Xác nhận tính phản hồi thời gian thực và trải nghiệm không bị chặn hội thoại của người dùng.

### Gaps Summary

Không có gap kỹ thuật nào trong mã nguồn. Toàn bộ 10 must-haves và 5 yêu cầu (RBAC-01 đến RBAC-05) đã được hiện thực hóa đầy đủ, không stub, không anti-pattern và 152/152 tests tự động đều vượt qua. Hệ thống sẵn sàng cho bước kiểm thử thủ công UX trên Telegram (UAT).

---

_Verified: 2026-10-25T13:00:00Z_
_Verifier: Claude (gsd-verifier)_
