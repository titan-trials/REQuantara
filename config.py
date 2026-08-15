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

# ---------------------------------------------------------------------------
# EXECUTION REALISM (Version 15)
#
# TRANSACTION_COST_BPS: per-side cost in basis points. Alpaca charges no
# commission, so this stands in for bid-ask spread and market impact. It is NOT
# cosmetic: with zero costs the backtest silently favours high-turnover
# strategies, so it biases which strategy the auto-selector PICKS, not just the
# returns it reports. 5 bps (0.05%) per side is a conservative retail estimate
# for liquid US large-caps.
#
# EXECUTION_LAG: 1 means a decision made at today's close executes at
# tomorrow's open - which is what actually happens, since the job runs after
# the close and DAY market orders queue for the next session. Confirmed by real
# fills on 2026-08-14: submitted 08:00 UTC, filled 13:33 UTC (09:33 ET).
# Setting 0 restores same-bar execution and is only for isolating accounting
# behaviour in tests.
# ---------------------------------------------------------------------------
TRANSACTION_COST_BPS = 5.0
EXECUTION_LAG = 1

# Portfolio
INITIAL_CAPITAL = 10000  # Starting with $10,000