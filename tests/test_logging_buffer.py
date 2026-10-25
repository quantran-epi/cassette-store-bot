import logging

from src.bot.logging_handler import RingBufferLogHandler


def test_ring_buffer_capacity_eviction():
    """Verify handler caps records at capacity and evicts oldest FIFO."""
    handler = RingBufferLogHandler(capacity=5)
    logger = logging.getLogger("test_capacity")
    logger.setLevel(logging.INFO)
    logger.addHandler(handler)

    for i in range(10):
        logger.info(f"Message {i}")

    logs = handler.get_logs(limit=10)
    assert len(logs) == 5
    assert "Message 5" in logs[0]
    assert "Message 9" in logs[4]


def test_ring_buffer_get_logs_limit():
    """Verify limit parameter returns the most recent N lines."""
    handler = RingBufferLogHandler(capacity=20)
    logger = logging.getLogger("test_limit")
    logger.setLevel(logging.INFO)
    logger.addHandler(handler)

    for i in range(10):
        logger.info(f"Log line {i}")

    logs_3 = handler.get_logs(limit=3)
    assert len(logs_3) == 3
    assert "Log line 7" in logs_3[0]
    assert "Log line 9" in logs_3[2]


def test_ring_buffer_errors_only():
    """Verify errors_only=True returns only WARNING, ERROR, or CRITICAL records."""
    handler = RingBufferLogHandler(capacity=20)
    logger = logging.getLogger("test_errors")
    logger.setLevel(logging.DEBUG)
    logger.addHandler(handler)

    logger.debug("Debug msg")
    logger.info("Info msg")
    logger.warning("Warning msg")
    logger.error("Error msg")
    logger.critical("Critical msg")

    all_logs = handler.get_logs(limit=10, errors_only=False)
    assert len(all_logs) == 5

    error_logs = handler.get_logs(limit=10, errors_only=True)
    assert len(error_logs) == 3
    assert any("Warning msg" in line for line in error_logs)
    assert any("Error msg" in line for line in error_logs)
    assert any("Critical msg" in line for line in error_logs)
    assert not any("Info msg" in line for line in error_logs)


def test_ring_buffer_html_escaping():
    """Verify special HTML characters are escaped using html.escape to prevent Telegram parse errors."""
    handler = RingBufferLogHandler(capacity=10)
    logger = logging.getLogger("test_escape")
    logger.setLevel(logging.INFO)
    logger.addHandler(handler)

    logger.info("<script>alert('xss & dangerous');</script>")

    logs = handler.get_logs(limit=10)
    assert len(logs) == 1
    assert "&lt;script&gt;" in logs[0]
    assert "&amp;" in logs[0]
    assert "<script>" not in logs[0]


def test_format_logs_for_telegram_truncation():
    """Verify format_logs_for_telegram truncates older lines when output exceeds max_chars."""
    handler = RingBufferLogHandler(capacity=50)
    logger = logging.getLogger("test_format")
    logger.setLevel(logging.INFO)
    logger.addHandler(handler)

    # Add 20 long messages
    long_msg = "X" * 300
    for i in range(20):
        logger.info(f"[{i:02d}] {long_msg}")

    # Set max_chars low (e.g., 1000)
    formatted = handler.format_logs_for_telegram(limit=20, max_chars=1000)
    assert len(formatted) <= 1000
    assert "... (đã cắt bớt các dòng cũ)" in formatted
    # Most recent message should be preserved
    assert "[19]" in formatted


def test_format_logs_for_telegram_empty():
    """Verify empty buffer returns plain text without HTML tags for pre/code safety."""
    handler = RingBufferLogHandler(capacity=10)
    formatted = handler.format_logs_for_telegram()
    assert formatted == "(Không có nhật ký nào)"
    assert "<" not in formatted
