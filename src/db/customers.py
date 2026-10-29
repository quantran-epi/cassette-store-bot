import json
import re
from collections.abc import Sequence

import aiosqlite

from src.db.connection import remove_accents
from src.models.customer import Customer

# Words that carry no lookup value in "tìm khách <...>" phrasing.
_CUSTOMER_FILLERS = {
    "khach", "khách", "tim", "tìm", "tra", "cuu", "cứu", "kiem", "kiểm", "xem",
    "cua", "của", "cho", "sdt", "so", "số", "dien", "điện", "thoai", "thoại",
    "ten", "tên", "dia", "địa", "chi", "chỉ", "hang", "hàng",
    "o", "ở", "tai", "tại", "ve", "về", "tp", "thanh", "thành", "pho", "phố", "tinh", "tỉnh",
}
_HONORIFICS = {"anh", "chi", "chị", "bac", "bác", "ong", "ông", "co", "cô", "chu", "chú", "em"}

_CUSTOMER_SEARCH_PATTERN = re.compile(
    r"^(?:tim|tra\s+cuu|kiem\s+tra|xem|co)\s+(?:xem\s+)?(?:thong\s+tin\s+)?khach\b|"
    r"^khach\b(?!.*\b(?:\+?84|0)[35789]\d{8}\b.*\b(?:bang|cuon|lay|gui|thu|cod|\d+k\b))|"
    r"\bco\s+khach\b"
)
_CUSTOMER_ORDER_QUERY_PATTERN = re.compile(
    r"\b(?:khach\s+nao|ai)\b.*\b(?:mua|chi\s+tieu|dat|don)\b|"
    r"\btop(?:\s+\d+)?\s+khach\b|"
    r"\bkhach\b.*\b(?:mua|chi\s+tieu|dat)\b.*\b(?:nhieu|it|cao)\s+nhat\b|"
    r"\b(?:may|bao\s+nhieu)\s+don\b|"
    r"\b(?:da|tung|co)\b.*?\b(?:mua|dat)\b|"
    r"\bbao\s+lau\b|"
    r"\b(?:lan\s+)?(?:cuoi|gan\s+nhat)\b|"
    r"\b(?:chua|ko|khong)\s+mua\b|"
    r"\blich\s+su\s+(?:mua|don)\b",
    re.DOTALL,
)


def _row_to_customer(row: aiosqlite.Row) -> Customer:
    """Convert a database row to Customer domain model."""
    return Customer(
        id=row["id"],
        name=row["name"],
        phones=json.loads(row["phones"]) if isinstance(row["phones"], str) else row["phones"],
        addresses=(
            json.loads(row["addresses"]) if isinstance(row["addresses"], str) else row["addresses"]
        ),
        notes=row["notes"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


async def create_customer(db: aiosqlite.Connection, customer: Customer) -> int:
    """Insert a customer record and return generated ID."""
    cursor = await db.execute(
        """
        INSERT INTO customers (name, phones, addresses, notes)
        VALUES (?, ?, ?, ?)
        """,
        (
            customer.name,
            json.dumps(customer.phones, ensure_ascii=False),
            json.dumps(customer.addresses, ensure_ascii=False),
            customer.notes,
        ),
    )
    await db.commit()
    return cursor.lastrowid  # type: ignore[return-value]


async def get_customer_by_id(db: aiosqlite.Connection, customer_id: int) -> Customer | None:
    """Retrieve customer by primary key ID."""
    async with db.execute("SELECT * FROM customers WHERE id = ?", (customer_id,)) as cursor:
        row = await cursor.fetchone()
        if not row:
            return None
        return _row_to_customer(row)


async def get_customer_by_phone(db: aiosqlite.Connection, phone: str) -> Customer | None:
    """Find a customer whose JSON phones array contains the target phone string."""
    query = """
        SELECT DISTINCT c.*
        FROM customers c, json_each(c.phones) AS p
        WHERE p.value = ?
        LIMIT 1
    """
    async with db.execute(query, (phone,)) as cursor:
        row = await cursor.fetchone()
        if not row:
            return None
        return _row_to_customer(row)


def is_customer_search(query: str) -> bool:
    """True for direct customer profile lookup, not order analytics."""
    clean = remove_accents(query).strip().lower()
    return bool(_CUSTOMER_SEARCH_PATTERN.search(clean)) and not _CUSTOMER_ORDER_QUERY_PATTERN.search(clean)


def is_customer_analytics(query: str) -> bool:
    """True when query ranks or aggregates customers by order activity."""
    return bool(_CUSTOMER_ORDER_QUERY_PATTERN.search(remove_accents(query).strip().lower()))



async def search_customers(
    db: aiosqlite.Connection, query: str, limit: int = 5
) -> list[Customer]:
    """Find customers by name/phone/address tokens (accent-insensitive, ANDed).

    Every substantive token must match the concatenated profile or appear as a substring of
    one of the customer's phones (partial phone lookup). Tokens are bound as SQL parameters.
    """
    clean_q = remove_accents(query).strip().lower()

    # Slot-aware matching when explicit "tên X" or "ở/tại/địa chỉ Y" cues exist
    name_m = re.search(r"\bten\s+([^,]+?)(?:\s+(?:o|tai|dia\s+chi|sdt|so\s+dien\s+thoai)\b|$)", clean_q)
    addr_m = re.search(r"\b(?:o|tai|dia\s+chi)\s+([^,]+?)(?:\s+(?:ten|sdt|so\s+dien\s+thoai)\b|$)", clean_q)
    name_tokens = [t for t in re.split(r"\s+", name_m.group(1)) if t and t not in _CUSTOMER_FILLERS and t not in _HONORIFICS] if name_m else []
    addr_tokens = [t for t in re.split(r"\s+", addr_m.group(1)) if t and t not in _CUSTOMER_FILLERS and t not in _HONORIFICS] if addr_m else []

    if name_tokens or addr_tokens:
        slot_conds: list[str] = []
        slot_params: list[str] = []
        for tok in name_tokens:
            slot_conds.append("word_match(c.name, ?) = 1")
            slot_params.append(tok)
        for tok in addr_tokens:
            slot_conds.append("(word_match(c.addresses, ?) = 1 OR unaccent(c.addresses) LIKE ?)")
            slot_params.extend([tok, f"%{tok}%"])
        if slot_conds:
            slot_params.append(limit)
            slot_sql = f"SELECT c.* FROM customers c WHERE {' AND '.join(slot_conds)} ORDER BY c.id LIMIT ?"
            async with db.execute(slot_sql, slot_params) as cursor:
                rows = await cursor.fetchall()
            if rows:
                return [_row_to_customer(row) for row in rows]

    tokens = [t for t in re.split(r"\s+", remove_accents(query)) if t]
    tokens = [t for t in tokens if t not in _CUSTOMER_FILLERS and t not in _HONORIFICS]
    if not tokens:
        fallback = remove_accents(query).strip()
        tokens = [fallback] if fallback else []
    if not tokens:
        return []

    haystack = "(c.name || ' ' || c.phones || ' ' || c.addresses || ' ' || c.notes)"
    conds: list[str] = []
    params: list[str] = []
    for tok in tokens:
        conds.append(
            f"(word_match({haystack}, ?) = 1 "
            "OR EXISTS (SELECT 1 FROM json_each(c.phones) p WHERE p.value LIKE ?))"
        )
        params.extend([tok, f"%{tok}%"])

    params.append(limit)
    sql = (
        f"SELECT c.* FROM customers c WHERE {' AND '.join(conds)} "
        "ORDER BY c.id LIMIT ?"
    )
    async with db.execute(sql, params) as cursor:
        rows = await cursor.fetchall()

    # Whole-word AND is strict: "hà nội" misses "Hanoi cũ" (one token). Retry per-token as
    # accent-insensitive substring before giving up — same field set, still parameterized.
    if not rows and len(tokens) > 1:
        sub_conds = [
            f"(unaccent({haystack}) LIKE ? "
            "OR EXISTS (SELECT 1 FROM json_each(c.phones) p WHERE p.value LIKE ?))"
            for _ in tokens
        ]
        sub_params: list[str] = []
        for tok in tokens:
            sub_params.extend([f"%{tok}%", f"%{tok}%"])
        sub_params.append(limit)
        async with db.execute(
            f"SELECT c.* FROM customers c WHERE {' AND '.join(sub_conds)} ORDER BY c.id LIMIT ?",
            sub_params,
        ) as cursor:
            rows = await cursor.fetchall()

    return [_row_to_customer(row) for row in rows]


async def update_customer(db: aiosqlite.Connection, customer: Customer) -> bool:
    """Update existing customer details and timestamp. Return True if updated."""
    if customer.id is None:
        return False

    cursor = await db.execute(
        """
        UPDATE customers
        SET name = ?,
            phones = ?,
            addresses = ?,
            notes = ?,
            updated_at = CURRENT_TIMESTAMP
        WHERE id = ?
        """,
        (
            customer.name,
            json.dumps(customer.phones, ensure_ascii=False),
            json.dumps(customer.addresses, ensure_ascii=False),
            customer.notes,
            customer.id,
        ),
    )
    await db.commit()
    return cursor.rowcount > 0


async def list_customers(
    db: aiosqlite.Connection, limit: int = 50, offset: int = 0
) -> Sequence[Customer]:
    """List paginated customers ordered by created_at descending."""
    query = "SELECT * FROM customers ORDER BY created_at DESC LIMIT ? OFFSET ?"
    async with db.execute(query, (limit, offset)) as cursor:
        rows = await cursor.fetchall()
        return [_row_to_customer(row) for row in rows]


async def add_address(
    db: aiosqlite.Connection, customer_id: int, new_address: str
) -> bool:
    """Append new address to customer's address list if not already present.

    Compares normalized addresses (stripped, lower-cased) to avoid duplicates.
    Returns True if added, False if already exists or customer not found.
    """
    clean_address = new_address.strip()
    if not clean_address:
        return False

    customer = await get_customer_by_id(db, customer_id)
    if not customer:
        return False

    normalized_existing = {addr.strip().lower() for addr in customer.addresses}
    if clean_address.lower() in normalized_existing:
        return False

    customer.addresses.append(clean_address)
    return await update_customer(db, customer)

