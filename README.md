# FinScout

AI-powered stock discovery engine. Beats Screener.in by being proactive — it tells you *which* companies to look at, with plain-English explanations, instead of making you build queries.

Three tabs:
1. **Discover** — AI-curated weekly picks ranked by a 7-factor composite score
2. **My Portfolio** — upload your holdings, ask Claude questions about them
3. **Deep Dive** — any ticker, full breakdown with AI explanations

---

## How AI Is Used

| Model | Where it's used | Why this model |
|---|---|---|
| **`claude-opus-5-5`** (reasoning) | • "Why Now" paragraphs on the Discover feed<br>• Portfolio Copilot (`"which holding looks weakest?"`)<br>• Deep Dive AI summaries | Best Claude for financial reasoning. Uses **extended thinking** (10K-token budget) so it can actually weigh evidence like a human analyst. ~$15/M input, ~$75/M output. |
| **`claude-haiku-5-5`** (fast + cheap) | • News sentiment scoring (500+ companies × daily)<br>• One-line ratio explanations<br>• Light triage tasks | 10x cheaper, 3x faster. Perfect for high-volume classification where you don't need deep reasoning. |

### Where Claude is called

- `app/agents/why_now.py` → Opus 5.5 generates the "Why Now" blurb per pick
- `app/agents/copilot.py` → Opus 5.5 answers portfolio questions with extended thinking
- `app/agents/explainer.py` → Haiku 5.5 explains any ratio in one sentence
- `app/scoring/sentiment.py` → Haiku 5.5 rates headlines 0–100 at scale

### Cost per month (personal use, ~30 picks curated weekly)

| Item | Monthly |
|---|---|
| Opus 5.5 (Why Now + Copilot) | ~$20 |
| Haiku 5.5 (sentiment × 100 companies × 30 days) | ~$8 |
| Everything else (yfinance, Finnhub free, NSE data) | $0 |
| **Total** | **~$28/month** |

Turn on prompt caching to drop this to **~$15/month**.

---

## Project Structure

```
finscout/
├── app/
│   ├── main.py              # Streamlit entry — three tabs
│   ├── config.py            # loads .env
│   ├── db.py                # Postgres + SQLAlchemy models
│   ├── data/                # yfinance, Finnhub, NSE pullers
│   ├── scoring/             # 7-factor composite score engine
│   ├── agents/              # Claude agents (why_now, copilot, explainer)
│   ├── ui/                  # Streamlit pages (discover, portfolio, deep_dive)
│   └── jobs/                # Nightly cron + Monday feed curation
├── Dockerfile
├── docker-compose.yml       # app + scheduler + Postgres
├── requirements.txt
└── .env.example
```

---

## Setup (3 commands)

### 1. Clone & configure

```bash
cp .env.example .env
# edit .env — paste your Anthropic + Finnhub keys
```

### 2. Launch everything with Docker

```bash
docker compose up --build
```

This starts:
- **finscout-app** → Streamlit UI on http://localhost:8501
- **finscout-scheduler** → runs nightly ingest + Monday curation
- **finscout-db** → Postgres + pgvector

### 3. Prime the database (one-time)

In a second terminal:

```bash
docker compose exec app python -m app.jobs.nightly 50
```

This pulls the top 50 NSE companies, scores them, and populates the DB. Takes ~15 minutes. Bump to `500` once you've validated.

Then generate Monday picks:

```bash
docker compose exec app python -m app.jobs.monday_feed
```

Open http://localhost:8501 — the Discover tab is now populated.

---

## The 7-Factor Score

Every company gets a 0–100 composite score, weighted blend of:

| Factor | Weight | Signal |
|---|---|---|
| Growth | 25% | Revenue YoY over last 4 quarters |
| Profitability | 20% | ROCE and margin trend |
| Momentum | 20% | 3-month price change |
| Insider | 10% | Promoter buy/sell cluster |
| Sentiment | 10% | Haiku 5.5 reads 30d of news |
| Valuation | 10% | PE vs sector |
| Quality | 5% | Debt/equity, interest coverage |

The composite is the single number users see on the Discover feed.

---

## Why FinScout Beats Screener.in

| Screener.in | FinScout |
|---|---|
| Blank query box — user must know what to search | **AI-curated weekly feed** |
| Shows numbers only | **Every number has a 1-sentence AI explanation** |
| Backward-looking ratios | **Includes news sentiment + momentum + insider signals** |
| No portfolio intelligence | **Portfolio Copilot answers natural questions** |
| Static announcement alerts | **AI anomaly detection** (margin compression, accruals, etc.) |

---

## Data Sources (all free)

| Source | Covers | Cost |
|---|---|---|
| **yfinance** | Prices, financials, insider trades for every public stock globally | Free |
| **NSE archive CSV** | Full NSE ticker master list | Free |
| **Finnhub** | Company news (90 days back) | Free: 60 calls/min |
| **SEC EDGAR** (optional, US stocks) | 10-K/10-Q filings | Free |

---

## Development

### Run without Docker

```bash
python3.12 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
# Start Postgres however you like, then:
streamlit run app/main.py
```

### Run just the nightly ingestion

```bash
python -m app.jobs.nightly 20   # top 20 companies, quick smoke test
```

### Run Monday curation

```bash
python -m app.jobs.monday_feed
```

---

## Roadmap

- [ ] Natural language → SQL screen builder (`"small-caps growing 20%+ with no debt"`)
- [ ] Earnings call transcript ingestion + Q&A
- [ ] Peer comparison with sector median overlays
- [ ] Scenario simulator (`"if rates drop 50bp, which of my holdings benefit?"`)
- [ ] Email digest every Monday morning
- [ ] Mobile-friendly Next.js replacement for Streamlit UI

---

## License

MIT — do what you want.
