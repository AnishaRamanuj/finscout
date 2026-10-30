"""Nightly ingestion + scoring job."""
import time
from datetime import datetime

from app.config import settings
from app.data.tickers import fetch_nse_tickers
from app.data.financials import fetch_company_financials
from app.data.news import fetch_news
from app.scoring.engine import compute_scores
from app.db import SessionLocal, Company, Financials, Score, init_db


def run_nightly(limit: int = 100):
    """
    Pulls top `limit` NSE tickers, fetches financials + news, computes scores.
    Default 100 for safety; raise to 500+ once you've validated it works.
    """
    init_db()

    print(f"[{datetime.utcnow()}] Fetching NSE ticker master...")
    tickers = fetch_nse_tickers().head(limit)
    print(f"  → {len(tickers)} tickers")

    with SessionLocal() as session:
        for i, row in tickers.iterrows():
            try:
                print(f"  [{i + 1}/{len(tickers)}] {row.ticker}")
                data = fetch_company_financials(row.yf_symbol)
                info = data["info"]

                company = session.get(Company, row.ticker) or Company(ticker=row.ticker)
                company.yf_symbol = row.yf_symbol
                company.name = info.get("name") or row.name
                company.sector = info.get("sector")
                company.industry = info.get("industry")
                company.market_cap = info.get("market_cap")
                company.updated_at = datetime.utcnow()
                session.merge(company)

                fin = Financials(
                    ticker=row.ticker,
                    period=datetime.utcnow().strftime("%Y-%m"),
                    pe=info.get("pe"),
                    pb=info.get("pb"),
                    roce=info.get("roce"),
                    raw={"info": info},
                )
                session.add(fin)

                headlines = [n.get("headline", "") for n in fetch_news(row.ticker, days=14)]
                scores_dict = compute_scores(row.ticker, data, headlines)

                score = session.get(Score, row.ticker) or Score(ticker=row.ticker)
                for k, v in scores_dict.items():
                    setattr(score, k, v)
                score.computed_at = datetime.utcnow()
                session.merge(score)

                session.commit()
                time.sleep(0.5)
            except Exception as e:
                print(f"    skip {row.ticker}: {e}")
                session.rollback()

    print(f"[{datetime.utcnow()}] Nightly done.")


if __name__ == "__main__":
    import sys
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 100
    run_nightly(n)
