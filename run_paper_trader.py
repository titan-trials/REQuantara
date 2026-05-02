import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from strategy.paper_trader import run_paper_trader
from config import TICKERS, START, END, INITIAL_CAPITAL, STOP_LOSS, POSITION_SIZE

if __name__ == "__main__":
    print("Quantara Paper Trader - Automated Run")
    signals = run_paper_trader(TICKERS, START, END, INITIAL_CAPITAL, STOP_LOSS, POSITION_SIZE)
    print("\n--- TODAY'S SIGNALS ---")
    print(signals.to_string())