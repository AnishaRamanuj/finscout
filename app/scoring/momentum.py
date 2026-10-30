"""Momentum = 3-month price change."""
import pandas as pd


def score_momentum(price_1y: dict) -> float:
    if not price_1y:
        return 50.0
    try:
        prices = pd.Series(price_1y.get("Close", {}))
        if len(prices) < 60:
            return 50.0
        latest = prices.iloc[-1]
        past = prices.iloc[-63] if len(prices) > 63 else prices.iloc[0]
        pct = (latest - past) / past * 100 if past else 0

        if pct >= 20:
            return 95.0
        if pct >= 10:
            return 80.0
        if pct >= 5:
            return 65.0
        if pct >= 0:
            return 55.0
        if pct >= -10:
            return 40.0
        return 25.0
    except Exception:
        return 50.0
