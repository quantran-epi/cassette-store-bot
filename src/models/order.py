from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field


class TapeItem(BaseModel):
    """One physical tape medium (phôi) line: label + count."""

    label: str
    qty: int = Field(ge=1)


class OrderStatus(str, Enum):
    """Order lifecycle status enum (8 states)."""

    CHO_LAM = "CHO_LAM"
    DANG_LAM = "DANG_LAM"
    DA_DONG_GOI = "DA_DONG_GOI"
    DA_TAO_DON = "DA_TAO_DON"
    SHIPPER_DA_LAY = "SHIPPER_DA_LAY"
    DA_GIAO = "DA_GIAO"
    BOM_HANG = "BOM_HANG"
    HUY_DON = "HUY_DON"


class Order(BaseModel):
    """Order domain model storing customer snapshot, items text, and lifecycle status."""

    id: int | None = None
    customer_id: int | None = None
    customer_completed_orders: int | None = None
    customer_completed_spend: int | None = None
    customer_name: str
    customer_phone: str
    shipping_address: str
    items_text: str
    total_amount: int = 0
    cod_amount: int = 0
    payment_method: str = "COD"
    status: OrderStatus = OrderStatus.CHO_LAM
    tracking_code: str | None = None
    tape_quantity: int | None = None
    tapes: list[TapeItem] = Field(default_factory=list)
    tape_genres: list[str] = Field(default_factory=list)
    tape_artists: list[str] = Field(default_factory=list)
    photo_file_ids: list[str] = Field(default_factory=list)
    raw_text: str = ""
    notes: str = ""
    created_by_user_id: int | None = None
    created_by_name: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None
