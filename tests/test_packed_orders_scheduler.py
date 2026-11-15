from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from telegram.error import TelegramError

from src.bot.app import (
    JOB_PACKED_ORDERS_NAME,
    packed_orders_job_callback,
    schedule_packed_orders_checker,
)
from src.db.connection import get_db_connection
from src.db.schema import init_db
from src.models.order import OrderStatus


def test_schedule_registers_hourly_job_and_replaces_previous():
    app = MagicMock()
    old_job = MagicMock()
    app.job_queue.get_jobs_by_name.return_value = [old_job]

    schedule_packed_orders_checker(app)

    app.job_queue.get_jobs_by_name.assert_called_once_with(JOB_PACKED_ORDERS_NAME)
    old_job.schedule_removal.assert_called_once_with()
    app.job_queue.run_repeating.assert_called_once_with(
        packed_orders_job_callback,
        interval=3600,
        first=3600,
        name=JOB_PACKED_ORDERS_NAME,
    )


def test_schedule_without_job_queue():
    schedule_packed_orders_checker(SimpleNamespace(job_queue=None))


@pytest.mark.parametrize("packed_count", [0, 2])
@pytest.mark.parametrize("file_db", [False, True])
async def test_reminder_counts_only_packed_orders(test_db, tmp_path, packed_count, file_db):
    path = str(tmp_path / "orders.db") if file_db else ":memory:"
    settings = SimpleNamespace(telegram_super_admin_id=999, sqlite_db_path=path)
    context = SimpleNamespace(
        bot_data={"settings": settings, "db": None if file_db else test_db},
        bot=SimpleNamespace(send_message=AsyncMock()),
    )

    async def seed(db):
        statuses = [s.value for s in OrderStatus if s != OrderStatus.DA_DONG_GOI]
        statuses += [OrderStatus.DA_DONG_GOI.value] * packed_count
        await db.executemany(
            """INSERT INTO orders
               (customer_name, customer_phone, shipping_address, items_text, status, created_at)
               VALUES ('Khách thử', '0901234567', 'Địa chỉ thử', 'Băng thử', ?, '2020-01-01')""",
            [(status,) for status in statuses],
        )
        await db.commit()

    if file_db:
        async with get_db_connection(path) as db:
            await init_db(db)
            await seed(db)
    else:
        await seed(test_db)

    await packed_orders_job_callback(context)

    if not packed_count:
        context.bot.send_message.assert_not_awaited()
        return
    context.bot.send_message.assert_awaited_once()
    kwargs = context.bot.send_message.await_args.kwargs
    assert kwargs["chat_id"] == 999
    assert f"{packed_count} đơn đã đóng gói" in kwargs["text"]
    assert "TẠO ĐƠN VẬN CHUYỂN" in kwargs["text"]
    assert kwargs["reply_markup"].inline_keyboard[0][0].callback_data == "ord_ls:DA_DONG_GOI:1"

    # Each later hourly tick must remind again and use the current recipient.
    settings.telegram_super_admin_id = 888
    await packed_orders_job_callback(context)
    assert context.bot.send_message.await_count == 2
    assert context.bot.send_message.await_args.kwargs["chat_id"] == 888

    async def clear_packed(db):
        await db.execute("UPDATE orders SET status = 'DA_TAO_DON' WHERE status = 'DA_DONG_GOI'")
        await db.commit()

    if file_db:
        async with get_db_connection(path) as db:
            await clear_packed(db)
    else:
        await clear_packed(test_db)
    await packed_orders_job_callback(context)
    assert context.bot.send_message.await_count == 2


@pytest.mark.parametrize("settings", [None, SimpleNamespace(telegram_super_admin_id=None)])
async def test_no_super_admin_skips_database_and_message(settings):
    context = SimpleNamespace(bot_data={"settings": settings}, bot=AsyncMock())
    with patch("src.bot.handlers.admin._get_active_db_context") as db_context:
        await packed_orders_job_callback(context)
    db_context.assert_not_called()
    context.bot.send_message.assert_not_awaited()


@pytest.mark.parametrize("error", [TelegramError("Send failed"), RuntimeError("DB failed")])
async def test_job_logs_errors_without_raising(test_db, caplog, error):
    context = SimpleNamespace(
        bot_data={"settings": SimpleNamespace(telegram_super_admin_id=999), "db": test_db},
        bot=SimpleNamespace(send_message=AsyncMock(side_effect=error)),
    )
    with patch("src.db.orders.count_orders_by_status", new_callable=AsyncMock) as count:
        count.return_value = 1
        if isinstance(error, RuntimeError):
            count.side_effect = error
        await packed_orders_job_callback(context)
    assert "Packed orders reminder failed" in caplog.text
