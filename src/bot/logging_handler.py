import collections
import html
import logging
from typing import Any


class RingBufferLogHandler(logging.Handler):
    """In-memory ring buffer log handler with fixed capacity."""

    def __init__(self, capacity: int = 100) -> None:
        super().__init__()
        self.capacity = capacity
        self.buffer: collections.deque[dict[str, Any]] = collections.deque(maxlen=capacity)

    def emit(self, record: logging.LogRecord) -> None:
        try:
            msg = self.format(record)
            self.buffer.append(
                {
                    "level": record.levelname,
                    "msg": msg,
                    "created": record.created,
                }
            )
        except Exception:
            self.handleError(record)

    def get_logs(self, limit: int = 25, errors_only: bool = False) -> list[str]:
        """Retrieve recent log lines, optionally filtering errors and escaping HTML."""
        records = list(self.buffer)
        if errors_only:
            records = [r for r in records if r["level"] in ("WARNING", "ERROR", "CRITICAL")]
        selected = records[-limit:]
        return [html.escape(r["msg"]) for r in selected]

    def format_logs_for_telegram(
        self, limit: int = 25, errors_only: bool = False, max_chars: int = 3800
    ) -> str:
        """Format logs as a single string bounded by max_chars for safe Telegram delivery."""
        lines = self.get_logs(limit=limit, errors_only=errors_only)
        if not lines:
            return "(Không có nhật ký nào)"

        prefix = "... (đã cắt bớt các dòng cũ)\n"
        # Assemble lines from newest backwards
        included: list[str] = []
        current_len = 0

        for line in reversed(lines):
            line_cost = len(line) + 1  # newline
            if current_len + line_cost > max_chars:
                break
            included.append(line)
            current_len += line_cost

        included.reverse()
        if len(included) < len(lines):
            # Truncation occurred
            header = prefix
            # Ensure total doesn't exceed max_chars including prefix
            while included and len(header) + sum(len(x) + 1 for x in included) > max_chars:
                included.pop(0)
            return header + "\n".join(included)

        return "\n".join(included)
