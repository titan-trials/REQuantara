from strategy.runner import run_all_strategies
from strategy.optimizer import optimize_all_tickers
from evaluation.exporter import export_results
from strategy.ml_signal import run_ml_strategy
from config import TICKERS, START, END, INITIAL_CAPITAL, STOP_LOSS, POSITION_SIZE

'''
# Run strategy comparison
results = run_all_strategies(TICKERS, START, END, INITIAL_CAPITAL, STOP_LOSS, POSITION_SIZE)
print(results.to_string())
export_results(results, "strategy_comparison")

# Optimize EMA crossover across all tickers
opt_summary = optimize_all_tickers(TICKERS, START, END, INITIAL_CAPITAL, STOP_LOSS, POSITION_SIZE)
print(opt_summary.to_string())
export_results(opt_summary, "optimization_summary")
'''

df_test, metrics, model, feature_cols, scaler = run_ml_strategy(
    "NVDA", START, END, INITIAL_CAPITAL, STOP_LOSS, POSITION_SIZE
)


import pandas as pd
coefficients = pd.Series(model.coef_[0], index=feature_cols)
print("\nModel Feature Weights:")
print(coefficients.sort_values(ascending=False))