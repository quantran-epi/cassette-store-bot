import logging
import re

from openai import AsyncOpenAI

from src.models.mutation import IntentType
from src.models.order import OrderStatus
from src.services.order_search import PHONE_PATTERN, is_search_intent

logger = logging.getLogger(__name__)

MUTATION_PREFIXES: tuple[str, ...] = (
    "sửa",
    "đổi",
    "huỷ",
    "hủy",
    "cập nhật",
    "thay",
    "chuyển",
    "bỏ",
    "bớt",
    "thêm ghi chú",
    "mã vận đơn",
    "vận đơn là",
)

REPLY_ORDER_ID_PATTERN = re.compile(
    r"(?:CHI TIẾT ĐƠN HÀNG|Mã đơn:?)\s*#?(\d+)", re.IGNORECASE
)

FAST_PATH_STATUS_PATTERNS: list[tuple[re.Pattern, OrderStatus]] = [
    (re.compile(r"^(?:huỷ|hủy)\s+đơn\s*(?:#|số)?\s*(\d+)$", re.IGNORECASE), OrderStatus.HUY_DON),
    (re.compile(r"^đơn\s*(?:#|số)?\s*(\d+)\s+(?:đã\s+giao|giao\s+thành\s+công)$", re.IGNORECASE), OrderStatus.DA_GIAO),
    (re.compile(r"^đơn\s*(?:#|số)?\s*(\d+)\s+bom(?:\s+hàng)?$", re.IGNORECASE), OrderStatus.BOM_HANG),
    (re.compile(r"^(?:làm|bắt\s+đầu\s+làm)\s+đơn\s*(?:#|số)?\s*(\d+)$", re.IGNORECASE), OrderStatus.DANG_LAM),
    (re.compile(r"^(?:đã\s+)?đóng\s+gói\s+đơn\s*(?:#|số)?\s*(\d+)$", re.IGNORECASE), OrderStatus.DA_DONG_GOI),
]


def extract_order_id_from_reply(reply_text: str | None) -> int | None:
    """Extract Order ID integer from replied bot order card messages per D-05."""
    if not reply_text or not isinstance(reply_text, str):
        return None
    match = REPLY_ORDER_ID_PATTERN.search(reply_text)
    return int(match.group(1)) if match else None


def parse_fast_path_status(text: str) -> tuple[int, OrderStatus] | None:
    """Parse short status commands directly into (order_id, target_status) in 0ms without LLM per D-06."""
    cleaned = text.strip()
    for pattern, target_status in FAST_PATH_STATUS_PATTERNS:
        match = pattern.match(cleaned)
        if match:
            return int(match.group(1)), target_status
    return None


async def classify_intent(
    text: str,
    client: AsyncOpenAI | None,
    model_id: str,
    has_reply_order: bool = False,
) -> IntentType:
    """3-Way Intent Router categorizing messages into CREATE, SEARCH, or MUTATE (D-01 to D-06)."""
    trimmed = text.strip().lower()

    # Step 1: Replying to bot order card message always routes to MUTATE
    if has_reply_order:
        return IntentType.MUTATE

    # Step 2: Unambiguous status fast-paths
    if parse_fast_path_status(text) is not None:
        return IntentType.MUTATE

    # Step 3: Explicit mutation prefixes
    if any(trimmed.startswith(p) for p in MUTATION_PREFIXES):
        return IntentType.MUTATE

    # Step 4: Explicit or conversational search intent
    if is_search_intent(text):
        return IntentType.SEARCH

    # Step 5: Ambiguity check (contains phone number AND mutation keyword) -> prioritize MUTATE per D-02
    if any(cue in trimmed for cue in ("sửa", "đổi", "huỷ", "hủy")):
        return IntentType.MUTATE

    # Step 6: Contains Vietnamese phone number -> CREATE
    if PHONE_PATTERN.search(text):
        return IntentType.CREATE

    # Step 7: Fallback lightweight LLM classification (10-20 tokens per D-04)
    if client is not None:
        try:
            prompt = (
                "Phân loại tin nhắn sau thành đúng 1 trong 3 nhãn: CREATE, SEARCH, MUTATE.\n"
                "- CREATE: Tạo đơn hàng mới (chứa thông tin khách, địa chỉ, hàng hoá).\n"
                "- SEARCH: Tìm kiếm, tra cứu đơn hàng, xem lịch sử hoặc thống kê.\n"
                "- MUTATE: Yêu cầu sửa đổi, cập nhật thông tin, thay đổi trạng thái đơn hàng.\n"
                f"Tin nhắn: <message>{text}</message>\n"
                "Chỉ trả về duy nhất 1 từ: CREATE, SEARCH, hoặc MUTATE."
            )
            response = await client.chat.completions.create(
                model=model_id,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=5,
                temperature=0.0,
            )
            val = (response.choices[0].message.content or "").strip().upper()
            if "MUTATE" in val:
                return IntentType.MUTATE
            if "SEARCH" in val:
                return IntentType.SEARCH
            if "CREATE" in val:
                return IntentType.CREATE
        except Exception as e:
            logger.warning("LLM intent classification fallback failed: %s", e)

    return IntentType.CREATE
