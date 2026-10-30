"""Generate AI pros/cons for the top-N scoring companies."""
from datetime import datetime
from sqlalchemy import select, desc

from app.db import SessionLocal, Score, Company, Financials
from app.agents.pros_cons import generate_pros_cons


def run_pros_cons(top_n: int = 30):
    print(f"[{datetime.utcnow()}] Pros/Cons for top {top_n}")
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

            scores = {
                "growth": score.growth, "profitability": score.profitability,
                "momentum": score.momentum, "valuation": score.valuation,
                "quality": score.quality, "sentiment": score.sentiment,
                "insider": score.insider, "composite": score.composite,
            }
            data = {
                "sector": company.sector,
                "market_cap": company.market_cap,
                "current_price": company.current_price,
                "pct_change_1y": company.pct_change_1y,
                "pe": fin.pe if fin else None,
                "pb": fin.pb if fin else None,
                "roce": fin.roce if fin else None,
            }

            try:
                result = generate_pros_cons(company.name, company.ticker, scores, data)
                company.pros_cons = result
                s.merge(company)
                s.commit()
                print(f"  ✓ {company.ticker}  pros={len(result.get('pros', []))} cons={len(result.get('cons', []))}")
            except Exception as e:
                print(f"  ✗ {company.ticker}: {e}")
                s.rollback()


if __name__ == "__main__":
    import sys
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 30
    run_pros_cons(n)
