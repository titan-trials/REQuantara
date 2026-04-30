# Quantara — Project Context Document
---

## Who I Am
Economics + Mathematics student at UC Santa Cruz. Goal is to become a 
Quantitative Developer or Researcher. This project serves as both a 
learning tool and a foundation for a real quant research platform. 
Intro to C++ background, learning Python through this project.

## What Quantara Is
A Python-based quantitative trading strategy simulator built from scratch.
Philosophy: understanding over performance. Every component is built to be 
fully understood before moving on. No black boxes.

## Current State
- Versions 1-7 complete. 
- Paper trader live and logging signals.
- Next session: check signal outcomes, review codebase

## Paper Trading - First Signals (2026-04-29)
| Ticker | Strategy | Price | Signal |
|--------|----------|-------|--------|
| NVDA | EMA Crossover | $213.17 | BUY |
| TSLA | Logistic Regression | $376.02 | BUY |
| AAPL | EMA Crossover | $270.71 | BUY |
| JPM | SMA Crossover | $311.45 | BUY |
| IBM | Random Forest | $233.04 | BUY |

## Auto Selection Results
| Ticker | Best Strategy | Score | Sharpe | Return | MaxDD |
|--------|--------------|-------|--------|--------|-------|
| TSLA | Logistic Regression | 1.1713 | 1.018 | 236.07% | -36.60% |
| NVDA | EMA Crossover | 1.1044 | 1.062 | 191.86% | -36.77% |
| IBM | Random Forest | 1.0240 | 1.243 | 65.71% | -9.65% |
| AAPL | EMA Crossover | 0.8541 | 0.917 | 67.43% | -13.09% |
| JPM | SMA Crossover | 0.7898 | 0.874 | 45.92% | -13.03% |

## Key Findings Across All Versions
- EMA Crossover dominates momentum stocks (NVDA, AAPL)
- LR dominates highly volatile stocks (TSLA)
- RF dominates stable data rich stocks (IBM)
- Rule based beats ML when data is limited
- Composite scoring captures return AND safety simultaneously
- RSI filter too restrictive on momentum stocks
- Bollinger Bands work better on mean reverting assets

## Composite Score Formula
Score = (Sharpe × 0.5) + ((1 - abs(MaxDrawdown/100)) × 0.3) + (TotalReturn/100 × 0.2)
- Above 1.0 = genuinely good strategy
- 0.5 to 1.0 = acceptable
- Below 0.5 = failing

## What To Build Next (Version 7)
- Real time data integration  
- Strategy retraining schedule
- Performance monitoring dashboard
- Live signal generation using auto selected strategies

## What To Do Next Session
1. Run paper trader again - check if signals changed
2. Compare prices to yesterday to validate BUY calls
3. Full codebase review before adding anything new
4. Scheduler and dashboard are Version 8

## ML Results So Far
- NVDA Logistic Regression Test Sharpe: 0.682
- Key finding: RSI positive weight, everything else negative
- Model learns NVDA continues when momentum builds, 
  pulls back when overextended

## What To Build Next
1. Extend ML to all tickers
2. Add Random Forest model
3. Compare ML vs rule based strategies formally
4. Begin Neural Network exploration

## Project Architecture
REQuantara/
├── data/
│   └── loader.py              # yfinance data fetching, returns clean df
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
│   └── metrics.py             # calculate_metrics (prints), get_metrics (returns dict)
├── plots/
│   └── visualizer.py          # plot_results(df) - 3 panel chart
├── strategy/
│   ├── runner.py              # run_all_strategies(tickers, ...) - multi stock/strategy
│   └── optimizer.py           # optimize_ema_crossover(ticker, ...) - walk forward
├── config.py                  # all settings live here
├── main.py                    # entry point
└── CONTEXT.md                 # this file

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

## Key Technical Decisions
- Data source: yfinance (clean, free, sufficient for backtesting)
- Returns tracked as actual dollar portfolio value, not percentage multipliers
- One day signal lag built into all strategies (Position = Signal.shift(1))
  to avoid lookahead bias
- Stop loss: exit if price drops 5% below entry price
- Position sizing: risk 50% of capital per trade (single stock)
- Sharpe Ratio is primary ranking metric, max drawdown as tiebreaker
- Sharpe annualized with sqrt(252)

## Strategies Built
| Strategy | File | Key Parameters |
|----------|------|----------------|
| SMA Crossover | sma_crossover.py | fast=20, slow=50 |
| EMA Crossover | sma_crossover.py | fast=20, slow=50 |
| SMA + RSI Combined | sma_crossover.py | fast=20, slow=50, rsi_high=70 |
| Bollinger Bands | bollinger_signal.py | window=20, num_std=2 |

## Latest Results (Multi-Stock, Multi-Strategy)
Ticker  Strategy            Return   Sharpe   MaxDD
NVDA    EMA Crossover       138.72%  0.973    -36.77%
NVDA    Bollinger Bands      21.47%  0.820     -9.94%
NVDA    SMA Crossover        88.41%  0.807    -39.69%
AAPL    EMA Crossover        44.30%  0.766    -13.20%
JPM     SMA Crossover        34.08%  0.755    -13.00%
NVDA    SMA+RSI Combined     59.09%  0.725    -37.44%
AAPL    SMA+RSI Combined     26.70%  0.706    -14.26%
AAPL    SMA Crossover        34.28%  0.703    -15.66%
TSLA    EMA Crossover       107.15%  0.702    -43.15%
JPM     SMA+RSI Combined     23.58%  0.629     -9.46%
TSLA    SMA Crossover        68.52%  0.606    -31.35%
TSLA    SMA+RSI Combined     30.50%  0.437    -27.70%
JPM     Bollinger Bands       9.49%  0.357     -8.44%
JPM     EMA Crossover        10.61%  0.305    -15.21%
TSLA    Bollinger Bands       7.86%  0.300     -8.45%
AAPL    Bollinger Bands       5.25%  0.288     -4.14%

## Optimization Results So Far
- NVDA EMA Crossover optimized: Fast=36, Slow=193
  - Train Sharpe: 1.853, Test Sharpe: 1.267
  - Overfit Gap: 0.586 (acceptable but monitor)
  - Still to run: TSLA, AAPL, JPM + other strategies

## Version Roadmap
### Version 1 Done - Single stock, SMA, basic backtest
### Version 2 Done - EMA, RSI, Bollinger, risk management
### Version 3 Done - Multi-strategy, multi-stock, Sharpe ranking
### Version 4 Done - Parameter optimization, walk forward testing
### Version 5 Done - Machine learning signal generation
### Version 6 Done - Autonomous strategy evaluation

## Known Issues / Technical Debt
- yfinance returns multi-level columns, fixed with df.columns.get_level_values(0)
  and df.columns.name = None in loader.py
- squeeze() needed when comparing columns due to pandas version strictness
- Optimizer currently only built for EMA Crossover — needs extending to 
  other strategies
- TSLA extremely difficult to beat with any strategy due to volatility
- RSI filter too restrictive on momentum stocks (NVDA, TSLA)

## What To Build Next
1. Extend optimizer to all strategies and all tickers
2. Build optimization results comparison table
3. Add CONTEXT.md update habit after each session
4. Begin Version 5 - ML signal generation (start with linear regression)

## How To Run
```powershell
# Activate environment
.\venv\Scripts\Activate.ps1

# Run full strategy comparison
python main.py

# Current main.py is set to run optimizer on NVDA
# To run strategy comparison instead, update main.py imports
```

## Libraries
- yfinance — market data
- pandas — data manipulation  
- matplotlib — visualization
- itertools — parameter combinations (optimizer)


