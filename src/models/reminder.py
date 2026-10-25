from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum


class ReminderStatus(StrEnum):
    PENDING = "PENDING"
    SENT = "SENT"
    CANCELLED = "CANCELLED"


@dataclass
class Reminder:
    id: int | None
    order_id: int
    remind_at: datetime | str
    reminder_text: str
    status: ReminderStatus = ReminderStatus.PENDING
    created_by_user_id: int | None = None
    created_at: datetime | str | None = None
    sent_at: datetime | str | None = None
