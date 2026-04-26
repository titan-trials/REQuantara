from strategy.runner import run_all_strategies
from config import TICKER, START, END, INITIAL_CAPITAL, STOP_LOSS, POSITION_SIZE

results = run_all_strategies(TICKER, START, END, INITIAL_CAPITAL, STOP_LOSS, POSITION_SIZE)
print(results.to_string())