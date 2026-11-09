# What Makes a Stock Winner — Variable Research for FinScout

> Scope: a synthesis of academic factor research, practitioner frameworks (Piotroski, Greenblatt, O'Neil, Lynch, Novy-Marx, AQR), Indian-market practitioners (Marcellus, Safal Niveshak, Screener.in multibagger screens) and alternative-data sources, framed against what FinScout already computes. The output is an opinionated master list of **~85 variables**, ranked by expected lift ÷ build cost for the Indian universe.

---

## TL;DR

FinScout today scores on **14 variables**: revenue YoY, ROCE, PE, sector-median PE, 1y price change, 3m return, 5/20-day MA, two MACDs, NSE delivery %, bulk/block deal direction, LLM news sentiment, a constant-60 quality placeholder, and a composite blend. That's a respectable momentum + value + fundamentals base, but it is missing most of the **quality, cash-flow, earnings-revision, positioning and governance** signals that the academic literature and Indian multibagger research credit as the strongest long-horizon predictors.

The **highest-leverage adds** are, in order: Piotroski F-Score, Cash-Flow-from-Operations / EBITDA, Promoter Pledge %, earnings-estimate revisions, 12-1 month momentum (academic-standard), gross profitability (GP/A), FCF yield, 52-week-high proximity, Altman Z-score, and Beneish M-score. Every one of these can be computed from data you can already pull — Screener.in, NSE bhavcopy, or yfinance fundamentals — and together they should lift pick accuracy by multiples more than another MACD variant.

The **biggest single gap** is **cash-flow quality**: FinScout has no CFO/EBITDA, no accrual ratio, no FCF, no debt-service coverage and no promoter-pledge check. For the Indian market in particular, that's the gap between "picked a compounder" and "picked a story that imploded at the next results."

---

## Section A — Top 20 Highest-Leverage Adds for FinScout

Ranked by `(expected accuracy lift) ÷ (implementation effort)`. Each lift estimate is directional, not a backtested figure.

### 1. Piotroski F-Score (9-point composite)
**Why:** Piotroski (2000) showed that combining a value filter (low P/B) with a high F-Score produced up to 7.5% annual outperformance over 20 years. The nine binary tests cover profitability (positive NI, positive CFO, rising ROA, CFO > NI), leverage/liquidity (falling long-term debt, rising current ratio, no new share issuance), and operating efficiency (rising gross margin, rising asset turnover). It is the single most-cited quality composite in the literature. **Source: yfinance + Screener.in CSV parse. Effort: medium. Already derivable from data you pull nightly.** [Piotroski F-Score guide](https://www.quant-investing.com/blog/piotroski-f-score-complete-guide), [FairPriceIndex 9-point test](https://www.fairpriceindex.com/education/piotroski-f-score)

### 2. Cash-Flow-from-Operations / EBITDA
**Why:** Marcellus's Consistent Compounders framework uses CFO/EBITDA as a forensic flag — a persistent gap between reported profit and real cash generation is the single biggest early warning for Indian accounting manipulation (Vakrangee, Manpasand Beverages, DHFL all failed this years before blowing up). A ratio below ~0.8 sustained for 2+ years is a red flag. **Source: yfinance cash-flow statement. Effort: easy.** [Marcellus CCP deck](https://marcellus.in/wp-content/uploads/product-decks/ccp-regular.pdf)

### 3. Promoter Pledge %
**Why:** Kalia (2024) and Chauhan et al. (2021) both document that high promoter-pledge is strongly associated with future crash risk and lower firm value in Indian firms. Behera & Dora (IIT KGP, 2026) find pledging firms carry significantly higher downside risk. Practitioners treat pledging > 25% of promoter holding as a hard disqualifier. **Source: BSE/NSE corporate filings, Screener.in field. Effort: easy.** [Kalia JAMR 2024](https://ideas.repec.org/a/eme/jamrpp/jamr-01-2023-0003.html), [Chauhan et al. Financial Management 2021](https://econpapers.repec.org/RePEc:bla:finmgt:v:50:y:2021:i:1:p:261-280)

### 4. Analyst Earnings-Estimate Revisions (Up-vs-Down ratio, 60d)
**Why:** The earnings-revision factor is one of the most persistent documented anomalies (post-earnings-announcement drift / Bernard & Thomas, 1989). Rising consensus estimates are the clearest version of "a company is beating expectations" — stronger than the earnings surprise itself on some samples. **Source: Trendlyne/Tickertape APIs (paid) or scrape MoneyControl consensus. Effort: medium.** [PEAD overview Wikipedia](https://en.wikipedia.org/wiki/Post%E2%80%93earnings-announcement_drift)

### 5. 12-1 Month Momentum (academic standard)
**Why:** FinScout's momentum is a 3-month return and a MACD overlay. The academic-standard momentum factor is the trailing 12-month return **excluding the most recent month** (Jegadeesh & Titman 1993, replicated in India, EU, and 23 other markets by Rouwenhorst). Skipping the most recent month separates momentum from short-term mean-reversion. **Source: already have `price_1y`. Effort: 10 lines of code.** [Jegadeesh & Titman JF 1993 overview](https://alphaarchitect.com/2014/11/the-secret-to-momentum-is-the-52-week-high/)

### 6. Gross Profitability (GP/A)
**Why:** Novy-Marx (2013) showed gross profits / total assets predicts the cross-section of returns as well as book-to-market. It is the cleanest profitability measure because accrual-laden items below the gross-profit line (SG&A, taxes, interest) are more polluted. The "quality placeholder" of 60 in FinScout should be replaced with this. **Source: yfinance income + balance sheet. Effort: easy.** [Novy-Marx JFE 2013](https://www.nber.org/papers/w15940)

### 7. Free Cash Flow Yield (FCF/EV or FCF/Mcap)
**Why:** Vanguard, O'Shaughnessy and VictoryShares all identify FCF yield as among the strongest long-horizon value signals, with FCF/EV often outperforming E/P in multi-decade backtests. PE ignores reinvestment; FCF yield rewards companies that generate real cash. **Source: yfinance cash-flow statement. Effort: easy.** [VictoryShares FCF/EV 31-year study (promotional)](https://www.etftrends.com/?p=529956)

### 8. 52-Week High Proximity
**Why:** George & Hwang (JF 2004) showed that `current price / 52w high` is a better momentum predictor than past returns, because it captures underreaction to news. Unlike 3-6 month momentum, the 52w-high effect does not reverse in the long run. **Source: already computable from `price_1y`. Effort: 5 lines.** [George & Hwang 52-Week High paper summary](https://alphaarchitect.com/2014/11/the-secret-to-momentum-is-the-52-week-high/)

### 9. Altman Z-Score (bankruptcy risk gate)
**Why:** Altman (1968) defined a 5-variable discriminant for bankruptcy risk: working capital / TA, retained earnings / TA, EBIT / TA, market-cap / total liabilities, sales / TA. Z < 1.8 = distress; Z > 2.99 = safe. Simple, well-validated, and critical as a **gate** — you don't want to recommend stocks sliding toward Vedanta-like events. **Source: yfinance + Screener fundamentals. Effort: easy.** [Beneish/Altman relationship paper](https://jbsd.umt.edu.my/wp-content/uploads/2024/12/2-THE-RELATIONSHIP-OF-Z-SCORE-AND-BENEISH-M-SCORE-1.pdf)

### 10. Beneish M-Score (earnings manipulation flag)
**Why:** Beneish (1999) built an 8-variable probit model that flagged roughly 75% of SEC enforcement cases in its development sample. The 8 inputs (DSRI, GMI, AQI, SGI, DEPI, SGAI, TATA, LVGI) each compare current-year ratios to prior-year ratios. Score > -1.78 → possible manipulation. Critical as a **red-flag gate** on the Indian universe where mid-cap earnings quality can be fragile. **Source: yfinance fundamentals + lag. Effort: medium.** [Beneish M-score wikipedia](https://www.wikipedia.org/wiki/Beneish_M-score)

### 11. EV/EBITDA (capital-structure-neutral value)
**Why:** EV/EBITDA is the standard private-equity and analyst metric because it strips out capital-structure differences. For Indian capex-heavy sectors (cement, steel, infrastructure), PE is distorted by leverage, but EV/EBITDA is not. Multiple backtests show EV/EBITDA outperforms PE as a value sorting variable. **Source: yfinance `info.enterpriseToEbitda`. Effort: trivial.** [EV/EBITDA factor summary](https://www.scribd.com/document/477657060/tev-to-ebitda-research-pdf)

### 12. 3-Year Sales CAGR + 3-Year EPS CAGR
**Why:** FinScout's growth looks at YoY only, which is noisy for cyclicals and one-off boosts. Multi-year compound growth is the Marcellus "consistent compounder" filter (10y of double-digit sales growth + RoCE > CoC = ~10% of BSE500). Combining 3y sales growth > 15% + 3y EPS growth > 15% is the most-used Indian multibagger screen. **Source: yfinance / Screener. Effort: easy.** [Marcellus CCP](https://marcellus.in/wp-content/uploads/product-decks/ccp-regular.pdf)

### 13. Interest Coverage Ratio
**Why:** EBIT / Interest Expense. Below 2 = fragile; below 1 = covenant-breach territory. Blog multibagger screens consistently use ICR > 5 as a safety floor. Simple, powerful, and matches Marcellus's Little Champs small-cap screen. **Source: yfinance. Effort: trivial.**

### 14. Debt / Equity Ratio (with sector adjustment)
**Why:** Universally used in Indian multibagger screens (D/E < 0.5 for most industries). The sector adjustment matters — NBFCs run at 5-7x and are fine, cement should be < 1x. Combine with ICR for a solvency gate. **Source: yfinance. Effort: trivial.**

### 15. ROCE × 3Y Consistency (not just latest)
**Why:** FinScout's profitability score reads only the latest ROCE. The Marcellus thesis is that *consistency* — ROCE > cost-of-capital in every one of the last 10 years — is what separates compounders from one-year wonders. At minimum, require ROCE > 15% in **each** of the last 3 years, not just the trailing one. **Source: yfinance historical statements. Effort: easy.**

### 16. FII + DII Shareholding Change (QoQ delta)
**Why:** Acharya et al. (IGC 2015) found FII flows cause price pressure on Indian stocks; shareholding-pattern deltas are a leading indicator of institutional conviction. Rising FII+DII share over 2-3 quarters while promoters hold flat = positive. The opposite (both reducing) = red flag. **Source: NSE/BSE quarterly shareholding filings. Effort: medium (needs scrape).** [Acharya et al. IGC 2015](https://www.theigc.org/sites/default/files/2015/08/Acharya-et-al-2015-Working-paper-1.pdf)

### 17. Accrual Ratio (Sloan's Earnings Quality)
**Why:** Sloan (1996) showed that firms with high accruals (reported profits not backed by cash) underperform firms with low accruals by ~10% a year. Accruals = (NI − CFO) / Total Assets. Lower is better. Replicated globally including India. **Source: yfinance. Effort: easy.** [Sloan 1996 overview](https://kailashconcepts.com/?p=236160)

### 18. Insider Buying Cluster Signal (vs single trades)
**Why:** Cohen, Malloy & Pomorski (JF 2012) show that **clustered** insider purchases — 3+ insiders buying within consecutive days — predict ~2× the abnormal returns of single trades. FinScout's current bulk/block deal score is a close cousin but doesn't separate the cluster vs single pattern. **Source: BSE insider-trading disclosures. Effort: medium.** [Davenport summary of Cohen-Malloy-Pomorski](https://www.investdavenport.com/?p=20478)

### 19. Idiosyncratic Volatility (3m rolling σ of residuals vs Nifty)
**Why:** Frazzini & Pedersen's Betting-Against-Beta (2014) shows low-beta / low-vol stocks earn higher risk-adjusted returns than high-beta stocks across 20 markets including India. A low-vol tilt reduces drawdown without proportionally reducing upside. **Source: computable from `price_1y` + Nifty series. Effort: easy.** [BAB summary](https://alphaarchitect.com/betting-against-beta-bab-construction/)

### 20. Earnings Announcement Surprise + Drift (post-results window)
**Why:** PEAD (Ball & Brown 1968, Bernard & Thomas 1989) is one of the most persistent documented anomalies. In practice: measure reported EPS vs consensus, and treat the 60 trading days post-announcement as a "buy the beat, sell the miss" window for your momentum score. **Source: MoneyControl consensus scrape + corporate results calendar. Effort: medium.** [PEAD summary](https://en.wikipedia.org/wiki/Post%E2%80%93earnings-announcement_drift)

---

## Section B — Five Trap Variables (sound smart, add noise)

1. **Short-term RSI < 30 as a buy signal in trending markets.** The Wilmott forum consensus and multiple backtests show mean-reversion setups (RSI oversold + Bollinger lower band) lose money in trending regimes. In a strong uptrend, RSI can sit at 70+ for weeks, and in a downtrend RSI 20 is not a bottom — it's a mid-slide. Only use with an ADX > 25 trend filter, or skip. [Wilmott thread](https://forum.wilmott.com/viewtopic.php?p=555401)

2. **Dividend yield alone.** Yield-hunting without quality is a classic trap. Many high-yield Indian PSUs (Coal India in 2015-20, select oil marketers) stayed cheap because the business was declining. Use dividend only as a **tiebreaker** on quality-passing stocks.

3. **P/E < 10 "deep value" with no quality filter.** Novy-Marx's work explicitly shows that profitability and value interact — cheap stocks without quality underperform cheap stocks with quality. A naive "low PE" screen in India dredges up perennially-cheap microcaps with governance issues.

4. **Google Trends search volume.** Loughlin & Harnisch and a 2025 MDPI study both find Google Trends is **not** statistically significant for predicting stock returns once you control for news sentiment and Twitter. It looks like a clever alt-data signal; it isn't. [MDPI big-tech sentiment study](https://www.mdpi.com/1911-8074/18/12/660)

5. **Raw book-to-market (P/B) for asset-light businesses.** P/B works for banks and asset-heavy manufacturers but is near-meaningless for IT services, consumer brands and SaaS where the real assets are off-balance-sheet. Use industry-adjusted P/B or skip for these sectors.

---

## Section C — Open Research Questions to A/B Test

1. **Earnings-revision factor vs raw YoY growth on the Indian universe.** US evidence favors revisions; for India (less analyst coverage, more small-cap retail) this may reverse.

2. **Does Piotroski F-score work on the Indian non-value universe?** Piotroski's original test was on cheap stocks (low P/B). Many Indian compounders trade at 40-80x PE — does the F-score add anything there, or does it over-filter?

3. **12-1 vs 6-1 vs 9-1 momentum formation on Indian mid-caps.** Mid-cap liquidity and promoter-driven ownership create different momentum dynamics than US large caps.

4. **Does promoter-buying signal beat insider-trading signals in India?** US research is on executive insider trades; Indian promoter activity (via creeping acquisition, open-market purchases) may have different predictive power.

5. **Does sector-relative-strength as a gate improve pick accuracy more than sector-relative-strength as a scoring input?** Current FinScout doesn't use sector RS at all.

6. **LLM news sentiment vs analyst-report sentiment vs earnings-call transcript sentiment.** Three different corpora with different signal half-lives.

7. **Does the bulk/block deal "insider" score work better scaled by float (not by raw count)?** A 50k-share block in Reliance is noise; in a 200cr micro-cap it's a signal.

---

## Section D — Master Variable Taxonomy (~85 variables)

Legend: **[IN]** already in FinScout · **[EZ]** easy add (existing data) · **[MED]** medium (new scrape/compute) · **[HARD]** hard (paid data / new infra).

### D1. Quality / Earnings Durability

- **ROCE (latest)** — EBIT / (Equity + Debt − Cash). **[IN]**
- **ROCE 3y mean, min, slope** — consistency matters more than peak. **[EZ]**
- **ROE (latest and 3y)** — return on shareholders' equity. **[EZ]**
- **Gross Profitability (GP/A)** — Novy-Marx's cleanest profitability signal. **[EZ]** [Novy-Marx](https://www.nber.org/papers/w15940)
- **Operating margin (and 3y trend)** — margin expansion is a strong compounder signal.
- **Net margin (and sector-relative)** — industry-adjusted.
- **CFO / EBITDA ratio** — the Marcellus forensic flag. **[EZ]**
- **CFO / Net Income** — proxies accrual quality from cash perspective.
- **Accrual Ratio (Sloan)** — (NI − CFO) / Total Assets. **[EZ]** [Sloan 1996](https://kailashconcepts.com/?p=236160)
- **Cash Conversion Cycle (DSO + DIO − DPO)** — working-capital efficiency.
- **Working Capital / Sales** — companies that grow revenue without proportional WC expansion are high quality.
- **Free Cash Flow margin** — FCF / Sales.
- **Piotroski F-Score (9 binary tests)** — the quality composite. **[EZ]** [Piotroski guide](https://www.quant-investing.com/blog/piotroski-f-score-complete-guide)
- **Quality-Minus-Junk composite (AQR)** — profitability + growth + safety + payout combined. **[MED]** [QMJ paper](https://images.aqr.com/-/media/AQR/Documents/Insights/Working-Papers/Quality-Minus-Junk.pdf)
- **Return on Invested Capital (ROIC)** — Greenblatt's version: EBIT / (NWC + Net Fixed Assets).

### D2. Growth (beyond raw YoY)

- **Revenue YoY (1q)** — **[IN]** (current growth signal).
- **Revenue 3y CAGR** — smooths quarterly noise. **[EZ]**
- **Revenue 5y CAGR** — Marcellus compounder filter.
- **EPS YoY** — directly tied to shareholder returns.
- **EPS 3y CAGR**.
- **EPS acceleration** — is YoY growth faster than 3y CAGR? (a positive second derivative).
- **Forward estimates revision ratio** — analyst upgrades − downgrades, 60/90d. **[MED]**
- **Current quarter EPS growth (CAN SLIM "C")** — O'Neil requires ≥18-25%.
- **Annual EPS growth streak (CAN SLIM "A")** — ≥5 years of growth.
- **Sales per share growth** — dilution-adjusted.
- **Order book / backlog growth** — for capital-goods / defense / infra.
- **Same-store-sales growth (SSSG)** — for retail (DMart, Trent).
- **Management guidance vs actual beat ratio** — a quality-of-forecast signal.

### D3. Value

- **P/E (TTM)** — **[IN]**.
- **Forward P/E (on consensus EPS)** — **[MED]**.
- **PE vs sector median** — **[IN]**.
- **PE vs own 5y median (Shiller-style for single stock)** — "is this stock cheap vs its own history?"
- **PEG ratio (Lynch)** — P/E ÷ EPS growth rate; < 1 attractive, < 1.5 reasonable GARP. [Validea GARP](https://blog.validea.com/?p=7627)
- **EV/EBITDA** — capital-structure-neutral value. **[EZ]**
- **EV/EBIT** — Greenblatt's earnings yield. **[EZ]** [Greenblatt](https://reasonabledeviations.com/2020/06/08/greenblatt-magic-formula/)
- **EV/Sales** — useful for non-profitable growers (new-economy, SaaS).
- **FCF Yield (FCF / Market Cap)** — Lynch's > 35% rule.
- **FCF/EV** — VictoryShares reports best 31y Sharpe on this.
- **Book-to-Market** — the original Fama-French value factor.
- **Dividend Yield** — tiebreaker only.
- **Yield Gap (Earnings yield − 10y G-Sec)** — proxies vs risk-free rate in India.
- **Magic Formula rank (combined EBIT/EV + ROIC)** — Greenblatt composite. **[EZ]**

### D4. Momentum

- **3m return** — **[IN]**.
- **12-1 momentum (12m return skipping latest month)** — academic standard. **[EZ]** [Jegadeesh-Titman](https://alphaarchitect.com/2014/11/the-secret-to-momentum-is-the-52-week-high/)
- **6-1 momentum** — shorter-horizon variant.
- **52-week-high proximity (price / 52w high)** — George-Hwang. **[EZ]**
- **Distance from 200-day SMA** — classic trend-follow filter.
- **5-day / 20-day MA cross** — **[IN]**.
- **MACD (7,21,9)** — **[IN]**.
- **MACD (12,26,9)** — **[IN]**.
- **Risk-adjusted momentum** — 12-1 return ÷ realized volatility.
- **Earnings momentum** — successive quarterly EPS beats.
- **Sector-relative momentum (RS vs its Nifty sector)** — are we picking the leaders within a sector?
- **Idiosyncratic momentum** — return residual after Fama-French factors stripped.

### D5. Low-Vol / Risk

- **Beta vs Nifty (3y weekly)** — Betting-Against-Beta anomaly. **[EZ]**
- **Idiosyncratic volatility (3m rolling σ of residuals)** — low-vol anomaly. **[EZ]**
- **Max drawdown (1y, 3y)** — behavioral tolerance signal.
- **Sortino ratio** — downside-only vol-adjusted return.
- **Downside deviation (σ of negative daily returns)**.
- **Beta-adjusted return** — compare realized return vs expected from CAPM.

### D6. Technical Overlays Beyond MACD

- **RSI(14)** — only usable with ADX trend filter.
- **ADX(14)** — trend-strength gate, filters RSI/BB traps.
- **Bollinger %B** — standardized position in bands; use only with ADX.
- **OBV (On-Balance Volume)** — accumulation/distribution.
- **VWAP vs close** — institutional-conviction proxy.
- **A/D line (Accumulation/Distribution)** — Chaikin volume-weighted.
- **Ichimoku cloud position** — trend + support/resistance combined.
- **ATR(14)** — volatility-based position sizing input.

### D7. Flow / Positioning

- **FII shareholding Δ QoQ** — institutional conviction. **[MED]** [Acharya 2015](https://www.theigc.org/sites/default/files/2015/08/Acharya-et-al-2015-Working-paper-1.pdf)
- **DII shareholding Δ QoQ** — mutual funds + insurance.
- **Promoter shareholding Δ** — creeping acquisition signal.
- **Promoter pledge %** — crash-risk gate. **[EZ]** [Kalia 2024](https://ideas.repec.org/a/eme/jamrpp/jamr-01-2023-0003.html)
- **Promoter buying (open market, last 2q)** — strongest conviction signal.
- **Bulk/block deal direction** — **[IN]**.
- **Bulk/block ratio to free float** — size-scaled; critical for small-caps.
- **Short interest % of float** — low in India but check where available.
- **Put/Call open interest ratio (stock options)** — Pan & Poteshman predictive at 1-3m.
- **Options skew (25-delta put vs call IV)** — crash-risk proxy.
- **Delivery %** — **[IN]**.
- **Delivery % slope (5-10 day)** — **[IN]**.

### D8. Sentiment (beyond LLM headlines)

- **LLM news sentiment (current)** — **[IN]**.
- **News story count velocity** — is coverage accelerating?
- **Analyst consensus change (upgrades − downgrades, 30/60d)** — **[MED]**.
- **Analyst target-price Δ** — revisions direction.
- **Estimate dispersion (σ of analyst estimates / mean)** — disagreement predicts volatility.
- **Earnings-call transcript sentiment** — management tone via LLM.
- **StockTwits message volume + sentiment** — mixed US evidence; untested on India tickers.
- **Reddit post count (r/IndianStockMarket, r/IndiaInvestments)** — retail interest proxy.
- **Google Trends** — **[TRAP, see §B]**.

### D9. Corporate Actions

- **Buyback announcement (trailing 1y)** — strong signal when at a premium to CMP.
- **Dividend initiation or raise** — Lintner-style quality signal.
- **Insider open-market buying (count, cluster) last 90d** — Cohen-Malloy-Pomorski. **[MED]** [paper summary](https://www.investdavenport.com/?p=20478)
- **Stock split / bonus** — mostly neutral in modern markets.
- **QIP / preferential issue in last 12m** — dilution penalty.
- **Rights issue** — distress signal in India mid-caps.

### D10. Governance / Earnings Quality

- **Beneish M-Score** — manipulation flag. **[EZ]** [wikipedia](https://www.wikipedia.org/wiki/Beneish_M-score)
- **Altman Z-Score** — distress flag. **[EZ]**
- **Auditor change in last 2y** — big red flag in India (DHFL pattern).
- **Related-party transactions (% of revenue)** — governance risk.
- **CEO tenure, CFO tenure** — stability proxy.
- **Effective tax rate vs statutory rate** — too low = quality-of-earnings concern.
- **Days Sales Outstanding (DSO) trend** — rising receivables = potential channel stuffing.
- **Contingent liabilities / net worth** — hidden off-balance-sheet risk.

### D11. Leverage / Solvency

- **Debt/Equity (with sector adjustment)**. **[EZ]**
- **Net debt / EBITDA** — "how many years of EBITDA to pay off debt".
- **Interest Coverage Ratio (EBIT / Interest)** — > 5 for safety.
- **Debt-Service Coverage Ratio** — comprehensive solvency.
- **Current ratio** — Piotroski F-score component.
- **Quick ratio** — liquidity ex-inventory.

### D12. Macro / Sector

- **Sector relative strength (sector index / Nifty)** — are we buying in a leading sector? [Tapetide sector rotation](https://tapetide.com/insight/sector-rotation?benchmark=nifty-50)
- **Beta to 10y G-Sec yield** — interest-rate sensitivity (NBFCs, real estate).
- **FX sensitivity (INR/USD beta)** — material for IT services, pharma exporters.
- **Commodity exposure proxies (oil, copper, steel)** — relevant for sector-specific plays.
- **Nifty regime filter (above/below 200DMA)** — CAN SLIM "M" gate.

### D13. Alt-Data (optional, higher effort)

- **LinkedIn hiring velocity (job postings count Δ)** — signal is real but non-trivial to scrape. **[HARD]** [LinkUp jobs alpha claims](https://www.linkup.com/use-cases/job-listings-are-untapped-sources-of-alpha)
- **App download velocity (where business is app-driven)** — Zomato, Paytm, Nykaa style.
- **Patent filings count YoY** — innovation proxy for pharma, IT.
- **Glassdoor / AmbitionBox rating trend** — employee-satisfaction proxy.
- **Satellite imagery / traffic counts** — expensive, not worth it for FinScout's budget.
- **Credit card spend data (where observable)** — US-mostly, limited India use.

### D14. India-Specific

- **Promoter pledge %** — **(see §A #3)**.
- **FII vs DII crossover signal (both buying = max conviction)** — Indian flow structure.
- **Shareholding pattern filing Δ around results** — Indian regulatory cadence.
- **SEBI disclosure flags (show-cause notices, settlements)** — hard governance check.
- **IndAS vs Ind-AS restatement delta** — one-time quality signals.
- **DRHP red flags for new IPOs** — related-party sales, auditor changes before listing.
- **Mutual fund scheme ownership concentration** — single-fund >5% = liquidity risk.
- **Nifty index inclusion/exclusion calendar** — rebalance flows predict short-term moves.
- **Index weight vs free-float cap** — passive-flow signal.
- **Grey-market premium (IPOs, pre-listing)** — sentiment proxy.

---

## Section E — Proposed Replacement for the "Quality 5%" Placeholder

FinScout today sets `quality = 60.0` as a constant. Replace with a **composite quality score** combining:

- Piotroski F-Score (normalized to 0-100: F/9 × 100).  
- ROCE 3y mean (0-100 scaled).  
- CFO/EBITDA ratio (floor 0.6, cap 1.0 → scaled).  
- Gross Profitability (GP/A) decile within sector.  
- Piotroski F ≥ 6 **AND** Altman Z ≥ 2.99 as a hard gate (if fails → quality capped at 40).

Reweight the composite to: Growth 20 / **Quality 20** / Profitability 15 / Momentum 20 / Insider 7 / Sentiment 8 / Valuation 10. That lifts quality from 5% placeholder to a 20% weight backed by six durable signals, and matches AQR's own QMJ structure.

---

## Section F — Suggested Implementation Order

**Week 1 (zero new infra):** Piotroski F-Score · CFO/EBITDA · Gross Profitability · 12-1 momentum · 52-week-high proximity · Altman Z · Beneish M · EV/EBITDA · 3y Sales + EPS CAGR · ROCE 3y mean. All computable from your existing yfinance pulls.

**Week 2 (add Screener.in scrape):** Promoter pledge · Promoter + FII + DII shareholding Δ · Debt/Equity · Interest coverage · 3y dividend history.

**Week 3 (add consensus data):** Analyst estimate revisions · Forward PE · Analyst target-price Δ · Earnings surprise + PEAD window.

**Week 4+ (optional alt-data):** LinkedIn hiring velocity · earnings-call transcript sentiment (LLM) · Reddit mention velocity.

Each week's set should be backtested on your 1,720-stock universe against a held-out 6-month window before weighting.

---

*Research synthesized from Fama-French, AQR, Novy-Marx, Piotroski, Beneish, Altman, Jegadeesh-Titman, George-Hwang, Sloan, Cohen-Malloy-Pomorski, Pan-Poteshman, Marcellus Consistent Compounders, O'Neil CAN SLIM, Lynch GARP, Greenblatt Magic Formula, Indian-market screens (Screener.in, Trendlyne, Tickertape blog content), and Reddit / practitioner community references. See inline hyperlinks for primary sources.*
