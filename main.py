from strategy.runner import run_all_strategies
from strategy.optimizer import optimize_ema_crossover
from evaluation.exporter import export_results, export_optimization
from config import TICKERS, START, END, INITIAL_CAPITAL, STOP_LOSS, POSITION_SIZE

# Run strategy comparison
results = run_all_strategies(TICKERS, START, END, INITIAL_CAPITAL, STOP_LOSS, POSITION_SIZE)
print(results.to_string())
export_results(results, "strategy_comparison")

# Run optimizer on NVDA
opt_result = optimize_ema_crossover("NVDA", START, END, INITIAL_CAPITAL, STOP_LOSS, POSITION_SIZE)
export_optimization(opt_result, "NVDA")