import re
from pydantic import BaseModel, Field, field_validator

# Vietnamese mobile numbers: 10 digits starting with 03, 05, 07, 08, 09
VN_PHONE_REGEX = re.compile(r"^0[35789]\d{8}$")


class ExtractedOrder(BaseModel):
    """Pydantic model for structured LLM order extraction with normalization."""

    customer_name: str | None = Field(default=None, description="Tên khách hàng nếu có trong tin nhắn")
    customer_phone: str | None = Field(default=None, description="Số điện thoại khách hàng (10 chữ số)")
    shipping_address: str | None = Field(default=None, description="Địa chỉ giao hàng chi tiết")
    items_text: str | None = Field(default=None, description="Danh sách các cuốn băng cassette kèm số lượng")
    total_amount: int = Field(default=0, ge=0, description="Tổng giá trị đơn hàng tính theo VNĐ")
    cod_amount: int = Field(default=0, ge=0, description="Số tiền COD cần thu khách khi giao tính theo VNĐ")
    deposit_amount: int = Field(default=0, ge=0, description="Số tiền khách đã chuyển khoản đặt cọc trước")
    payment_method: str = Field(default="COD", description="Hình thức thanh toán: COD hoặc CHUYEN_KHOAN")
    notes: str = Field(default="", description="Ghi chú thêm về đơn hàng hoặc yêu cầu của khách")

    @field_validator("customer_phone", mode="before")
    @classmethod
    def normalize_vietnamese_phone(cls, v: str | None) -> str | None:
        """Normalize Vietnamese mobile phone number into 10-digit standard form."""
        if not v or not isinstance(v, str):
            return None

        # Remove spaces, dots, dashes, parentheses
        cleaned = re.sub(r"[\s.\-()]", "", v)

        # Convert +84 prefix to 0
        if cleaned.startswith("+84"):
            cleaned = "0" + cleaned[3:]
        elif cleaned.startswith("84") and len(cleaned) == 11:
            cleaned = "0" + cleaned[2:]

        # Validate against 10-digit VN mobile network prefix
        if VN_PHONE_REGEX.match(cleaned):
            return cleaned

        return None
