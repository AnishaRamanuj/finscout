"""Monday morning: generate Why-Now blurbs for the top 10 scoring companies."""
from datetime import datetime
from sqlalchemy import select, desc

from app.config import settings
from app.db import SessionLocal, Score, Company, Financials, WhyNow
from app.agents.why_now import generate_why_now


def run_monday_curation(top_n: int = 10):
    print(f"[{datetime.utcnow()}] Monday curation — top {top_n}")
    with SessionLocal() as s:
        rows = s.execute(
            select(Score, Company)
            .join(Company, Score.ticker == Company.ticker)
            .order_by(desc(Score.composite))
            .limit(top_n)
        ).all()

        for score, company in rows:
            fin = s.execute(
                select(Financials)
                .where(Financials.ticker == company.ticker)
                .order_by(desc(Financials.fetched_at))
            ).scalar_one_or_none()

            data = {
                "sector": company.sector,
                "market_cap": company.market_cap,
                "pe": fin.pe if fin else None,
                "roce": fin.roce if fin else None,
                "price": (fin.raw or {}).get("info", {}).get("price") if fin else None,
            }
            score_breakdown = {
                "growth": score.growth,
                "profitability": score.profitability,
                "momentum": score.momentum,
                "valuation": score.valuation,
                "sentiment": score.sentiment,
            }

            try:
                text = generate_why_now(company.ticker, company.name, score_breakdown, data)
                s.add(WhyNow(ticker=company.ticker, text=text, model=settings.model_reasoning))
                s.commit()
                print(f"  ✓ {company.ticker}")
            except Exception as e:
                print(f"  ✗ {company.ticker}: {e}")
                s.rollback()


if __name__ == "__main__":
    run_monday_curation()
