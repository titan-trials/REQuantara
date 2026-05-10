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
multi-strategy, multi-stock analysis with ML signal generation and
live paper trading via automated GitHub Actions scheduler.

---

## Current State
- Versions 1-7 complete
- Paper trader live and logging signals automatically via GitHub Actions
- Scheduler runs daily at 9PM UTC (2PM PDT) on weekdays
- Next: Version 8 — performance dashboard and codebase cleanup

---

## How To Run
```powershell
# Activate environment
.\venv\Scripts\Activate.ps1

# Run modes by changing MODE in main.py
# Options: "compare", "optimize", "ml", "rf", "auto", "paper"
python main.py

# Run automated paper trader directly
python run_paper_trader.py
```

---

## Project Architecture
REQuantara/
├── .github/
│   └── workflows/
│       └── paper_trader.yml   # GitHub Actions scheduler - runs daily 9PM UTC
├── data/
│   └── loader.py              # yfinance data fetching, cleans multi-level columns
├── indicators/
│   ├── moving_average.py      # compute_sma(df, window)
│   ├── ema.py                 # compute_ema(df, window)
│   ├── rsi.py                 # compute_rsi(df, window=14)
│   └── bollinger.py           # compute_bollinger_bands(df, window=20, num_std=2)
├── signals/
│   ├── sma_crossover.py       # generate_signals, generate_crossover_signals,
│   │                          # generate_ema_crossover_signals, generate_combined_signals
│   └── bollinger_signal.py    # generate_bollinger_signals
├── backtest/
│   └── engine.py              # run_backtest(df, initial_capital, stop_loss, position_size)
├── evaluation/
│   ├── metrics.py             # calculate_metrics (prints), get_metrics (returns dict)
│   └── exporter.py            # export_results, export_optimization - saves to Excel
├── plots/
│   └── visualizer.py          # plot_results(df) - 3 panel chart (returns, price, RSI)
├── strategy/
│   ├── runner.py              # run_all_strategies(tickers) - multi stock/strategy grid
│   ├── optimizer.py           # optimize_ema_crossover, optimize_all_tickers
│   ├── ml_signal.py           # run_ml_strategy (LR), run_rf_strategy (RF)
│   │                          # build_features (14 features), build_target
│   ├── auto_selector.py       # auto_select - picks best strategy per ticker
│   │                          # compute_composite_score, evaluate_rule_based, evaluate_ml
│   └── paper_trader.py        # run_paper_trader - live signals on current data
│                              # get_recent_data, generate_current_signal, log_signals
├── results/                   # Excel exports and paper trading log
│   └── paper_trading_log.csv  # auto updated by GitHub Actions
├── config.py                  # all settings
├── main.py                    # entry point with MODE switch
├── run_paper_trader.py        # standalone script for GitHub Actions
└── CONTEXT.md                 # this file

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
```

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

---

## Optimization Results (EMA Crossover)
Ticker  Fast  Slow  Train Sharpe  Test Sharpe  Overfit Gap
NVDA    36    193   1.853         1.267         0.586
TSLA    7     21    2.218         0.445         1.773
AAPL    5     24    1.883         0.373         1.510
JPM     33    113   1.279         0.289         0.990
Key finding: TSLA and AAPL severely overfit. Only NVDA shows robust optimization.

---

## Auto Selection Results (Composite Score)
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

---

## Paper Trading Log
Scheduler: GitHub Actions, daily 9PM UTC (2PM PDT), weekdays only
Log file: results/paper_trading_log.csv (auto committed to repo)
Date        NVDA    TSLA    AAPL    JPM     IBM
Apr 29      213.17  376.02  270.71  311.45  233.04  ALL BUY
Apr 30      209.25  372.80  270.17  309.25  227.10  IBM SELL
May 2       198.45  390.82  280.14  312.47  232.20  TSLA SELL
May 4       198.45  390.82  280.14  312.47  232.20  TSLA SELL (same prices - weekend)
May 5       198.48  392.51  276.83  307.65  229.48  TSLA SELL

Signal accuracy so far:
- TSLA SELL at $390 — correct, held above that level
- AAPL BUY — correct, recovered from Apr 30 dip
- NVDA BUY — incorrect, continued declining from $213 to $198
- JPM BUY — mixed, slight decline
- IBM — strategy switching between RF and Bollinger (known issue)

---

## Key Technical Decisions
- Data source: yfinance (free, clean, sufficient for daily backtesting)
- Returns tracked as actual dollar portfolio value not percentage multipliers
- One day signal lag (Position = Signal.shift(1)) prevents lookahead bias
- Stop loss: exit if price drops 5% below entry
- Position sizing: 50% of capital per trade (single stock)
- Sharpe annualized with sqrt(252)
- Walk forward split: first 50% train, second 50% test

---

## Key Research Findings
- EMA Crossover dominates momentum stocks (NVDA, AAPL)
- LR dominates highly volatile stocks (TSLA)
- RF dominates stable data rich stocks (IBM, AAPL)
- Rule based beats ML when training data is limited
- RSI filter too restrictive on momentum stocks
- Bollinger Bands better suited for mean reverting assets
- More training data (2015 vs 2020) significantly improves ML results
- TSLA optimization severely overfits — unreliable parameters
- Composite score captures return AND safety simultaneously

---

## Known Issues / Technical Debt
- IBM strategy switches between RF and Bollinger between runs — 
  auto selector re-evaluates every run instead of locking in strategy
- Timestamp format inconsistent in paper_trading_log.csv
  (early entries: M/D/YYYY H:MM, later: YYYY-MM-DD HH:MM:SS)
- Optimizer only built for EMA Crossover — needs extending to other strategies
- squeeze() needed throughout due to pandas version strictness
- yfinance multi-level columns fixed in loader.py but fragile
- NVDA EMA Crossover stuck on BUY despite price declining — EMA lag issue
- No strategy lock — auto selector picks differently each run

---

## Version Roadmap
### Version 1 (Done) — Single stock, SMA, basic backtest
### Version 2 (Done) — EMA, RSI, Bollinger, risk management
### Version 3 (Done) — Multi-strategy, multi-stock, Sharpe ranking
### Version 4 (Done) — Parameter optimization, walk forward testing
### Version 5 (Done) — ML signal generation (LR + RF)
### Version 6 (Done) — Autonomous strategy selection, composite scoring
### Version 7 (Done) — Paper trading, GitHub Actions scheduler
### Version 8 (planned) — Performance dashboard, codebase cleanup
  - Fix strategy lock issue
  - Fix timestamp consistency
  - Streamlit dashboard for paper trading visualization
  - Strategy retraining schedule
  - Codebase review and refactor

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

## Notes from Plot Diagnostics
- TSLA is having issues relating to momentum. Examined from Apr. 29, - May 8th /2026
  - model keeps misreading momentum as overextension rather than sustained momentum
  - Might be worth adding a spefific momentum checker that is forcibly weighed more due to how momentum heavy TSLA is