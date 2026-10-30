"""News sentiment via Claude Haiku 5.5 — cheap, fast at scale."""
from anthropic import Anthropic
from app.config import settings

_client = Anthropic(api_key=settings.anthropic_api_key) if settings.anthropic_api_key else None


def score_news_sentiment(ticker: str, headlines: list[str]) -> float:
    if not _client or not headlines:
        return 50.0
    joined = "\n".join(h[:200] for h in headlines[:30])
    try:
        resp = _client.messages.create(
            model=settings.model_fast,
            max_tokens=10,
            system="Rate stock news sentiment on a 0-100 scale. 0 = very bearish, 50 = neutral, 100 = very bullish. Return only the number.",
            messages=[{"role": "user", "content": f"{ticker}:\n{joined}"}],
        )
        value = float(resp.content[0].text.strip())
        return max(0.0, min(100.0, value))
    except Exception:
        return 50.0
