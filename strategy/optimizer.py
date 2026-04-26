import pandas as pd
import itertools
from data.loader import load_data
from indicators.ema import compute_ema
from signals.sma_crossover import generate_ema_crossover_signals
from backtest.engine import run_backtest
from evaluation.metrics import get_metrics

def optimize_ema_crossover(ticker, start, end, initial_capital, stop_loss, position_size):
    
    # Define parameter grid
    fast_range = range(5, 51)
    slow_range = range(20, 201)
    
    # Split data into train and test
    full_df = load_data(ticker, start, end)
    midpoint = len(full_df) // 2
    train_dates = full_df.index[:midpoint]
    test_dates = full_df.index[midpoint:]
    
    train_start = str(train_dates[0].date())
    train_end = str(train_dates[-1].date())
    test_start = str(test_dates[0].date())
    test_end = str(test_dates[-1].date())
    
    print(f"Train period: {train_start} to {train_end}")
    print(f"Test period : {test_start} to {test_end}")

    # Grid search on training data
    best_sharpe = -999
    best_params = None
    results = []

    for fast in fast_range:
        for slow in slow_range:
            if fast >= slow:
                continue
            try:
                df = load_data(ticker, train_start, train_end)
                df = compute_ema(df, fast)
                df = compute_ema(df, slow)
                df = generate_ema_crossover_signals(df, fast, slow)
                df = run_backtest(df, initial_capital, stop_loss, position_size)
                metrics = get_metrics(df, initial_capital)
                sharpe = metrics["Sharpe_Ratio"]

                results.append({
                    "fast": fast,
                    "slow": slow,
                    "sharpe": sharpe
                })

                if sharpe > best_sharpe:
                    best_sharpe = sharpe
                    best_params = (fast, slow)

            except:
                continue

    print(f"Best parameters found: Fast={best_params[0]}, Slow={best_params[1]}, Sharpe={best_sharpe}")
    # Test best parameters on unseen test data
    print(f"\nRunning best parameters on test data...")
    
    df_test = load_data(ticker, test_start, test_end)
    df_test = compute_ema(df_test, best_params[0])
    df_test = compute_ema(df_test, best_params[1])
    df_test = generate_ema_crossover_signals(df_test, best_params[0], best_params[1])
    df_test = run_backtest(df_test, initial_capital, stop_loss, position_size)
    test_metrics = get_metrics(df_test, initial_capital)

    print(f"\n--- OPTIMIZATION RESULTS: {ticker} ---")
    print(f"Best Parameters    : Fast={best_params[0]}, Slow={best_params[1]}")
    print(f"Train Sharpe       : {best_sharpe}")
    print(f"Test Sharpe        : {test_metrics['Sharpe_Ratio']}")
    print(f"Test Total Return  : {test_metrics['Total_Return']}%")
    print(f"Test Max Drawdown  : {test_metrics['Max_Drawdown']}%")
    print(f"Overfit Gap        : {round(best_sharpe - test_metrics['Sharpe_Ratio'], 3)}")
    
    return {
        "best_params": best_params,
        "train_sharpe": best_sharpe,
        "test_metrics": test_metrics,
        "all_results": pd.DataFrame(results)
    }
