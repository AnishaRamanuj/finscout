"""News fetch via Finnhub."""
from datetime import datetime, timedelta
import finnhub
from app.config import settings


def fetch_news(ticker: str, days: int = 30) -> list[dict]:
    if not settings.finnhub_api_key:
        return []
    client = finnhub.Client(api_key=settings.finnhub_api_key)
    today = datetime.utcnow().date()
    start = today - timedelta(days=days)
    try:
        return client.company_news(ticker, _from=str(start), to=str(today)) or []
    except Exception:
        return []
