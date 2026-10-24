import pytest

from src.db.connection import remove_accents
from src.services.order_search import (
    is_search_intent,
    sanitize_and_validate_sql,
)


def test_unaccent_remove_accents():
    assert remove_accents("Tuấn Vũ") == "tuan vu"
    assert remove_accents("Đà Nẵng") == "da nang"
    assert remove_accents("Đức Thành") == "duc thanh"
    assert remove_accents(None) == ""
    assert remove_accents("") == ""


@pytest.mark.asyncio
async def test_unaccent_sqlite(test_db):
    cursor = await test_db.execute("SELECT unaccent('Tuấn Vũ') AS unaccented")
    row = await cursor.fetchone()
    assert row["unaccented"] == "tuan vu"

    cursor = await test_db.execute("SELECT unaccent('Đà Nẵng') AS unaccented")
    row = await cursor.fetchone()
    assert row["unaccented"] == "da nang"


def test_sql_sanitizer_valid():
    sql1 = "SELECT * FROM orders"
    assert sanitize_and_validate_sql(sql1) == "SELECT * FROM orders LIMIT 20"

    sql2 = "SELECT * FROM orders WHERE status = 'CHO_LAM' LIMIT 5"
    assert sanitize_and_validate_sql(sql2) == "SELECT * FROM orders WHERE status = 'CHO_LAM' LIMIT 5"

    sql3 = "```sql\nSELECT o.* FROM orders o;\n```"
    assert sanitize_and_validate_sql(sql3) == "SELECT o.* FROM orders o LIMIT 20"

    sql4 = "select count(*) from orders;"
    assert sanitize_and_validate_sql(sql4) == "select count(*) from orders LIMIT 20"


def test_sql_sanitizer_rejections():
    # Multi-statement injection defense
    with pytest.raises(ValueError, match="nhiều câu lệnh SQL"):
        sanitize_and_validate_sql("SELECT * FROM orders; DROP TABLE orders")

    with pytest.raises(ValueError, match="nhiều câu lệnh SQL"):
        sanitize_and_validate_sql("SELECT 1; SELECT 2;")

    # Not starting with SELECT
    with pytest.raises(ValueError, match="bắt đầu bằng SELECT"):
        sanitize_and_validate_sql("DELETE FROM orders")

    with pytest.raises(ValueError, match="bắt đầu bằng SELECT"):
        sanitize_and_validate_sql("INSERT INTO orders (customer_name) VALUES ('x')")

    with pytest.raises(ValueError, match="bắt đầu bằng SELECT"):
        sanitize_and_validate_sql("SHOW TABLES")

    # Forbidden DDL/DML keywords inside SELECT
    with pytest.raises(ValueError, match="từ khoá cấm"):
        sanitize_and_validate_sql("SELECT * FROM orders WHERE id IN (DELETE FROM orders)")

    with pytest.raises(ValueError, match="từ khoá cấm"):
        sanitize_and_validate_sql("SELECT * FROM orders WHERE 1=1 OR PRAGMA schema_version")

    with pytest.raises(ValueError, match="từ khoá cấm"):
        sanitize_and_validate_sql("SELECT * FROM (ALTER TABLE orders ADD COLUMN x TEXT)")


def test_is_search_intent():
    assert is_search_intent("tìm đơn anh Tuấn") is True
    assert is_search_intent("Tìm đơn Tuấn Vũ") is True
    assert is_search_intent("  tra cứu đơn hôm qua ") is True
    assert is_search_intent("kiểm tra đơn 123") is True
    assert is_search_intent("xem lại đơn anh Hải") is True
    assert is_search_intent("hỏi đơn hàng gửi đi Đà Nẵng") is True

    # Negative cases
    assert is_search_intent("Tuấn Vũ 2 cuốn gửi 123 Lê Lợi 0903123456") is False
    assert is_search_intent("Khánh Ly hạ trắng thu 300k") is False
    assert is_search_intent("đơn mới nè") is False
