# Quantara — Project Context Document
---

## Who I Am
Economics + Mathematics student at UC Santa Cruz. Goal is to become a
Quantitative Developer or Researcher. This project serves as both a
learning tool and a foundation for a real quant research platform.
Intro to C++ background, learning Python through this project.
Philosophy: understanding over performance. No black boxes.

---

## What Quantara Is
A Python-based quantitative trading strategy simulator built from scratch.
Started with one stock, one indicator, one rule. Now runs autonomous
multi-strategy, multi-stock analysis with ML signal generation, live paper
trading via GitHub Actions, real order execution via Alpaca paper trading,
and a full performance analytics layer (Version 9) that parses the live
signal history into trades, win/loss stats, drawdown, and automated
problem detection.

---

## Current State
- Versions 1-9 complete.
- Paper trader live, logging signals, executing Alpaca orders automatically
- Scheduler runs daily at 9PM UTC (2PM PDT) on weekdays
- Alpaca paper trading account: $10,000
- Live stop loss enforcement added (previously backtest-only — see "Stop Loss Gap" below)
- Dashboard has 5 tabs: Paper Trader, Strategy Results, Auto Selection, ML Analysis, Performance
- Currently open Alpaca positions: NVDA, AAPL (both past -5% stop loss from live peak as of Jun 16 — expected to close on next scheduled run now that enforcement is fixed)
- TSLA, JPM, IBM currently on SELL/HOLD — no open positions

---

## How To Run
```powershell
# Activate environment
.\venv\Scripts\Activate.ps1

# Run modes by changing MODE in main.py
# Options: "compare", "optimize", "ml", "rf", "auto", "paper", "diagnostic"
python main.py

# Run automated paper trader directly (also executes Alpaca orders)
python run_paper_trader.py

# Set env vars for local Alpaca testing
$env:ALPACA_KEY="your_key"
$env:ALPACA_SECRET="your_secret"

# Test performance analytics functions standalone
python test_performance.py
```

---

## Project Architecture
REQuantara/

├── .github/

│   └── workflows/

│       └── paper_trader.yml      # GitHub Actions - runs daily 9PM UTC

│                                 # commit step: commit before pull --rebase, then push

├── data/

│   └── loader.py                 # yfinance data fetching, cleans multi-level columns

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

│   └── performance.py            # Version 9 — build_trade_segments, ticker_summary,

│                                 # win_loss_stats, drawdown_tracker, signal_quality_score,

│                                 # signal_quality_weekly, detect_problems

├── plots/

│   └── visualizer.py             # plot_results(df) - 3 panel chart

│                                 # plot_diagnostic(ticker) - LR diagnostic chart

├── strategy/

│   ├── runner.py                 # run_all_strategies(tickers) - multi stock/strategy grid

│   ├── optimizer.py              # optimize_ema_crossover, optimize_all_tickers

│   ├── ml_signal.py              # run_ml_strategy (LR), run_rf_strategy (RF)

│   │                             # build_features (14 features), build_target

│   ├── auto_selector.py          # auto_select - picks best strategy per ticker

│   │                             # compute_composite_score, evaluate_rule_based, evaluate_ml

│   │                             # NOTE: scores 2015-2024 backtest only, no live data awareness

│   ├── paper_trader.py           # run_paper_trader - live signals + Alpaca execution

│   │                             # get_recent_data, generate_current_signal, log_signals

│   └── alpaca_executor.py        # get_client, execute_signal, get_pending_orders,

│                                 # check_stop_loss (NEW — live stop loss enforcement)

├── results/

│   └── paper_trading_log.csv     # auto updated by GitHub Actions daily

├── config.py                     # all settings + Alpaca credentials via os.getenv

├── main.py                       # entry point with MODE switch

├── dashboard.py                  # Streamlit dashboard - Bloomberg institutional style

│                                 # Tab 5 "Performance" added in Version 9

├── run_paper_trader.py           # standalone script for GitHub Actions

├── test_performance.py           # standalone test harness for evaluation/performance.py

└── CONTEXT.md                    # this file

---

## Dashboard
Live: https://requantara-e4epzjkmfgtgb9almgh3le.streamlit.app
Built with Streamlit Community Cloud
Auto-updates when GitHub Actions commits new paper trading data
Style: Bloomberg meets modern fintech — dark navy, Inter font, JetBrains Mono for data
Tabs: Paper Trader, Strategy Results, Auto Selection, ML Analysis, Performance (new in V9)
Portfolio summary row (value, P&L, return %, best/worst performer) added above tabs
Note: Repo currently public for Streamlit — may go private later; redeploy/reboot from
share.streamlit.io if it ever goes dark after a visibility change

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
- Position check: skips BUY if position OR pending order exists (duplicate fix)
- **Stop loss enforcement (NEW)**: `check_stop_loss()` in `alpaca_executor.py` compares
  Alpaca's live `avg_entry_price` against current price before evaluating the model's
  signal. If drawdown from entry ≤ -5%, force-sells regardless of signal. This closed a
  gap where STOP_LOSS was applied in backtesting but never in live execution — NVDA and
  AAPL were both sitting past -5% live with no exit pending when this was caught.
- Secrets stored in GitHub Actions secrets (ALPACA_KEY, ALPACA_SECRET)
- Local testing: set via $env: in PowerShell

---

## Strategies Built
| Strategy | File | Key Parameters |
|----------|------|----------------|
| SMA Crossover | sma_crossover.py | fast=20, slow=50 |
| EMA Crossover | sma_crossover.py | fast=20, slow=50 |
| SMA + RSI Combined | sma_crossover.py | fast=20, slow=50, rsi_high=70 |
| Bollinger Bands | bollinger_signal.py | window=20, num_std=2 |
| Logistic Regression | ml_signal.py | 14 features, walk forward split |
| Random Forest | ml_signal.py | 100 trees, 14 features, walk forward split |

---

## ML Features (14 total)
EMA_gap, RSI, BB_position, Momentum_5, Momentum_10, Momentum_20,
Momentum_30, RSI_slope, Volatility_10, Volatility_20, SMA_gap,
Price_vs_SMA20, Price_vs_SMA50, BB_width

---

## Multi-Strategy Results (2015-2024, test period)
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

---

## ML Results Summary
Ticker  LR Sharpe   RF Sharpe   Better Model

TSLA    1.252       0.675       LR

AAPL    0.760       0.928       RF

NVDA    0.707       0.850       RF

IBM     0.680       0.887       RF

JPM     0.043       0.405       RF
Key finding: RF dominates stable data rich stocks, LR dominates volatile ones.
NN deferred — insufficient daily data (~625 training days) to outperform simpler models.
NN viable in Quantara NN project (minute data, 50k-120k samples per ticker).

---

## Optimization Results (EMA Crossover)
Ticker  Fast  Slow  Train Sharpe  Test Sharpe  Overfit Gap

NVDA    36    193   1.853         1.267         0.586

TSLA    7     21    2.218         0.445         1.773

AAPL    5     24    1.883         0.373         1.510

JPM     33    113   1.279         0.289         0.990
Key finding: TSLA and AAPL severely overfit. Only NVDA shows robust optimization.

---

## Auto Selection Results (Composite Score, 2015-2024 backtest)
Ticker  Best Strategy         Score   Sharpe  Return   MaxDD

TSLA    Logistic Regression   1.1713  1.018   236.07%  -36.60%

NVDA    EMA Crossover         1.1044  1.062   191.86%  -36.77%

IBM     Random Forest         1.0240  1.243   65.71%    -9.65%

AAPL    EMA Crossover         0.8541  0.917   67.43%   -13.09%

JPM     SMA Crossover         0.7898  0.874   45.92%   -13.03%

## Composite Score Formula
Score = (Sharpe × 0.5) + ((1 - abs(MaxDrawdown/100)) × 0.3) + (TotalReturn/100 × 0.2)
- Above 1.0 = genuinely good
- 0.5 to 1.0 = acceptable
- Below 0.5 = failing

## ⚠️ Why the auto-selector still favors rule-based strategies despite live underperformance
The auto-selector scores the 2015-2024 backtest only — it has zero awareness of the live
paper trading log. It is not measuring the same thing Version 9's live analytics measure,
and the two are not in conflict even when they appear to disagree:
- NVDA and JPM's strong backtest scores come from riding multi-year trends with very few
  trades — the exact same low-frequency, slow-to-exit behavior now showing up live as a
  48-day (NVDA) and 34-day (JPM) single-trade holding period.
- The 49-day live window (Apr 29 - Jun 16, 2026) is far too short to say whether current
  drawdowns are normal noise inside a longer trend (consistent with backtest behavior) or
  an actual trend break the backtest never saw. Don't read live underperformance as the
  backtest being "wrong" — they're different sample periods and the live one is still tiny.

---

## Paper Trading Performance (Apr 29 — Jun 16, 2026)
Ticker  Entry     Jun 16    Return   Signal      P&L ($2k)

NVDA    $213.17   $212.45   -0.3%    BUY         -$7

TSLA    $376.02   $411.15   +9.3%    SELL/HOLD   +$186

AAPL    $270.71   $296.42   +9.5%    BUY         +$190

JPM     $311.45   $319.40   +2.6%    SELL/HOLD   +$51

IBM     $233.04   $268.71   +15.3%   SELL/HOLD   +$306

Total                                             +$726 (+7.3%)
Portfolio path: peaked ~+10.8% in early June, dipped to ~+3.9% during a broad pullback,
recovered to +7.3% by Jun 16. Not linear — worth remembering when reading any single
snapshot.
Scheduler: GitHub Actions, daily 9PM UTC (2PM PDT), weekdays only
Log file: results/paper_trading_log.csv (auto committed to repo, cleaned/deduped/sorted
chronologically as of Jun 16 — watch for re-introduced merge conflict markers if pushing
around the same time as a scheduled Actions run)

---

## Version 9 — Performance Analytics (COMPLETE)
Full research report generated: `Quantara_Version9_Report.docx` (Apr 29 - Jun 16, 2026
reporting period). Covers all findings below in detail with supporting tables.

**Trade segmentation** (`evaluation/performance.py`): walks the CSV chronologically per
ticker, closes a "segment" on strategy change or BUY→SELL flip, tracks entry/exit
price/date, duration, P&L, P&L%, and OPEN/CLOSED status. Unrealized P&L on open positions
marked with `*` in the dashboard rather than shown as a separate number (avoids two
competing P&L figures).

**Closed trade counts, Apr 29 - Jun 16 (49 days):**
Ticker  Strategy              Closed Trades   Holding Period   Character

NVDA    EMA Crossover         0               48 days (open)   Buy & hold

JPM     SMA Crossover         1               34 days          Buy & hold

AAPL    EMA Crossover*        6               4-13 days        Moderate

TSLA    Logistic Regression   5               0-7 days         Active

IBM     Random Forest*        4               0-20 days        Active
*Switched strategy at least once during the period.

**Key finding — trade frequency divide:** Rule-based crossover strategies (NVDA, JPM)
barely trade once a position is open — slow 20/50-period signals are designed to filter
noise and are correspondingly slow to register anything short of a full trend reversal.
ML strategies (TSLA, IBM) trade far more often since they're trained to predict
next-period direction. Not a bug — different strategies solving different problems. Not
directly comparable on trade count.

**Key finding — ML momentum misread (TSLA & IBM):** Both LR (TSLA) and RF (IBM) exit
near local tops and re-enter after the best part of the move has passed:
- TSLA: ran $376→$445 (May 14 peak, +18.4%). Model exited May 2 at $390.82 (missed most
  of the run), re-entered May 14 at $445.27 right before the reversal, closed that
  re-entry at -$125.81 (-6.3%) on May 21.
- IBM: ran $233→$329.23 (Jun 3 peak, +41%). Model exited May 22 at $252.97 (missed most
  of the run), didn't re-enter until Jun 9 at $280.82 — well after the peak, on the way
  down. IBM's current drawdown from live peak is -18.4%, worst in the portfolio.
- Likely cause: RSI/BB_position features read sustained momentum as "overextension"
  rather than confirmed trend. Candidate fix: momentum-weighted feature or separate
  momentum-aware model variant for trending vs mean-reverting regimes.

**Win/Loss stats (16 closed trades, all tickers):**
Win Rate: 56.3%   Avg Win: +$74.48   Avg Loss: -$57.73

Biggest win: +$178.90 (IBM, May 2 - May 22)

Biggest loss: -$125.81 (TSLA, May 14 - May 21)

**Drawdown from live trading peak (not backtest peak):**
Ticker  Peak       Peak Date    Current   Current DD   Max DD

NVDA    $235.74    May 15       $212.45   -9.9%        -15.0%

TSLA    $445.27    May 14       $411.15   -7.7%        -14.3%

AAPL    $315.20    Jun 3        $296.42   -6.0%        -7.8%

JPM     $320.72    Jun 15       $319.40   -0.4%        -6.1%

IBM     $329.23    Jun 3        $268.71   -18.4%       -18.4%
IBM has shown zero recovery from its low — current DD equals max DD. All five tickers
are currently past the 5% stop loss threshold from their live peaks (this is what
surfaced the stop loss enforcement gap, see below).

**Signal quality score (next-day directional accuracy on BUY signals):**
Ticker  Signals Checked  Accuracy   Strategy Type

AAPL    27               55.6%      Rule-based (best in portfolio, still ~coin flip)

NVDA    35               45.7%      Rule-based

JPM     25               40.0%      Rule-based

TSLA    13               38.5%      ML (Logistic Regression)

IBM     19               36.8%      ML (Random Forest)
Important nuance: this metric is most diagnostic for TSLA/IBM since LR/RF are explicitly
trained on next-period direction — their sub-40% scores are a real, meaningful
underperformance finding and the quantitative confirmation of the momentum misread above.
It's less applicable to NVDA/JPM/AAPL since crossover strategies aren't designed to win
on a daily basis, only to ride confirmed multi-week trends.

**Weekly signal quality — tested, held back from dashboard.** Sample sizes too small
(2-5 signals/ticker/week) to be stable — swings between 0% and 100% week to week on pure
noise for most tickers. AAPL showed a loose upward trend (~50% late April → 100% by
mid-June) but flagged as preliminary only given sample size. Revisit with more data or a
rolling window instead of discrete week buckets. Function exists as
`signal_quality_weekly()` in `evaluation/performance.py` if needed later.

**Problem detection** (`detect_problems()`): scans switch flags, drawdown vs stop loss,
and signal accuracy (only flags accuracy if ≥10 signals checked, to avoid noise on small
samples). Dashboard groups flags by ticker with severity icons (🔴 CRITICAL / 🟡 WARNING
/ 🟢 OK) rather than one flat list — much easier to scan per ticker.

---

## Alpaca Orders / Live Position History
First real paper trades placed May 24, 2026: NVDA, AAPL, JPM (duplicate NVDA order from
manual testing was cancelled). Since then TSLA and IBM have both sold off through normal
signal flow (IBM sold Jun 16 @ $270.55, TSLA sold Jun 15 @ $411.77). As of Jun 16, only
NVDA and AAPL remain open — both past the -5% stop loss threshold, expected to force-sell
on the next scheduled run now that live stop loss enforcement is fixed (see Alpaca
Integration section above).

---

## Key Technical Decisions
- Data source: yfinance (free, clean, sufficient for daily backtesting)
- Returns tracked as actual dollar portfolio value not percentage multipliers
- One day signal lag (Position = Signal.shift(1)) prevents lookahead bias
- Stop loss: exit if price drops 5% below entry — now enforced in BOTH backtest AND live
  execution (live enforcement added Jun 2026, see Alpaca Integration)
- Position sizing: 50% of capital per trade (single stock)
- Sharpe annualized with sqrt(252)
- Walk forward split: first 50% train, second 50% test
- Alpaca execution: MarketOrderRequest, TimeInForce.DAY
- Duplicate order prevention: checks both open positions AND pending orders
- Trade segment definition (V9): closes on strategy change OR BUY→SELL flip within same
  strategy — tracked at ticker+strategy granularity, then rolled up to ticker-level
  summaries so both views are available without duplicating logic
- GitHub Actions commit order: commit local changes BEFORE pull --rebase, then push —
  avoids "cannot pull with rebase: unstaged changes" failures

---

## Key Research Findings
- EMA Crossover dominates momentum stocks (NVDA, AAPL) — in backtest
- LR dominates highly volatile stocks (TSLA) — in backtest
- RF dominates stable data rich stocks (IBM, AAPL) — in backtest
- Rule based beats ML when training data is limited
- RSI filter too restrictive on momentum stocks
- Bollinger Bands better suited for mean reverting assets
- More training data (2015 vs 2020) significantly improves ML results
- TSLA optimization severely overfits — unreliable parameters
- Composite score captures return AND safety simultaneously
- TSLA momentum misread: LR sees sustained momentum as overextension (confirmed live,
  see Version 9 section)
- IBM shows the same momentum misread as TSLA, at larger scale (+41% run missed)
- Live trade frequency reveals a structural divide: rule-based strategies barely trade
  once positioned; ML strategies trade often — different tradeoffs, not a bug
- Backtest auto-selector scores and live performance are measuring different time
  windows and are not contradictory even when they look like it (see callout above)

---

## Known Issues / Technical Debt
- IBM and AAPL have each switched strategy once live (IBM: RF ↔ Bollinger; AAPL: EMA ↔
  RF) — auto selector re-evaluates every run, no strategy lock-in period
- Timestamp format inconsistent in early CSV rows (cosmetic only, self-resolved once
  GitHub Actions took over)
- Optimizer only built for EMA Crossover — needs extending
- squeeze() needed throughout due to pandas version strictness
- NVDA EMA Crossover slow to exit declining positions — EMA lag (0 closed trades in 48
  days as of Jun 16)
- JPM SMA Crossover same lag issue — 1 trade in 34 days
- No strategy lock — auto selector picks differently each run
- TSLA/IBM momentum misread — ML models read sustained momentum as overextension,
  costing significant gains on both tickers' best moves (quantified in V9 report)
- Weekly signal quality too noisy at current sample sizes — held back from dashboard
- ~~Stop loss not enforced in live execution~~ — FIXED Jun 2026, see Alpaca Integration

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
  - Live stop loss enforcement fix
  - Full research report compiled (Quantara_Version9_Report.docx)
### Version 10 (planned) — Candidates, not yet prioritized
  - Momentum-aware feature or model variant for TSLA/IBM (highest priority candidate)
  - Strategy lock-in period to reduce AAPL/IBM switching instability
  - Revisit weekly signal quality with more data or rolling window
  - Quantara NN merger: separate daily (this project) and intraday (NN) systems, unified
    dashboard, SQLite when going live, fix Alpaca NN position sizing bug
  - Momentum Fix:
    - Ended up runing a Streak based system. The system works in that you have a stock close higher than it did on a previous day so
    - So much so that it makes a streak of days where it closed higher (or lower) than yesterday. Then we run a ADX and momentum accel. checks to see 
    - how strong the stock really is in terms of explosive growth over X days. 
  

---

## Related Project
Quantara NN — separate intraday trading system
- Minute data, MLP neural network, Nemotron LLM reasoning
- Alpaca live order execution
- Multi-agent pipeline
- Position sizing bug: stacks positions despite 2% limit
  Fix: check pending orders + open positions before buying (same pattern as this
  project's duplicate order fix)

---

## GitHub
Repo: https://github.com/titan-trials/REQuantara
Actions: https://github.com/titan-trials/REQuantara/actions
Local: C:\Users\logic\OneDrive\Desktop\REQuantara

## Libraries
- yfinance — market data
- pandas — data manipulation
- matplotlib — visualization
- scikit-learn — ML models
- openpyxl — Excel export
- streamlit — dashboard
- plotly — interactive charts
- alpaca-py — paper trading execution

## Notes from Plot Diagnostics
- TSLA: LR model misreads sustained momentum as overextension
  - Examined Apr 29 - May 8, 2026 initially, confirmed again through Jun 16 in V9 report
  - RSI staying near 70, BB_position climbing above 1.0
  - Model fires SELL during entire recovery from $372 to $445
  - Fix: add momentum-weighted feature or momentum-aware model
- IBM: same pattern, larger scale — missed $233→$329 run (+41%), currently -18.4% from
  live peak with zero recovery