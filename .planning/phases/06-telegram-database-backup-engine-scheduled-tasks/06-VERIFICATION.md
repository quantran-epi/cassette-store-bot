---
phase: 06-telegram-database-backup-engine-scheduled-tasks
verified: 2026-10-25T14:45:00Z
status: human_needed
score: 11/11 must-haves verified
overrides_applied: 0
human_verification:
  - test: "Gõ lệnh /backup trong chat Telegram với bot bằng tài khoản Super Admin"
    expected: "Bot lập tức gửi tin nhắn tiến trình '⏳ Đang tạo snapshot...', sau đó cập nhật thông số và gửi file Document 'cassette_store_backup_YYYYMMDD_HHMMSS.sqlite3.gz' không kèm inline keyboard"
    why_human: "Không thể kiểm chứng trực tiếp việc truyền nhận file Document thực tế trên giao diện Telegram mobile mà không thao tác người dùng"
  - test: "Mở menu /admin, bấm nút [💾 Sao lưu DB] bằng tài khoản Super Admin"
    expected: "Tin nhắn được sửa thành thông báo tiến trình, tạo snapshot và gửi file Document nén trực tiếp vào chat"
    why_human: "Cần kiểm tra phản hồi giao diện mượt mà, không giật lag hoặc nhấp nháy trên ứng dụng Telegram"
  - test: "Tải file .sqlite3.gz từ Telegram về máy tính cá nhân và giải nén"
    expected: "File giải nén thành file .sqlite3 nguyên vẹn, mở được bằng DB Browser for SQLite hoặc sqlite3 CLI, đọc đủ bảng orders và customers với dữ liệu khớp với DB bot"
    why_human: "Xác minh tính khả dụng của file backup đối với người dùng cuối khi cần phục hồi offline"
  - test: "Vào menu /admin -> [⏰ Đặt giờ sao lưu] -> chọn mốc giờ (VD: 03:00) hoặc bấm [✏️ Nhập giờ khác] và nhập '04:15'"
    expected: "Giao diện cập nhật giờ sao lưu mới với biểu tượng tích xanh, bot xác nhận đặt lịch thành công mà không cần restart"
    why_human: "Kiểm tra luồng tương tác và trải nghiệm người dùng với bàn phím inline và tin nhắn văn bản"
  - test: "Vào menu /admin -> [👥 Quản lý danh sách truy cập] -> chọn 1 user -> bấm [✏️ Đổi tên] -> gửi tin nhắn tên mới"
    expected: "Thẻ thông tin người dùng được cập nhật tên hiển thị mới ngay lập tức"
    why_human: "Xác nhận luồng sửa đổi thông tin người dùng trực quan qua Telegram"
---

# Phase 6: Telegram Database Backup Engine & Scheduled Tasks Verification Report

**Phase Goal:** Cơ sở dữ liệu SQLite được tự động sao lưu định kỳ và sao lưu thủ công tức thì dưới dạng snapshot an toàn gửi trực tiếp vào Telegram Super Admin
**Verified:** 2026-10-25T14:45:00Z
**Status:** human_needed
**Re-verification:** No — initial verification

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | Snapshot engine creates an atomic hot backup using VACUUM INTO on live WAL SQLite connection | ✓ VERIFIED | `src/services/backup.py:56` calls `await db.execute("VACUUM INTO ?", (raw_path,))` producing clean hot snapshot without blocking WAL writers; tested in `tests/test_backup_engine.py:test_snapshot_creation_and_integrity` |
| 2 | Snapshot is compressed with gzip (compresslevel=6) to .sqlite3.gz, reducing size 75-85%, and raw snapshot is unlinked immediately in try...finally | ✓ VERIFIED | `src/services/backup.py:60-71` streams to `gzip.open(..., compresslevel=6)` in `asyncio.to_thread` with `try...finally` deleting `raw_path`; tested in `tests/test_backup_engine.py` |
| 3 | Directory retention prunes older backup archives, retaining at most 7 newest .sqlite3.gz files | ✓ VERIFIED | `src/services/backup.py:20-41` scans `backups/`, sorts descending, and unlinks archives beyond `keep_count=7`; verified in `test_retention_pruning` |
| 4 | Safety gate blocks document upload and raises structured warning if compressed backup size exceeds 48MB | ✓ VERIFIED | `SAFE_SIZE_LIMIT = 48 * 1024 * 1024` in `src/services/backup.py:16`, `is_oversized` returned and checked in `src/bot/handlers/backup.py:32`, `src/bot/handlers/admin.py:185`, and `src/bot/app.py:62`; verified in `test_oversized_backup_detection` |
| 5 | Telegram document transmission retries up to 3 times with exponential backoff (2s, 5s, 10s) upon transient network errors | ✓ VERIFIED | `src/services/backup.py:95-134` retries on `(TimedOut, NetworkError)` with `delays=(2.0, 5.0, 10.0)` leaving file intact on disk on failure; verified in `test_send_backup_document_retry_on_network_error` |
| 6 | PTB JobQueue schedules daily database backup at configured time (default 02:00 AM Asia/Ho_Chi_Minh) and runs quietly in the background | ✓ VERIFIED | `src/bot/app.py:111-125` registers `daily_backup_job_callback` targeting `Asia/Ho_Chi_Minh` timezone with `APScheduler 3.11.3`; initialized in `_do_sync` on startup; verified in `test_schedule_daily_backup_registers_job` |
| 7 | Super Admin can view and change the daily backup schedule time via Telegram /admin menu, immediately rescheduling the JobQueue task without bot restart | ✓ VERIFIED | `adm:bkp:menu`, `adm:bkp:set:<time>`, and `adm:bkp:custom_prompt` in `src/bot/handlers/admin.py:224-291, 871-894` persist `backup_schedule_time` to SQLite `system_settings` and call `schedule_daily_backup`; verified in `test_backup_schedule_menu_navigation_and_presets` |
| 8 | Super Admin executing /backup or clicking [💾 Sao lưu DB] receives progress feedback, DB statistics, and the .sqlite3.gz document directly in chat | ✓ VERIFIED | `src/bot/handlers/backup.py:20` and `src/bot/handlers/admin.py:173` reply with progress text `⏳ Đang tạo snapshot...`, execute backup, format statistics caption, and deliver document without inline keyboard; verified in `test_backup_command_as_super_admin` |
| 9 | Only users with SUPER_ADMIN role can trigger manual backup or modify backup schedules; regular admins or staff are rejected with alert | ✓ VERIFIED | `@require_role(UserRole.SUPER_ADMIN)` guards `backup_command` (`src/bot/handlers/backup.py:14`), role checks guard `adm:bkp:trigger`, `adm:bkp:set:`, `adm:bkp:custom_prompt` (`src/bot/handlers/admin.py:168, 242, 268`); verified in `test_backup_command_unauthorized` |
| 10 | Model switcher selectable list starts empty, adds models upon successful 1-token probe, and allows deleting unused models while protecting active model | ✓ VERIFIED | `build_model_switcher_keyboard` defaults to empty list (`src/bot/handlers/admin.py:566, 591, 730`); probed models appended in `handle_admin_text_input:824`; `adm:mdl:del_menu` and `adm:mdl:del:` protect active model (`src/bot/handlers/admin.py:698-724`); verified in `test_admin_suite_refinements.py` |
| 11 | Admin can rename whitelist user display names via 60-second interactive prompt, updating SQLite admin_users.name immediately | ✓ VERIFIED | `update_admin_user_name` in `src/db/admin.py:81` updates `admin_users.name`; `adm:wl:rename_prompt:<id>` sets 60s TTL prompt in `src/bot/handlers/admin.py:469`, text input updates DB and re-renders card (`src/bot/handlers/admin.py:896-932`); verified in `test_whitelist_rename_user_flow` |

**Score:** 11/11 truths verified

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `src/services/backup.py` | Core backup engine & resilient document uploader | ✓ VERIFIED | 136 lines; exports `execute_backup`, `prune_old_backups`, `send_backup_document`, `SAFE_SIZE_LIMIT`, `DEFAULT_RETENTION_COUNT` |
| `tests/test_backup_engine.py` | Unit test suite for backup engine | ✓ VERIFIED | 178 lines; 6 tests covering snapshot, gzip, retention, 48MB gate, retry backoff |
| `src/bot/handlers/backup.py` | `/backup` command handler with role protection | ✓ VERIFIED | 69 lines; exports `backup_command` guarded by `@require_role(UserRole.SUPER_ADMIN)` |
| `src/bot/keyboards.py` | Admin keyboards for backup schedules and model deletion | ✓ VERIFIED | Contains `build_backup_schedule_keyboard` (presets + custom prompt) and `build_model_delete_keyboard` |
| `src/bot/handlers/admin.py` | Admin handler callbacks for backup trigger and schedule configuration | ✓ VERIFIED | Handles `adm:bkp:trigger`, `adm:bkp:menu`, `adm:bkp:set:`, `adm:bkp:custom_prompt`, `adm:mdl:del_menu`, `adm:mdl:del:`, `adm:wl:rename_prompt:` |
| `src/bot/app.py` | PTB JobQueue scheduler and startup synchronization | ✓ VERIFIED | Exports `schedule_daily_backup` and `daily_backup_job_callback`; registers `/backup` command |
| `src/db/admin.py` | SQLite admin user name update query | ✓ VERIFIED | Exports `update_admin_user_name` updating `admin_users.name` |
| `tests/test_backup_scheduler.py` | Scheduler unit test suite | ✓ VERIFIED | 8 tests covering registration, reschedule, execution, oversized alert, send failure alert |
| `tests/test_backup_handlers.py` | Backup command and admin menu test suite | ✓ VERIFIED | 7 tests covering `/backup`, RBAC denials, schedule menu navigation, custom prompt validation |
| `tests/test_admin_suite_refinements.py` | Admin suite refinement test suite | ✓ VERIFIED | 4 tests covering model list empty default, model add/del, active model protection, user rename |

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| `src/services/backup.py` | `aiosqlite.Connection` | `await db.execute("VACUUM INTO ?", (raw_path,))` | ✓ WIRED | Line 56 executes atomic hot snapshot |
| `src/services/backup.py` | `telegram.Bot.send_document` | `await bot.send_document(...)` | ✓ WIRED | Lines 107-116 transmit document with timeout and retry configuration |
| `src/bot/app.py` | `src/services/backup.py` | `execute_backup(db)` in `daily_backup_job_callback` | ✓ WIRED | Lines 55, 60 call backup service on nightly schedule |
| `src/bot/handlers/backup.py` | `src/services/backup.py` | `execute_backup(db)` in `backup_command` | ✓ WIRED | Lines 9, 30 call backup service on `/backup` command |
| `src/bot/handlers/admin.py` | `src/bot/app.py` | `schedule_daily_backup` on schedule change | ✓ WIRED | Lines 248, 250, 886, 888 reschedule JobQueue dynamically |

### Data-Flow Trace (Level 4)

| Artifact | Data Variable | Source | Produces Real Data | Status |
|----------|---------------|--------|---------------------|--------|
| `src/services/backup.py` (`execute_backup`) | `stats` (`gz_path`, `raw_size`, `gz_size`, `order_count`, `customer_count`) | `db.execute("VACUUM INTO ?")` and `SELECT COUNT(*) FROM orders / customers` | Yes; queries real database tables and computes real filesystem sizes | ✓ FLOWING |
| `src/services/backup.py` (`send_backup_document`) | `doc` (binary file stream) | `open(file_path, "rb")` | Yes; reads actual `.sqlite3.gz` file from filesystem | ✓ FLOWING |
| `src/bot/app.py` (`daily_backup_job_callback`) | `backup_time` / `stats` | `get_setting(db, "backup_schedule_time")` / `execute_backup` | Yes; reads schedule from SQLite settings and runs hot backup | ✓ FLOWING |
| `src/bot/handlers/admin.py` (`handle_admin_text_input`) | `new_name` | `update_admin_user_name(db, target_id, new_name)` | Yes; executes real SQL UPDATE on `admin_users` table | ✓ FLOWING |
| `src/bot/handlers/admin.py` (model switcher) | `available_models` | `get_setting` / `set_setting` with 1-token probe verification | Yes; probes 9router endpoint and updates SQLite settings | ✓ FLOWING |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| VACUUM INTO + gzip compression + table integrity check | Python script creating WAL SQLite DB with records, taking backup, and decompressing | `BACKUP_SPOT_CHECK: PASS` | ✓ PASS |
| Full project automated test suite | `.venv/bin/pytest tests/ -v` | `177 passed in 1.01s` | ✓ PASS |
| Backup engine test suite | `.venv/bin/pytest tests/test_backup_engine.py -v` | `6 passed in 0.15s` | ✓ PASS |
| Backup scheduler test suite | `.venv/bin/pytest tests/test_backup_scheduler.py -v` | `8 passed in 0.22s` | ✓ PASS |
| Backup handlers test suite | `.venv/bin/pytest tests/test_backup_handlers.py -v` | `7 passed in 0.18s` | ✓ PASS |
| Admin suite refinements test suite | `.venv/bin/pytest tests/test_admin_suite_refinements.py -v` | `4 passed in 0.12s` | ✓ PASS |

### Probe Execution

No probe scripts found under `scripts/`. Step skipped.

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|-------------|-------------|--------|----------|
| BKP-01 | 06-01-PLAN.md | Hệ thống tạo bản sao lưu snapshot SQLite an toàn bằng lệnh `VACUUM INTO` từ live DB đang bật WAL và nén bằng `gzip` giảm 75-85% dung lượng | ✓ SATISFIED | Implemented in `src/services/backup.py:44-93`; tested in `tests/test_backup_engine.py:test_snapshot_creation_and_integrity` |
| BKP-02 | 06-01-PLAN.md | Hệ thống gửi file nén `.sqlite3.gz` trực tiếp qua Telegram Document tới chat riêng của Super Admin (`TELEGRAM_SUPER_ADMIN_ID`) kèm kiểm tra giới hạn 50MB | ✓ SATISFIED | Implemented in `src/services/backup.py:95-134` and `src/bot/handlers/backup.py:32-56`; tested in `test_oversized_backup_detection` and `test_send_backup_document_success` |
| BKP-03 | 06-02-PLAN.md | Hệ thống tự động sao lưu định kỳ hàng ngày vào lúc 02:00 sáng (giờ Việt Nam, UTC+7) thông qua PTB JobQueue / background scheduler | ✓ SATISFIED | Implemented in `src/bot/app.py:44-126`; registered in `_do_sync` on startup; tested in `tests/test_backup_scheduler.py` |
| BKP-04 | 06-02-PLAN.md | Super Admin có thể kích hoạt sao lưu thủ công tức thì theo yêu cầu bằng lệnh `/backup` hoặc nút bấm trên menu `/admin` kèm phản hồi file ngay lập tức | ✓ SATISFIED | Implemented in `src/bot/handlers/backup.py:14-69` and `src/bot/handlers/admin.py:168-222`; tested in `tests/test_backup_handlers.py` |

All 4 requirements (BKP-01, BKP-02, BKP-03, BKP-04) are fully accounted for and satisfied. No orphaned requirements.

### Anti-Patterns Found

Debt markers (`TBD`, `FIXME`, `XXX`, `TODO`, `HACK`, `PLACEHOLDER`): None found.

Code review quality observations (from 06-REVIEW.md):

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| `src/bot/handlers/admin.py` | 224-239, 329-362 | `action_state` not cleared on cancel navigation to `adm:bkp:menu` or `adm:wl:view:` | ⚠️ Warning | If user cancels custom prompt and types message within 60s, `handle_admin_text_input` intercepts it |
| `src/bot/handlers/admin.py` | 815-840 | Model name length unchecked before callback generation | ⚠️ Warning | Model IDs > 52 chars exceed Telegram 64-byte `callback_data` limit |
| `.gitignore` | 5-8 | `backups/`, `*.sqlite3`, `*.sqlite3.gz` omitted | ⚠️ Warning | Local customer backup snapshots in `backups/` are untracked instead of ignored |
| `src/services/backup.py` | 44 | Absence of mutex lock for concurrent backup runs | ⚠️ Warning | Simultaneous `/backup` and scheduled backup may collide on filename |
| `src/bot/app.py` | 104 | HTML error message in `daily_backup_job_callback` not escaped | ℹ️ Info | Special characters `<, >, &` in exception text could cause Telegram parse error |

### Human Verification Required

#### 1. Manual Backup via `/backup` Command
- **Test:** Open Telegram, send `/backup` command from Super Admin account.
- **Expected:** Bot replies with `"⏳ Đang tạo snapshot và nén dữ liệu cơ sở dữ liệu..."`, replaces it with completion text, and delivers `.sqlite3.gz` file with caption showing timestamp, reduction %, and order/customer counts.
- **Why human:** Verify actual Telegram Document transfer, mobile client download, and progress message transition.

#### 2. Manual Backup via `/admin` Menu Button
- **Test:** Open `/admin` menu, click `[💾 Sao lưu DB]`.
- **Expected:** Message text updates in-place to progress indicator, then sends Document archive directly to chat. Regular admin accounts clicking this button receive alert popup.
- **Why human:** Verify inline button interaction and permission alert popup.

#### 3. Archive Decompression and Database Integrity
- **Test:** Download the `.sqlite3.gz` file from Telegram onto local machine, extract via `gzip -d` or Archive Utility, open in SQLite viewer.
- **Expected:** Valid SQLite database containing `orders`, `customers`, `admin_users`, and `system_settings` tables with full data intact.
- **Why human:** Confirm end-to-end viability of the backup archive for actual disaster recovery.

#### 4. Backup Schedule Time Configuration
- **Test:** In `/admin`, click `[⏰ Đặt giờ sao lưu]`, click a preset (e.g. `03:00`), then click `[✏️ Nhập giờ khác]` and enter `04:30`.
- **Expected:** Schedule card reflects new time, checkmark appears on active preset, JobQueue reschedules immediately.
- **Why human:** Verify interactive text prompt, validation feedback, and menu card rendering.

#### 5. Whitelist User Renaming & Model Deletion
- **Test:** In `/admin` -> `[👥 Quản lý danh sách truy cập]`, view a user, click `[✏️ Đổi tên]`, send a new name; in `[🤖 Cấu hình Model AI]`, verify `[🗑️ Xoá model]` menu.
- **Expected:** User display name updates immediately; active model is protected from deletion while unused models can be removed.
- **Why human:** Verify UX flow and mobile button layout.

### Gaps Summary

No blocking functional gaps. All 11 must-have truths and 4 requirements are implemented in the codebase and verified by 177 automated tests.
Status is set to `human_needed` to validate live Telegram Document transfer, UI feedback, and archive restoration in an actual Telegram client environment.

---

_Verified: 2026-10-25T14:45:00Z_
_Verifier: Claude (gsd-verifier)_
