# Quantara Configuration

# Alpaca
import os
ALPACA_KEY = os.getenv("ALPACA_KEY")
ALPACA_SECRET = os.getenv("ALPACA_SECRET")
ALPACA_BASE_URL = "https://paper-api.alpaca.markets"

TICKERS = ["NVDA", "TSLA", "AAPL", "JPM", "IBM"]
START = "2015-01-01"
END = "2024-01-01"
FAST_WINDOW = 20
SLOW_WINDOW = 50
EMA_FAST = 20
EMA_SLOW = 50

# Risk Management
STOP_LOSS = 0.05       # Exit if position drops 5% from entry

# ---------------------------------------------------------------------------
# POSITION SIZING - TWO SEPARATE CONSTANTS, DO NOT MERGE THEM AGAIN
#
# These two numbers look like they mean the same thing. They do not.
#
# BACKTEST_POSITION_SIZE is used by backtest/engine.py, which simulates ONE
# ticker at a time against its own private INITIAL_CAPITAL. There is no
# competition for capital between tickers, so 1.0 simply means "when the
# strategy says to be in a trade, be fully in that trade." Anything below 1.0
# just parks part of that ticker's dedicated capital in cash for no modelled
# reason, which drags returns down without modelling any real constraint.
#
# LIVE_POSITION_SIZE is used by strategy/alpaca_executor.py and is a fraction
# of TOTAL ACCOUNT EQUITY, with all five tickers drawing on the same pool.
# 5 tickers x 0.20 = 100% invested, no margin. Setting this to 0.50 means
# 5 x 0.50 = 250% gross exposure funded by Alpaca margin - that is the
# ~1.91x leverage bug found in Version 11.
#
# Rationale for 0.20: the "2% rule" is risk per trade, not position size.
# position size = risk% / stop distance%. With a 5% nominal stop (~9% in gap
# scenarios), 2% risk per trade implies a 20-22% position.
# ---------------------------------------------------------------------------
BACKTEST_POSITION_SIZE = 1.0   # fraction of ONE ticker's own capital, single-ticker sim
LIVE_POSITION_SIZE = 0.20      # fraction of TOTAL account equity, shared across 5 tickers

# Portfolio
INITIAL_CAPITAL = 10000  # Starting with $10,000