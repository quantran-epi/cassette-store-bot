import re
from typing import Any

SEARCH_PREFIX_KEYWORDS: tuple[str, ...] = (
    "tìm",
    "tra cứu",
    "kiểm tra",
    "xem lại đơn",
    "hỏi đơn",
)

FORBIDDEN_SQL_KEYWORDS: set[str] = {
    "INSERT",
    "UPDATE",
    "DELETE",
    "DROP",
    "ALTER",
    "CREATE",
    "REPLACE",
    "ATTACH",
    "DETACH",
    "PRAGMA",
    "VACUUM",
    "EXEC",
}


def is_search_intent(text: str) -> bool:
    """Check if trimmed text starts with any search prefix keyword (case-insensitive)."""
    trimmed = text.strip().lower()
    return any(trimmed.startswith(prefix) for prefix in SEARCH_PREFIX_KEYWORDS)


def sanitize_and_validate_sql(raw_sql: str) -> str:
    """Sanitize and strictly validate LLM-generated SQL query (D-05, T-04-01).

    Rules:
    - Strip markdown fences (```sql ... ```)
    - Strip trailing semicolons
    - Reject any remaining semicolon (multi-statement injection defense)
    - Verify statement starts with SELECT
    - Reject if any forbidden DDL/DML keywords appear
    - Append LIMIT 20 if no LIMIT clause exists
    """
    cleaned = raw_sql.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:sql)?\s*", "", cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(r"\s*```$", "", cleaned)
    cleaned = cleaned.strip()

    # Strip trailing semicolons
    cleaned = re.sub(r";+\s*$", "", cleaned).strip()

    if ";" in cleaned:
        raise ValueError("Phát hiện nhiều câu lệnh SQL (chống SQL injection).")

    if not re.match(r"^\s*SELECT\b", cleaned, re.IGNORECASE):
        raise ValueError("Câu lệnh truy vấn bắt buộc phải bắt đầu bằng SELECT.")

    tokens = set(re.findall(r"\b[A-Za-z_]+\b", cleaned.upper()))
    forbidden_used = tokens.intersection(FORBIDDEN_SQL_KEYWORDS)
    if forbidden_used:
        raise ValueError(f"Phát hiện từ khoá cấm thay đổi dữ liệu: {sorted(forbidden_used)}")

    if not re.search(r"\bLIMIT\s+\d+\b", cleaned, re.IGNORECASE):
        cleaned = f"{cleaned} LIMIT 20"

    return cleaned
