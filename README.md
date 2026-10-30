# FinScout

AI-powered stock discovery engine. Beats Screener.in by being **proactive** — it tells you *which* companies to look at, with plain-English explanations, instead of making you build queries.

Three tabs:
1. **Discover** — AI-curated weekly picks ranked by a 7-factor composite score
2. **My Portfolio** — upload your holdings, ask the AI questions about them
3. **Deep Dive** — any ticker, full breakdown with AI explanations

---

## Pick Your LLM (one line in `.env`)

FinScout works with two backends. Flip one env var to switch — no code changes needed.

```bash
LLM_PROVIDER=anthropic   # Claude Opus 5.5 + Haiku 5.5 — best quality, ~$28/mo
LLM_PROVIDER=ollama      # Local models via Ollama — free, offline, slower
```

### Option 1 — Claude (default, recommended)

| Model | Where it's used | Why |
|---|---|---|
| **`claude-opus-5-5`** | "Why Now" paragraphs on Discover feed · Portfolio Copilot · Deep Dive summaries | Best model for financial reasoning. Uses **extended thinking** (10K-token budget) to weigh evidence like a real analyst. |
| **`claude-haiku-5-5`** | News sentiment scoring (100s of headlines daily) · One-line ratio explanations | 10× cheaper, 3× faster. Perfect for high-volume work. |

**Monthly cost (personal use, ~30 picks curated weekly):** ~$28, or ~$15 with prompt caching.

### Option 2 — Ollama (free, local, offline)

Install Ollama once:

```bash
# macOS
brew install ollama

# or download the installer from https://ollama.com/download
```

Pull the models (one-time, ~10 GB download total):

```bash
ollama pull qwen2.5:14b     # reasoning model (needs ~10GB RAM)
ollama pull llama3.2:3b     # fast model (needs ~3GB RAM)
```

Keep Ollama running in the background — FinScout talks to it on `http://localhost:11434`.

**If you have less RAM**, use smaller models in `.env`:
- `OLLAMA_REASONING_MODEL=qwen2.5:7b` (needs ~5GB)
- `OLLAMA_FAST_MODEL=llama3.2:1b` (needs ~2GB)

Monthly cost: **$0**. Quality is lower than Claude but fully private.

### Where the LLM is called

- [`app/agents/why_now.py`](app/agents/why_now.py) — reasoning tier
- [`app/agents/copilot.py`](app/agents/copilot.py) — reasoning tier
- [`app/agents/explainer.py`](app/agents/explainer.py) — fast tier
- [`app/scoring/sentiment.py`](app/scoring/sentiment.py) — fast tier

All of them go through [`app/llm/factory.py`](app/llm/factory.py), which picks the provider based on `LLM_PROVIDER` in `.env`.

---

## Project Structure

```
finscout/
├── app/
│   ├── main.py              # Streamlit entry — three tabs
│   ├── config.py            # loads .env
│   ├── db.py                # Postgres + SQLAlchemy models
│   ├── llm/                 # 🆕 LLM provider abstraction
│   │   ├── base.py          #    common interface
│   │   ├── anthropic_provider.py
│   │   ├── ollama_provider.py
│   │   └── factory.py       #    picks provider from .env
│   ├── data/                # yfinance + NSE pullers (all free, no keys)
│   ├── scoring/             # 7-factor composite score engine
│   ├── agents/              # Why-Now, Copilot, Explainer
│   ├── ui/                  # Streamlit pages
│   └── jobs/                # Nightly cron + Monday curation
├── Dockerfile
├── docker-compose.yml
├── requirements.txt
└── .env.example
```

---

## Fastest Path to Real Data (10 minutes)

### Step 1 — Set up `.env`

```bash
cd /Users/anisharamanuj/Downloads/finscout
cp .env.example .env
```

Edit `.env`:
- Set `LLM_PROVIDER=anthropic` (or `ollama` if you want free)
- Paste your Anthropic key (if using Claude) — that's the only key you need
- For `.env` **inside Docker**, keep `POSTGRES_HOST=db`
- For running locally **outside** Docker, change to `POSTGRES_HOST=localhost`

### Step 2 — Start Postgres only (fastest)

```bash
docker compose up -d db
```

Takes ~15 seconds. Postgres is now running on `localhost:5432`.

### Step 3 — Install Python deps locally

```bash
python3.12 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### Step 4 — Pull data for 20 companies (smoke test)

```bash
POSTGRES_HOST=localhost python -m app.jobs.nightly 20
```

Takes ~3–5 minutes. Pulls financials, prices, news, and computes scores for the top 20 NSE companies.

### Step 5 — Generate the AI "Why Now" picks

```bash
POSTGRES_HOST=localhost python -m app.jobs.monday_feed
```

Takes ~1 minute. Claude Opus writes a paragraph for the top 10.

### Step 6 — Launch the UI

```bash
POSTGRES_HOST=localhost streamlit run app/main.py
```

Open **http://localhost:8501** → Discover tab shows your first real picks.

---

## Full Docker Launch (once everything works locally)

```bash
docker compose up --build
```

This starts:
- **finscout-app** → Streamlit UI on http://localhost:8501
- **finscout-scheduler** → runs nightly at 3 AM IST, Monday curation at 6 AM IST
- **finscout-db** → Postgres + pgvector

---

## The 7-Factor Score

Every company gets a 0–100 composite score, weighted blend of:

| Factor | Weight | Signal |
|---|---|---|
| Growth | 25% | Revenue YoY over last 4 quarters |
| Profitability | 20% | ROCE and margin trend |
| Momentum | 20% | 3-month price change |
| Insider | 10% | Promoter buy/sell cluster |
| Sentiment | 10% | LLM reads 30d of news |
| Valuation | 10% | PE vs sector |
| Quality | 5% | Debt/equity, interest coverage |

---

## Why FinScout Beats Screener.in

| Screener.in | FinScout |
|---|---|
| Blank query box — user must know what to search | **AI-curated weekly feed** |
| Shows numbers only | **Every number has an AI explanation** |
| Backward-looking ratios | **News sentiment + momentum + insider signals** |
| No portfolio intelligence | **Portfolio Copilot answers natural questions** |
| Static announcement alerts | **AI anomaly detection** |

---

## Data Sources (all free)

| Source | Covers | Cost |
|---|---|---|
| **yfinance** | Prices, financials, **news headlines** for every public stock | Free, no key |
| **NSE archive CSV** | Full NSE ticker master list | Free, no key |
| **NSE bulk & block deals** | Daily high-conviction Indian trade disclosures (public filings) — powers the **Insider** score factor | Free, no key |
| **SEC EDGAR** (optional, US) | 10-K/10-Q filings | Free, email in User-Agent |

> **No Finnhub, no paid news API.** The only key FinScout needs is your Anthropic key (and even that is optional if you run Ollama).

---

## Roadmap

- [ ] Natural language → SQL screen builder (`"small-caps growing 20%+ with no debt"`)
- [ ] Earnings call transcript ingestion + Q&A
- [ ] Peer comparison with sector median overlays
- [ ] Email digest every Monday morning
- [ ] Mobile-friendly Next.js UI

---

## License

MIT — do what you want.
