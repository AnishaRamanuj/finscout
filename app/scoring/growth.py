"""Growth = revenue YoY trend over the last 4 quarters."""
import pandas as pd


def score_growth(quarterly_income: dict) -> float:
    if not quarterly_income:
        return 50.0
    try:
        df = pd.DataFrame(quarterly_income)
        revenue_row = None
        for key in ["Total Revenue", "TotalRevenue", "Revenue"]:
            if key in df.index:
                revenue_row = df.loc[key]
                break
        if revenue_row is None:
            return 50.0

        values = revenue_row.dropna().astype(float).tolist()[:4]
        if len(values) < 2:
            return 50.0

        yoy = (values[0] - values[-1]) / abs(values[-1]) if values[-1] else 0
        pct = yoy * 100
        if pct >= 30:
            return 95.0
        if pct >= 20:
            return 85.0
        if pct >= 10:
            return 70.0
        if pct >= 5:
            return 60.0
        if pct >= 0:
            return 50.0
        if pct >= -10:
            return 35.0
        return 20.0
    except Exception:
        return 50.0
