# Quantara Configuration
# Change settings here to run different backtests

TICKERS = ["NVDA", "TSLA", "AAPL", "JPM"]
START = "2020-01-01"
END = "2024-01-01"
FAST_WINDOW = 20
SLOW_WINDOW = 50
EMA_FAST = 20
EMA_SLOW = 50

# Risk Management
STOP_LOSS = 0.05       # Exit if position drops 5% from entry
POSITION_SIZE = 0.50   # Risk only 2% of portfolio per trade

# Portfolio
INITIAL_CAPITAL = 10000  # Starting with $10,000