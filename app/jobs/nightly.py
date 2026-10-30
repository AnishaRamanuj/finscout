"""Nightly ingestion + scoring job."""
import time
from datetime import datetime

from app.config import settings
from app.data.tickers import fetch_nse_tickers
from app.data.financials import fetch_company_financials
from app.data.news import fetch_news
from app.data.nse_trades import fetch_trades_for_ticker
from app.data.universes import get_universe
from app.scoring.engine import compute_scores
from app.db import SessionLocal, Company, Financials, Score, init_db


def run_nightly(limit: int = 100, universe: str = "nifty50"):
    """
    Pulls `limit` NSE tickers from the chosen universe, fetches financials +
    news + bulk/block deals, computes scores.

    universe: 'nifty50' (default) | 'nifty100' | 'all'
    """
    init_db()

    print(f"[{datetime.utcnow()}] Fetching NSE ticker master...")
    tickers = fetch_nse_tickers()
    allowed = get_universe(universe)
    if allowed:
        tickers = tickers[tickers["ticker"].isin(allowed)].reset_index(drop=True)
        print(f"  → filtered to universe '{universe}' ({len(tickers)} available)")
    tickers = tickers.head(limit)
    print(f"  → ingesting {len(tickers)} tickers")

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

                headlines = [n.get("headline", "") for n in fetch_news(row.yf_symbol, days=14)]
                nse_trades = fetch_trades_for_ticker(row.ticker)
                scores_dict = compute_scores(row.ticker, data, headlines, nse_trades)

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
    uni = sys.argv[2] if len(sys.argv) > 2 else "nifty50"
    run_nightly(n, uni)
