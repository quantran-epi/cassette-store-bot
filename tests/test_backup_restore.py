import gzip
import os
import sqlite3
from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, MagicMock, patch

import aiosqlite
import pytest

import src.services.backup as backup_service
from src.bot.handlers.backup import (
    handle_backup_document,
    handle_restore_callback,
)
from src.bot.security import UserRole
from src.db.schema import init_db
from src.services.backup import (
    RestoreApplyError,
    RestoreValidationError,
    apply_staged_restore,
    execute_backup,
    stage_restore_archive,
)

SUPER_ID = 999


async def _make_db(path: str, orders: int = 2, customers: int = 2) -> None:
    async with aiosqlite.connect(path) as db:
        await init_db(db)
        for i in range(customers):
            await db.execute(
                "INSERT INTO customers (name, phones, addresses) VALUES (?, ?, ?)",
                (f"Khach {i + 1}", "[]", "[]"),
            )
        for i in range(orders):
            await db.execute(
                """
                INSERT INTO orders (
                    customer_id, customer_name, customer_phone, shipping_address,
                    items_text, total_amount, cod_amount, payment_method, status
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    (i % max(customers, 1)) + 1,
                    f"Khach {i + 1}",
                    "0900000000",
                    "Ha Noi",
                    "2 bang",
                    100000,
                    100000,
                    "COD",
                    "CHO_LAM",
                ),
            )
        await db.commit()


async def _make_archive(tmp_path, orders: int = 2, customers: int = 2) -> tuple[str, str]:
    db_path = str(tmp_path / "source.db")
    backup_dir = str(tmp_path / "backups")
    await _make_db(db_path, orders=orders, customers=customers)
    async with aiosqlite.connect(db_path) as db:
        stats = await execute_backup(db, backup_dir=backup_dir)
    return stats["gz_path"], backup_dir


def _counts(db_path: str) -> tuple[int, int]:
    conn = sqlite3.connect(db_path)
    try:
        return (
            conn.execute("SELECT COUNT(*) FROM orders").fetchone()[0],
            conn.execute("SELECT COUNT(*) FROM customers").fetchone()[0],
        )
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Service tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_stage_and_apply_round_trip(tmp_path):
    gz_path, backup_dir = await _make_archive(tmp_path, orders=3, customers=2)
    staging = str(tmp_path / "staging")

    staged = stage_restore_archive(gz_path, staging)

    assert staged["order_count"] == 3
    assert staged["customer_count"] == 2
    assert staged["raw_size"] > 0
    assert os.path.exists(staged["staged_path"])

    target_db = str(tmp_path / "target.db")
    await _make_db(target_db, orders=1, customers=1)
    assert _counts(target_db) == (1, 1)

    before = [f for f in os.listdir(backup_dir) if f.startswith("pre_restore_")]
    result = apply_staged_restore(staged["staged_path"], target_db, backup_dir=backup_dir)

    assert result["safety_path"].startswith(os.path.join(backup_dir, "pre_restore_"))
    assert os.path.exists(result["safety_path"])
    assert _counts(target_db) == (3, 2)
    after = [f for f in os.listdir(backup_dir) if f.startswith("pre_restore_")]
    assert len(after) == len(before) + 1
    # Safety snapshot reflects the pre-restore data.
    assert _counts(result["safety_path"]) == (1, 1)


def test_stage_rejects_non_gzip_and_removes_staged(tmp_path):
    gz_path = tmp_path / "bad.gz"
    gz_path.write_bytes(b"not gzip at all")
    staging = str(tmp_path / "staging")

    with pytest.raises(RestoreValidationError):
        stage_restore_archive(str(gz_path), staging)

    assert not os.path.exists(os.path.join(staging, "restore.sqlite3"))


def test_stage_rejects_gzip_with_non_sqlite_payload(tmp_path):
    gz_path = tmp_path / "text.gz"
    with gzip.open(gz_path, "wb") as f:
        f.write(b"hello world, not a database")
    staging = str(tmp_path / "staging")

    with pytest.raises(RestoreValidationError):
        stage_restore_archive(str(gz_path), staging)

    assert not os.path.exists(os.path.join(staging, "restore.sqlite3"))


def test_stage_rejects_missing_required_table(tmp_path):
    raw = tmp_path / "partial.sqlite3"
    conn = sqlite3.connect(str(raw))
    conn.execute("CREATE TABLE customers (id INTEGER PRIMARY KEY, name TEXT, phones TEXT, addresses TEXT)")
    conn.commit()
    conn.close()

    gz_path = tmp_path / "partial.gz"
    with open(raw, "rb") as f_in, gzip.open(gz_path, "wb") as f_out:
        f_out.write(f_in.read())

    staging = str(tmp_path / "staging")
    with pytest.raises(RestoreValidationError, match="thiếu bảng"):
        stage_restore_archive(str(gz_path), staging)

    assert not os.path.exists(os.path.join(staging, "restore.sqlite3"))


@pytest.mark.asyncio
async def test_stage_rejects_oversized_payload(tmp_path, monkeypatch):
    gz_path, _ = await _make_archive(tmp_path)
    monkeypatch.setattr(backup_service, "MAX_RESTORE_UNCOMPRESSED", 1024)
    staging = str(tmp_path / "staging")

    with pytest.raises(RestoreValidationError, match="vượt quá giới hạn"):
        stage_restore_archive(gz_path, staging)

    assert not os.path.exists(os.path.join(staging, "restore.sqlite3"))


@pytest.mark.asyncio
async def test_apply_failure_before_write_keeps_data_and_reports_truth(tmp_path):
    gz_path, backup_dir = await _make_archive(tmp_path, orders=2, customers=2)
    staging = str(tmp_path / "staging")
    staged = stage_restore_archive(gz_path, staging)

    target_db = str(tmp_path / "target.db")
    await _make_db(target_db, orders=1, customers=1)

    # Make the snapshot step fail by pointing backup_dir at an existing file.
    blocker = tmp_path / "blocker"
    blocker.write_text("x")

    with pytest.raises(RestoreApplyError) as exc_info:
        apply_staged_restore(staged["staged_path"], target_db, backup_dir=str(blocker))

    assert exc_info.value.current_data_safe is True
    assert "không bị thay đổi" in str(exc_info.value)
    assert _counts(target_db) == (1, 1)


# ---------------------------------------------------------------------------
# Handler tests
# ---------------------------------------------------------------------------


def _make_context(user_id: int = SUPER_ID) -> MagicMock:
    context = MagicMock()
    settings = MagicMock()
    settings.sqlite_db_path = "test_target.db"
    settings.telegram_super_admin_id = SUPER_ID
    context.bot_data = {
        "settings": settings,
        "admin_roles": {SUPER_ID: UserRole.SUPER_ADMIN},
        "whitelist_user_ids": {SUPER_ID},
    }
    context.user_data = {}
    context.application = MagicMock()
    return context


def _make_upload_update(user_id: int = SUPER_ID, file_size: int = 1024) -> MagicMock:
    update = MagicMock()
    user = MagicMock()
    user.id = user_id
    update.effective_user = user
    update.callback_query = None

    message = MagicMock()
    message.document = MagicMock()
    message.document.file_name = "backup.sqlite3.gz"
    message.document.file_size = file_size
    message.document.get_file = AsyncMock()
    message.document.get_file.return_value.download_to_drive = AsyncMock()
    message.reply_text = AsyncMock()
    update.effective_message = message
    return update


def _make_callback_update(data: str, user_id: int = SUPER_ID) -> MagicMock:
    update = MagicMock()
    user = MagicMock()
    user.id = user_id
    update.effective_user = user

    query = MagicMock()
    query.data = data
    query.from_user = user
    query.answer = AsyncMock()
    query.edit_message_text = AsyncMock()
    update.callback_query = query
    update.effective_message = None
    return update


@pytest.mark.asyncio
async def test_document_upload_stages_and_asks_confirmation():
    update = _make_upload_update()
    context = _make_context()

    with patch("src.bot.handlers.backup.tempfile.mkdtemp", return_value="/tmp/restore_x"), \
         patch("src.bot.handlers.backup.stage_restore_archive", return_value={
             "staged_path": "/tmp/restore_x/restore.sqlite3",
             "raw_size": 4096,
             "order_count": 7,
             "customer_count": 3,
         }) as stage_mock:
        await handle_backup_document(update, context)

    stage_mock.assert_called_once()
    pending = context.user_data["pending_restore"]
    assert pending["user_id"] == SUPER_ID
    assert pending["stats"]["order_count"] == 7
    assert pending["temp_dir"] == "/tmp/restore_x"

    text = update.effective_message.reply_text.await_args[0][0]
    assert "XÁC NHẬN" in text
    assert "thay thế toàn bộ dữ liệu hiện tại" in text
    keyboard = update.effective_message.reply_text.await_args.kwargs["reply_markup"]
    callbacks = [b.callback_data for row in keyboard.inline_keyboard for b in row]
    assert f"adm:rst:ok:{pending['token']}" in callbacks
    assert f"adm:rst:cancel:{pending['token']}" in callbacks


@pytest.mark.asyncio
async def test_document_upload_rejects_oversized_file():
    update = _make_upload_update(file_size=25 * 1024 * 1024)
    context = _make_context()

    with patch("src.bot.handlers.backup.tempfile.mkdtemp") as mkdtemp:
        await handle_backup_document(update, context)

    mkdtemp.assert_not_called()
    assert "quá lớn" in update.effective_message.reply_text.await_args[0][0]
    assert "pending_restore" not in context.user_data


@pytest.mark.asyncio
async def test_document_upload_invalid_archive_cleans_up():
    update = _make_upload_update()
    context = _make_context()

    with patch("src.bot.handlers.backup.tempfile.mkdtemp", return_value="/tmp/restore_x"), \
         patch(
             "src.bot.handlers.backup.stage_restore_archive",
             side_effect=RestoreValidationError("bad gzip"),
         ), \
         patch("src.bot.handlers.backup.shutil.rmtree") as rmtree_mock:
        await handle_backup_document(update, context)

    rmtree_mock.assert_called_once_with("/tmp/restore_x", ignore_errors=True)
    assert "không hợp lệ" in update.effective_message.reply_text.await_args[0][0]
    assert "pending_restore" not in context.user_data


@pytest.mark.asyncio
async def test_callback_confirm_applies_restore_and_reloads():
    update = _make_callback_update("adm:rst:ok:tok")
    context = _make_context()
    context.user_data["pending_restore"] = {
        "token": "tok",
        "user_id": SUPER_ID,
        "temp_dir": "/tmp/restore_x",
        "staged_path": "/tmp/restore_x/restore.sqlite3",
        "stats": {"order_count": 7, "customer_count": 3},
        "expires_at": 10**12,
    }

    @asynccontextmanager
    async def fake_conn(_path):
        yield MagicMock()

    with patch(
        "src.bot.handlers.backup.apply_staged_restore",
        return_value={"safety_path": "backups/pre_restore_x.sqlite3"},
    ) as apply_mock, patch(
        "src.bot.handlers.backup.shutil.rmtree"
    ) as rmtree_mock, patch(
        "src.bot.app.startup_sync", new_callable=AsyncMock
    ) as sync_mock, patch(
        "src.db.connection.get_db_connection", fake_conn
    ), patch(
        "src.db.schema.init_db", new_callable=AsyncMock
    ):
        await handle_restore_callback(update, context)

    apply_mock.assert_called_once_with(
        "/tmp/restore_x/restore.sqlite3", "test_target.db"
    )
    sync_mock.assert_awaited_once()
    rmtree_mock.assert_called_once_with("/tmp/restore_x", ignore_errors=True)
    assert "pending_restore" not in context.user_data
    final_text = update.callback_query.edit_message_text.await_args_list[-1][0][0]
    assert "THÀNH CÔNG" in final_text
    assert "7 đơn hàng" in final_text


@pytest.mark.asyncio
async def test_callback_cancel_keeps_db_untouched():
    update = _make_callback_update("adm:rst:cancel:tok")
    context = _make_context()
    context.user_data["pending_restore"] = {
        "token": "tok",
        "user_id": SUPER_ID,
        "temp_dir": "/tmp/restore_x",
        "staged_path": "/tmp/restore_x/restore.sqlite3",
        "stats": {},
        "expires_at": 10**12,
    }

    with patch("src.bot.handlers.backup.apply_staged_restore") as apply_mock, \
         patch("src.bot.handlers.backup.shutil.rmtree") as rmtree_mock:
        await handle_restore_callback(update, context)

    apply_mock.assert_not_called()
    rmtree_mock.assert_called_once_with("/tmp/restore_x", ignore_errors=True)
    assert "pending_restore" not in context.user_data
    assert "Đã huỷ" in update.callback_query.edit_message_text.await_args[0][0]


@pytest.mark.asyncio
async def test_callback_confirm_rejects_different_user():
    update = _make_callback_update("adm:rst:ok:tok", user_id=888)
    context = _make_context()
    # 888 is also a Super Admin, but did not upload this file.
    context.bot_data["admin_roles"][888] = UserRole.SUPER_ADMIN
    context.user_data["pending_restore"] = {
        "token": "tok",
        "user_id": SUPER_ID,
        "temp_dir": "/tmp/restore_x",
        "staged_path": "/tmp/restore_x/restore.sqlite3",
        "stats": {},
        "expires_at": 10**12,
    }

    with patch("src.bot.handlers.backup.apply_staged_restore") as apply_mock:
        await handle_restore_callback(update, context)

    apply_mock.assert_not_called()
    alert = update.callback_query.answer.await_args
    assert alert.kwargs.get("show_alert") is True
    assert "Chỉ người đã gửi file" in alert.args[0]


@pytest.mark.asyncio
async def test_callback_expired_request_cleans_up():
    update = _make_callback_update("adm:rst:ok:tok")
    context = _make_context()
    context.user_data["pending_restore"] = {
        "token": "tok",
        "user_id": SUPER_ID,
        "temp_dir": "/tmp/restore_x",
        "staged_path": "/tmp/restore_x/restore.sqlite3",
        "stats": {},
        "expires_at": 1,
    }

    with patch("src.bot.handlers.backup.apply_staged_restore") as apply_mock, \
         patch("src.bot.handlers.backup.shutil.rmtree") as rmtree_mock:
        await handle_restore_callback(update, context)

    apply_mock.assert_not_called()
    rmtree_mock.assert_called_once_with("/tmp/restore_x", ignore_errors=True)
    assert "hết hạn" in update.callback_query.edit_message_text.await_args[0][0]


@pytest.mark.asyncio
async def test_callback_stale_token_does_not_apply_newer_upload():
    update = _make_callback_update("adm:rst:ok:old-token")
    context = _make_context()
    context.user_data["pending_restore"] = {
        "token": "new-token",
        "user_id": SUPER_ID,
        "temp_dir": "/tmp/restore_x",
        "staged_path": "/tmp/restore_x/restore.sqlite3",
        "stats": {},
        "expires_at": 10**12,
    }

    with patch("src.bot.handlers.backup.apply_staged_restore") as apply_mock:
        await handle_restore_callback(update, context)

    apply_mock.assert_not_called()
    assert "lần tải file cũ" in update.callback_query.edit_message_text.await_args[0][0]
    assert context.user_data["pending_restore"]["token"] == "new-token"


@pytest.mark.asyncio
async def test_document_upload_rejects_non_super_admin():
    update = _make_upload_update(user_id=888)
    context = _make_context()
    context.bot_data["admin_roles"][888] = UserRole.ADMIN

    await handle_backup_document(update, context)

    assert "Từ chối truy cập" in update.effective_message.reply_text.await_args[0][0]
    assert "pending_restore" not in context.user_data


@pytest.mark.asyncio
async def test_callback_unauthorized_user_rejected_by_decorator():
    update = _make_callback_update("adm:rst:ok:tok", user_id=888)
    context = _make_context()
    context.bot_data["admin_roles"] = {SUPER_ID: UserRole.SUPER_ADMIN, 888: UserRole.ADMIN}
    context.user_data["pending_restore"] = {
        "token": "tok",
        "user_id": 888,
        "temp_dir": "/tmp/restore_x",
        "staged_path": "/tmp/restore_x/restore.sqlite3",
        "stats": {},
        "expires_at": 10**12,
    }

    with patch("src.bot.handlers.backup.apply_staged_restore") as apply_mock:
        await handle_restore_callback(update, context)

    apply_mock.assert_not_called()
    alert = update.callback_query.answer.await_args
    assert alert.kwargs.get("show_alert") is True


def test_app_registers_document_and_restore_handlers():
    from pydantic import SecretStr
    from telegram.ext import CallbackQueryHandler, MessageHandler

    from src.bot.app import build_application
    from src.config import Settings

    settings = Settings(telegram_bot_token=SecretStr("fake"))
    app = build_application(settings)
    handlers = app.handlers.get(0, [])

    doc_handlers = [h for h in handlers if isinstance(h, MessageHandler)]
    assert any(h.callback is handle_backup_document for h in doc_handlers)

    patterns = [
        h.pattern.pattern
        for h in handlers
        if isinstance(h, CallbackQueryHandler) and hasattr(h.pattern, "pattern")
    ]
    assert any("adm:rst:" in p for p in patterns)
