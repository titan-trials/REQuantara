import pandas as pd
from data.loader import load_data
from indicators.moving_average import compute_sma
from indicators.ema import compute_ema
from indicators.rsi import compute_rsi
from indicators.bollinger import compute_bollinger_bands
from signals.sma_crossover import generate_crossover_signals, generate_ema_crossover_signals, generate_combined_signals
from signals.bollinger_signal import generate_bollinger_signals
from backtest.engine import run_backtest
from evaluation.metrics import get_metrics
from strategy.ml_signal import run_ml_strategy, run_rf_strategy

def compute_composite_score(metrics):
    sharpe = metrics["Sharpe_Ratio"]
    drawdown = abs(metrics["Max_Drawdown"]) / 100
    total_return = metrics["Total_Return"] / 100

    # Please Note score is on a scale roughly 0 to 2, with higher being better
    # Sharpe contributes 50%, Drawdown contributes 30%, Total Return contributes(Raw Return) 20%
    score = (sharpe * 0.5) + ((1 - drawdown) * 0.3) + (total_return * 0.2)
    return round(score, 4)

def evaluate_rule_based(ticker, test_start, test_end, initial_capital, stop_loss, position_size):
    strategies = [
        {
            "name": "SMA Crossover",
            "build": lambda df: [compute_sma(df, 20), compute_sma(df, 50)][-1],
            "signal": lambda df: generate_crossover_signals(df, 20, 50)
        },
        {
            "name": "EMA Crossover",
            "build": lambda df: [compute_ema(df, 20), compute_ema(df, 50)][-1],
            "signal": lambda df: generate_ema_crossover_signals(df, 20, 50)
        },
        {
            "name": "SMA + RSI",
            "build": lambda df: [compute_sma(df, 20), compute_sma(df, 50), compute_rsi(df)][-1],
            "signal": lambda df: generate_combined_signals(df, 20, 50)
        },
        {
            "name": "Bollinger Bands",
            "build": lambda df: compute_bollinger_bands(df),
            "signal": generate_bollinger_signals
        }
    ]

    results = []
    for strategy in strategies:
        try:
            df = load_data(ticker, test_start, test_end)
            df = strategy["build"](df)
            df = strategy["signal"](df)
            df = run_backtest(df, initial_capital, stop_loss, position_size)
            metrics = get_metrics(df, initial_capital)
            metrics["Strategy"] = strategy["name"]
            metrics["Score"] = compute_composite_score(metrics)
            results.append(metrics)
        except:
            continue

    return results

def evaluate_ml(ticker, start, end, initial_capital, stop_loss, position_size):
    results = []

    try:
        _, lr_metrics, _, _, _ = run_ml_strategy(
            ticker, start, end, initial_capital, stop_loss, position_size
        )
        lr_metrics["Strategy"] = "Logistic Regression"
        lr_metrics["Score"] = compute_composite_score(lr_metrics)
        results.append(lr_metrics)
    except:
        pass

    try:
        _, rf_metrics, _, _ = run_rf_strategy(
            ticker, start, end, initial_capital, stop_loss, position_size
        )
        rf_metrics["Strategy"] = "Random Forest"
        rf_metrics["Score"] = compute_composite_score(rf_metrics)
        results.append(rf_metrics)
    except:
        pass

    return results

def auto_select(tickers, start, end, initial_capital, stop_loss, position_size):
    # Test period is second half of date range
    full_df = load_data(tickers[0], start, end)
    midpoint = len(full_df) // 2
    test_start = str(full_df.index[midpoint].date())
    test_end = str(full_df.index[-1].date())

    print(f"Evaluating on test period: {test_start} to {test_end}")

    selections = []

    for ticker in tickers:
        print(f"\nEvaluating {ticker}...")
        all_results = []

        rule_results = evaluate_rule_based(
            ticker, test_start, test_end, initial_capital, stop_loss, position_size
        )
        all_results.extend(rule_results)

        ml_results = evaluate_ml(
            ticker, start, end, initial_capital, stop_loss, position_size
        )
        all_results.extend(ml_results)

        results_df = pd.DataFrame(all_results)
        best = results_df.loc[results_df["Score"].idxmax()]

        selections.append({
            "Ticker": ticker,
            "Best_Strategy": best["Strategy"],
            "Score": best["Score"],
            "Sharpe": best["Sharpe_Ratio"],
            "Total_Return": best["Total_Return"],
            "Max_Drawdown": best["Max_Drawdown"]
        })

        print(f"Winner: {best['Strategy']} (Score: {best['Score']})")

    final_df = pd.DataFrame(selections).set_index("Ticker")
    return final_df