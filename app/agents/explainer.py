"""Haiku 5.5 explains any ratio in one plain-English sentence."""
from anthropic import Anthropic
from app.config import settings

_client = Anthropic(api_key=settings.anthropic_api_key) if settings.anthropic_api_key else None


def explain_ratio(ratio_name: str, value: float, sector_median: float | None = None) -> str:
    if not _client:
        return ""
    ctx = f"{ratio_name} = {value}"
    if sector_median is not None:
        ctx += f"; sector median = {sector_median}"
    try:
        resp = _client.messages.create(
            model=settings.model_fast,
            max_tokens=100,
            system="You explain stock ratios in ONE sentence (max 25 words) for a retail investor. Compare against sector median when provided. No disclaimers.",
            messages=[{"role": "user", "content": ctx}],
        )
        return resp.content[0].text.strip()
    except Exception:
        return ""
