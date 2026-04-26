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

def build_sma_indicators(df):
    df = compute_sma(df, 20)
    df = compute_sma(df, 50)
    return df

def build_ema_indicators(df):
    df = compute_ema(df, 20)
    df = compute_ema(df, 50)
    return df

def build_combined_indicators(df):
    df = compute_sma(df, 20)
    df = compute_sma(df, 50)
    df = compute_rsi(df)
    return df

def build_bollinger_indicators(df):
    df = compute_bollinger_bands(df)
    df = compute_rsi(df)
    return df

STRATEGIES = [
    {
        "name": "SMA Crossover",
        "indicators": build_sma_indicators,
        "signal": lambda df: generate_crossover_signals(df, 20, 50)
    },
    {
        "name": "EMA Crossover",
        "indicators": build_ema_indicators,
        "signal": lambda df: generate_ema_crossover_signals(df, 20, 50)
    },
    {
        "name": "SMA + RSI Combined",
        "indicators": build_combined_indicators,
        "signal": lambda df: generate_combined_signals(df, 20, 50)
    },
    {
        "name": "Bollinger Bands",
        "indicators": build_bollinger_indicators,
        "signal": generate_bollinger_signals
    }
]

def run_all_strategies(ticker, start, end, initial_capital, stop_loss, position_size):
    results = []

    for strategy in STRATEGIES:
        df = load_data(ticker, start, end)
        df = strategy["indicators"](df)
        df = strategy["signal"](df)
        df = run_backtest(df, initial_capital, stop_loss, position_size)
        metrics = get_metrics(df, initial_capital)
        metrics["Strategy"] = strategy["name"]
        results.append(metrics)

    results_df = pd.DataFrame(results)
    results_df = results_df.set_index("Strategy")
    results_df = results_df.sort_values("Sharpe_Ratio", ascending=False)
    return results_df