from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock

import aiosqlite
import pytest
from telegram import InlineKeyboardMarkup

from src.bot.handlers.admin_milestones import (
    handle_milestone_text_input,
    render_milestone_detail_card,
)
from src.bot.keyboards import (
    build_milestone_confirm_delete_keyboard,
    build_milestone_detail_keyboard,
    build_milestone_list_keyboard,
)
from src.db.milestones import (
    create_milestone_rule,
    delete_milestone_rule,
    get_current_period_key,
    get_milestone_metric_value,
    get_milestone_rule_by_id,
    list_milestone_rules,
    toggle_milestone_rule_active,
    update_milestone_rule,
)
from src.db.orders import create_order
from src.db.schema import init_db
from src.models.milestone import MilestonePeriod, MilestoneRule, MilestoneTargetType
from src.models.order import Order, OrderStatus
from src.services.milestones import (
    FIREWORKS_EFFECT_ID,
    check_and_trigger_milestones,
    compute_milestone_pace_and_deadline,
)

TZ_VN = timezone(timedelta(hours=7))


@pytest.fixture
async def db():
    """In-memory SQLite connection with schema initialized."""
    conn = await aiosqlite.connect(":memory:")
    conn.row_factory = aiosqlite.Row
    await init_db(conn)
    yield conn
    await conn.close()


@pytest.mark.asyncio
async def test_milestone_rules_crud(db):
    rule = MilestoneRule(
        period=MilestonePeriod.MONTH,
        target_type=MilestoneTargetType.ORDER_COUNT,
        target_value=100,
        only_delivered=False,
        message_template="Chúc mừng đạt {target_value} đơn!",
        effect_enabled=True,
        is_active=True,
    )
    rule_id = await create_milestone_rule(db, rule)
    assert rule_id > 0

    fetched = await get_milestone_rule_by_id(db, rule_id)
    assert fetched is not None
    assert fetched.id == rule_id
    assert fetched.period == MilestonePeriod.MONTH
    assert fetched.target_value == 100
    assert fetched.is_active is True
    assert fetched.effect_enabled is True

    # List rules
    rules = await list_milestone_rules(db)
    assert len(rules) == 1

    # Toggle active
    await toggle_milestone_rule_active(db, rule_id)
    toggled = await get_milestone_rule_by_id(db, rule_id)
    assert toggled is not None and toggled.is_active is False

    active_rules = await list_milestone_rules(db, active_only=True)
    assert len(active_rules) == 0

    # Update rule
    toggled.target_value = 150
    toggled.is_active = True
    await update_milestone_rule(db, toggled)
    updated = await get_milestone_rule_by_id(db, rule_id)
    assert updated is not None and updated.target_value == 150 and updated.is_active is True

    # Delete rule
    deleted = await delete_milestone_rule(db, rule_id)
    assert deleted is True
    assert await get_milestone_rule_by_id(db, rule_id) is None


@pytest.mark.asyncio
async def test_period_key_generation():
    dt = datetime(2026, 10, 31, 15, 30, tzinfo=TZ_VN)
    assert get_current_period_key(MilestonePeriod.ALL_TIME, dt) == "all"
    assert get_current_period_key(MilestonePeriod.YEAR, dt) == "2026"
    assert get_current_period_key(MilestonePeriod.MONTH, dt) == "2026-10"
    assert get_current_period_key(MilestonePeriod.WEEK, dt) == "2026-43"


@pytest.mark.asyncio
async def test_milestone_metrics_calculation(db):
    # Insert orders with different statuses and amounts
    base_order = Order(
        customer_name="Nguyen Van A",
        customer_phone="0912345678",
        shipping_address="Hanoi",
        items_text="2 bang nha que",
        total_amount=200000,
        cod_amount=200000,
        status=OrderStatus.CHO_LAM,
    )
    # 1 CHO_LAM (200k)
    await create_order(db, base_order)

    # 1 DA_GIAO (500k)
    order_delivered = base_order.model_copy(
        update={"total_amount": 500000, "status": OrderStatus.DA_GIAO}
    )
    await create_order(db, order_delivered)

    # 1 BOM_HANG (300k) - should be excluded from both
    order_bom = base_order.model_copy(
        update={"total_amount": 300000, "status": OrderStatus.BOM_HANG}
    )
    await create_order(db, order_bom)

    # 1 HUY_DON (400k) - should be excluded from both
    order_cancel = base_order.model_copy(
        update={"total_amount": 400000, "status": OrderStatus.HUY_DON}
    )
    await create_order(db, order_cancel)

    # Metric: all_time order count for only_delivered=False -> 2 orders (CHO_LAM + DA_GIAO)
    cnt_any = await get_milestone_metric_value(
        db, MilestonePeriod.ALL_TIME, MilestoneTargetType.ORDER_COUNT, only_delivered=False
    )
    assert cnt_any == 2

    # Metric: all_time revenue for only_delivered=False -> 700k (200k + 500k)
    rev_any = await get_milestone_metric_value(
        db, MilestonePeriod.ALL_TIME, MilestoneTargetType.REVENUE, only_delivered=False
    )
    assert rev_any == 700000

    # Metric: all_time order count for only_delivered=True -> 1 order (DA_GIAO)
    cnt_del = await get_milestone_metric_value(
        db, MilestonePeriod.ALL_TIME, MilestoneTargetType.ORDER_COUNT, only_delivered=True
    )
    assert cnt_del == 1

    # Metric: all_time revenue for only_delivered=True -> 500k (DA_GIAO)
    rev_del = await get_milestone_metric_value(
        db, MilestonePeriod.ALL_TIME, MilestoneTargetType.REVENUE, only_delivered=True
    )
    assert rev_del == 500000


@pytest.mark.asyncio
async def test_milestone_trigger_broadcast_and_deduplication(db):
    bot = MagicMock()
    bot.send_message = AsyncMock()

    rule = MilestoneRule(
        period=MilestonePeriod.ALL_TIME,
        target_type=MilestoneTargetType.ORDER_COUNT,
        target_value=2,
        only_delivered=False,
        message_template="🎉 Chúc mừng shop đạt {current_value} đơn hàng!",
        effect_enabled=True,
        is_active=True,
    )
    rule_id = await create_milestone_rule(db, rule)
    rule.id = rule_id

    # 1 order created -> threshold 2 not reached yet
    o1 = Order(
        customer_name="Test",
        customer_phone="0901234567",
        shipping_address="Hanoi",
        items_text="Bang 1",
        total_amount=100000,
        status=OrderStatus.CHO_LAM,
    )
    await create_order(db, o1)

    triggered = await check_and_trigger_milestones(
        bot=bot,
        db=db,
        whitelist_ids=[111, 222],
        trigger_point="order_created",
    )
    assert len(triggered) == 0
    assert bot.send_message.call_count == 0

    # 2nd order created -> threshold 2 reached!
    o2 = Order(
        customer_name="Test 2",
        customer_phone="0901234568",
        shipping_address="Hanoi",
        items_text="Bang 2",
        total_amount=150000,
        status=OrderStatus.CHO_LAM,
    )
    await create_order(db, o2)

    triggered = await check_and_trigger_milestones(
        bot=bot,
        db=db,
        whitelist_ids=[111, 222],
        trigger_point="order_created",
    )
    assert len(triggered) == 1
    assert triggered[0][0].id == rule_id
    assert triggered[0][1] == 2

    # Verify broadcast was sent with fireworks effect
    assert bot.send_message.call_count == 2
    for call in bot.send_message.call_args_list:
        kwargs = call.kwargs
        assert kwargs["message_effect_id"] == FIREWORKS_EFFECT_ID
        assert "Chúc mừng shop đạt 2 đơn hàng!" in kwargs["text"]

    # 3rd order created -> should NOT trigger again in same period
    bot.send_message.reset_mock()
    o3 = Order(
        customer_name="Test 3",
        customer_phone="0901234569",
        shipping_address="Hanoi",
        items_text="Bang 3",
        total_amount=200000,
        status=OrderStatus.CHO_LAM,
    )
    await create_order(db, o3)

    triggered = await check_and_trigger_milestones(
        bot=bot,
        db=db,
        whitelist_ids=[111, 222],
        trigger_point="order_created",
    )
    assert len(triggered) == 0
    assert bot.send_message.call_count == 0


@pytest.mark.asyncio
async def test_milestone_trigger_filter_by_delivery(db):
    bot = MagicMock()
    bot.send_message = AsyncMock()

    # Rule for delivered only
    delivered_rule = MilestoneRule(
        period=MilestonePeriod.ALL_TIME,
        target_type=MilestoneTargetType.ORDER_COUNT,
        target_value=1,
        only_delivered=True,
        message_template="Giao thành công mốc {current_value} đơn!",
        effect_enabled=False,
        is_active=True,
    )
    await create_milestone_rule(db, delivered_rule)

    o = Order(
        customer_name="Test",
        customer_phone="0901234567",
        shipping_address="Hanoi",
        items_text="Bang 1",
        total_amount=100000,
        status=OrderStatus.CHO_LAM,
    )
    await create_order(db, o)

    # Triggering on order_created must NOT fire delivered_rule
    res_create = await check_and_trigger_milestones(
        bot=bot,
        db=db,
        whitelist_ids=[111],
        trigger_point="order_created",
    )
    assert len(res_create) == 0

    # Now simulate order being marked DA_GIAO
    await db.execute("UPDATE orders SET status = 'DA_GIAO'")
    await db.commit()

    res_del = await check_and_trigger_milestones(
        bot=bot,
        db=db,
        whitelist_ids=[111],
        trigger_point="order_delivered",
    )
    assert len(res_del) == 1
    assert bot.send_message.call_count == 1
    # effect_enabled is False, so message_effect_id must be None
    assert bot.send_message.call_args.kwargs.get("message_effect_id") is None


def test_milestone_keyboards_structure():
    rule = MilestoneRule(
        id=1,
        period=MilestonePeriod.MONTH,
        target_type=MilestoneTargetType.ORDER_COUNT,
        target_value=50,
        only_delivered=True,
        message_template="Test",
        effect_enabled=True,
        is_active=True,
    )
    kb_list = build_milestone_list_keyboard([rule])
    assert isinstance(kb_list, InlineKeyboardMarkup)
    callbacks = [btn.callback_data for row in kb_list.inline_keyboard for btn in row]
    assert "adm:ms:view:1" in callbacks
    assert "adm:ms:add:period" in callbacks
    assert "adm:dash:main" in callbacks

    kb_detail = build_milestone_detail_keyboard(rule)
    detail_cbs = [btn.callback_data for row in kb_detail.inline_keyboard for btn in row]
    assert "adm:ms:toggle:1" in detail_cbs
    assert "adm:ms:effect:1" in detail_cbs
    assert "adm:ms:edittpl:1" in detail_cbs
    assert "adm:ms:delprompt:1" in detail_cbs
    assert "adm:ms:list" in detail_cbs

    kb_del = build_milestone_confirm_delete_keyboard(1)
    del_cbs = [btn.callback_data for row in kb_del.inline_keyboard for btn in row]
    assert "adm:ms:delconfirm:1" in del_cbs
    assert "adm:ms:view:1" in del_cbs


@pytest.mark.asyncio
async def test_milestone_wizard_and_text_input(db):
    update = MagicMock()
    context = MagicMock()
    context.user_data = {
        "action_state": {"action": "await_milestone_val"},
        "milestone_draft": {
            "period": MilestonePeriod.MONTH,
            "target_type": MilestoneTargetType.REVENUE,
            "only_delivered": False,
        },
    }
    context.bot_data = {"db": db, "whitelist_user_ids": {12345}}
    update.message = MagicMock()
    update.message.text = "20tr"
    update.message.reply_text = AsyncMock()

    handled = await handle_milestone_text_input(update, context)
    assert handled is True
    assert context.user_data["milestone_draft"]["target_value"] == 20000000
    assert "template" in context.user_data["milestone_draft"]
    update.message.reply_text.assert_called_once()


def test_compute_milestone_pace_and_deadline():
    # Saturday Oct 31, 2026
    dt = datetime(2026, 10, 31, 10, 0, tzinfo=TZ_VN)

    # Week: Saturday + Sunday = 2 days left
    res_week = compute_milestone_pace_and_deadline(
        MilestonePeriod.WEEK,
        MilestoneTargetType.ORDER_COUNT,
        target_value=10,
        current_value=6,
        dt=dt,
    )
    assert res_week["remaining"] == 4
    assert res_week["days_left"] == 2
    assert res_week["deadline_date"] == datetime(2026, 11, 1).date()
    assert res_week["pace"] == 2.0  # 4 / 2 = 2.0 orders/day

    # Month: Oct 31 is the last day of month -> 1 day left
    res_month = compute_milestone_pace_and_deadline(
        MilestonePeriod.MONTH,
        MilestoneTargetType.REVENUE,
        target_value=10000000,
        current_value=8000000,
        dt=dt,
    )
    assert res_month["remaining"] == 2000000
    assert res_month["days_left"] == 1
    assert res_month["deadline_date"] == datetime(2026, 10, 31).date()
    assert res_month["pace"] == 2000000.0

    # All-time has no deadline
    res_all = compute_milestone_pace_and_deadline(
        MilestonePeriod.ALL_TIME,
        MilestoneTargetType.ORDER_COUNT,
        target_value=100,
        current_value=50,
        dt=dt,
    )
    assert res_all["remaining"] == 50
    assert res_all["days_left"] is None
    assert res_all["pace"] is None


@pytest.mark.asyncio
async def test_render_milestone_detail_card_with_pace(db):
    rule = MilestoneRule(
        id=99,
        period=MilestonePeriod.WEEK,
        target_type=MilestoneTargetType.ORDER_COUNT,
        target_value=10,
        only_delivered=False,
        message_template="🎉 Chúc mừng!",
        effect_enabled=True,
        is_active=True,
    )
    await create_milestone_rule(db, rule)

    card = await render_milestone_detail_card(db, rule)
    assert "CHI TIẾT MỐC #99" in card
    assert "Tiến độ:" in card
    assert "Còn thiếu:" in card
    assert "Thời hạn:" in card
    assert "Tốc độ cần đạt:" in card

