import pandas as pd
from indicators.moving_average import compute_sma
from indicators.ema import compute_ema
from indicators.rsi import compute_rsi
from indicators.bollinger import compute_bollinger_bands
from signals.sma_crossover import generate_crossover_signals, generate_ema_crossover_signals, generate_combined_signals
from signals.bollinger_signal import generate_bollinger_signals
from strategy.ml_signal import build_features, build_target
from sklearn.linear_model import LogisticRegression
from sklearn.ensemble import RandomForestClassifier
from sklearn.preprocessing import StandardScaler
from datetime import datetime, timedelta
from data.loader import load_data
from strategy.auto_selector import auto_select, compute_composite_score
from evaluation.metrics import get_metrics
from backtest.engine import run_backtest
import os
from strategy.alpaca_executor import get_client, execute_signal


def get_recent_data(ticker, lookback_days=300):
    end = datetime.today().strftime("%Y-%m-%d")
    start = (datetime.today() - timedelta(days=lookback_days)).strftime("%Y-%m-%d")
    df = load_data(ticker, start, end)
    return df

def log_signals(signals, log_file="results/paper_trading_log.csv"):
    os.makedirs("results", exist_ok=True)
    signals_df = pd.DataFrame(signals)
    signals_df["Timestamp"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    if os.path.exists(log_file):
        existing = pd.read_csv(log_file)
        updated = pd.concat([existing, signals_df], ignore_index=True)
    else:
        updated = signals_df
    
    updated.to_csv(log_file, index=False)
    print(f"Signals logged to: {log_file}")

def generate_current_signal(df, strategy_name, initial_capital, stop_loss, position_size):
    try:
        if strategy_name == "SMA Crossover":
            df = compute_sma(df, 20)
            df = compute_sma(df, 50)
            df = generate_crossover_signals(df, 20, 50)
            return int(df["Signal"].iloc[-1])

        elif strategy_name == "EMA Crossover":
            df = compute_ema(df, 20)
            df = compute_ema(df, 50)
            df = generate_ema_crossover_signals(df, 20, 50)
            return int(df["Signal"].iloc[-1])

        elif strategy_name == "SMA + RSI":
            df = compute_sma(df, 20)
            df = compute_sma(df, 50)
            df = compute_rsi(df)
            df = generate_combined_signals(df, 20, 50)
            return int(df["Signal"].iloc[-1])

        elif strategy_name == "Bollinger Bands":
            df = compute_bollinger_bands(df)
            df = generate_bollinger_signals(df)
            return int(df["Signal"].iloc[-1])

        elif strategy_name == "Logistic Regression":
            df = build_features(df)
            df = build_target(df)
            df = df.dropna()
            feature_cols = [
                "EMA_gap", "RSI", "BB_position", "Momentum_5", "Momentum_10",
                "Momentum_20", "Momentum_30", "RSI_slope", "Volatility_10",
                "Volatility_20", "SMA_gap", "Price_vs_SMA20", "Price_vs_SMA50",
                "BB_width"
            ]
            X = df[feature_cols]
            y = df["Target"]
            midpoint = len(df) // 2
            scaler = StandardScaler()
            X_scaled = scaler.fit_transform(X)
            model = LogisticRegression()
            model.fit(X_scaled[:midpoint], y[:midpoint])
            today_signal = model.predict(X_scaled[-1:])[0]
            return int(today_signal)

        elif strategy_name == "Random Forest":
            df = build_features(df)
            df = build_target(df)
            df = df.dropna()
            feature_cols = [
                "EMA_gap", "RSI", "BB_position", "Momentum_5", "Momentum_10",
                "Momentum_20", "Momentum_30", "RSI_slope", "Volatility_10",
                "Volatility_20", "SMA_gap", "Price_vs_SMA20", "Price_vs_SMA50",
                "BB_width"
            ]
            X = df[feature_cols]
            y = df["Target"]
            midpoint = len(df) // 2
            model = RandomForestClassifier(n_estimators=100, random_state=42)
            model.fit(X.iloc[:midpoint], y.iloc[:midpoint])
            today_signal = model.predict(X.iloc[-1:])[0]
            return int(today_signal)

    except Exception as e:
        print(f"Signal generation failed: {e}")
        return 0

def run_paper_trader(tickers, start, end, initial_capital, stop_loss, position_size):
    print(f"\n{'='*50}")
    print(f"QUANTARA PAPER TRADER")
    print(f"Date: {datetime.today().strftime('%Y-%m-%d')}")
    print(f"{'='*50}")

    # Get best strategy per ticker from historical analysis
    print("\nRunning auto selection to find best strategies...")
    selections = auto_select(tickers, start, end, initial_capital, stop_loss, position_size)

    signals = []

    for ticker in tickers:
        print(f"\n--- {ticker} ---")
        best_strategy = selections.loc[ticker, "Best_Strategy"]
        print(f"Selected Strategy: {best_strategy}")

        # Fetch recent real data
        df_recent = get_recent_data(ticker)

        # Generate today's signal using best strategy
        signal = generate_current_signal(df_recent, best_strategy, 
                                        initial_capital, stop_loss, position_size)

        current_price = df_recent["Close"].squeeze().iloc[-1]
        
        print(f"Current Price     : ${current_price:.2f}")
        print(f"Today's Signal    : {'BUY' if signal == 1 else 'SELL/HOLD'}")

        # Execute on Alpaca
        try:
            client = get_client()
            execute_signal(client, ticker, signal, current_price)
        except Exception as e:
            print(f"[{ticker}] Alpaca execution failed: {e}")

        signals.append({
            "Ticker": ticker,
            "Strategy": best_strategy,
            "Signal": signal,
            "Price": round(current_price, 2),
            "Action": "BUY" if signal == 1 else "SELL/HOLD"
        })

    log_signals(signals)
    return pd.DataFrame(signals).set_index("Ticker")