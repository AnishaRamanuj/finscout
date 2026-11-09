# FinScout

**AI-powered stock discovery for the Indian market.** FinScout reads the whole NSE universe every night, scores every stock on a 7-factor composite, writes a plain-English "Why Now" for the top picks, and lets you backtest your own calls with a one-click Track Record.

It replaces the blank query box of a traditional screener with a curated feed of the picks you should actually look at this week — each one with the fundamentals, momentum, target and risk already synthesised.

```
┌──────────────────────┐    nightly    ┌─────────────────┐   weekly    ┌──────────────────┐
│  yfinance · NSE API  │ ──────────▶   │  7-factor score │ ──────────▶ │  Picks · Target  │
│  bulk & block deals  │               │  per stock      │             │  Why Now · Risk  │
│  news headlines      │               └─────────────────┘             └──────────────────┘
└──────────────────────┘                                                         │
                                                                                 ▼
                                                                    ┌──────────────────────┐
                                                                    │ 📌 Track → Track     │
                                                                    │ Record (success %)   │
                                                                    └──────────────────────┘
```

MIT-licensed · Python 3.12 · Streamlit UI · Postgres backend · works with Claude *or* Ollama.

---

## The six tabs

| Tab | What it does |
|---|---|
| **This Week's AI Picks** | Weekly curated feed. Every card clears a momentum ≥ 60 gate. One click to 📌 Track a pick. |
| **Find Stocks** | Interactive screener over the whole scored universe. |
| **Rate my CSV** | Drop a Screener.in-style CSV, get a full research report per row. |
| **My Money** | Upload your holdings; AI copilot answers questions like "which of mine is at most risk this month?". |
| **Research a Stock** | Any ticker, full breakdown with AI-written pros and cons. |
| **Track Record** | Every pick you clicked Track lives here. Success rate, days-to-target, mark-to-market, per-pick price chart. |

---

## Quickstart — 3 commands

**With Docker (recommended):**

```bash
cp .env.example .env            # edit: add ANTHROPIC_API_KEY, or set LLM_PROVIDER=ollama
docker compose up --build       # brings up Postgres + app + nightly scheduler
# first load → seed the universe (one-off, ~3 min for 20 tickers):
docker compose exec app python -m app.jobs.nightly 20 nifty50
```

Open **http://localhost:8501**.

**Local (no Docker, Postgres already running):**

```bash
make setup       # creates venv, installs deps
make seed        # pulls 20 tickers + scores them
make ui          # streamlit run app/main.py on :8501
```

---

## Pick your LLM — one line in `.env`

```bash
LLM_PROVIDER=anthropic   # Claude Opus 5.5 + Haiku 5.5 — best quality, ~$28/mo
LLM_PROVIDER=ollama      # Local models — free, offline, slower
```

**Claude** (default). Needs an [Anthropic API key](https://console.anthropic.com).
- `claude-opus-5-5` — extended thinking (10K tokens) writes the "Why Now" paragraphs and Portfolio Copilot answers.
- `claude-haiku-5-5` — scores news sentiment across hundreds of headlines/day. 10× cheaper, 3× faster than Opus.
- Monthly cost: ~$28 for weekly curation of 30 picks, or ~$15 with prompt caching.

**Ollama** (free, local, works offline). Install from [ollama.com/download](https://ollama.com/download), then:

```bash
ollama pull qwen2.5:14b     # reasoning model (~10 GB RAM)
ollama pull llama3.2:3b     # fast model (~3 GB RAM)
```

Smaller alternatives: `qwen2.5:7b` (5 GB) and `llama3.2:1b` (2 GB). Set them in `.env`.

Both providers go through [`app/llm/factory.py`](app/llm/factory.py). Swap by flipping one env var — no code changes.

---

## The 7-factor composite score

Every stock in the universe gets a 0–100 composite. Implemented in [`app/scoring/engine.py`](app/scoring/engine.py).

| Factor | Weight | What it measures | Source |
|---|---|---|---|
| **Growth** | 25% | Revenue YoY from latest quarterly income | yfinance |
| **Profitability** | 20% | ROCE (×3, clamped 0–100) | yfinance |
| **Momentum** | 20% | 3-month price change | yfinance `price_1y` |
| **Insider** | 10% | NSE bulk + block deals, buy-side vs sell-side (block = 1.5×) | NSE archives |
| **Sentiment** | 10% | LLM rates recent headlines 0–100 | Yahoo Finance news + Claude Haiku / Ollama fast |
| **Valuation** | 10% | P/E band, inverted | yfinance |
| **Quality** | 5% | Placeholder for now — see [docs/winner-variables-research.md](docs/winner-variables-research.md) for the Piotroski F-Score plan |

On top of the composite, Discover layers:

- **Verdict** — `Strong Pick` (≥70), `Pick` (≥58), `Hold` (≥48), `Watch` / `Avoid` (below). Watch + Avoid are filtered out.
- **Upside / Target** ([`app/scoring/upside.py`](app/scoring/upside.py)) — fair-PE anchor on the sector median, with growth + quality bumps and a 1-year rally penalty. Clamped to −40% / +150%.
- **Momentum Lite gate ≥ 60** ([`app/scoring/momentum_lite.py`](app/scoring/momentum_lite.py)) — MACD(7,21,9) + MACD(12,26,9) + NSE delivery % + 5/20-day MA cross, each worth 25 points. No pick reaches the board without the chart agreeing.
- **Hidden Gem flag** — strong fundamentals + hasn't rallied yet + decent upside.
- **Final ranking**: `composite + upside × 0.35 + momentum × 0.25`, hidden gems first.

---

## Track Record — the honest scoreboard

Click **📌 Track {TICKER}** on any pick card. FinScout treats that click as "I'm buying this today": records entry price, target, verdict and reasons at that moment.

From then on:
- **Refresh prices** pulls the live quote, appends a daily sample, updates the running peak.
- The instant the live price touches the target, the pick flips to `target_hit`, records `days_to_target` and the realised return.
- Picks that go a full year without hitting target auto-expire.

Track Record aggregates it all:

| Tile | What |
|---|---|
| **Hit rate (closed)** | `target_hit / (target_hit + expired)` |
| **Avg days to target** | On hits only |
| **Avg return on hit** | `(hit_price / entry − 1) × 100`, averaged |
| **Open picks MTM** | Live mark-to-market across open positions |

Each pick has a drill-in with a price chart from entry forward, horizontal reference lines for entry + target, and a vertical marker when target was hit.

Implemented in [`app/scoring/tracker.py`](app/scoring/tracker.py) and [`app/ui/tracker.py`](app/ui/tracker.py).

---

## Project structure

```
finscout/
├── app/
│   ├── main.py              # Streamlit entry — six tabs
│   ├── config.py            # env loader
│   ├── db.py                # SQLAlchemy models
│   ├── llm/                 # provider abstraction (Claude / Ollama)
│   ├── data/                # yfinance + NSE pullers
│   ├── scoring/             # 7-factor + upside + tracker
│   ├── agents/              # Why-Now, Copilot, Explainer
│   ├── ui/                  # one file per tab
│   └── jobs/                # nightly + Monday curation + APScheduler
├── docs/
│   └── winner-variables-research.md   # 85-variable research report
├── tests/
├── Dockerfile
├── docker-compose.yml
├── Makefile
├── requirements.txt
└── .env.example
```

---

## Data sources (all free, no paid APIs)

| Source | What | Cost |
|---|---|---|
| **yfinance** | Prices, financials, news headlines for every public stock | Free, no key |
| **NSE archive CSVs** | Full ticker master + Nifty 50/100/500/midcap/smallcap/microcap lists | Free, no key |
| **NSE bulk & block deals** | Daily high-conviction trade disclosures (powers the Insider factor) | Free, no key |
| **NSE bhavcopy** | Daily delivery % per stock (powers Momentum Lite) | Free, no key |

The only key you need is `ANTHROPIC_API_KEY` — and even that's optional if you run Ollama.

---

## Universes

You choose the universe at ingestion time — [`app/data/universes.py`](app/data/universes.py):

| Universe | Size | How it's resolved |
|---|---|---|
| `nifty50` | 50 | Hardcoded constituents |
| `nifty100` | 100 | NIFTY 50 + NIFTY NEXT 50 |
| `nifty500` | ~500 | Live NSE index CSV |
| `midcap150` / `smallcap250` / `microcap250` | ~150/250/250 | Live NSE index CSV |
| `totalmarket` | ~750 | Nifty Total Market Index |
| `all` | ~1,700 | Full NSE master, no filter |

Run: `python -m app.jobs.nightly <limit> <universe>` — e.g. `python -m app.jobs.nightly 500 nifty500`.

---

## Scheduling

[`app/jobs/scheduler.py`](app/jobs/scheduler.py) uses APScheduler with `Asia/Kolkata` timezone:

- **Nightly** — 03:00 IST, pulls 100 tickers from `nifty100`.
- **Monday curation** — 06:00 IST, generates a "Why Now" paragraph for the top 10 scoring companies.

Change the schedule or universe in `app/jobs/scheduler.py`.

---

## Full Docker launch

```bash
docker compose up --build
```

Starts three containers:
- `finscout-app` — Streamlit UI on http://localhost:8501
- `finscout-scheduler` — APScheduler running nightly + Monday jobs
- `finscout-db` — Postgres 16 + pgvector

Stop with `docker compose down` (data persists in the `pgdata` volume). To nuke everything: `docker compose down -v`.

---

## Roadmap — see [docs/winner-variables-research.md](docs/winner-variables-research.md) for the detail

Top 3 adds coming next:

1. **Piotroski F-Score** — real quality signal to replace the constant-60 placeholder.
2. **CFO / EBITDA ratio** — Marcellus-style forensic flag for Indian accounting manipulation.
3. **Promoter Pledge %** — crash-risk predictor from Screener.in.

Further out: earnings-estimate revisions, 12-1 month academic momentum, FCF yield, Altman Z-score, Beneish M-score, FII/DII shareholding deltas. ~85 variables ranked in the research doc.

---

## License

MIT — see [LICENSE](LICENSE). Do what you want, no warranty.

---

Built by [Anisha Ramanuj](https://github.com/AnishaRamanuj).
