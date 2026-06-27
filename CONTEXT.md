# Quantara — Project Context Document
---

## What Quantara Is
A Python-based quantitative trading strategy simulator built from scratch.
Started with one stock, one indicator, one rule. Now runs autonomous
multi-strategy, multi-stock analysis with ML signal generation, live paper
trading via GitHub Actions, real order execution via Alpaca paper trading,
a full performance analytics layer, and a narrated event feed explaining
what actually happened to the money and why.

---

## Current State (as of Jun 27, 2026)
- Versions 1-10 complete.
- Paper trader live, logging signals, executing Alpaca orders automatically.
- Scheduler runs daily at 9PM UTC (2PM PDT) on weekdays via GitHub Actions.
- Alpaca paper trading account: $10,000.
- Live stop loss enforcement CONFIRMED WORKING — fired correctly on NVDA Jun 24, 2026
  (sold at -7.7% from real Alpaca entry $216.72, realized -$123). NVDA completed a full
  exit/re-entry cycle and is trading normally since.
- CSV now logs what Alpaca actually executed on stop loss days, not just the model's
  opinion — see "Stop Loss CSV Accuracy Fix" below.
- `FEATURE_COLS` centralized as a single constant in `ml_signal.py` (16 features:
  original 14 + Mom_accel + ADX_14). `paper_trader.py` imports and uses the same
  constant — no more separate, driftable copies of the feature list.
- Dashboard has 6 tabs: Paper Trader, Strategy Results, Auto Selection, ML Analysis,
  Performance, Recent Trading Events.
- TSLA, JPM, IBM on SELL/HOLD as of last check (Jun 26). NVDA and AAPL hold open
  positions.

---

## How To Run
```powershell
# Activate environment
.\venv\Scripts\Activate.ps1

# Run modes by changing MODE in main.py
# Options: "compare", "optimize", "ml", "rf", "auto", "paper", "diagnostic"
python main.py

# Run automated paper trader directly (also executes Alpaca orders — careful, this trades)
python run_paper_trader.py

# Set env vars for local Alpaca testing
$env:ALPACA_KEY="your_key"
$env:ALPACA_SECRET="your_secret"

# Test performance analytics functions standalone (safe, no trading)
python test_performance.py
```

---

## Project Architecture
```
REQuantara/
├── .github/
│   └── workflows/
│       └── paper_trader.yml      # GitHub Actions - runs daily 9PM UTC
│                                 # commit step: commit local changes BEFORE
│                                 # pull --rebase, then push (avoids unstaged-
│                                 # changes rebase failures)
├── data/
│   └── loader.py                 # yfinance fetch; keeps Close, High, Low
│                                 # (High/Low added for ADX_14 support)
├── indicators/
│   ├── moving_average.py         # compute_sma(df, window)
│   ├── ema.py                    # compute_ema(df, window)
│   ├── rsi.py                    # compute_rsi(df, window=14)
│   └── bollinger.py              # compute_bollinger_bands(df, window=20, num_std=2)
├── signals/
│   ├── sma_crossover.py          # generate_signals, generate_crossover_signals,
│   │                             # generate_ema_crossover_signals, generate_combined_signals
│   └── bollinger_signal.py       # generate_bollinger_signals
├── backtest/
│   └── engine.py                 # run_backtest(df, initial_capital, stop_loss, position_size)
├── evaluation/
│   ├── metrics.py                # calculate_metrics (prints), get_metrics (returns dict)
│   ├── exporter.py               # export_results, export_optimization - saves to Excel
│   └── performance.py            # build_trade_segments, ticker_summary, win_loss_stats,
│                                 # drawdown_tracker, signal_quality_score,
│                                 # signal_quality_weekly, detect_problems,
│                                 # build_event_feed, KNOWN_EXIT_REASON_OVERRIDES
├── plots/
│   └── visualizer.py             # plot_results(df) - 3 panel chart
│                                 # plot_diagnostic(ticker) - LR diagnostic chart
├── strategy/
│   ├── runner.py                 # run_all_strategies(tickers) - multi stock/strategy grid
│   ├── optimizer.py              # optimize_ema_crossover, optimize_all_tickers
│   ├── ml_signal.py              # FEATURE_COLS constant (16 features, single source
│   │                             # of truth) + run_ml_strategy (LR), run_rf_strategy
│   │                             # (RF), build_features, build_target
│   ├── auto_selector.py          # auto_select - picks best strategy per ticker
│   │                             # compute_composite_score, evaluate_rule_based, evaluate_ml
│   │                             # NOTE: scores 2015-2024 backtest only, no live data
│   │                             # awareness; EMA Crossover here is always default
│   │                             # 20/50, never the optimizer's tuned parameters
│   ├── paper_trader.py           # run_paper_trader - live signals + Alpaca execution
│   │                             # get_recent_data, generate_current_signal (imports
│   │                             # FEATURE_COLS from ml_signal.py), log_signals
│   │                             # CRITICAL: logs the ACTUAL executed Signal/Action,
│   │                             # overridden to SELL when exit_reason == STOP_LOSS —
│   │                             # never just the model's raw opinion
│   └── alpaca_executor.py        # get_client, execute_signal (ALWAYS returns a
│                                 # (result, reason) tuple — reason is one of
│                                 # "STOP_LOSS", "SIGNAL", None), get_pending_orders,
│                                 # check_stop_loss
├── results/
│   └── paper_trading_log.csv     # auto updated by GitHub Actions daily; rows written
│                                 # after the Stop Loss CSV Accuracy Fix include a 7th
│                                 # field, Exit_Reason
├── config.py                     # all settings + Alpaca credentials via os.getenv
├── main.py                       # entry point with MODE switch
├── dashboard.py                  # Streamlit dashboard - Bloomberg institutional style
│                                 # 6 tabs: Paper Trader, Strategy Results, Auto
│                                 # Selection, ML Analysis, Performance, Recent
│                                 # Trading Events
├── walk_forward_test.py          # one-off script: momentum-feature robustness check
│                                 # across 4 historical window lengths (see Version 10)
├── run_paper_trader.py           # standalone script for GitHub Actions
├── test_performance.py           # standalone test harness for evaluation/performance.py
└── CONTEXT.md                    # this file
```

---

## Dashboard
- Live: https://requantara-e4epzjkmfgtgb9almgh3le.streamlit.app
- Built with Streamlit Community Cloud, auto-updates when GitHub Actions commits new
  paper trading data
- Style: Bloomberg meets modern fintech — dark navy, Inter font, JetBrains Mono for data
- 6 tabs: Paper Trader, Strategy Results, Auto Selection, ML Analysis, Performance,
  Recent Trading Events
- Portfolio summary row (value, P&L, return %, best/worst performer) sits above the tabs
- Note: repo currently public for Streamlit — may go private later; redeploy/reboot
  from share.streamlit.io if it ever goes dark after a visibility change

---

## Config Settings
```python
TICKERS = ["NVDA", "TSLA", "AAPL", "JPM", "IBM"]
START = "2015-01-01"
END = "2024-01-01"
FAST_WINDOW = 20
SLOW_WINDOW = 50
EMA_FAST = 20
EMA_SLOW = 50
STOP_LOSS = 0.05
POSITION_SIZE = 0.50
INITIAL_CAPITAL = 10000

# Alpaca (loaded from environment variables)
ALPACA_KEY = os.getenv("ALPACA_KEY")
ALPACA_SECRET = os.getenv("ALPACA_SECRET")
ALPACA_BASE_URL = "https://paper-api.alpaca.markets"
```

---

## Alpaca Integration
- Paper trading account: $10,000
- SDK: alpaca-py
- Execution: MarketOrderRequest, TimeInForce.DAY
- Position sizing: 50% of portfolio per ticker
- Position check: skips BUY if position OR pending order exists (duplicate-order fix)
- **Stop loss enforcement**: `check_stop_loss()` in `alpaca_executor.py` compares
  Alpaca's live `avg_entry_price` against current price before evaluating the model's
  signal. If drawdown from entry ≤ -5%, force-sells regardless of signal. CONFIRMED
  WORKING live on NVDA, Jun 24, 2026.
- `execute_signal()` always returns a `(result, reason)` tuple, never a bare value —
  `reason` is `"STOP_LOSS"`, `"SIGNAL"`, or `None`. This is what lets the CSV and the
  Recent Trading Events feed know *why* a trade happened, not just that it happened.
- Secrets stored in GitHub Actions secrets (ALPACA_KEY, ALPACA_SECRET)
- Local testing: set via `$env:` in PowerShell

---

## Strategies Built
| Strategy | File | Key Parameters |
|----------|------|----------------|
| SMA Crossover | sma_crossover.py | fast=20, slow=50 |
| EMA Crossover | sma_crossover.py | fast=20, slow=50 |
| SMA + RSI Combined | sma_crossover.py | fast=20, slow=50, rsi_high=70 |
| Bollinger Bands | bollinger_signal.py | window=20, num_std=2 |
| Logistic Regression | ml_signal.py | 16 features, walk forward split |
| Random Forest | ml_signal.py | 100 trees, 16 features, walk forward split |

**Current live strategy per ticker:** NVDA → EMA Crossover, TSLA → Logistic Regression,
AAPL → EMA Crossover, JPM → SMA Crossover, IBM → Random Forest. (Auto-selected from
2015-2024 backtest composite scores — see "Auto-Selector vs Live Performance" note below
for why this doesn't always match recent live results.)

---

## ML Features (16 total)
**Original 14:** EMA_gap, RSI, BB_position, Momentum_5, Momentum_10, Momentum_20,
Momentum_30, RSI_slope, Volatility_10, Volatility_20, SMA_gap, Price_vs_SMA20,
Price_vs_SMA50, BB_width

**Added in Version 10:** Mom_accel, ADX_14 (10-day momentum acceleration and 14-period
Average Directional Index — kept after testing, see Version 10 section)

**Tested and rejected in Version 10:** Streak, Streak_Squared (consecutive-day-count
features — removed after failing on both models, see Version 10 section)

Single source of truth: `FEATURE_COLS` constant defined once at the top of
`strategy/ml_signal.py`. `run_ml_strategy`, `run_rf_strategy`, and
`paper_trader.py`'s `generate_current_signal` all import and use this same constant —
no per-function local copies, so the feature set can't silently drift between
backtest/research code and live signal generation.

---

## Backtest Results Reference (2015-2024)

### Multi-Strategy Results (test period, default parameters)
```
Ticker  Strategy              Return   Sharpe   MaxDD
NVDA    EMA Crossover         138.72%  0.973    -36.77%
NVDA    Bollinger Bands        21.47%  0.820     -9.94%
NVDA    SMA Crossover          88.41%  0.807    -39.69%
AAPL    EMA Crossover          44.30%  0.766    -13.20%
JPM     SMA Crossover          34.08%  0.755    -13.00%
NVDA    SMA+RSI Combined       59.09%  0.725    -37.44%
AAPL    SMA+RSI Combined       26.70%  0.706    -14.26%
AAPL    SMA Crossover          34.28%  0.703    -15.66%
TSLA    EMA Crossover         107.15%  0.702    -43.15%
JPM     SMA+RSI Combined       23.58%  0.629     -9.46%
TSLA    SMA Crossover          68.52%  0.606    -31.35%
TSLA    SMA+RSI Combined       30.50%  0.437    -27.70%
JPM     Bollinger Bands         9.49%  0.357     -8.44%
JPM     EMA Crossover          10.61%  0.305    -15.21%
TSLA    Bollinger Bands         7.86%  0.300     -8.45%
AAPL    Bollinger Bands         5.25%  0.288     -4.14%
```

### ML Results Summary (original 14-feature set)
```
Ticker  LR Sharpe   RF Sharpe   Better Model
TSLA    1.252       0.675       LR
AAPL    0.760       0.928       RF
NVDA    0.707       0.850       RF
IBM     0.680       0.887       RF
JPM     0.043       0.405       RF
```
Key finding: RF dominates stable data-rich stocks, LR dominates volatile ones. NN
deferred — insufficient daily data (~625 training days) to outperform simpler models.
NN viable in Quantara NN project (minute data, 50k-120k samples per ticker).

### Optimization Results (EMA Crossover, tuned fast/slow windows)
```
Ticker  Fast  Slow  Train Sharpe  Test Sharpe  Overfit Gap
NVDA    36    193   1.853         1.267         0.586
TSLA    7     21    2.218         0.445         1.773
AAPL    5     24    1.883         0.373         1.510
JPM     33    113   1.279         0.289         0.990
```
Key finding: TSLA and AAPL severely overfit — unreliable parameters. Only NVDA shows
robust optimization. **Important:** these tuned parameters are NOT what the live
auto-selector uses — `auto_selector.py`'s `evaluate_rule_based()` always runs default
20/50 EMA Crossover, never these optimized windows. The optimizer is a separate,
standalone analysis path.

### Auto Selection Results (composite score, 2015-2024 backtest)
```
Ticker  Best Strategy         Score   Sharpe  Return   MaxDD
TSLA    Logistic Regression   1.1713  1.018   236.07%  -36.60%
NVDA    EMA Crossover         1.1044  1.062   191.86%  -36.77%
IBM     Random Forest         1.0240  1.243   65.71%    -9.65%
AAPL    EMA Crossover         0.8541  0.917   67.43%   -13.09%
JPM     SMA Crossover         0.7898  0.874   45.92%   -13.03%
```

**Composite Score Formula:**
`Score = (Sharpe × 0.5) + ((1 - abs(MaxDrawdown/100)) × 0.3) + (TotalReturn/100 × 0.2)`
- Above 1.0 = genuinely good
- 0.5 to 1.0 = acceptable
- Below 0.5 = failing

---

## ⚠️ Auto-Selector vs Live Performance — Why They Can Disagree
The auto-selector scores the 2015-2024 backtest only — it has zero awareness of the
live paper trading log. It is not measuring the same thing as live performance, and the
two are not in conflict even when they appear to disagree:
- NVDA and JPM's strong backtest scores come from riding multi-year trends with very
  few trades — the exact same low-frequency, slow-to-exit behavior that shows up live
  as NVDA going 0-for-48-days and JPM holding a single trade for 34 days.
- The live window (weeks, not years) is far too short to say whether current
  drawdowns are normal noise inside a longer trend (consistent with backtest behavior)
  or an actual trend break the backtest never saw. Don't read live underperformance as
  the backtest being "wrong" — they're different sample periods, and the live one is
  still tiny by comparison.

---

## Version 9 — Performance Analytics (COMPLETE)
Full research report generated: `Quantara_Version9_Report.docx` (Apr 29 – Jun 16, 2026
reporting period). Built the entire analytics layer this version is named for:

**Trade segmentation** (`evaluation/performance.py`, `build_trade_segments()`): walks
the CSV chronologically per ticker, closes a "segment" on strategy change or BUY→SELL
flip, tracks entry/exit price/date, duration, P&L, P&L%, and OPEN/CLOSED status.
Tracked at ticker+strategy granularity, then rolled up to ticker-level summaries
(`ticker_summary()`) so both views exist without duplicating logic. Unrealized P&L on
open positions marked with `*` rather than shown as a separate competing number.

**Key finding — trade frequency divide:** Rule-based crossover strategies (NVDA, JPM)
barely trade once a position is open — slow 20/50-period signals are designed to
filter noise and are correspondingly slow to register anything short of a full trend
reversal (NVDA: 0 closed trades in 48 days; JPM: 1 trade in 34 days). ML strategies
(TSLA, IBM) trade far more often since they're trained to predict next-period
direction. Not a bug — different strategies solving different problems, not directly
comparable on trade count.

**Key finding — ML momentum misread (TSLA & IBM):** Both LR (TSLA) and RF (IBM) exit
near local tops and re-enter after the best part of the move has already passed:
- **TSLA:** ran $376→$445 (May 14 peak, +18.4%). Model exited May 2 at $390.82 (missed
  most of the run), re-entered May 14 at $445.27 right before the reversal, closed
  that re-entry at -$125.81 (-6.3%) on May 21.
- **IBM:** ran $233→$329.23 (Jun 3 peak, +41%). Model exited May 22 at $252.97 (missed
  most of the run), didn't re-enter until Jun 9 at $280.82 — well after the peak, on
  the way down. IBM's drawdown from that live peak reached -18.4%, the worst in the
  portfolio.
- Likely cause: RSI/BB_position features read sustained momentum as "overextension"
  rather than confirmed trend. This became the explicit subject of the Version 10
  investigation below.

**Win/Loss stats** (`win_loss_stats()`, 16 closed trades through Jun 16): Win Rate
56.3%, Avg Win +$74.48, Avg Loss -$57.73. Biggest win: +$178.90 (IBM, May 2–22).
Biggest loss: -$125.81 (TSLA, May 14–21).

**Drawdown tracker** (`drawdown_tracker()`): tracks each ticker's running peak price
*since live tracking began*, not the backtest peak. This is what first surfaced that
every ticker was sitting past the 5% stop loss threshold from its own live peak with
no automatic exit — the gap that led directly to the Stop Loss CSV Accuracy Fix below.

**Signal quality score** (`signal_quality_score()`): next-day directional accuracy on
BUY signals. Most diagnostic for TSLA/IBM (LR/RF are explicitly trained on next-period
direction — their sub-40% scores are a real, meaningful underperformance finding and
the quantitative confirmation of the momentum misread above). Less applicable to
NVDA/JPM/AAPL since crossover strategies aren't designed to win on a daily basis, only
to ride confirmed multi-week trends.

**Weekly signal quality** (`signal_quality_weekly()`): built and tested, held back
from the dashboard. Sample sizes too small (2-5 signals/ticker/week) to be stable —
swings between 0% and 100% week to week on pure noise for most tickers. AAPL showed a
loose upward trend (~50% late April → 100% by mid-June) but flagged as preliminary
only given sample size. Revisit with more data or a rolling window instead of discrete
week buckets.

**Problem detection** (`detect_problems()`): scans switch flags, drawdown vs stop loss
threshold, and signal accuracy (only flags accuracy if ≥10 signals checked, to avoid
noise on small samples). Dashboard groups flags by ticker with severity icons (🔴
CRITICAL / 🟡 WARNING / 🟢 OK) rather than one flat list.

---

## Version 10 — Momentum Feature Investigation (COMPLETE, no live changes)

**Hypothesis going in:** TSLA (LR) and IBM (RF) showed the recurring momentum-misread
pattern documented in Version 9 — exiting near local tops, re-entering after
pullbacks. Both tickers' ADX_14 distributions (computed during this investigation)
showed they spend >50% of their time in a "trending" regime (median ADX ~32-33), yet
their feature sets were dominated by mean-reversion-flavored indicators (RSI,
BB_position, BB_width, Price_vs_SMA20/50 — 6 of the original 14 features). Hypothesis:
adding explicit momentum-persistence features would let LR/RF correctly weight
sustained trends instead of reading them as overextension.

**Features built and tested**, added to `build_features()`:
- `Streak` — signed consecutive up/down day count
- `Streak_Squared` — magnitude-only version, tested to check for a non-linear
  relationship (e.g. "short streak = momentum, long streak = exhaustion")
- `Mom_accel` — 10-day momentum minus 10-day momentum from 5 days ago
- `ADX_14` — standard 14-period Average Directional Index, direction-agnostic trend
  strength (required adding High/Low columns to `data/loader.py`'s `load_data()`,
  which previously kept only Close)

**Result 1 — `Streak` rejected.** RF ranked `Streak` dead last (lowest importance) on
every single ticker, no exceptions. LR's coefficient was negative on every ticker
(implying long streaks predict reversal, not continuation — opposite of the
hypothesis). TSLA and IBM, the actual target tickers, both got WORSE on both models:
```
              LR Sharpe                  RF Sharpe
TSLA:  1.252 -> 1.093 (-0.159)     0.675 -> 0.509 (-0.166)
IBM:   0.685 -> 0.504 (-0.181)     1.162 -> 0.944 (-0.218)
```
Meanwhile NVDA and AAPL — not target tickers — improved on both models. First sign the
new features might matter more for NVDA/AAPL than for the tickers they were built for.

**Result 2 — `Streak_Squared` also rejected.** Added specifically to test whether the
relationship was non-linear (RF should detect that natively if it existed). RF ranked
`Streak_Squared` dead last on every ticker — even lower than plain `Streak`. LR showed
only small (<0.1) Sharpe changes either direction. Conclusion: not a linearity
problem — the feature isn't predictive in raw or squared form, on either model, for
any ticker. Decided not to pursue manual bucketing into "strong/weak" categories,
since RF already had full access to find any threshold effect on its own and
consistently didn't.

**Result 3 — NVDA/AAPL "improvement" was a false lead, caught by walk-forward check.**
A single 50/50-split composite score comparison initially suggested NVDA-RF
(16-feature) would beat NVDA's live EMA Crossover by a wide margin. This comparison
was invalid — the EMA baseline number came from a different, unverified historical
test window than the new RF run. Recomputed fairly (same exact window, default 20/50
EMA via `auto_selector.py`'s actual logic) across 4 robustness windows (all starting
2015-01-01, ending 2024/2023/2022/2021 — note: these are 4 different total-history
lengths each internally split 50/50, NOT 4 independent disjoint train/test periods):
- **NVDA:** EMA beat RF-with-momentum in ALL 4 windows, often by ~2x margin. RF win
  rate: 0%.
- **AAPL:** LR-with-momentum beat EMA in 2/4 windows (most recent two), lost the other
  2 (lost badly on the 2022 window). LR win rate: 50% — a coin flip, not a finding.

Conclusion: the single-window NVDA result was a baseline-comparison error, not a real
edge. AAPL's split result doesn't clear the bar for a robust improvement either.

**Final decision:** `Streak` and `Streak_Squared` removed entirely from
`build_features()` and `FEATURE_COLS`. `Mom_accel` and `ADX_14` were KEPT — neither
actively hurt anything in any test, `ADX_14` was NVDA's #1 RF feature importance in
every run, and `Mom_accel` was consistently mid-pack to positive across all five
tickers. **No live strategy assignment changed** as a result of this investigation:
TSLA still LR, IBM still RF, NVDA and AAPL still EMA Crossover, JPM still SMA
Crossover. Purely a backtest research investigation.

**Bigger-picture finding worth remembering:** IBM's ADX profile (median ~33, mean
~35.4) is nearly identical to TSLA's (median ~31.6, mean ~35.1) — IBM is NOT the
"boring mean-reverting" stock its reputation suggests; it trends just as much as TSLA
on average. The original momentum-misread problem is real and confirmed, but explicit
momentum-persistence features (in the three forms tested here) were not the fix. The
actual cause may lie elsewhere — possibly in how RSI/BB features are scaled/weighted
relative to momentum features rather than momentum features being absent, or in the
train/test split methodology itself. **This remains unresolved — see Version 11.**

**Process note:** this thread is a good case study in why the walk-forward check
matters most exactly when a single-window result looks convincing, not despite it.
The NVDA "win" looked clean and would have been easy to ship without the second check.
Apply the same standard before trusting any single backtest-window result going
forward — the same instinct that already caught TSLA/AAPL's EMA Crossover overfitting
in the original optimizer work.

---

## Version 10 — Stop Loss CSV Accuracy Fix (COMPLETE)
**The problem:** when the live stop loss force-sells a position, the CSV log was still
writing the MODEL's opinion (Signal/Action), not what Alpaca actually executed. NVDA's
June 24, 2026 stop loss trigger logged as `Signal: 1, Action: BUY` even though Alpaca
force-sold the position that same day. This made `build_trade_segments()` show NVDA as
one continuous 58-day OPEN position straddling the real exit, and made it genuinely
hard to figure out what had happened without manually cross-referencing the CSV
against Alpaca's activity feed — the original complaint that started this thread.

**Fix, across 3 files:**
- **`alpaca_executor.py`** — `execute_signal()` now ALWAYS returns a `(result, reason)`
  tuple instead of a single value. `reason` is `"STOP_LOSS"`, `"SIGNAL"`, or `None`,
  consistent across every return path (stop loss, BUY, SELL, both skip cases). Also
  fixed a pre-existing bug in `get_position()` where the except path returned
  `None, None` (a tuple) instead of `None` — meant `position is None` checks could
  silently misbehave.
- **`paper_trader.py`** — call site updated to
  `order_result, exit_reason = execute_signal(...)`. If `exit_reason == "STOP_LOSS"`,
  the logged `Signal`/`Action` are OVERRIDDEN to `0`/`"SELL/HOLD"` before writing to
  the CSV, regardless of what the model originally recommended. The CSV is now a
  record of what actually happened to the money, not the model's opinion — the
  model's opinion is research data, independently recoverable by re-running
  `generate_current_signal`, not something the live log needs to preserve at the cost
  of misrepresenting the actual trade.
- **`evaluation/performance.py`** — new `Exit_Reason` column (7th CSV field, present
  only on rows written after this fix). `build_trade_segments()` reads it via `.get()`
  for backward compatibility with pre-fix rows, defaulting to `"SIGNAL"` if missing.

**Known one-off historical exception:** NVDA's Jun 24, 2026 row predates this fix, so
it was manually corrected (Signal 1→0, Action BUY→SELL/HOLD) but deliberately left at
6 fields — no `Exit_Reason` backfilled, to avoid a CSV column-count parse crash.
`build_event_feed()` has a small hardcoded `KNOWN_EXIT_REASON_OVERRIDES` dict mapping
this one specific (ticker, timestamp) pair to `"STOP_LOSS"` manually. Not a pattern to
extend — a one-time documented correction for data that predates tracking. Every stop
loss trigger from this point forward logs correctly with no manual intervention.

---

## Version 10 — "Recent Trading Events" Dashboard Tab (COMPLETE)
New 6th dashboard tab, built on the Stop Loss CSV fix above. Answers "what happened to
my portfolio and why" without cross-referencing Alpaca manually — the actual fix to
the "7 steps to find out NVDA sold" problem.

**`build_event_feed()`** (`evaluation/performance.py`) generates one narrated entry
per: closed trade exit (tagged STOP_LOSS vs SIGNAL, with dollar gain/loss), new entry
(BUY), and strategy switch (detected by walking the raw log per ticker, flagging any
day Strategy differs from the prior day). Returns a list sorted most-recent-first by
default. No share counts in messages — the CSV doesn't log real Alpaca quantities,
only an implied $2k-per-ticker assumption used elsewhere on the dashboard, and
dollar-only language was judged more honest than presenting a fictional quantity.

**Example (verified working on NVDA's real stop loss event):**
> 🔴 NVDA sold @ $200.04 — stop loss (5%) triggered (down 6.2% from your $213.17
> entry). You realized a loss of $123 on this position.

**Dashboard tab features:**
- Date range filter (7/14/30/90 days, or All time)
- Ticker filter dropdown
- Sort toggle: "Most Recent" (default, chronological) or "Severity" (Critical →
  Negative → Warning → Positive → Neutral; Python's stable sort preserves recency
  within each severity group)
- Color/icon coding: CRITICAL = red 🔴 (stop loss), NEGATIVE = red 🔸 (signal loss),
  POSITIVE = green 🟢 (signal gain), WARNING = amber 🟡 (strategy switch), NEUTRAL =
  grey ⚪ (buy — intentionally muted/low-opacity, since most days are routine entries
  that shouldn't visually compete with things that need attention)

---

## Alpaca Live Order History
First real paper trades placed May 24, 2026: NVDA, AAPL, JPM (a duplicate NVDA order
from manual testing was cancelled). TSLA and IBM have each sold off and re-entered
multiple times through normal signal flow since. NVDA completed its first full
stop-loss-triggered exit on Jun 24, 2026 (sold at $200.04, -7.7% from entry $216.72,
-$123 realized), then re-entered and has traded normally since under the now-corrected
logging.

---

## Key Technical Decisions
- Data source: yfinance (free, clean, sufficient for daily backtesting)
- Returns tracked as actual dollar portfolio value, not percentage multipliers
- One day signal lag (`Position = Signal.shift(1)`) prevents lookahead bias
- Stop loss: exit if price drops 5% below entry — enforced in BOTH backtest AND live
  execution (live enforcement added and confirmed working Jun 2026)
- Position sizing: 50% of capital per trade (single stock)
- Sharpe annualized with sqrt(252)
- Walk forward split: first 50% train, second 50% test
- Alpaca execution: MarketOrderRequest, TimeInForce.DAY
- Duplicate order prevention: checks both open positions AND pending orders
- Trade segment definition: closes on strategy change OR BUY→SELL flip within the same
  strategy — tracked at ticker+strategy granularity, rolled up to ticker-level
  summaries so both views exist without duplicating logic
- GitHub Actions commit order: commit local changes BEFORE `pull --rebase`, then push
  — avoids "cannot pull with rebase: unstaged changes" failures
- The live CSV log reflects what Alpaca actually executed, never just the model's raw
  signal — model opinion is recoverable separately by re-running the model, but the
  permanent record should never misrepresent the real trade
- `FEATURE_COLS` is defined exactly once, in `ml_signal.py`, and imported everywhere
  else it's needed — no per-function local copies of the feature list

---

## Key Research Findings
- EMA Crossover dominates momentum stocks (NVDA, AAPL) — in backtest
- LR dominates highly volatile stocks (TSLA) — in backtest
- RF dominates stable data-rich stocks (IBM, AAPL) — in backtest
- Rule-based beats ML when training data is limited
- RSI filter too restrictive on momentum stocks
- Bollinger Bands better suited for mean-reverting assets
- More training data (2015 vs 2020) significantly improves ML results
- TSLA optimization severely overfits — unreliable parameters
- Composite score captures return AND safety simultaneously
- TSLA and IBM both show a confirmed momentum misread: LR/RF exit near local tops,
  re-enter after pullbacks. Quantified in Version 9, investigated (unresolved) in
  Version 10.
- Live trade frequency reveals a structural divide: rule-based strategies barely trade
  once positioned; ML strategies trade often — different tradeoffs, not a bug
- Backtest auto-selector scores and live performance measure different time windows
  and are not contradictory even when they appear to disagree
- IBM's ADX trend-strength profile is nearly identical to TSLA's — IBM is not the
  "boring" stock its reputation suggests
- Adding momentum-persistence features (Streak, Streak_Squared) did not fix the
  TSLA/IBM momentum misread — tested properly via walk-forward validation, rejected.
  The fix for this problem requires a different approach (see Version 11)

---

## Known Issues / Technical Debt
- IBM and AAPL have each switched strategy at least once live (IBM: RF ↔ Bollinger;
  AAPL: EMA ↔ RF) — auto-selector re-evaluates every run, no strategy lock-in period
- Timestamp format inconsistent in early CSV rows (cosmetic only, self-resolved once
  GitHub Actions took over)
- Optimizer only built for EMA Crossover — needs extending to other strategies
- `squeeze()` needed throughout due to pandas version strictness
- NVDA EMA Crossover and JPM SMA Crossover are both slow to exit declining positions —
  structural property of long-window crossover signals, not a bug
- No strategy lock — auto-selector can pick differently each run
- **TSLA/IBM momentum misread — UNRESOLVED.** Quantified in Version 9, investigated in
  Version 10 (momentum-persistence features tested and rejected). Needs a different
  angle: candidates include a regime classifier upstream of LR/RF, reweighting the
  RSI/BB-heavy feature set, or revisiting the train/test split methodology itself.
- Weekly signal quality too noisy at current sample sizes — held back from dashboard,
  revisit with more data or a rolling window
- NVDA's Jun 24, 2026 stop loss exit is a known, documented, manually-corrected
  one-off exception in the historical CSV/event feed data (see Version 10 — Stop Loss
  CSV Accuracy Fix). Not a pattern, won't recur.

---

## Version Roadmap
### Version 1 ✅ — Single stock, SMA, basic backtest
### Version 2 ✅ — EMA, RSI, Bollinger, risk management
### Version 3 ✅ — Multi-strategy, multi-stock, Sharpe ranking
### Version 4 ✅ — Parameter optimization, walk forward testing
### Version 5 ✅ — ML signal generation (LR + RF)
### Version 6 ✅ — Autonomous strategy selection, composite scoring
### Version 7 ✅ — Paper trading, GitHub Actions scheduler
### Version 8 ✅ — Streamlit dashboard, Alpaca paper trading integration
### Version 9 ✅ — Performance Analytics
  - Trade segmentation (ticker + strategy level, rolled up to ticker level)
  - Win/loss stats, drawdown tracker, signal quality score
  - Problem detection grouped by ticker with severity icons
  - Live stop loss enforcement added (later found to have a logging gap — fixed in V10)
  - Full research report compiled (`Quantara_Version9_Report.docx`)
### Version 10 ✅ — Momentum Investigation, Stop Loss Accuracy Fix, Recent Trading Events
  - Momentum feature investigation (Streak, Streak_Squared, Mom_accel, ADX_14) —
    CLOSED, no live strategy changes. Streak/Streak_Squared rejected after testing;
    Mom_accel and ADX_14 kept (harmless to mildly positive, did not fix TSLA/IBM)
  - `FEATURE_COLS` centralized as a single constant, eliminating feature-list drift
    between backtest and live code
  - Stop Loss CSV Accuracy Fix — CSV now logs what Alpaca actually executed on stop
    loss days, not just the model's opinion
  - Recent Trading Events dashboard tab — narrated event feed with severity sort/filter
### Version 11 (planned) — Not yet started
  - **TSLA/IBM momentum-misread fix — still UNRESOLVED.** Momentum-persistence
    features didn't work (Version 10). Next angle should be different: a regime
    classifier upstream of LR/RF, RSI/BB feature reweighting, or revisiting the
    train/test split methodology — not more features in the same shape.
  - Strategy lock-in period to reduce AAPL/IBM switching instability
  - Revisit weekly signal quality with more data or a rolling window
  - Quantara NN merger: separate daily (this project) and intraday (NN) systems,
    unified dashboard, SQLite when going live, fix Alpaca NN position sizing bug

---

## Related Project
**Quantara NN** — separate intraday trading system
- Minute data, MLP neural network, Nemotron LLM reasoning
- Alpaca live order execution
- Multi-agent pipeline
- Position sizing bug: stacks positions despite 2% limit. Fix: check pending orders +
  open positions before buying (same pattern as this project's duplicate order fix)

---

## GitHub
- Repo: https://github.com/titan-trials/REQuantara
- Actions: https://github.com/titan-trials/REQuantara/actions
- Local: `C:\Users\logic\OneDrive\Desktop\REQuantara`

## Libraries
- yfinance — market data
- pandas — data manipulation
- matplotlib — visualization
- scikit-learn — ML models
- openpyxl — Excel export
- streamlit — dashboard
- plotly — interactive charts
- alpaca-py — paper trading execution