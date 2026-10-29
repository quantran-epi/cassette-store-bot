"""Legacy blob migration service."""

from dataclasses import dataclass, field
from datetime import datetime, UTC
from pathlib import Path
from typing import Any
import json
import logging

import aiosqlite

from src.models.customer import Customer
from src.models.order import OrderStatus
from src.services.tape_parser import build_tape_columns

logger = logging.getLogger(__name__)

STATUS_MAP: dict[str, OrderStatus] = {
    "Đã giao thành công": OrderStatus.DA_GIAO,
    "Đã tạo đơn": OrderStatus.DA_TAO_DON,
    "Đã chuyển hoàn": OrderStatus.BOM_HANG,
    "Chờ chuyển hoàn": OrderStatus.BOM_HANG,
}
PAYMENT_METHOD_MAP = {"Chuyển khoản trước": "CHUYEN_KHOAN", "COD": "COD"}
LEGACY_MARKER_PREFIX = "legacy_id: "
EMPTY_ITEMS_TEXT = "Không có chi tiết mặt hàng"


@dataclass
class ImportSummary:
    customers_created: int = 0
    customers_reused: int = 0
    orders_created: int = 0
    orders_skipped: int = 0
    errors: list[str] = field(default_factory=list)


def _required_text(value: Any, field_name: str, index: int) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field_name}[{index}] requires non-empty string field")
    return value.strip()


def parse_legacy_blob(blob_path_or_content: str | Path | dict) -> tuple[list[dict], list[dict]]:
    """Load and validate only legacy customer/order branches."""
    if isinstance(blob_path_or_content, (str, Path)):
        with open(blob_path_or_content, "r", encoding="utf-8") as f:
            data = json.load(f)
    elif isinstance(blob_path_or_content, dict):
        data = blob_path_or_content
    else:
        raise ValueError("Invalid blob input type")

    if not isinstance(data, dict) or not isinstance(data.get("payload"), dict):
        raise ValueError("Legacy blob requires object payload")
    payload = data["payload"]
    customer_branch = payload.get("customer")
    order_branch = payload.get("order")
    if not isinstance(customer_branch, dict) or not isinstance(order_branch, dict):
        raise ValueError("Legacy blob requires customer and order objects")
    customers = customer_branch.get("customers")
    orders = order_branch.get("orders")
    if not isinstance(customers, list) or not isinstance(orders, list):
        raise ValueError("Legacy customer/order collections must be lists")

    customer_ids: set[str] = set()
    for index, raw_customer in enumerate(customers):
        if not isinstance(raw_customer, dict):
            raise ValueError(f"customers[{index}] must be an object")
        legacy_id = _required_text(raw_customer.get("id"), "customers", index)
        if "|" in legacy_id or "\n" in legacy_id:
            raise ValueError(f"customers[{index}].id contains invalid marker delimiter")
        if legacy_id in customer_ids:
            raise ValueError(f"duplicate legacy customer id: {legacy_id}")
        customer_ids.add(legacy_id)

    order_ids: set[str] = set()
    for index, raw_order in enumerate(orders):
        if not isinstance(raw_order, dict):
            raise ValueError(f"orders[{index}] must be an object")
        order_id = _required_text(raw_order.get("id"), "orders", index)
        customer_id = _required_text(raw_order.get("customerId"), "orders", index)
        if "|" in order_id or "\n" in order_id:
            raise ValueError(f"orders[{index}].id contains invalid marker delimiter")
        if order_id in order_ids:
            raise ValueError(f"duplicate legacy order id: {order_id}")
        if customer_id not in customer_ids:
            raise ValueError(f"orders[{index}] references unknown customerId: {customer_id}")
        order_ids.add(order_id)
    return customers, orders


def _format_legacy_customer_notes(raw_cust: dict) -> str:
    parts: list[str] = []
    if raw_cust.get("id"):
        parts.append(f"{LEGACY_MARKER_PREFIX}{raw_cust['id']}")
    if raw_cust.get("isVIP"):
        parts.append("VIP: True")
    if raw_cust.get("isInBlacklist"):
        parts.append("Blacklist: True")
    for key in ("difficulty", "area"):
        if raw_cust.get(key):
            parts.append(f"{key}: {raw_cust[key]}")
    note = raw_cust.get("note", "")
    if isinstance(note, str) and note.strip():
        parts.append(note.strip())
    return " | ".join(parts)


def map_legacy_customer(raw_cust: dict) -> Customer:
    name = (raw_cust.get("name") or "").strip() or "Khách chưa rõ tên"
    mobile = (raw_cust.get("mobile") or "").strip()
    address = (raw_cust.get("address") or "").strip()
    province = (raw_cust.get("province") or "").strip()
    address_parts = [address]
    if province and province not in address:
        address_parts.append(province)
    address_parts = [part for part in address_parts if part]
    return Customer(
        name=name,
        phones=[mobile] if mobile else [],
        addresses=[", ".join(address_parts)] if address_parts else [],
        notes=_format_legacy_customer_notes(raw_cust),
    )


def _embedded_customer(raw_order: dict) -> Customer | None:
    snapshot = raw_order.get("customer")
    return map_legacy_customer(snapshot) if isinstance(snapshot, dict) else None


def map_legacy_order(
    raw_order: dict,
    customer_id_map: dict[str, int],
    customer_snapshot: Customer | None = None,
) -> dict[str, Any]:
    """Map order fields, preferring embedded customer snapshot over master snapshot."""
    legacy_customer_id = raw_order.get("customerId", "")
    customer_id = customer_id_map.get(legacy_customer_id)
    embedded = _embedded_customer(raw_order)
    preferred = embedded or customer_snapshot
    name = (preferred.name if preferred and preferred.name != "Khách chưa rõ tên" else "")
    phone = preferred.phones[0] if preferred and preferred.phones else ""
    address = preferred.addresses[0] if preferred and preferred.addresses else ""
    if embedded and not address:
        address = str(raw_order.get("customer", {}).get("address") or "").strip()
    name = name or (raw_order.get("name") or "").strip() or "Khách vãng lai"

    raw_note = raw_order.get("note")
    note = raw_note.strip() if isinstance(raw_note, str) else ""
    raw_placed = raw_order.get("placedItems")
    if isinstance(raw_placed, list):
        item_lines: list[str] = []
        for item in raw_placed:
            if isinstance(item, dict):
                line = f"{item.get('count', 1)} cuốn {item.get('type', '')}".strip()
                item_note = item.get("note")
                if isinstance(item_note, str) and item_note.strip():
                    line = f"{line} ({item_note.strip()})"
                item_lines.append(line)
            elif isinstance(item, str) and item.strip():
                item_lines.append(item.strip())
        items_text = ", ".join(item_lines)
    elif isinstance(raw_placed, str):
        items_text = raw_placed.strip()
    else:
        items_text = ""
    if not items_text:
        items_text = note or EMPTY_ITEMS_TEXT

    raw_status = raw_order.get("status")
    status = STATUS_MAP.get(raw_status.strip() if isinstance(raw_status, str) else "", OrderStatus.DA_GIAO)
    raw_payment = raw_order.get("paymentMethod")
    payment = PAYMENT_METHOD_MAP.get(raw_payment.strip() if isinstance(raw_payment, str) else "", "COD")
    created_at = raw_order.get("createdDate") or datetime.now(UTC).isoformat()
    order_id = raw_order["id"]
    order_notes = f"{LEGACY_MARKER_PREFIX}{order_id}"
    if note:
        order_notes += f" | {note}"
    tape_cols = build_tape_columns(items_text, None, None, None)
    return {
        "customer_id": customer_id,
        "customer_name": name,
        "customer_phone": phone,
        "shipping_address": address,
        "items_text": items_text,
        "total_amount": int(raw_order.get("paymentAmount") or 0),
        "cod_amount": int(raw_order.get("codAmount") or 0),
        "payment_method": payment,
        "status": status.value,
        "tracking_code": (raw_order.get("shippingCode") or "").strip() or None,
        "tape_quantity": tape_cols.quantity,
        "tapes_json": tape_cols.tapes_json,
        "tape_genre_json": tape_cols.genres_json,
        "tape_artist_json": tape_cols.artists_json,
        "notes": order_notes,
        "created_at": created_at,
        "updated_at": created_at,
    }


def _has_marker(notes: Any, legacy_id: str) -> bool:
    marker = f"{LEGACY_MARKER_PREFIX}{legacy_id}"
    return isinstance(notes, str) and marker in notes.split(" | ")


class LegacyBlobImporter:
    def __init__(self, blob_path_or_content: str | Path | dict):
        self.blob_path_or_content = blob_path_or_content

    async def run(self, db: aiosqlite.Connection, dry_run: bool = True) -> ImportSummary:
        if not dry_run and db.in_transaction:
            raise RuntimeError("Cannot apply legacy import while caller transaction is active")
        summary = ImportSummary()
        raw_customers, raw_orders = parse_legacy_blob(self.blob_path_or_content)
        existing_phone_map: dict[str, int] = {}
        async with db.execute("SELECT id, phones FROM customers") as cursor:
            async for row in cursor:
                try:
                    for phone in json.loads(row[1] or "[]"):
                        if phone:
                            existing_phone_map[str(phone).strip()] = row[0]
                except (TypeError, json.JSONDecodeError):
                    continue

        existing_order_markers: set[str] = set()
        async with db.execute("SELECT notes FROM orders") as cursor:
            async for row in cursor:
                notes = row[0]
                if isinstance(notes, str):
                    existing_order_markers.update(
                        token[len(LEGACY_MARKER_PREFIX):]
                        for token in notes.split(" | ")
                        if token.startswith(LEGACY_MARKER_PREFIX)
                    )

        if not dry_run:
            await db.execute("BEGIN IMMEDIATE")
        try:
            legacy_to_sqlite_cid: dict[str, int] = {}
            mapped_customers: dict[str, Customer] = {}
            simulated_next_cid = 1000000
            for raw_customer in raw_customers:
                legacy_id = raw_customer["id"]
                customer = map_legacy_customer(raw_customer)
                mapped_customers[legacy_id] = customer
                phone = customer.phones[0] if customer.phones else ""
                if phone and phone in existing_phone_map:
                    legacy_to_sqlite_cid[legacy_id] = existing_phone_map[phone]
                    summary.customers_reused += 1
                elif dry_run:
                    simulated_next_cid += 1
                    legacy_to_sqlite_cid[legacy_id] = simulated_next_cid
                    if phone:
                        existing_phone_map[phone] = simulated_next_cid
                    summary.customers_created += 1
                else:
                    cursor = await db.execute(
                        "INSERT INTO customers (name, phones, addresses, notes) VALUES (?, ?, ?, ?)",
                        (customer.name, json.dumps(customer.phones, ensure_ascii=False),
                         json.dumps(customer.addresses, ensure_ascii=False), customer.notes),
                    )
                    legacy_to_sqlite_cid[legacy_id] = cursor.lastrowid
                    if phone:
                        existing_phone_map[phone] = cursor.lastrowid
                    summary.customers_created += 1

            for raw_order in raw_orders:
                legacy_id = raw_order["id"]
                if legacy_id in existing_order_markers:
                    summary.orders_skipped += 1
                    continue
                order = map_legacy_order(raw_order, legacy_to_sqlite_cid, mapped_customers[raw_order["customerId"]])
                if dry_run:
                    summary.orders_created += 1
                    existing_order_markers.add(legacy_id)
                    continue
                await db.execute(
                    """INSERT INTO orders (
                        customer_id, customer_name, customer_phone, shipping_address,
                        items_text, total_amount, cod_amount, payment_method, status,
                        tracking_code, tape_quantity, tapes_json, tape_genre_json,
                        tape_artist_json, notes, created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (order["customer_id"], order["customer_name"], order["customer_phone"],
                     order["shipping_address"], order["items_text"], order["total_amount"],
                     order["cod_amount"], order["payment_method"], order["status"],
                     order["tracking_code"], order["tape_quantity"], order["tapes_json"],
                     order["tape_genre_json"], order["tape_artist_json"], order["notes"],
                     order["created_at"], order["updated_at"]),
                )
                summary.orders_created += 1
                existing_order_markers.add(legacy_id)
            if not dry_run:
                await db.commit()
        except Exception as exc:
            if not dry_run:
                await db.rollback()
            summary.errors.append(str(exc))
            logger.error("Migration failed, transaction rolled back: %s", exc)
            raise
        return summary
