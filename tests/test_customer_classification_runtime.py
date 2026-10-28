"""Offline dispatcher checks: temporary DB, real PTB updates, no network transport."""
import json
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest
from telegram import Update
from telegram.ext import Application, CallbackQueryHandler, MessageHandler, TypeHandler, filters
from telegram.request import BaseRequest

from src.bot.handlers.ingest import process_extracted_order
from src.bot.handlers.mutation import handle_mutation_flow
from src.bot.handlers.orders import handle_order_nav_callback
from src.bot.handlers.search import handle_customer_callback, handle_search_callback
from src.bot.keyboards import format_customer_classification
from src.bot.security import whitelist_gate
from src.db.connection import get_db_connection
from src.db.customers import create_customer
from src.db.orders import create_order, hydrate_customer_stats
from src.db.schema import init_db
from src.models.customer import Customer
from src.models.extractor import ExtractedOrder
from src.models.order import Order, OrderStatus
from src.services.order_search import (
    SearchResult,
    SearchResultType,
    _execute_search_plan,
    fetch_search_page,
    parse_search_plan,
)


class OfflineRequest(BaseRequest):
    def __init__(self):
        self.calls = []

    @property
    def read_timeout(self):
        return 5

    async def initialize(self):
        pass

    async def shutdown(self):
        pass

    async def do_request(self, url, method, request_data=None, **kwargs):
        endpoint = url.rsplit("/", 1)[-1]
        params = request_data.parameters if request_data else {}
        self.calls.append((endpoint, params))
        if endpoint == "getMe":
            result = {"id": 999, "is_bot": True, "first_name": "Offline", "username": "offline_bot"}
        elif endpoint in ("sendMessage", "editMessageText"):
            result = {"message_id": 10, "date": 0, "chat": {"id": 123, "type": "private"}, "text": params["text"]}
        elif endpoint in ("answerCallbackQuery", "sendChatAction"):
            result = True
        else:
            raise AssertionError(f"Unexpected Bot API endpoint: {endpoint}")
        return 200, json.dumps({"ok": True, "result": result}).encode()


@pytest.mark.asyncio
async def test_classification_through_dispatcher(tmp_path):
    request = OfflineRequest()
    app = Application.builder().token("999:offline-only").request(request).get_updates_request(OfflineRequest()).build()
    errors = []

    async def on_error(update, context):
        errors.append(context.error)

    async def preview(update, context):
        await process_extracted_order(update, context, ExtractedOrder(
            customer_phone="0901000001", items_text="Băng mới", total_amount=100000,
        ), raw_text="offline fixture")

    async def mutate(update, context):
        await handle_mutation_flow(update, context, update.message.text)

    app.add_error_handler(on_error)
    app.add_handler(TypeHandler(Update, whitelist_gate), group=-1)
    app.add_handler(CallbackQueryHandler(handle_order_nav_callback, pattern=r"^ord_(ls|vls):"))
    app.add_handler(CallbackQueryHandler(handle_customer_callback, pattern=r"^cus_"))
    app.add_handler(CallbackQueryHandler(handle_search_callback, pattern=r"^sch_"))
    app.add_handler(MessageHandler(filters.Regex("^preview$"), preview))
    app.add_handler(MessageHandler(filters.Regex("^sửa"), mutate))
    async with get_db_connection(str(tmp_path / "offline.sqlite3")) as db:
        await init_db(db)
        app.bot_data.update(db=db, whitelist_user_ids={123}, maintenance_mode=False,
                            settings=SimpleNamespace(nine_router_model_id="offline"), openai_client=object())
        regular = await create_customer(db, Customer(name="Khách Quen", phones=["0901000000"], addresses=["Hà Nội"]))
        bom = await create_customer(db, Customer(name="Khách Bom", phones=["0901000001"], addresses=["Hà Nội"]))
        for i in range(6):
            await create_order(db, Order(customer_id=regular, customer_name="Khách Quen", customer_phone="0901000000", shipping_address="Hà Nội", items_text=f"Băng {i}", total_amount=2000000, status=OrderStatus.DA_GIAO if i < 5 else OrderStatus.CHO_LAM))
        await create_order(db, Order(customer_id=bom, customer_name="Khách Bom", customer_phone="0901000001", shipping_address="Hà Nội", items_text="Băng bom", total_amount=9000000, status=OrderStatus.BOM_HANG))
        plan = parse_search_plan(json.dumps({"list": {"purpose": "Đơn khách", "sql": "SELECT * FROM orders ORDER BY id"}, "aggregates": []}))
        result = await _execute_search_plan(None, "offline", db, "fixture", plan, 1, 5)
        assert result.orders[0].customer_completed_orders == 5
        orders = await fetch_search_page(db, "SELECT * FROM orders ORDER BY id", 1)
        assert orders[0].customer_completed_orders == 5
        assert orders[0].customer_completed_spend == 10000000
        # One batch query, including repeated IDs, BOM-only and unknown customer association.
        batch = orders + [Order(customer_id=bom, customer_name="B", customer_phone="", shipping_address="", items_text=""), Order(customer_name="Unknown", customer_phone="", shipping_address="", items_text="")]
        traced = []
        await db.set_trace_callback(traced.append)
        await hydrate_customer_stats(db, batch)
        await db.set_trace_callback(None)
        assert len(traced) == 1
        assert batch[-2].customer_completed_orders == batch[-2].customer_completed_spend == 0
        assert batch[-1].customer_completed_orders is None
        async with app:
            app.user_data[123]["searches"] = {"offline": {"query": "fixture", "result": SearchResult(result_type=SearchResultType.ORDERS, sql_executed="SELECT * FROM orders", orders=orders), "page": 1}}
            user = {"id": 123, "is_bot": False, "first_name": "Tester"}
            counter = 0

            async def dispatch(data=None, text=None):
                nonlocal counter
                counter += 1
                message = {"message_id": counter, "date": 0, "chat": {"id": 123, "type": "private"}, "from": user, "text": text or "fixture"}
                payload = {"update_id": counter}
                if data:
                    payload["callback_query"] = {"id": str(counter), "from": user, "chat_instance": "offline", "data": data, "message": message}
                else:
                    payload["message"] = message
                start = len(request.calls)
                await app.process_update(Update.de_json(payload, app.bot))
                assert not errors, errors
                return [params["text"] for endpoint, params in request.calls[start:] if endpoint in ("sendMessage", "editMessageText")][-1]

            for callback in ("ord_ls:CHO_LAM:1", "ord_vls:CHO_LAM:6:1", f"cus_v:{regular}:offline", "sch_bk:offline"):
                body = await dispatch(data=callback)
                assert "⭐ <b>TẦN SUẤT:</b> <b>KHÁCH THÂN THIẾT</b>" in body
                assert "🥇 <b>CHI TIÊU:</b> <b>TỪ 10 TRIỆU</b>" in body
            body = await dispatch(data=f"cus_pg:{regular}:2")
            assert "Trang 2/2" in body
            for body in (await dispatch(data=f"cus_v:{bom}:offline"), await dispatch(text="preview")):
                assert "🆕 <b>TẦN SUẤT:</b> <b>KHÁCH VÃNG LAI</b> (0 đơn hoàn thành)" in body
                assert "🪙 <b>CHI TIÊU:</b> <b>DƯỚI 1 TRIỆU</b> (0 đ)" in body
                assert "CẢNH BÁO" in body
            with patch("src.bot.handlers.mutation.search_target_orders_for_mutation", AsyncMock(return_value=orders[:2])):
                body = await dispatch(text="sửa đơn khách quen")
                assert "CHỌN ĐƠN HÀNG CẦN SỬA" in body
                assert body.count("KHÁCH THÂN THIẾT") == 2
        assert any(endpoint == "editMessageText" for endpoint, _ in request.calls)
        assert any(endpoint == "sendMessage" for endpoint, _ in request.calls)
        print(json.dumps({"transport": "offline BaseRequest", "dispatcher": "Application.process_update", "outgoing": [{"method": endpoint, "text": params["text"]} for endpoint, params in request.calls if endpoint in ("sendMessage", "editMessageText")]}, ensure_ascii=True))


def test_distinct_tier_markers():
    for count, spend, frequency, spending in ((0, 0, "🆕", "🪙"), (1, 1000000, "1️⃣", "🥉"), (2, 3000000, "🔁", "🥈"), (5, 10000000, "⭐", "🥇")):
        lines = format_customer_classification(count, spend).splitlines()
        assert len(lines) == 2
        assert lines[0].startswith(frequency + " <b>TẦN SUẤT:")
        assert lines[1].startswith(spending + " <b>CHI TIÊU:")
