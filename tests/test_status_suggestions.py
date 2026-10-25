from src.bot.keyboards import (
    build_mutation_confirm_keyboard,
    build_mutation_disambiguation_keyboard,
    build_mutation_status_keyboard,
    get_suggested_next_statuses,
)
from src.models.order import Order, OrderStatus


def test_get_suggested_next_statuses_dang_lam():
    """Verify suggestions for DANG_LAM include DA_DONG_GOI, DA_TAO_DON, HUY_DON."""
    suggestions = get_suggested_next_statuses(OrderStatus.DANG_LAM)
    status_values = [s[0] for s in suggestions]
    assert OrderStatus.DA_DONG_GOI in status_values
    assert OrderStatus.HUY_DON in status_values


def test_get_suggested_next_statuses_cho_lam():
    """Verify suggestions for CHO_LAM include DANG_LAM and HUY_DON."""
    suggestions = get_suggested_next_statuses(OrderStatus.CHO_LAM)
    status_values = [s[0] for s in suggestions]
    assert OrderStatus.DANG_LAM in status_values
    assert OrderStatus.HUY_DON in status_values


def test_get_suggested_next_statuses_shipper_da_lay():
    """Verify suggestions for SHIPPER_DA_LAY include DA_GIAO and BOM_HANG."""
    suggestions = get_suggested_next_statuses(OrderStatus.SHIPPER_DA_LAY)
    status_values = [s[0] for s in suggestions]
    assert OrderStatus.DA_GIAO in status_values
    assert OrderStatus.BOM_HANG in status_values


def test_build_mutation_confirm_keyboard():
    """Verify confirm keyboard has ✅ Xác nhận sửa and ❌ Huỷ with draft_id."""
    kb = build_mutation_confirm_keyboard("a1b2c3d4")
    buttons = kb.inline_keyboard
    assert len(buttons) == 1
    assert len(buttons[0]) == 2
    assert buttons[0][0].text == "✅ Xác nhận sửa"
    assert buttons[0][0].callback_data == "ord_mut_cf:a1b2c3d4"
    assert buttons[0][1].text == "❌ Huỷ"
    assert buttons[0][1].callback_data == "ord_mut_ca:a1b2c3d4"


def test_build_mutation_disambiguation_keyboard():
    """Verify disambiguation keyboard renders 1 button per order and cancel button."""
    orders = [
        Order(
            id=12,
            customer_name="Nam",
            customer_phone="0912345678",
            shipping_address="Hà Nội",
            items_text="Băng 1",
            total_amount=250000,
            status=OrderStatus.CHO_LAM,
        ),
        Order(
            id=15,
            customer_name="Nam",
            customer_phone="0912345678",
            shipping_address="Hà Nội",
            items_text="Băng 2",
            total_amount=400000,
            status=OrderStatus.DANG_LAM,
        ),
    ]
    kb = build_mutation_disambiguation_keyboard(orders, "draft123")
    rows = kb.inline_keyboard
    assert len(rows) == 3  # 2 orders + 1 cancel
    assert rows[0][0].callback_data == "ord_mut_sel:draft123:12"
    assert "#12" in rows[0][0].text
    assert "Nam" in rows[0][0].text
    assert rows[1][0].callback_data == "ord_mut_sel:draft123:15"
    assert rows[2][0].callback_data == "ord_mut_ca:draft123"
    assert rows[2][0].text == "❌ Huỷ"


def test_build_mutation_status_keyboard():
    """Verify status suggestion keyboard contains suggested statuses and back button."""
    kb = build_mutation_status_keyboard("draft123", 12, OrderStatus.DANG_LAM)
    rows = kb.inline_keyboard
    # Should have suggestion buttons and back button
    assert len(rows) >= 2
    last_row = rows[-1]
    assert last_row[0].text == "❌ Huỷ bỏ"
    assert last_row[0].callback_data == "ord_mut_ca:draft123"

    all_cbs = [btn.callback_data for r in rows for btn in r]
    assert any("ord_mut_st:draft123:12:DA_DONG_GOI" in cb for cb in all_cbs)
