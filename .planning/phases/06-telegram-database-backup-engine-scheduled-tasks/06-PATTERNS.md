# Phase 6: Telegram Database Backup Engine & Scheduled Tasks - Pattern Map

**Mapped:** 2026-10-25
**Files analyzed:** 10 (5 modified, 1 new service, 4 test suites)
**Analogs found:** 10 / 10

---

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|---|---|---|---|---|
| `src/services/backup.py` | service | file-I/O / batch | `src/services/llm_probe.py` | role-match |
| `src/bot/handlers/backup.py` | controller | request-response | `src/bot/handlers/logs.py` | exact |
| `src/bot/handlers/admin.py` | controller | request-response | `src/bot/handlers/admin.py` | exact |
| `src/bot/keyboards.py` | component / view | transform | `src/bot/keyboards.py` | exact |
| `src/bot/app.py` | config / entrypoint | setup / event-driven | `src/bot/app.py` | exact |
| `src/db/admin.py` | model / service | CRUD | `src/db/admin.py` | exact |
| `tests/test_backup_engine.py` | test | file-I/O / assert | `tests/test_db_orders.py` | role-match |
| `tests/test_backup_scheduler.py` | test | event-driven / mock | `tests/test_admin_handlers.py` | role-match |
| `tests/test_backup_handlers.py` | test | request-response / mock | `tests/test_admin_handlers.py` | exact |
| `tests/test_admin_suite_refinements.py` | test | request-response / CRUD | `tests/test_admin_handlers.py` | exact |

---

## Pattern Assignments

### 1. `src/services/backup.py` (service, file-I/O / batch)

**Analog:** `src/services/llm_probe.py` & standard library `aiosqlite` + `gzip`

**Imports pattern:**
```python
import asyncio
from datetime import datetime
import gzip
import logging
import os
import shutil
import zoneinfo
import aiosqlite
from telegram import Bot
from telegram.error import NetworkError, TimedOut
```

**Core snapshot, compression & retention pattern:**
```python
VN_TZ = zoneinfo.ZoneInfo("Asia/Ho_Chi_Minh")
SAFE_SIZE_LIMIT = 48 * 1024 * 1024  # 48 MB

def prune_old_backups(backup_dir: str, keep_count: int = 7) -> list[str]:
    """Prune oldest backups, keeping only the most recent keep_count .gz files."""
    if not os.path.exists(backup_dir):
        return []
    files = [
        os.path.join(backup_dir, f)
        for f in os.listdir(backup_dir)
        if f.startswith("cassette_store_backup_") and f.endswith(".sqlite3.gz")
    ]
    files.sort(key=os.path.getmtime, reverse=True)
    removed = []
    for old_file in files[keep_count:]:
        try:
            os.remove(old_file)
            removed.append(old_file)
        except OSError as e:
            logger.error("Failed to remove old backup %s: %s", old_file, e)
    return removed

async def execute_backup(db: aiosqlite.Connection, backup_dir: str = "backups") -> dict:
    """Create atomic VACUUM INTO snapshot, compress with gzip, prune old files, and query stats."""
    os.makedirs(backup_dir, exist_ok=True)
    now_vn = datetime.now(VN_TZ)
    ts = now_vn.strftime("%Y%m%d_%H%M%S")
    raw_path = os.path.join(backup_dir, f"snapshot_{ts}.sqlite3")
    gz_path = os.path.join(backup_dir, f"cassette_store_backup_{ts}.sqlite3.gz")

    await db.execute("VACUUM INTO ?", (raw_path,))
    raw_size = os.path.getsize(raw_path)

    def _compress():
        try:
            with open(raw_path, "rb") as f_in, gzip.open(gz_path, "wb", compresslevel=6) as f_out:
                shutil.copyfileobj(f_in, f_out)
        finally:
            if os.path.exists(raw_path):
                os.remove(raw_path)

    await asyncio.to_thread(_compress)
    gz_size = os.path.getsize(gz_path)
    await asyncio.to_thread(prune_old_backups, backup_dir, 7)

    async with db.execute("SELECT COUNT(*) FROM orders") as cur:
        order_count = (await cur.fetchone())[0]
    async with db.execute("SELECT COUNT(*) FROM customers") as cur:
        customer_count = (await cur.fetchone())[0]

    return {
        "gz_path": gz_path,
        "raw_path": raw_path,
        "timestamp_str": now_vn.strftime("%Y-%m-%d %H:%M:%S"),
        "raw_size": raw_size,
        "gz_size": gz_size,
        "order_count": order_count,
        "customer_count": customer_count,
        "is_oversized": gz_size >= SAFE_SIZE_LIMIT,
    }
```

**Upload & exponential retry pattern:**
```python
async def send_backup_document(
    bot: Bot,
    chat_id: int,
    file_path: str,
    caption: str,
    retries: int = 3,
    delays: tuple[float, ...] = (2.0, 5.0, 10.0),
) -> bool:
    """Upload document to Telegram chat with exponential backoff on network failures."""
    for attempt in range(retries):
        try:
            with open(file_path, "rb") as doc:
                await bot.send_document(
                    chat_id=chat_id,
                    document=doc,
                    filename=os.path.basename(file_path),
                    caption=caption,
                    parse_mode="HTML",
                    read_timeout=60.0,
                    write_timeout=60.0,
                    connect_timeout=30.0,
                )
            return True
        except (TimedOut, NetworkError) as err:
            delay = delays[attempt] if attempt < len(delays) else delays[-1]
            logger.warning("Upload attempt %d failed: %s. Retrying in %ss...", attempt + 1, err, delay)
            if attempt < retries - 1:
                await asyncio.sleep(delay)
        except Exception as err:
            logger.exception("Fatal error uploading backup document: %s", err)
            break
    return False
```

---

### 2. `src/bot/handlers/backup.py` (controller, request-response)

**Analog:** `src/bot/handlers/logs.py` & `src/bot/handlers/admin.py`

**Imports pattern:**
```python
import html
import logging
import aiosqlite
from telegram import Update
from telegram.ext import ContextTypes

from src.bot.handlers.admin import _get_active_db_context
from src.bot.security import UserRole, require_role
from src.services.backup import execute_backup, send_backup_document
```

**Command & role guard pattern:**
```python
@require_role(UserRole.SUPER_ADMIN)
async def backup_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /backup manual trigger command for Super Admin."""
    if not update.effective_message or not update.effective_user:
        return

    progress_msg = await update.effective_message.reply_text(
        "⏳ <b>Đang tạo snapshot và nén dữ liệu cơ sở dữ liệu...</b>",
        parse_mode="HTML",
    )

    try:
        async with _get_active_db_context(context) as db:
            if not db:
                await progress_msg.edit_text("❌ Không thể kết nối cơ sở dữ liệu.")
                return
            stats = await execute_backup(db)

        if stats["is_oversized"]:
            await progress_msg.edit_text(
                f"⚠️ <b>CẢNH BÁO DUNG LƯỢNG VƯỢT QUÁ 48MB</b>\n"
                f"File nén: <code>{stats['gz_size'] / (1024*1024):.2f} MB</code> (Giới hạn Telegram: 50MB)\n"
                f"Đường dẫn file trên server: <code>{stats['gz_path']}</code>",
                parse_mode="HTML",
            )
            return

        reduction = (1 - (stats["gz_size"] / max(stats["raw_size"], 1))) * 100
        caption = (
            f"💾 <b>BẢN SAO LƯU HỆ THỐNG</b>\n"
            f"────────────────────\n"
            f"⏱️ <b>Thời gian:</b> {stats['timestamp_str']} (UTC+7)\n"
            f"📦 <b>Dung lượng:</b> {stats['raw_size'] / (1024*1024):.2f} MB ➔ {stats['gz_size'] / (1024*1024):.2f} MB (Giảm {reduction:.1f}%)\n"
            f"📊 <b>Dữ liệu:</b> {stats['order_count']} đơn hàng | {stats['customer_count']} khách hàng\n"
            f"────────────────────"
        )

        success = await send_backup_document(
            bot=context.bot,
            chat_id=update.effective_user.id,
            file_path=stats["gz_path"],
            caption=caption,
        )

        if success:
            await progress_msg.edit_text("✅ Đã tạo và gửi bản sao lưu thành công!")
        else:
            await progress_msg.edit_text(
                f"❌ Lỗi gửi file qua Telegram sau 3 lần thử.\n"
                f"Bản sao lưu đã được giữ lại trên máy chủ: <code>{stats['gz_path']}</code>",
                parse_mode="HTML",
            )
    except Exception as e:
        logger.exception("Manual backup failed: %s", e)
        await progress_msg.edit_text(f"❌ Quá trình sao lưu thất bại: {html.escape(str(e))}")
```

---

### 3. `src/bot/handlers/admin.py` (controller, request-response)

**Analog:** Existing `src/bot/handlers/admin.py` lines 130-165, 408-532, 534-649

**Modifications needed:**
1. **Trigger manual backup from menu:** Wire `adm:bkp:trigger` (lines 158-160) to call `execute_backup` and `send_backup_document` per D-05.
2. **Schedule time configuration menu:** Add callback `adm:bkp:menu` and `adm:bkp:set:<time>` plus custom time prompt `adm:bkp:time_prompt` per D-15.
3. **Whitelist rename user:** Add callback `adm:wl:rename_prompt:<id>` and state handler `await_rename_user` in `handle_admin_text_input` per D-18.
4. **Model switcher refinement:** Default selectable model list empty per D-17, add model deletion callback `adm:mdl:del_prompt` and `adm:mdl:del:<model_name>`.

**State prompt and input handling pattern (lines 487-548):**
```python
# In handle_admin_callback:
if data.startswith("adm:wl:rename_prompt:"):
    await query.answer()
    target_id = int(data.split(":")[3])
    context.user_data["action_state"] = {
        "action": "await_user_rename",
        "target_id": target_id,
        "expires_at": time.time() + 60,
    }
    card_text = (
        f"✏️ <b>ĐỔI TÊN NGƯỜI DÙNG</b>\n"
        f"────────────────────\n"
        f"Gửi tin nhắn chứa tên mới cho ID: <code>{target_id}</code>.\n\n"
        f"⏳ <i>Hết hạn sau 60 giây.</i>"
    )
    keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("❌ Huỷ", callback_data=f"adm:wl:view:{target_id}")]])
    await query.edit_message_text(card_text, reply_markup=keyboard, parse_mode="HTML")
    return

# In handle_admin_text_input:
if action == "await_user_rename":
    target_id = action_state["target_id"]
    new_name = raw_text.strip()
    context.user_data.pop("action_state", None)
    async with _get_active_db_context(context) as db:
        if db:
            await update_admin_user_name(db, target_id, new_name)
    # Re-render user detail card...
```

---

### 4. `src/bot/keyboards.py` (component/view, transform)

**Analog:** Existing `src/bot/keyboards.py` lines 570-588, 655-717, 738-768

**New / modified keyboards needed:**
- `build_admin_main_keyboard`: Add button for `[⏰ Đặt giờ sao lưu]` (`adm:bkp:menu`).
- `build_whitelist_user_detail_keyboard`: Add button `[✏️ Đổi tên]` (`adm:wl:rename_prompt:{target_id}`) per D-18.
- `build_model_switcher_keyboard`: Support empty available models list and add `[🗑️ Xoá model]` (`adm:mdl:del_menu`) per D-17.
- `build_backup_schedule_keyboard`: Preset buttons (`01:00`, `02:00`, `03:00`, `04:00`, `✏️ Nhập giờ khác`) per D-15.
- `build_model_delete_keyboard`: List non-active models with delete callbacks per D-17.

**Pattern excerpt:**
```python
def build_backup_schedule_keyboard(current_time: str) -> InlineKeyboardMarkup:
    """Build backup schedule time picker with presets and custom input."""
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
```

---

### 5. `src/bot/app.py` (config / entrypoint, setup / event-driven)

**Analog:** Existing `src/bot/app.py` lines 46-81 (startup sync) and lines 82-170 (application builder)

**PTB JobQueue and daily backup job pattern:**
```python
import zoneinfo
from datetime import time
from telegram.ext import Application, ContextTypes

VN_TZ = zoneinfo.ZoneInfo("Asia/Ho_Chi_Minh")
JOB_BACKUP_NAME = "daily_database_backup"

async def daily_backup_job_callback(context: ContextTypes.DEFAULT_TYPE) -> None:
    """Scheduled background job: execute hot backup and upload to Super Admin."""
    settings = context.bot_data.get("settings")
    if not settings or not settings.telegram_super_admin_id:
        return

    super_admin_id = settings.telegram_super_admin_id
    try:
        from src.bot.handlers.admin import _get_active_db_context
        from src.services.backup import execute_backup, send_backup_document

        async with _get_active_db_context(context) as db:
            if not db:
                return
            stats = await execute_backup(db)

        if stats["is_oversized"]:
            await context.bot.send_message(
                chat_id=super_admin_id,
                text=f"⚠️ [Sao lưu tự động] File nén >= 48MB ({stats['gz_size'] / (1024*1024):.2f} MB). "
                     f"Lưu trữ tại: {stats['gz_path']}",
            )
            return

        reduction = (1 - (stats["gz_size"] / max(stats["raw_size"], 1))) * 100
        caption = (
            f"💾 <b>BẢN SAO LƯU ĐỊNH KỲ TỰ ĐỘNG</b>\n"
            f"────────────────────\n"
            f"⏱️ <b>Thời gian:</b> {stats['timestamp_str']} (UTC+7)\n"
            f"📦 <b>Dung lượng:</b> {stats['raw_size'] / (1024*1024):.2f} MB ➔ {stats['gz_size'] / (1024*1024):.2f} MB (Giảm {reduction:.1f}%)\n"
            f"📊 <b>Dữ liệu:</b> {stats['order_count']} đơn hàng | {stats['customer_count']} khách hàng\n"
            f"────────────────────"
        )

        sent = await send_backup_document(
            bot=context.bot,
            chat_id=super_admin_id,
            file_path=stats["gz_path"],
            caption=caption,
        )
        if not sent:
            await context.bot.send_message(
                chat_id=super_admin_id,
                text=f"❌ [Sao lưu tự động] Gửi file thất bại sau 3 lần thử. File lưu tại: {stats['gz_path']}",
            )
    except Exception as e:
        logging.getLogger(__name__).exception("Scheduled backup failed: %s", e)
        try:
            await context.bot.send_message(
                chat_id=super_admin_id,
                text=f"❌ [Sao lưu tự động] Gặp lỗi nghiêm trọng: {e}",
            )
        except Exception:
            pass

def schedule_daily_backup(app: Application, time_str: str = "02:00") -> None:
    """Schedule or replace daily backup in JobQueue at target HH:MM UTC+7."""
    jq = app.job_queue
    if not jq:
        return
    for job in jq.get_jobs_by_name(JOB_BACKUP_NAME):
        job.schedule_removal()

    h, m = map(int, time_str.split(":"))
    target_time = time(h, m, tzinfo=VN_TZ)
    jq.run_daily(
        daily_backup_job_callback,
        time=target_time,
        name=JOB_BACKUP_NAME,
    )
```

---

### 6. `src/db/admin.py` (model / service, CRUD)

**Analog:** Existing `src/db/admin.py` lines 4-21 (`create_or_update_admin_user`)

**Excerpt for user rename:**
```python
async def update_admin_user_name(
    db: aiosqlite.Connection, telegram_id: int, new_name: str
) -> bool:
    """Update display name for an existing admin user."""
    cursor = await db.execute(
        """
        UPDATE admin_users
        SET name = ?, updated_at = CURRENT_TIMESTAMP
        WHERE telegram_id = ?
        """,
        (new_name, telegram_id),
    )
    await db.commit()
    return cursor.rowcount > 0
```

---

## Shared Patterns

### Access Control Guard
**Source:** `src/bot/security.py:31-70`  
**Apply to:** `/backup` command handler, `adm:bkp:*` callbacks, and time schedule settings.
```python
@require_role(UserRole.SUPER_ADMIN)
async def handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> Any:
    ...
```

### Database Context Resolution
**Source:** `src/bot/handlers/admin.py:34-49`  
**Apply to:** Backup handlers, scheduler callback, and administrative text input.
```python
async with _get_active_db_context(context) as db:
    ...
```

### Dynamic System Settings
**Source:** `src/db/settings.py`  
**Apply to:** `backup_schedule_time` key in `system_settings` table.
```python
await set_setting(db, "backup_schedule_time", "02:00", description="Daily backup schedule time HH:MM")
current_time = await get_setting(db, "backup_schedule_time", default="02:00")
```

---

## No Analog Found

None. All required capabilities have direct analogs in existing modules or verified standard library / PTB components.

---

## Metadata

**Analog search scope:** `src/`, `tests/`  
**Files scanned:** 25  
**Pattern extraction date:** 2026-10-25
