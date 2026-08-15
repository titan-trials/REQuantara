"""
Walk-forward validation: does NVDA-RF / AAPL-LR with momentum features (Mom_accel, ADX_14)
actually beat their currently-live default EMA Crossover (20/50) across MULTIPLE
shifted test windows, not just the single 50/50 split used so far?
"""

import pandas as pd
from data.loader import load_data
from indicators.ema import compute_ema
from signals.sma_crossover import generate_ema_crossover_signals
from backtest.engine import run_backtest
from evaluation.metrics import get_metrics
from strategy.ml_signal import run_ml_strategy, run_rf_strategy
from strategy.auto_selector import compute_composite_score

INITIAL_CAPITAL = 10000
STOP_LOSS = 0.05
# Was hardcoded to 0.50. Now pulls the shared constant so this script can never
# silently drift from the rest of the backtest suite. NOTE: any results from
# this script recorded in CONTEXT.md before Aug 2026 were produced at 0.50 with
# whole-share flooring and are NOT comparable to new runs.
from config import BACKTEST_POSITION_SIZE as POSITION_SIZE
FULL_START = "2015-01-01"
FULL_END = "2024-01-01"

WINDOW_ENDS = ["2024-01-01", "2023-01-01", "2022-01-01", "2021-01-01"]


def run_default_ema(ticker, start, end):
    df = load_data(ticker, start, end)
    df = compute_ema(df, 20)
    df = compute_ema(df, 50)
    df = generate_ema_crossover_signals(df, 20, 50)
    df = run_backtest(df, INITIAL_CAPITAL, STOP_LOSS, POSITION_SIZE)
    metrics = get_metrics(df, INITIAL_CAPITAL)
    metrics["Score"] = compute_composite_score(metrics)
    return metrics


def run_window(ticker, model_fn, end_date):
    _, metrics, *_ = model_fn(ticker, FULL_START, end_date, INITIAL_CAPITAL, STOP_LOSS, POSITION_SIZE)
    metrics["Score"] = compute_composite_score(metrics)
    return metrics


results = []

for ticker, model_fn, model_name in [
    ("NVDA", run_rf_strategy, "Random Forest (16-feat)"),
    ("AAPL", run_ml_strategy, "Logistic Regression (16-feat)"),
]:
    for end_date in WINDOW_ENDS:
        ema_metrics = run_default_ema(ticker, FULL_START, end_date)
        ml_metrics = run_window(ticker, model_fn, end_date)

        results.append({
            "Ticker": ticker,
            "Window_End": end_date,
            "EMA_Score": ema_metrics["Score"],
            "EMA_Sharpe": ema_metrics["Sharpe_Ratio"],
            f"{model_name}_Score": ml_metrics["Score"],
            f"{model_name}_Sharpe": ml_metrics["Sharpe_Ratio"],
            "ML_Wins": ml_metrics["Score"] > ema_metrics["Score"]
        })

results_df = pd.DataFrame(results)
print(results_df.to_string())
print()
print("Win rate of ML over default EMA Crossover across windows:")
print(results_df.groupby("Ticker")["ML_Wins"].mean())