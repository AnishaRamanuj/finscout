"""Explains any ratio in one plain-English sentence."""
from app.llm import get_llm
from app.llm.base import CompletionRequest


SYSTEM = (
    "You explain stock ratios in ONE sentence (max 25 words) for a retail investor. "
    "Compare against sector median when provided. No disclaimers."
)


def explain_ratio(ratio_name: str, value: float, sector_median: float | None = None) -> str:
    ctx = f"{ratio_name} = {value}"
    if sector_median is not None:
        ctx += f"; sector median = {sector_median}"
    try:
        return get_llm().fast(CompletionRequest(
            system=SYSTEM,
            user=ctx,
            max_tokens=120,
        ))
    except Exception:
        return ""
