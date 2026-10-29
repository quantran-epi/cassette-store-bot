"""Legacy blob migration service.

Imports historical customers and orders from backup/blob JSON into SQLite.
"""

from dataclasses import dataclass, field
from datetime import datetime
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

PAYMENT_METHOD_MAP: dict[str, str] = {
    "Chuyển khoản trước": "CHUYEN_KHOAN",
    "COD": "COD",
}


@dataclass
class ImportSummary:
    """Summary of blob migration results."""

    customers_created: int = 0
    customers_reused: int = 0
    orders_created: int = 0
    orders_skipped: int = 0
    errors: list[str] = field(default_factory=list)


def parse_legacy_blob(blob_path_or_content: str | Path | dict) -> tuple[list[dict], list[dict]]:
    """Extract customers and orders lists from legacy JSON blob.

    Ignores codPayments, syncFailures, appContext, trelloCardId.
    """
    if isinstance(blob_path_or_content, (str, Path)):
        with open(blob_path_or_content, "r", encoding="utf-8") as f:
            data = json.load(f)
    elif isinstance(blob_path_or_content, dict):
        data = blob_path_or_content
    else:
        raise ValueError("Invalid blob input type")

    payload = data.get("payload", {}) if isinstance(data, dict) else {}
    customers = payload.get("customer", {}).get("customers", [])
    orders = payload.get("order", {}).get("orders", [])
    return customers, orders


def _format_legacy_customer_notes(raw_cust: dict) -> str:
    """Build structured notes string for legacy customer metadata."""
    notes_parts: list[str] = []
    cust_id = raw_cust.get("id")
    if cust_id:
        notes_parts.append(f"legacy_id: {cust_id}")
    if raw_cust.get("isVIP"):
        notes_parts.append("VIP: True")
    if raw_cust.get("isInBlacklist"):
        notes_parts.append("Blacklist: True")
    if raw_cust.get("difficulty"):
        notes_parts.append(f"difficulty: {raw_cust['difficulty']}")
    if raw_cust.get("area"):
        notes_parts.append(f"area: {raw_cust['area']}")
    raw_note = raw_cust.get("note", "").strip()
    if raw_note:
        notes_parts.append(raw_note)
    return " | ".join(notes_parts)


def map_legacy_customer(raw_cust: dict) -> Customer:
    """Convert raw legacy customer dict to Customer domain model."""
    name = (raw_cust.get("name") or "").strip() or "Khách chưa rõ tên"
    mobile = (raw_cust.get("mobile") or "").strip()
    phones = [mobile] if mobile else []

    address_parts = []
    addr = (raw_cust.get("address") or "").strip()
    province = (raw_cust.get("province") or "").strip()
    if addr:
        address_parts.append(addr)
    if province and province not in addr:
        address_parts.append(province)
    full_address = ", ".join(address_parts)
    addresses = [full_address] if full_address else []

    notes = _format_legacy_customer_notes(raw_cust)

    return Customer(
        name=name,
        phones=phones,
        addresses=addresses,
        notes=notes,
    )


def map_legacy_order(
    raw_order: dict,
    customer_id_map: dict[str, int],
    customer_snapshot: Customer | None = None,
) -> dict[str, Any]:
    """Convert raw legacy order to dict ready for SQLite orders table insertion."""
    legacy_cid = raw_order.get("customerId", "")
    customer_id = customer_id_map.get(legacy_cid)

    name = (
        (customer_snapshot.name if customer_snapshot else "")
        or raw_order.get("name", "")
        or "Khách vãng lai"
    )
    phone = (
        (customer_snapshot.phones[0] if customer_snapshot and customer_snapshot.phones else "")
        or ""
    )
    address = (
        (customer_snapshot.addresses[0] if customer_snapshot and customer_snapshot.addresses else "")
        or ""
    )

    raw_placed = raw_order.get("placedItems")
    if isinstance(raw_placed, list):
        # Format list of placed item dicts: e.g. [{"count": 5, "type": "SONY-50K", "note": ""}]
        item_lines: list[str] = []
        for item in raw_placed:
            if isinstance(item, dict):
                count = item.get("count", 1)
                itype = item.get("type", "")
                inote = item.get("note", "")
                line = f"{count} cuốn {itype}".strip()
                if inote:
                    line = f"{line} ({inote})"
                item_lines.append(line)
            elif isinstance(item, str):
                item_lines.append(item)
        items_text = ", ".join(item_lines)
    elif isinstance(raw_placed, str):
        items_text = raw_placed.strip()
    else:
        items_text = ""
    raw_status = (raw_order.get("status") or "").strip()
    status_enum = STATUS_MAP.get(raw_status, OrderStatus.DA_GIAO)

    raw_payment = (raw_order.get("paymentMethod") or "").strip()
    payment_method = PAYMENT_METHOD_MAP.get(raw_payment, "COD")

    total_amount = int(raw_order.get("paymentAmount") or 0)
    cod_amount = int(raw_order.get("codAmount") or 0)
    tracking_code = (raw_order.get("shippingCode") or "").strip() or None

    tape_cols = build_tape_columns(items_text, None, None, None)

    created_at = raw_order.get("createdDate")
    if not created_at:
        created_at = datetime.utcnow().isoformat()
    updated_at = created_at

    notes_parts: list[str] = []
    order_id = raw_order.get("id")
    if order_id:
        notes_parts.append(f"legacy_id: {order_id}")
    raw_note = (raw_order.get("note") or "").strip()
    if raw_note:
        notes_parts.append(raw_note)
    notes = " | ".join(notes_parts)

    return {
        "customer_id": customer_id,
        "customer_name": name,
        "customer_phone": phone,
        "shipping_address": address,
        "items_text": items_text,
        "total_amount": total_amount,
        "cod_amount": cod_amount,
        "payment_method": payment_method,
        "status": status_enum.value,
        "tracking_code": tracking_code,
        "tape_quantity": tape_cols.quantity,
        "tapes_json": tape_cols.tapes_json,
        "tape_genre_json": tape_cols.genres_json,
        "tape_artist_json": tape_cols.artists_json,
        "notes": notes,
        "created_at": created_at,
        "updated_at": updated_at,
    }


class LegacyBlobImporter:
    """Importer engine for legacy blob migration with transaction and dry-run."""

    def __init__(self, blob_path_or_content: str | Path | dict):
        self.blob_path_or_content = blob_path_or_content

    async def run(self, db: aiosqlite.Connection, dry_run: bool = True) -> ImportSummary:
        """Execute legacy migration.

        If dry_run is True, no DB changes are committed.
        If dry_run is False, wraps everything in a single transaction with full rollback on error.
        """
        summary = ImportSummary()
        raw_customers, raw_orders = parse_legacy_blob(self.blob_path_or_content)

        # 1. Load existing customers from SQLite into lookup map (normalized phone -> int id)
        existing_phone_map: dict[str, int] = {}
        async with db.execute("SELECT id, phones FROM customers") as cursor:
            async for row in cursor:
                c_id = row[0]
                phones_raw = row[1]
                if phones_raw:
                    try:
                        p_list = json.loads(phones_raw) if isinstance(phones_raw, str) else phones_raw
                        for p in p_list:
                            if p:
                                existing_phone_map[str(p).strip()] = c_id
                    except Exception:
                        pass

        # 2. Load existing orders to avoid duplicate imports (tracking_code and phone+created_at)
        existing_tracking_codes: set[str] = set()
        existing_order_keys: set[tuple[str, str]] = set()
        async with db.execute("SELECT customer_phone, tracking_code, created_at FROM orders") as cursor:
            async for row in cursor:
                c_phone = str(row[0] or "").strip()
                t_code = str(row[1] or "").strip()
                c_at = str(row[2] or "").strip()
                if t_code:
                    existing_tracking_codes.add(t_code)
                if c_phone and c_at:
                    existing_order_keys.add((c_phone, c_at))

        # Memory mapping for legacy customer string id -> sqlite integer id
        legacy_to_sqlite_cid: dict[str, int] = {}
        # Also store mapped customer model for quick field lookup
        mapped_cust_objects: dict[str, Customer] = {}

        # If not dry_run, begin explicit transaction
        if not dry_run:
            await db.execute("BEGIN IMMEDIATE")

        try:
            # Process customers
            simulated_next_cid = 1000000  # For dry-run customer ID simulation
            for raw_cust in raw_customers:
                legacy_id = str(raw_cust.get("id", ""))
                cust_model = map_legacy_customer(raw_cust)
                mapped_cust_objects[legacy_id] = cust_model

                phone = cust_model.phones[0] if cust_model.phones else ""
                if phone and phone in existing_phone_map:
                    # Reuse existing customer
                    sqlite_id = existing_phone_map[phone]
                    legacy_to_sqlite_cid[legacy_id] = sqlite_id
                    summary.customers_reused += 1
                else:
                    if dry_run:
                        simulated_next_cid += 1
                        legacy_to_sqlite_cid[legacy_id] = simulated_next_cid
                        if phone:
                            existing_phone_map[phone] = simulated_next_cid
                        summary.customers_created += 1
                    else:
                        cursor = await db.execute(
                            """
                            INSERT INTO customers (name, phones, addresses, notes)
                            VALUES (?, ?, ?, ?)
                            """,
                            (
                                cust_model.name,
                                json.dumps(cust_model.phones, ensure_ascii=False),
                                json.dumps(cust_model.addresses, ensure_ascii=False),
                                cust_model.notes,
                            ),
                        )
                        new_id = cursor.lastrowid
                        assert new_id is not None
                        legacy_to_sqlite_cid[legacy_id] = new_id
                        if phone:
                            existing_phone_map[phone] = new_id
                        summary.customers_created += 1

            # Process orders
            for raw_ord in raw_orders:
                legacy_cid = str(raw_ord.get("customerId", ""))
                cust_obj = mapped_cust_objects.get(legacy_cid)
                order_dict = map_legacy_order(raw_ord, legacy_to_sqlite_cid, cust_obj)

                t_code = order_dict["tracking_code"]
                c_phone = order_dict["customer_phone"]
                c_at = order_dict["created_at"]

                # Check idempotency duplicate criteria
                is_duplicate = False
                if t_code and t_code in existing_tracking_codes:
                    is_duplicate = True
                elif (c_phone, c_at) in existing_order_keys:
                    is_duplicate = True

                if is_duplicate:
                    summary.orders_skipped += 1
                    continue

                if dry_run:
                    summary.orders_created += 1
                    if t_code:
                        existing_tracking_codes.add(t_code)
                    if c_phone and c_at:
                        existing_order_keys.add((c_phone, c_at))
                else:
                    await db.execute(
                        """
                        INSERT INTO orders (
                            customer_id, customer_name, customer_phone, shipping_address,
                            items_text, total_amount, cod_amount, payment_method,
                            status, tracking_code, tape_quantity, tapes_json,
                            tape_genre_json, tape_artist_json, notes, created_at, updated_at
                        ) VALUES (
                            ?, ?, ?, ?,
                            ?, ?, ?, ?,
                            ?, ?, ?, ?,
                            ?, ?, ?, ?, ?
                        )
                        """,
                        (
                            order_dict["customer_id"],
                            order_dict["customer_name"],
                            order_dict["customer_phone"],
                            order_dict["shipping_address"],
                            order_dict["items_text"],
                            order_dict["total_amount"],
                            order_dict["cod_amount"],
                            order_dict["payment_method"],
                            order_dict["status"],
                            order_dict["tracking_code"],
                            order_dict["tape_quantity"],
                            order_dict["tapes_json"],
                            order_dict["tape_genre_json"],
                            order_dict["tape_artist_json"],
                            order_dict["notes"],
                            order_dict["created_at"],
                            order_dict["updated_at"],
                        ),
                    )
                    summary.orders_created += 1
                    if t_code:
                        existing_tracking_codes.add(t_code)
                    if c_phone and c_at:
                        existing_order_keys.add((c_phone, c_at))

            if not dry_run:
                await db.commit()

        except Exception as e:
            if not dry_run:
                await db.rollback()
            summary.errors.append(str(e))
            logger.error("Migration failed, transaction rolled back: %s", e)
            raise

        return summary
