import datetime
import zoneinfo
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.bot.app import (
    JOB_BACKUP_NAME,
    VN_TZ,
    _do_sync,
    daily_backup_job_callback,
    schedule_daily_backup,
)


def test_constants():
    """Verify timezone and job name constants."""
    assert VN_TZ == zoneinfo.ZoneInfo("Asia/Ho_Chi_Minh")
    assert JOB_BACKUP_NAME == "daily_database_backup"


def test_schedule_daily_backup_registers_job():
    """Test 1: schedule_daily_backup registers daily job at specified time."""
    app = MagicMock()
    jq = MagicMock()
    app.job_queue = jq
    jq.get_jobs_by_name.return_value = []

    schedule_daily_backup(app, "02:00")

    jq.get_jobs_by_name.assert_called_once_with(JOB_BACKUP_NAME)
    jq.run_daily.assert_called_once()
    call_kwargs = jq.run_daily.call_args.kwargs
    assert call_kwargs["name"] == JOB_BACKUP_NAME
    assert call_kwargs["time"] == datetime.time(2, 0, tzinfo=VN_TZ)


def test_schedule_daily_backup_reschedule():
    """Test 2: calling schedule_daily_backup removes previous jobs and registers new time."""
    app = MagicMock()
    jq = MagicMock()
    app.job_queue = jq

    old_job = MagicMock()
    jq.get_jobs_by_name.return_value = [old_job]

    schedule_daily_backup(app, "03:30")

    old_job.schedule_removal.assert_called_once()
    jq.run_daily.assert_called_once()
    call_kwargs = jq.run_daily.call_args.kwargs
    assert call_kwargs["name"] == JOB_BACKUP_NAME
    assert call_kwargs["time"] == datetime.time(3, 30, tzinfo=VN_TZ)


def test_schedule_daily_backup_no_job_queue():
    """Verify schedule_daily_backup safely no-ops when job_queue is None."""
    app = MagicMock()
    app.job_queue = None
    # Must not raise
    schedule_daily_backup(app, "02:00")


@pytest.mark.asyncio
async def test_daily_backup_job_callback_execution():
    """Test 3: daily_backup_job_callback executes backup and sends document to Super Admin."""
    context = MagicMock()
    settings = MagicMock()
    settings.telegram_super_admin_id = 999888
    context.bot_data = {"settings": settings}
    context.bot.send_message = AsyncMock()

    stats = {
        "gz_path": "/tmp/backups/cassette_store_backup_20261025_020000.sqlite3.gz",
        "raw_path": "/tmp/backups/snapshot.sqlite3",
        "timestamp_str": "2026-10-25 02:00:00",
        "raw_size": 10 * 1024 * 1024,
        "gz_size": 2 * 1024 * 1024,
        "order_count": 42,
        "customer_count": 15,
        "is_oversized": False,
    }

    mock_db = MagicMock()

    with patch("src.bot.handlers.admin._get_active_db_context") as mock_db_ctx, \
         patch("src.services.backup.execute_backup", new_callable=AsyncMock) as mock_exec, \
         patch("src.services.backup.send_backup_document", new_callable=AsyncMock) as mock_send:

        # Set up async context manager mock
        mock_ctx = MagicMock()
        mock_ctx.__aenter__ = AsyncMock(return_value=mock_db)
        mock_ctx.__aexit__ = AsyncMock(return_value=None)
        mock_db_ctx.return_value = mock_ctx

        mock_exec.return_value = stats
        mock_send.return_value = True

        await daily_backup_job_callback(context)

        mock_exec.assert_awaited_once_with(mock_db)
        mock_send.assert_awaited_once()
        send_kwargs = mock_send.await_args.kwargs
        assert send_kwargs["chat_id"] == 999888
        assert send_kwargs["file_path"] == stats["gz_path"]
        assert "2026-10-25 02:00:00" in send_kwargs["caption"]
        assert "42 đơn hàng" in send_kwargs["caption"]
        assert "15 khách hàng" in send_kwargs["caption"]


@pytest.mark.asyncio
async def test_daily_backup_job_callback_oversized_alert():
    """Verify oversized backup triggers red alert message instead of document upload."""
    context = MagicMock()
    settings = MagicMock()
    settings.telegram_super_admin_id = 999888
    context.bot_data = {"settings": settings}
    context.bot.send_message = AsyncMock()

    stats = {
        "gz_path": "/tmp/backups/huge_backup.sqlite3.gz",
        "raw_path": "/tmp/backups/snapshot.sqlite3",
        "timestamp_str": "2026-10-25 02:00:00",
        "raw_size": 100 * 1024 * 1024,
        "gz_size": 49 * 1024 * 1024,
        "order_count": 5000,
        "customer_count": 2000,
        "is_oversized": True,
    }

    mock_db = MagicMock()

    with patch("src.bot.handlers.admin._get_active_db_context") as mock_db_ctx, \
         patch("src.services.backup.execute_backup", new_callable=AsyncMock) as mock_exec, \
         patch("src.services.backup.send_backup_document", new_callable=AsyncMock) as mock_send:

        mock_ctx = MagicMock()
        mock_ctx.__aenter__ = AsyncMock(return_value=mock_db)
        mock_ctx.__aexit__ = AsyncMock(return_value=None)
        mock_db_ctx.return_value = mock_ctx

        mock_exec.return_value = stats

        await daily_backup_job_callback(context)

        mock_send.assert_not_called()
        context.bot.send_message.assert_awaited_once()
        alert_text = context.bot.send_message.await_args.kwargs["text"]
        assert "48MB" in alert_text
        assert "huge_backup.sqlite3.gz" in alert_text


@pytest.mark.asyncio
async def test_daily_backup_job_callback_send_failure_alert():
    """Verify failure of send_backup_document triggers alert message to admin."""
    context = MagicMock()
    settings = MagicMock()
    settings.telegram_super_admin_id = 999888
    context.bot_data = {"settings": settings}
    context.bot.send_message = AsyncMock()

    stats = {
        "gz_path": "/tmp/backups/backup.sqlite3.gz",
        "raw_path": "/tmp/backups/snapshot.sqlite3",
        "timestamp_str": "2026-10-25 02:00:00",
        "raw_size": 10 * 1024 * 1024,
        "gz_size": 2 * 1024 * 1024,
        "order_count": 10,
        "customer_count": 5,
        "is_oversized": False,
    }

    mock_db = MagicMock()

    with patch("src.bot.handlers.admin._get_active_db_context") as mock_db_ctx, \
         patch("src.services.backup.execute_backup", new_callable=AsyncMock) as mock_exec, \
         patch("src.services.backup.send_backup_document", new_callable=AsyncMock) as mock_send:

        mock_ctx = MagicMock()
        mock_ctx.__aenter__ = AsyncMock(return_value=mock_db)
        mock_ctx.__aexit__ = AsyncMock(return_value=None)
        mock_db_ctx.return_value = mock_ctx

        mock_exec.return_value = stats
        mock_send.return_value = False

        await daily_backup_job_callback(context)

        context.bot.send_message.assert_awaited_once()
        alert_text = context.bot.send_message.await_args.kwargs["text"]
        assert "thất bại" in alert_text
        assert "backup.sqlite3.gz" in alert_text


@pytest.mark.asyncio
async def test_startup_sync_loads_backup_time():
    """Test 4: _do_sync reads backup_schedule_time and registers daily backup job."""
    app = MagicMock()
    app.bot_data = {"admin_roles": {}, "whitelist_user_ids": set()}
    db = MagicMock()
    settings = MagicMock()
    settings.telegram_super_admin_id = 123456
    settings.telegram_whitelist_user_ids = [123456]

    with patch("src.bot.app.sync_root_super_admin", new_callable=AsyncMock), \
         patch("src.bot.app.list_admin_users", new_callable=AsyncMock, return_value=[]), \
         patch("src.bot.app.get_setting", new_callable=AsyncMock) as mock_get_setting, \
         patch("src.bot.app.schedule_daily_backup") as mock_schedule:

        async def fake_get_setting(conn, key, default=None):
            if key == "backup_schedule_time":
                return "03:45"
            return default

        mock_get_setting.side_effect = fake_get_setting

        await _do_sync(app, db, settings)

        mock_schedule.assert_called_once_with(app, "03:45")
