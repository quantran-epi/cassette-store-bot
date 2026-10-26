import re

from pydantic import BaseModel, Field, field_validator

from src.models.order import TapeItem

# Vietnamese mobile numbers: 10 digits starting with 03, 05, 07, 08, 09
VN_PHONE_REGEX = re.compile(r"^0[35789]\d{8}$")


class ExtractedOrder(BaseModel):
    """Pydantic model for structured LLM order extraction with normalization."""

    customer_name: str | None = Field(default=None, description="Tên khách hàng nếu có trong tin nhắn")
    customer_phone: str | None = Field(default=None, description="Số điện thoại khách hàng (10 chữ số)")
    shipping_address: str | None = Field(default=None, description="Địa chỉ giao hàng chi tiết")
    items_text: str | None = Field(default=None, description="Danh sách các cuốn băng cassette kèm số lượng")
    tapes: list[TapeItem] = Field(
        default_factory=list,
        description="Phôi băng shop phải lấy từ kho: mỗi item {label, qty} (VD: sony 90p x6)",
    )
    tape_genres: list[str] = Field(
        default_factory=list,
        description="Thể loại nội dung best effort (VD: nhạc vàng, hải ngoại); [] khi không rõ",
    )
    tape_artists: list[str] = Field(
        default_factory=list,
        description="Tên ca sĩ / nghệ sĩ xuất hiện trong đơn (VD: Chế Linh, Thanh Tuyền); không đoán",
    )
    total_amount: int = Field(default=0, ge=0, description="Tổng giá trị đơn hàng tính theo VNĐ")
    cod_amount: int = Field(default=0, ge=0, description="Số tiền COD cần thu khách khi giao tính theo VNĐ")
    deposit_amount: int = Field(default=0, ge=0, description="Số tiền khách đã chuyển khoản đặt cọc trước")
    payment_method: str = Field(default="COD", description="Hình thức thanh toán: COD hoặc CHUYEN_KHOAN")
    notes: str = Field(default="", description="Ghi chú thêm về đơn hàng hoặc yêu cầu của khách")
    reminder_at: str | None = Field(
        default=None,
        description="Thời gian nhắc việc dạng ISO 'YYYY-MM-DD HH:MM' nếu khách yêu cầu ngày giờ cụ thể (VD: thứ 2 tuần sau, mai giao...)",
    )
    reminder_note: str | None = Field(
        default=None,
        description="Nội dung cụ thể cần nhắc lịch (VD: 'Gửi hàng cho khách', 'Giao sau 17h')",
    )

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

    @field_validator("tapes", mode="before")
    @classmethod
    def normalize_tapes(cls, v: object) -> list:
        """Normalize LLM tape items: strip labels, drop empty labels and qty < 1."""
        if not v:
            return []
        raw = v if isinstance(v, list) else []
        if isinstance(raw, dict):
            raw = [raw]
        items: list = []
        for item in raw:
            data = item.model_dump() if isinstance(item, TapeItem) else item
            if not isinstance(data, dict):
                continue
            label = str(data.get("label") or "").strip()
            try:
                qty = int(data.get("qty"))
            except (TypeError, ValueError):
                continue
            if not label or qty < 1:
                continue
            items.append({"label": label, "qty": qty})
        return items

    @field_validator("tape_genres", mode="before")
    @classmethod
    def normalize_tape_genres(cls, v: object) -> list[str]:
        """Strip genre strings and drop empties."""
        if not v or not isinstance(v, list):
            return []
        return [g.strip() for g in v if isinstance(g, str) and g.strip()]

    @field_validator("tape_artists", mode="before")
    @classmethod
    def normalize_tape_artists(cls, v: object) -> list[str]:
        """Strip artist names, drop empties, dedupe case-insensitively."""
        if not v or not isinstance(v, list):
            return []
        seen: set[str] = set()
        out: list[str] = []
        for item in v:
            if not isinstance(item, str):
                continue
            name = item.strip()
            if not name:
                continue
            key = name.casefold()
            if key in seen:
                continue
            seen.add(key)
            out.append(name)
        return out
