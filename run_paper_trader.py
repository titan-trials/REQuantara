import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from strategy.paper_trader import run_paper_trader
from config import (
    TICKERS, START, END, INITIAL_CAPITAL, STOP_LOSS,
    BACKTEST_POSITION_SIZE,
)

if __name__ == "__main__":
    # BACKTEST_POSITION_SIZE is correct here even though this script places real
    # (paper) orders. The value passed in is only used to score candidate
    # strategies inside auto_select, which is a pure backtest. The size of the
    # actual Alpaca order is set by LIVE_POSITION_SIZE, read directly by
    # strategy/alpaca_executor.py.
    print("Quantara Paper Trader - Automated Run")
    signals = run_paper_trader(TICKERS, START, END, INITIAL_CAPITAL, STOP_LOSS, BACKTEST_POSITION_SIZE)
    print("\n--- TODAY'S SIGNALS ---")
    print(signals.to_string())