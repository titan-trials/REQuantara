import pandas as pd
from indicators.moving_average import compute_sma
from indicators.ema import compute_ema
from indicators.rsi import compute_rsi
from indicators.bollinger import compute_bollinger_bands
from signals.sma_crossover import generate_crossover_signals, generate_ema_crossover_signals, generate_combined_signals
from signals.bollinger_signal import generate_bollinger_signals
from strategy.ml_signal import FEATURE_COLS, build_features, build_target
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
from evaluation.account_log import log_account_state


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
            
            X = df[FEATURE_COLS]
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

            X = df[FEATURE_COLS]
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
            order_result, exit_reason = execute_signal(client, ticker, signal, current_price)
        except Exception as e:
            print(f"[{ticker}] Alpaca execution failed: {e}")
            exit_reason = None

        #Ensuring that the logged signal reflects the actual action taken, especially in case of a stop loss trigger
        if exit_reason == "STOP_LOSS":
            logged_signal = 0
            logged_action = "SELL/HOLD"
        else:
            logged_signal = signal
            logged_action = "BUY" if signal == 1 else "SELL/HOLD"

        signals.append({
            "Ticker": ticker,
            "Strategy": best_strategy,
            "Signal": logged_signal,
            "Price": round(current_price, 2),
            "Action": logged_action,
            "Exit_Reason": exit_reason if exit_reason else ""
        })

    log_signals(signals)

    # Measure the account AFTER all orders for the day have been submitted, so
    # the snapshot reflects the state the trades actually left it in.
    #
    # This is the only place in the project that records ground truth rather
    # than reconstructing it from yfinance closes. It is wrapped defensively
    # and on its own client because a measurement failure must never be able to
    # affect trading - by this point every order is already submitted anyway.
    print(f"\n{'='*50}\nACCOUNT SNAPSHOT\n{'='*50}")
    try:
        log_account_state(get_client())
    except Exception as e:
        print(f"[paper_trader] Account logging failed (trading unaffected): "
              f"{type(e).__name__}: {e}")

    return pd.DataFrame(signals).set_index("Ticker")