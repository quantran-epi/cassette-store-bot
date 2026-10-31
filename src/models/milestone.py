from datetime import datetime
from enum import Enum

from pydantic import BaseModel


class MilestonePeriod(str, Enum):
    """Time scope for milestone calculation."""

    WEEK = "week"
    MONTH = "month"
    YEAR = "year"
    ALL_TIME = "all_time"


class MilestoneTargetType(str, Enum):
    """Metric type for milestone."""

    ORDER_COUNT = "order_count"
    REVENUE = "revenue"


class MilestoneRule(BaseModel):
    """Milestone celebration threshold rule."""

    id: int | None = None
    period: MilestonePeriod
    target_type: MilestoneTargetType
    target_value: int
    only_delivered: bool = False
    message_template: str
    effect_enabled: bool = True
    is_active: bool = True
    created_at: datetime | None = None
    updated_at: datetime | None = None


class MilestoneLog(BaseModel):
    """Record of triggered milestone per period cycle."""

    id: int | None = None
    rule_id: int
    period_key: str
    current_value: int
    triggered_at: datetime | None = None
