"""Composite scoring engine — weighted blend of the 7 factors."""
from app.scoring.growth import score_growth
from app.scoring.momentum import score_momentum
from app.scoring.valuation import score_valuation
from app.scoring.sentiment import score_news_sentiment
from app.scoring.insider import score_insider

WEIGHTS = {
    "growth": 0.25,
    "profitability": 0.20,
    "momentum": 0.20,
    "insider": 0.10,
    "sentiment": 0.10,
    "valuation": 0.10,
    "quality": 0.05,
}


def compute_scores(
    ticker: str,
    financials: dict,
    news_headlines: list[str],
    nse_trades: list[dict] | None = None,
) -> dict:
    info = financials.get("info", {})
    growth = score_growth(financials.get("quarterly_income", {}))
    momentum = score_momentum(financials.get("price_1y", {}))
    valuation = score_valuation(info.get("pe"))
    sentiment = score_news_sentiment(ticker, news_headlines)
    insider = score_insider(nse_trades or [])

    profitability = min(100, max(0, (info.get("roce") or 0) * 100 * 3))
    quality = 60.0

    scores = {
        "growth": growth,
        "profitability": profitability,
        "momentum": momentum,
        "insider": insider,
        "sentiment": sentiment,
        "valuation": valuation,
        "quality": quality,
    }
    composite = sum(scores[k] * w for k, w in WEIGHTS.items())
    scores["composite"] = round(composite, 2)
    return scores
