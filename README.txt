# Quantara — Quantitative Trading Strategy Simulator

## What is Quantara?
Quantara is a Python-based quantitative trading strategy simulator built from the ground up.

The goal is to deeply understand how trading strategies are
constructed, tested, and evaluated  one component at a time.

## Philosophy
**Understanding over performance.**
Every component is built to be fully understood before moving on. No black boxes.
All strategies must be explained 

## Architecture
REQuantara/
│
├── data/
│   └── loader.py            # Downloads and cleans price data
├── indicators/
│   └── moving_average.py    # SMA and future indicator calculations
├── signals/
│   └── sma_crossover.py     # Buy/sell rule logic
├── backtest/
│   └── engine.py            # Simulates trades, tracks cash and P&L
├── evaluation/
│   └── metrics.py           # Return, drawdown, win rate etc.
├── plots/
│   └── visualizer.py        # All chart and plot logic
├── main.py                  # Ties everything together, runs the sim
└── requirements.txt         # Project dependencies

## Version Roadmap

### Version 1 — Foundation (Completed) 
- 1 stock: NVDA
- 1 indicator: Simple Moving Average (SMA)
- 1 rule: Buy when Close > SMA, Sell when Close < SMA
- 1 backtest: Strategy vs Buy-and-Hold
- Data source: yfinance

### Version 2 — Expanding (Completed)
- Multiple indicators (EMA, RSI, Bollinger Bands)
- Multiple signal rules and combinations
- Basic risk management (stop loss, position sizing)

### Version 3 — Portfolio Level (Completed)
- Bollinger Bands indicator
- Run multiple strategies simultaneously
- Portfolio-level performance tracking
- Strategy comparison framework
- Sharpe Ratio metric
- Multiple stocks simultaneously
    NVDA — momentum/AI
    TSLA — volatile momentum  
    AAPL — stable growth
    JPM  — cyclical/mean reverting

### Version 4 — Intelligence Layer (Complete)
- Parameter optimization with walk forward testing
- Grid search across all tickers
- Overfit gap measurement
- Excel export for all results

### Version 5 — Machine Learning (Complete)
- Logistic Regression signal generation
- Random Forest signal generation  
- Feature engineering (14 features)
- Walk forward train/test split
- Extended date range to 2015 for more training data
- Key finding: RF dominates stable stocks, LR dominates volatile ones
- NN deferred — insufficient daily data to outperform simpler models

### Version 6 — Autonomous Evaluation (Complete)
- Composite scoring system (Sharpe 50%, Drawdown 30%, Return 20%)
- Auto selector runs all strategies per ticker
- Picks best strategy autonomously per ticker
- Final selections:
    NVDA → EMA Crossover (Score: 1.1044)
    TSLA → Logistic Regression (Score: 1.1713)
    AAPL → EMA Crossover (Score: 0.8541)
    JPM  → SMA Crossover (Score: 0.7898)
    IBM  → Random Forest (Score: 1.0240)

### Version 7 — Live Trading Readiness (Planned)
- Paper trading simulation
- Real time data integration
- Strategy retraining schedule
- Performance monitoring dashboard

## Setup Instructions

### 1. Clone or open the project folder
C:\Users\logic\OneDrive\Desktop\REQuantara
### 2. Create and activate virtual environment

```powershell
python -m venv venv
.\venv\Scripts\Activate.ps1
```
> Note: If activation is blocked, run this first:
> `Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser`

### 3. Install dependencies
```powershell
pip install -r requirements.txt
```

## How to Run
```powershell
python main.py
```

## Dependencies
Check requirements.txt

---
*Quantara is a long term project. It will grow.*

