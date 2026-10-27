import re
from enum import Enum

from pydantic import BaseModel, Field, field_validator

from src.models.order import OrderStatus, TapeItem

# Vietnamese mobile numbers: 10 digits starting with 03, 05, 07, 08, 09
VN_PHONE_REGEX = re.compile(r"^0[35789]\d{8}$")


class IntentType(str, Enum):
    """3-way intent classification for incoming chat messages (D-03)."""

    CREATE = "CREATE"
    SEARCH = "SEARCH"
    MUTATE = "MUTATE"


class OrderMutationDelta(BaseModel):
    """Structured mutation delta for 5 field groups per MUT-03."""

    target_order_id: int | None = Field(
        default=None, description="Mã đơn hàng cần sửa nếu có"
    )
    target_customer_keyword: str | None = Field(
        default=None, description="Tên khách hoặc từ khoá định danh đơn cũ"
    )
    new_status: OrderStatus | None = Field(
        default=None, description="Trạng thái mới nếu có"
    )
    status_disambiguation_needed: bool = Field(
        default=False, description="Cần chọn trạng thái kế tiếp do chưa rõ"
    )
    new_tracking_code: str | None = Field(
        default=None, description="Mã vận đơn mới"
    )
    new_notes: str | None = Field(
        default=None, description="Ghi chú mới hoặc sửa"
    )
    new_total_amount: int | None = Field(
        default=None, ge=0, description="Tổng tiền mới tính theo VNĐ"
    )
    new_cod_amount: int | None = Field(
        default=None, ge=0, description="Tiền COD mới tính theo VNĐ"
    )
    new_customer_phone: str | None = Field(
        default=None, description="Số điện thoại nhận hàng mới (10 chữ số)"
    )
    new_shipping_address: str | None = Field(
        default=None, description="Địa chỉ giao hàng mới"
    )
    new_customer_name: str | None = Field(
        default=None, description="Tên khách hàng mới"
    )
    new_items_text: str | None = Field(
        default=None, description="Danh sách món/băng mới hoặc sửa đổi"
    )
    new_tapes: list[TapeItem] | None = Field(
        default=None,
        description="Breakdown phôi mới {label, qty}; chỉ điền khi new_items_text thay đổi",
    )
    new_tape_genres: list[str] | None = Field(
        default=None,
        description="Thể loại nội dung mới; chỉ điền khi new_items_text thay đổi",
    )
    new_tape_artists: list[str] | None = Field(
        default=None,
        description="Tên ca sĩ mới; chỉ điền khi new_items_text thay đổi",
    )
    new_reminder_at: str | None = Field(
        default=None,
        description="Thời điểm nhắc việc mới dạng ISO 'YYYY-MM-DD HH:MM' (giờ Việt Nam)",
    )
    new_reminder_note: str | None = Field(
        default=None,
        description="Nội dung nhắc việc mới (VD: 'Gửi hàng cho khách')",
    )
    clear_reminder: bool = Field(
        default=False,
        description="True khi người dùng muốn bỏ lịch nhắc của đơn",
    )

    @field_validator("new_customer_phone", mode="before")
    @classmethod
    def validate_phone(cls, v: str | None) -> str | None:
        """Validate and normalize Vietnamese phone number into 10-digit format."""
        if not v or not isinstance(v, str):
            return None
        cleaned = re.sub(r"[\s.\-()]", "", v)
        if cleaned.startswith("+84"):
            cleaned = "0" + cleaned[3:]
        elif cleaned.startswith("84") and len(cleaned) == 11:
            cleaned = "0" + cleaned[2:]
        return cleaned if VN_PHONE_REGEX.match(cleaned) else None
