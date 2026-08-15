# Quantara

A quantitative trading system built from scratch in Python, and a record of what
happened when it was tested honestly.

**Headline finding: the strategies do not beat buying and holding the same
stocks.** Not by a small margin, and not because of a bug. Three separate
hypotheses were tested and all three were falsified.

This repository is a negative result. That is the point of it.

---

## What was built

Started as one stock, one indicator, one rule. Grew into a multi-strategy,
multi-ticker system with machine-learning signal generation, autonomous
strategy selection, live paper trading through Alpaca on a GitHub Actions
schedule, a Streamlit dashboard, and a performance analytics layer.

It ran live on paper money from April 2026 and returned **+20.10%** against a
**+4.48%** buy-and-hold benchmark over the same period — which looked like
evidence of a real edge, and was the reason for everything that followed.

---

## What went wrong

Roughly half that outperformance turned out to be **~1.9x leverage nobody had
noticed**. Checking that led to checking everything else.

**Bugs found in the accounting and execution layers:**

- One `POSITION_SIZE` constant meant "fraction of one ticker's capital" in the
  backtest and "fraction of the whole account" live — 5 tickers × 50% = 250%
  exposure, funded by margin.
- Share counts were floored to whole numbers, making effective position size
  depend on share price. A $365 stock got 18% when asked for 20%, and nothing
  at all at small sizes.
- The backtest stop loss sold and re-bought on the same bar, so it never
  removed exposure — it only reset the entry price lower.
- The backtest executed at the same close it computed the signal from. Live
  fills at the next open. This made gap risk structurally invisible.
- No transaction costs anywhere, which biased *which strategy got selected*,
  not just the returns reported.
- Three fail-open bugs in live order handling: an error could liquidate a
  position, place a duplicate order, or silently skip a stop loss.
- The auto-selector wrapped every strategy in a bare `except` and silently
  traded on an incomplete candidate field.
- Sharpe never subtracted a risk-free rate. `Win_Rate` was not a win rate.
  `Market_Return` — the buy-and-hold comparison — was computed on every
  backtest since day one and read by nothing.

Every one of these flattered the results.

---

## How the conclusion was reached

Each test was designed to remove one excuse for the previous result.

**1. The original five tickers.** Buy and hold beat every strategy on all five.
*Excuse:* the tickers were chosen in 2026 knowing how 2015–2024 went, and four
were large-cap tech during a historic bull run.

**2. Thirty-three hindsight-free tickers**, deliberately including known
decliners, with the strategy picked on the first half of history and scored on
the second — the way it actually deploys.

```
beat buy & hold on           2/33  =  6%     (no-skill baseline: 50%)
strategy chosen on train
also won on test             6/33  = 18%     (chance: 14%)
mean return          picked +9.6%  vs  buy & hold +62.3%
```

Applied uniformly with no picking, **no single strategy beat holding on more
than 7 of 33 tickers**, and five of six had a negative mean Sharpe.

**3. Indicator combinations.** 120 pairwise combinations × 33 tickers, with
tickers split into discovery and confirmation sets. Nothing survived
confirmation. (Desperate attempt by me tbh, was hoping for something interesting to happen)

**4. Fundamentals.** Ruled out before building: yfinance provides ~1.8 years of
quarterly data, roughly four usable rebalance points.

**5. Cross-sectional momentum** — a structurally different hypothesis, since it
ranks stocks rather than timing them and is always fully invested. On 2016–2026
it looked genuinely strong. Extended to 2000–2026 with nothing else changed:

```
2000-2009    momentum 10.80%   benchmark 11.17%    -0.36%
2010-2019    momentum 12.62%   benchmark 14.49%    -1.87%
2020-2026    momentum 17.71%   benchmark 12.71%    +5.01%

13 winning years out of 26 — a coin flip
```

The entire edge lived in one recent period. It was the decade, not the effect.

---

## Why the strategies fail

Daily-bar trend and mean-reversion rules on liquid US large-caps are the most
studied, most arbitraged setup in finance.

Meanwhile the strategies impose guaranteed costs. **Time out of the market
forfeits the equity risk premium** — the market's upward drift is what generates
return, so every day in cash gives some of it up, on top of transaction costs
and execution lag. Unless the signal is genuinely better than random, being out
is pure cost. The persistence test says the signal is not better than random.

---

## What this does *not* prove

- It tests **six specific strategies** on daily bars, not all strategies.
- It does not test intraday frequencies, non-price signals, fundamentals,
  sentiment, or long-short construction.
- The universe was written from memory and is **survivorship-contaminated**.
  A proper test needs point-in-time index membership including delisted names.
- It covers roughly one market over one 26-year window.

A negative result has limits too.

---

## What is in here

```
backtest/       execution engine — next-open fills, transaction costs,
                fractional shares
strategy/       six strategies, auto-selection, live Alpaca execution
evaluation/     metrics, risk-free rate, trade analytics, account logging
data/           yfinance loader + self-healing price cache
experiment_*.py the research harnesses that produced the findings
test_*.py       167 network-free assertions
check_health.py one-command status check over the live logs
CONTEXT.md      the full research log, version by version
```

The engineering is independent of the finding. The cache, execution model,
measurement layer, and test suite work on whatever they are pointed at.

---

## Running it

```bash
python check_health.py                      # status of the live system
python experiment_basket.py                 # the core negative result
python experiment_momentum_history.py       # 26-year momentum test
pytest-free: each test_*.py runs standalone
```

---

## Next step

**A research paper writing up these findings.**

The subject is not "I tried to beat the market." It is the gap between a
backtest that shows 500% and a system that survives being checked — and how
many separate errors, each individually plausible, have to be found before the
difference becomes visible. 

`CONTEXT.md` is the primary source: every version, every hypothesis, every bug,
including predictions that were recorded in advance and then failed.

This is not the end.
---

*Built by Nolan with some help. The strategies failed. The method held.*
