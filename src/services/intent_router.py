import logging
import re

from openai import AsyncOpenAI

from src.db.connection import remove_accents
from src.db.customers import is_customer_analytics, is_customer_search
from src.models.mutation import IntentDecision, IntentType
from src.models.order import OrderStatus
from src.services.order_search import PHONE_PATTERN, is_analytics_intent, is_search_intent

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
) -> IntentDecision:
    """Route once using deterministic rules, then LLM only for ambiguous text."""
    normalized = remove_accents(text).strip().lower()

    if has_reply_order or parse_fast_path_status(text) is not None:
        return IntentDecision(intent=IntentType.MUTATE)

    normalized_mutation_prefixes = tuple(remove_accents(p) for p in MUTATION_PREFIXES)
    if normalized.startswith(normalized_mutation_prefixes):
        return IntentDecision(intent=IntentType.MUTATE)

    if any(cue in normalized for cue in ("sua", "doi", "huy")):
        return IntentDecision(intent=IntentType.MUTATE)

    if is_customer_search(text):
        return IntentDecision(intent=IntentType.CUSTOMER_PROFILE)

    if is_customer_analytics(text) and not re.search(
        r"\b(?:da|tung|co)\s+mua\b|\blich\s+su\s+(?:mua|don)\b", normalized
    ):
        return IntentDecision(intent=IntentType.CUSTOMER_ANALYTICS)

    if is_analytics_intent(text):
        return IntentDecision(intent=IntentType.CUSTOMER_ANALYTICS)

    if is_search_intent(text):
        return IntentDecision(intent=IntentType.ORDER_SEARCH)

    if PHONE_PATTERN.search(text):
        return IntentDecision(intent=IntentType.CREATE)

    if client is None:
        return IntentDecision(intent=IntentType.CREATE, source="fallback")

    if client is not None:
        try:
            prompt = (
                "Phân loại tin nhắn sau thành đúng 1 nhãn:\n"
                "CREATE: tạo đơn hàng mới.\n"
                "MUTATE: sửa đơn hoặc đổi trạng thái.\n"
                "CUSTOMER_PROFILE: tìm hồ sơ khách theo tên, SĐT hoặc địa chỉ.\n"
                "ORDER_SEARCH: tìm đơn hoặc lịch sử mua.\n"
                "CUSTOMER_ANALYTICS: đếm, tổng hợp hoặc xếp hạng khách/đơn.\n"
                "UNCLEAR: không đủ chắc chắn để chọn các nhãn trên.\n"
                f"Tin nhắn: <message>{text}</message>\n"
                "Chỉ trả về đúng 1 nhãn."
            )
            response = await client.chat.completions.create(
                model=model_id,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=8,
                temperature=0.0,
            )
            raw = (response.choices[0].message.content or "").strip().upper()
            label = raw.split()[0] if raw else "UNCLEAR"
            try:
                intent = IntentType(label)
            except ValueError:
                intent = IntentType.UNCLEAR
            return IntentDecision(intent=intent, source="llm", confidence=0.8)
        except Exception as e:
            logger.warning("LLM intent classification fallback failed: %s", e)
            return IntentDecision(intent=IntentType.CREATE, source="fallback", confidence=0.0)

    return IntentDecision(intent=IntentType.UNCLEAR, source="fallback", confidence=0.0)
