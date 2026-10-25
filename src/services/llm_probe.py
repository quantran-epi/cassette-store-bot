from openai import AsyncOpenAI


async def probe_model_reachability(
    client: AsyncOpenAI,
    candidate_model: str,
    timeout: float = 5.0,
) -> tuple[bool, str]:
    """Test candidate model with a 1-token probe. Returns (success, detail_message)."""
    try:
        await client.chat.completions.create(
            model=candidate_model,
            messages=[{"role": "user", "content": "hi"}],
            max_tokens=1,
            timeout=timeout,
        )
        return True, "Kết nối thành công (HTTP 200 OK)"
    except Exception as exc:
        return False, f"Lỗi phản hồi: {exc}"
