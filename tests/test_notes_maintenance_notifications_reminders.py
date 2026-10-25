from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch
from zoneinfo import ZoneInfo

import pytest
from telegram import CallbackQuery, Message, Update, User
from telegram.ext import ApplicationHandlerStop

from src.bot.handlers.admin import handle_admin_callback
from src.bot.handlers.callbacks import handle_order_callback
from src.bot.handlers.order_actions import (
    handle_action_state_text,
    handle_order_action_callback,
    handle_order_status_callback,
)
from src.bot.keyboards import (
    build_order_detail_keyboard,
    render_order_detail_card,
)
from src.bot.security import UserRole, maintenance_gate
from src.db.customers import get_customer_by_phone
from src.db.orders import create_order, get_order_by_id
from src.db.reminders import (
    create_reminder,
    get_due_reminders,
    get_reminders_by_order_id,
    mark_reminder_sent,
)
from src.db.settings import get_maintenance_mode, set_maintenance_mode
from src.models.order import Order, OrderStatus
from src.models.reminder import Reminder
from src.services.extractor import extract_reminder_from_text

VN_TZ = ZoneInfo("Asia/Ho_Chi_Minh")


# ==========================================
# 1. Notes saved to Order, not Customer
# ==========================================
@pytest.mark.asyncio
async def test_notes_saved_to_order_not_customer(test_db):
    draft_id = "1234abcd"
    pending_orders = {
        draft_id: {
            "draft_id": draft_id,
            "customer_name": "Anh Ba Ghi Chú",
            "customer_phone": "0912345678",
            "shipping_address": "123 Phố Huế",
            "items_text": "2 cuốn Tuấn Vũ",
            "total_amount": 200000,
            "cod_amount": 200000,
            "payment_method": "COD",
            "notes": "Khách dặn gói kỹ trong hộp xốp",
            "photo_file_ids": [],
            "raw_text": "...",
        }
    }

    query = MagicMock(spec=CallbackQuery)
    query.data = f"ord:cf:{draft_id}"
    query.from_user = User(id=999, first_name="Staff", is_bot=False)
    query.edit_message_text = AsyncMock()

    update = MagicMock(spec=Update)
    update.callback_query = query
    update.effective_user = query.from_user

    bot = AsyncMock()
    context = MagicMock()
    context.user_data = {"pending_orders": pending_orders}
    context.application.bot_data = {
        "db": test_db,
        "whitelist_user_ids": {999, 111},
    }
    context.bot_data = context.application.bot_data
    context.bot = bot

    await handle_order_callback(update, context)

    # Verify Customer notes is EMPTY
    customer = await get_customer_by_phone(test_db, "0912345678")
    assert customer is not None
    assert customer.notes == ""

    # Verify Order notes HAS the note
    order = await get_order_by_id(test_db, 1)
    assert order is not None
    assert order.notes == "Khách dặn gói kỹ trong hộp xốp"

    # Verify order detail card displays notes
    card = render_order_detail_card(order)
    assert "Khách dặn gói kỹ trong hộp xốp" in card
    assert "GHI CHÚ:" in card or "Ghi chú:" in card

    # Verify broadcast sent to other user (111) but NOT creator (999)
    assert bot.send_message.call_count == 1
    assert bot.send_message.call_args[1]["chat_id"] == 111
    markup = bot.send_message.call_args[1]["reply_markup"]
    assert markup is not None
    btn = markup.inline_keyboard[0][0]
    assert btn.callback_data == "ord_v:1"
    assert "Xem chi tiết" in btn.text


# ==========================================
# 2. Maintenance Mode
# ==========================================
@pytest.mark.asyncio
async def test_maintenance_mode_settings_and_gate(test_db):
    # Default is False
    assert await get_maintenance_mode(test_db) is False

    await set_maintenance_mode(test_db, True)
    assert await get_maintenance_mode(test_db) is True

    await set_maintenance_mode(test_db, False)
    assert await get_maintenance_mode(test_db) is False


@pytest.mark.asyncio
async def test_maintenance_gate_blocks_staff_allows_super_admin():
    update_staff = MagicMock(spec=Update)
    staff_user = User(id=101, first_name="Staff", is_bot=False)
    update_staff.effective_user = staff_user
    msg_staff = AsyncMock(spec=Message)
    update_staff.effective_message = msg_staff
    update_staff.callback_query = None

    context = MagicMock()
    context.bot_data = {
        "maintenance_mode": True,
        "admin_roles": {101: UserRole.STAFF, 999: UserRole.SUPER_ADMIN},
    }

    # Staff blocked
    with pytest.raises(ApplicationHandlerStop):
        await maintenance_gate(update_staff, context)
    msg_staff.reply_text.assert_called_once()
    assert "Hệ thống đang bảo trì" in msg_staff.reply_text.call_args[0][0]

    # Super admin passes through without exception
    update_sa = MagicMock(spec=Update)
    sa_user = User(id=999, first_name="SuperAdmin", is_bot=False)
    update_sa.effective_user = sa_user
    update_sa.effective_message = AsyncMock(spec=Message)
    update_sa.callback_query = None

    await maintenance_gate(update_sa, context)


@pytest.mark.asyncio
async def test_whitelist_gate_enforces_maintenance_for_whitelisted_staff():
    """Verify whitelist_gate itself blocks whitelisted staff when maintenance_mode is True."""
    from src.bot.security import whitelist_gate

    staff_user = User(id=101, first_name="StaffMember", is_bot=False)
    update = MagicMock(spec=Update)
    update.effective_user = staff_user
    msg = AsyncMock(spec=Message)
    update.effective_message = msg
    update.callback_query = None

    context = MagicMock()
    context.bot_data = {
        "whitelist_user_ids": {101, 999},
        "maintenance_mode": True,
        "admin_roles": {101: UserRole.STAFF, 999: UserRole.SUPER_ADMIN},
    }

    with pytest.raises(ApplicationHandlerStop):
        await whitelist_gate(update, context)

    msg.reply_text.assert_called_once()
    assert "Hệ thống đang bảo trì" in msg.reply_text.call_args[0][0]


@pytest.mark.asyncio
async def test_admin_maintenance_toggle_and_broadcast(test_db):
    query = MagicMock(spec=CallbackQuery)
    query.data = "adm:maint:toggle"
    query.from_user = User(id=999, first_name="Boss", is_bot=False)
    query.answer = AsyncMock()
    query.edit_message_text = AsyncMock()

    update = MagicMock(spec=Update)
    update.callback_query = query
    update.effective_user = query.from_user

    bot = AsyncMock()
    context = MagicMock()
    context.bot_data = {
        "db": test_db,
        "maintenance_mode": False,
        "admin_roles": {999: UserRole.SUPER_ADMIN},
        "whitelist_user_ids": {999, 101, 102},
    }
    context.bot = bot

    # Toggle ON
    await handle_admin_callback(update, context)
    assert context.bot_data["maintenance_mode"] is True
    assert await get_maintenance_mode(test_db) is True
    # Broadcast called for all whitelisted users EXCLUDING performer 999
    assert bot.send_message.call_count == 2
    sent_chat_ids = {call[1]["chat_id"] for call in bot.send_message.call_args_list}
    assert 999 not in sent_chat_ids
    assert sent_chat_ids == {101, 102}
    broadcast_msg = bot.send_message.call_args_list[0][1]["text"]
    assert "THÔNG BÁO BẢO TRÌ" in broadcast_msg

    bot.send_message.reset_mock()

    # Toggle OFF
    await handle_admin_callback(update, context)
    assert context.bot_data["maintenance_mode"] is False
    assert await get_maintenance_mode(test_db) is False
    assert bot.send_message.call_count == 2
    sent_chat_ids = {call[1]["chat_id"] for call in bot.send_message.call_args_list}
    assert 999 not in sent_chat_ids
    broadcast_msg = bot.send_message.call_args_list[0][1]["text"]
    assert "HOẠT ĐỘNG TRỞ LẠI" in broadcast_msg


# ==========================================
# 3. Lifecycle Broadcasts
# ==========================================
@pytest.mark.asyncio
async def test_order_status_change_broadcasts(test_db):
    order = Order(
        customer_name="Trần Văn Nam",
        customer_phone="0987654321",
        shipping_address="456 Kim Mã",
        items_text="1 cuốn Chế Linh",
        total_amount=150000,
        cod_amount=150000,
        status=OrderStatus.CHO_LAM,
    )
    oid = await create_order(test_db, order)

    query = MagicMock(spec=CallbackQuery)
    query.from_user = User(id=999, first_name="Packer", is_bot=False)
    query.data = f"ord_st:{oid}:DA_DONG_GOI"
    query.answer = AsyncMock()
    query.edit_message_text = AsyncMock()

    update = MagicMock(spec=Update)
    update.callback_query = query

    bot = AsyncMock()
    context = MagicMock()
    context.application.bot_data = {
        "db": test_db,
        "whitelist_user_ids": {999, 101},
    }
    context.bot_data = context.application.bot_data
    context.bot = bot

    await handle_order_status_callback(update, context)

    # Verify DA_DONG_GOI broadcast sent excluding performer 999
    assert bot.send_message.call_count == 1
    assert bot.send_message.call_args[1]["chat_id"] == 101
    sent_text = bot.send_message.call_args[1]["text"]
    assert "ĐÃ ĐÓNG GÓI" in sent_text
    assert f"#{oid}" in sent_text
    btn = bot.send_message.call_args[1]["reply_markup"].inline_keyboard[0][0]
    assert btn.callback_data == f"ord_v:{oid}"

    bot.send_message.reset_mock()

    # Now change to DA_TAO_DON
    query.data = f"ord_st:{oid}:DA_TAO_DON"
    await handle_order_status_callback(update, context)
    assert bot.send_message.call_count == 1
    assert bot.send_message.call_args[1]["chat_id"] == 101
    sent_text = bot.send_message.call_args[1]["text"]
    assert "ĐÃ TẠO ĐƠN VẬN CHUYỂN" in sent_text
    btn2 = bot.send_message.call_args[1]["reply_markup"].inline_keyboard[0][0]
    assert btn2.callback_data == f"ord_v:{oid}"


# ==========================================
# 4. Reminders System
# ==========================================
@pytest.mark.asyncio
async def test_reminders_crud_and_due(test_db):
    order = Order(
        customer_name="Khách Hẹn",
        customer_phone="0901112233",
        shipping_address="789 Láng Hạ",
        items_text="3 phôi HF 90",
        total_amount=300000,
        cod_amount=300000,
    )
    oid = await create_order(test_db, order)

    # 1. Past due reminder
    past_due = (datetime.now(VN_TZ) - timedelta(minutes=10)).strftime("%Y-%m-%d %H:%M:%S")
    rem1 = Reminder(
        id=None,
        order_id=oid,
        remind_at=past_due,
        reminder_text="Giao hàng buổi sáng",
    )
    rid1 = await create_reminder(test_db, rem1)
    assert rid1 > 0

    # 2. Future reminder
    future = (datetime.now(VN_TZ) + timedelta(days=2)).strftime("%Y-%m-%d %H:%M:%S")
    rem2 = Reminder(
        id=None,
        order_id=oid,
        remind_at=future,
        reminder_text="Khách dặn tuần sau mới ship",
    )
    rid2 = await create_reminder(test_db, rem2, supersede_existing=False)
    assert rid2 > 0

    # Check order reminders
    order_reminders = await get_reminders_by_order_id(test_db, oid)
    assert len(order_reminders) == 2

    # Check due reminders
    due = await get_due_reminders(test_db)
    assert len(due) == 1
    assert due[0]["reminder_id"] == rid1
    assert due[0]["customer_name"] == "Khách Hẹn"

    # Mark sent
    assert await mark_reminder_sent(test_db, rid1) is True
    due_after = await get_due_reminders(test_db)
    assert len(due_after) == 0

    # Test default create_reminder supersedes pending reminder
    rem3 = Reminder(
        id=None,
        order_id=oid,
        remind_at=future,
        reminder_text="Đổi sang chiều thứ 5",
    )
    rid3 = await create_reminder(test_db, rem3)
    active_rems = await get_reminders_by_order_id(test_db, oid)
    assert len(active_rems) == 1
    assert active_rems[0].id == rid3


@pytest.mark.asyncio
async def test_extract_reminder_from_text_fallback():
    client = AsyncMock()
    # Mock LLM failure to test deterministic parser
    client.beta.chat.completions.parse = AsyncMock(side_effect=Exception("LLM network error"))

    now_base = datetime(2026, 10, 26, 8, 0, tzinfo=VN_TZ)
    iso_time, note = await extract_reminder_from_text(
        client, "dummy-model", "chiều mai 15h gọi lại cho khách", now_dt=now_base
    )
    assert iso_time == "2026-10-27 15:00"
    assert "chiều mai 15h gọi lại cho khách" in note


@pytest.mark.asyncio
async def test_order_detail_card_and_reminder_prompt():
    order = Order(
        id=42,
        customer_name="Bác Năm",
        customer_phone="0933445566",
        shipping_address="Hà Nội",
        items_text="Băng Chế Linh",
        total_amount=100000,
        cod_amount=100000,
        notes="Giao trước 12h",
    )
    kb = build_order_detail_keyboard(order, "2026-10-25", 1)
    # Check that reminder button exists
    all_buttons = [btn for row in kb.inline_keyboard for btn in row]
    reminder_btn = next((b for b in all_buttons if "ord_act:remind:42" in (b.callback_data or "")), None)
    assert reminder_btn is not None
    assert "nhắc" in reminder_btn.text.lower()

    # Test clicking reminder button sets state
    query = MagicMock(spec=CallbackQuery)
    query.data = "ord_act:remind:42"
    query.answer = AsyncMock()
    query.message = AsyncMock()

    update = MagicMock(spec=Update)
    update.callback_query = query
    bot = AsyncMock()
    context = MagicMock()
    context.bot = bot
    context.user_data = {}

    await handle_order_action_callback(update, context)
    assert context.user_data.get("action_state")["action"] == "await_reminder"
    assert context.user_data.get("action_state")["order_id"] == 42
    bot.send_message.assert_called_once()
    assert "ĐẶT LỊCH NHẮC VIỆC" in bot.send_message.call_args[1]["text"]


@pytest.mark.asyncio
async def test_handle_action_state_text_reminder(test_db):
    order = Order(
        customer_name="Bác Tư",
        customer_phone="0911223344",
        shipping_address="Hà Nội",
        items_text="Băng Nhạc Vàng",
        total_amount=150000,
        cod_amount=150000,
    )
    oid = await create_order(test_db, order)

    msg = AsyncMock(spec=Message)
    msg.text = "Thứ 2 tuần sau 10h sáng gửi hàng nhé"
    msg.reply_text = AsyncMock()

    update = MagicMock(spec=Update)
    update.message = msg
    update.effective_user = User(id=999, first_name="Staff", is_bot=False)

    context = MagicMock()
    context.bot_data = {
        "db": test_db,
        "openai_client": AsyncMock(),
        "active_model_id": "test-model",
    }
    context.user_data = {
        "action_state": {
            "action": "await_reminder",
            "order_id": oid,
            "expires_at": 9999999999,
        }
    }

    # Mock extract_reminder_from_text
    with patch(
        "src.services.extractor.extract_reminder_from_text",
        new=AsyncMock(return_value=("2026-11-02 10:00", "Gửi hàng cho khách")),
    ):
        handled = await handle_action_state_text(update, context, context.user_data["action_state"])
        assert handled is True

    # Verify action_state was cleared
    assert "action_state" not in context.user_data

    # Verify reminder saved in DB
    rems = await get_reminders_by_order_id(test_db, oid)
    assert len(rems) == 1
    assert rems[0].remind_at == "2026-11-02 10:00"
    assert rems[0].reminder_text == "Gửi hàng cho khách"

    msg.reply_text.assert_called_once()
    assert "ĐÃ ĐẶT LỊCH NHẮC THÀNH CÔNG" in msg.reply_text.call_args[0][0]


@pytest.mark.asyncio
async def test_order_creation_with_mai_gui_extracts_reminder():
    """Verify that messages with 'khách dặn mai gửi' get reminder_at automatically populated."""
    from src.models.extractor import ExtractedOrder
    from src.services.extractor import _apply_deterministic_fallbacks

    # Simulate LLM returning order without reminder_at but with raw_text / notes containing 'khách dặn mai gửi'
    extracted = ExtractedOrder(
        customer_name="Bác Hùng",
        customer_phone="0909123456",
        shipping_address="10 Đội Cấn HN",
        items_text="1 cuốn Lệ Quyên",
        total_amount=150000,
        cod_amount=150000,
        notes="khách dặn mai gửi",
    )
    raw_text = "Bác Hùng 0909123456 10 Đội Cấn HN lấy 1 cuốn Lệ Quyên 150k cod khách dặn mai gửi"

    result = _apply_deterministic_fallbacks(extracted, raw_text)
    assert result.reminder_at is not None
    # Must be tomorrow 09:00
    now_vn = datetime.now(VN_TZ)
    tomorrow_iso = (now_vn + timedelta(days=1)).strftime("%Y-%m-%d 09:00")
    assert result.reminder_at == tomorrow_iso
    assert result.reminder_note is not None


def test_app_handler_pattern_matches_remind():
    """Verify that CallbackQueryHandler regex in app.py matches ord_act:remind:{order_id}."""
    import re

    pattern = re.compile(
        r"^ord_act:(track|add_photo|view_photo|remind|remind_del|cancel)(:\d+)?$"
    )
    assert pattern.match("ord_act:remind:42") is not None
    assert pattern.match("ord_act:remind_del:42") is not None
    assert pattern.match("ord_act:cancel") is not None
    assert pattern.match("ord_act:track:12") is not None


@pytest.mark.asyncio
async def test_order_card_displays_reminder_and_deletion(test_db):
    order = Order(
        customer_name="Bác Bảy",
        customer_phone="0977889900",
        shipping_address="Hải Phòng",
        items_text="Băng Hương Lan",
        total_amount=200000,
        cod_amount=200000,
    )
    oid = await create_order(test_db, order)
    rem = Reminder(
        id=None,
        order_id=oid,
        remind_at="2026-10-30 09:00",
        reminder_text="Giao sáng thứ 6",
    )
    await create_reminder(test_db, rem)

    rems = await get_reminders_by_order_id(test_db, oid)
    assert len(rems) == 1

    card = render_order_detail_card(order, reminders=rems)
    assert "2026-10-30 09:00" in card
    assert "Giao sáng thứ 6" in card

    # Test clicking delete reminder
    query = MagicMock(spec=CallbackQuery)
    query.data = f"ord_act:remind_del:{oid}"
    query.answer = AsyncMock()
    query.message = AsyncMock()

    update = MagicMock(spec=Update)
    update.callback_query = query
    bot = AsyncMock()
    context = MagicMock()
    context.bot = bot
    context.bot_data = {"db": test_db}
    context.user_data = {}

    await handle_order_action_callback(update, context)
    bot.send_message.assert_called_once()
    assert "ĐÃ HUỶ LỊCH NHẮC" in bot.send_message.call_args[1]["text"]

    rems_after = await get_reminders_by_order_id(test_db, oid)
    assert len(rems_after) == 0


def test_sunday_weekday_formatting_and_thu2_tuan_sau():
    """Verify Sunday 2026-10-25 is Chủ Nhật and 'thứ 2 tuần sau' parses to 2026-11-02."""
    from src.services.extractor import VN_WEEKDAYS, _parse_vietnamese_relative_time

    # Sunday 2026-10-25
    sunday_dt = datetime(2026, 10, 25, 10, 0, tzinfo=VN_TZ)
    assert VN_WEEKDAYS[sunday_dt.weekday()] == "Chủ Nhật"

    # 'thứ 2 tuần sau' on Sunday must be 2026-11-02 (NOT 2026-10-27)
    res_next_week, _ = _parse_vietnamese_relative_time("thứ 2 tuần sau", sunday_dt)
    assert res_next_week == "2026-11-02 09:00"

    # 'thứ 2' (tomorrow) on Sunday must be 2026-10-26
    res_tomorrow, _ = _parse_vietnamese_relative_time("thứ 2", sunday_dt)
    assert res_tomorrow == "2026-10-26 09:00"

    # 'thứ 2 tuần sau' on Wednesday 2026-10-21 must be 2026-10-26
    wed_dt = datetime(2026, 10, 21, 10, 0, tzinfo=VN_TZ)
    res_wed, _ = _parse_vietnamese_relative_time("thứ 2 tuần sau", wed_dt)
    assert res_wed == "2026-10-26 09:00"


def test_cards_render_high_contrast_uppercase_labels():
    """Verify order detail, summary, and preview cards use uppercase labels for elderly clarity."""
    from src.bot.keyboards import format_order_item_summary, render_order_detail_card
    from src.bot.handlers.ingest import render_preview_card

    order = Order(
        id=99,
        customer_name="Bác Tư",
        customer_phone="0912345678",
        shipping_address="Hà Nội",
        items_text="2 cuốn Tuấn Vũ",
        total_amount=150000,
        cod_amount=150000,
        notes="Gói cẩn thận",
    )

    # 1. Detail card
    detail_card = render_order_detail_card(order)
    assert "👤 <b>KHÁCH:</b>" in detail_card
    assert "📞 <b>SĐT:</b>" in detail_card
    assert "📍 <b>ĐỊA CHỈ:</b>" in detail_card
    assert "💰 <b>TỔNG TIỀN:</b>" in detail_card
    assert "💵 <b>TIỀN COD THU:</b>" in detail_card
    assert "📝 <b>GHI CHÚ:</b>" in detail_card

    # 2. Summary item
    summary = format_order_item_summary(order)
    assert "📞 <b>SĐT:</b>" in summary
    assert "📍 <b>Đ/C:</b>" in summary
    assert "💰 <b>TIỀN:</b>" in summary

    # 3. Preview card
    draft = {
        "draft_id": "draft99",
        "customer_name": "Bác Tư",
        "customer_phone": "0912345678",
        "shipping_address": "Hà Nội",
        "items_text": "2 cuốn Tuấn Vũ",
        "total_amount": 150000,
        "cod_amount": 150000,
        "payment_method": "COD",
        "notes": "Gói cẩn thận",
    }
    preview_text, _ = render_preview_card(draft)
    assert "👤 <b>KHÁCH:</b>" in preview_text
    assert "📞 <b>SĐT:</b>" in preview_text
    assert "📍 <b>ĐỊA CHỈ:</b>" in preview_text
    assert "💰 <b>TỔNG TIỀN:</b>" in preview_text
    assert "💵 <b>TIỀN COD THU:</b>" in preview_text




