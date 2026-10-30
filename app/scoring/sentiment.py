"""News sentiment via the configured LLM's 'fast' tier."""
from app.llm import get_llm
from app.llm.base import CompletionRequest


SYSTEM = (
    "Rate stock news sentiment on a 0-100 scale. "
    "0 = very bearish, 50 = neutral, 100 = very bullish. "
    "Return only the number, nothing else."
)


def score_news_sentiment(ticker: str, headlines: list[str]) -> float:
    if not headlines:
        return 50.0
    joined = "\n".join(h[:200] for h in headlines[:30])
    try:
        text = get_llm().fast(CompletionRequest(
            system=SYSTEM,
            user=f"{ticker}:\n{joined}",
            max_tokens=10,
            temperature=0.0,
        ))
        value = float(text.strip().split()[0])
        return max(0.0, min(100.0, value))
    except Exception:
        return 50.0
