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
from strategy.auto_selector import auto_select, compute_composite_score, BUY_AND_HOLD
from evaluation.metrics import get_metrics
from backtest.engine import run_backtest
import os
from strategy.alpaca_executor import get_client, execute_signal
from evaluation.account_log import log_account_state


def get_recent_data(ticker, start=None):
    """Full price history from `start` through today, for live signal generation.

    Was `lookback_days=300`. That gave ~205 trading days, and after
    build_features().dropna() ate the indicator warm-up it left ~155 rows - of
    which generate_current_signal() then trained on only the first half. The
    live model was therefore fitted on ~77 days of data ending roughly four
    months ago, while the backtest fitted on ~1,100 days. They were not the
    same model, so backtest results said nothing about live behaviour.

    `end` is set to TOMORROW deliberately. yfinance treats the end date as
    exclusive, so passing today risks dropping today's bar - the one the signal
    is supposed to be computed from.
    """
    from config import START

    start = start or START
    end = (datetime.today() + timedelta(days=1)).strftime("%Y-%m-%d")
    return load_data(ticker, start, end)

def get_trading_date(df):
    """The date of the last bar of market data, as YYYY-MM-DD.

    This is the date the signals ACTUALLY describe. `datetime.now()` is the
    date the script happened to run, which is not the same thing: the
    scheduled job fires at 21:00 UTC and any manual run after ~20:00 ET rolls
    past UTC midnight, stamping Friday's closing prices with Saturday's date.
    That produced a phantom weekend trading day on 2026-08-15.

    Returns None if the frame is empty, so callers can fall back.
    """
    if df is None or len(df) == 0:
        return None
    return df.index[-1].strftime("%Y-%m-%d")


def log_signals(signals, log_file="results/paper_trading_log.csv", trading_date=None):
    os.makedirs("results", exist_ok=True)
    signals_df = pd.DataFrame(signals)

    # Date comes from the market data, clock time from the run. Every consumer
    # in evaluation/performance.py already treats Timestamp as "which trading
    # day is this row about" (sorting, weekly bucketing, drawdown dating), so
    # this aligns the field with how it was always used. The time component is
    # kept so you can still see when the job ran.
    now = datetime.now()
    if trading_date is None:
        trading_date = now.strftime("%Y-%m-%d")
        print("[paper_trader] WARNING: no market data date available, "
              "falling back to the system clock for Timestamp")
    signals_df["Timestamp"] = f"{trading_date} {now.strftime('%H:%M:%S')}"
    
    if os.path.exists(log_file):
        existing = pd.read_csv(log_file)
        updated = pd.concat([existing, signals_df], ignore_index=True)
    else:
        updated = signals_df
    
    updated.to_csv(log_file, index=False)
    print(f"Signals logged to: {log_file}")

def _split_for_live_prediction(df):
    """Everything-but-today to train on, today's row to predict.

    Returns (X_train, y_train, X_today).

    TWO TRAPS, both easy to reintroduce:

    1. NO HOLDOUT. The backtest trains on the first 50% and predicts the second
       50% because it is MEASURING generalisation. Live prediction is not a
       measurement - there is nothing to be honest about, and holding data back
       just makes the model worse. Train on everything available.

    2. THE LAST ROW'S LABEL IS FAKE. build_target() does
       `(close.shift(-1) > close).astype(int)`. On the final row shift(-1) is
       NaN, `NaN > close` is False, and astype(int) turns that into 0. So the
       last row carries a fabricated label of 0 that survives dropna() and
       would silently teach the model "today goes down" on every single run.
       It must be excluded from training - which is what `.iloc[:-1]` is for.
    """
    df = build_features(df)
    df = build_target(df)
    df = df.dropna()

    if len(df) < 100:
        raise ValueError(
            f"only {len(df)} usable rows after feature warm-up - "
            "not enough history to train a live model"
        )

    X = df[FEATURE_COLS]
    y = df["Target"]
    return X.iloc[:-1], y.iloc[:-1], X.iloc[[-1]]


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

        elif strategy_name == BUY_AND_HOLD:
            # Always long. execute_signal() buys once and then skips every
            # subsequent day because a position already exists. The stop loss
            # is bypassed for this strategy - see run_paper_trader below.
            return 1

        elif strategy_name == "Logistic Regression":
            X_train, y_train, X_today = _split_for_live_prediction(df)

            # Scaler fitted on TRAINING ROWS ONLY. It used to be
            # fit_transform(X) over the whole frame including today's row,
            # which leaks today's feature values into the scaling parameters.
            scaler = StandardScaler()
            X_train_scaled = scaler.fit_transform(X_train)
            X_today_scaled = scaler.transform(X_today)

            model = LogisticRegression(max_iter=1000)
            model.fit(X_train_scaled, y_train)
            return int(model.predict(X_today_scaled)[0])

        elif strategy_name == "Random Forest":
            X_train, y_train, X_today = _split_for_live_prediction(df)
            model = RandomForestClassifier(n_estimators=100, random_state=42)
            model.fit(X_train, y_train)
            return int(model.predict(X_today)[0])

        raise ValueError(f"Unknown strategy: {strategy_name!r}")

    except Exception as e:
        # FAIL CLOSED. This used to `return 0`, and 0 means SELL/HOLD - so a
        # crashed model would quietly liquidate a position. Returning None lets
        # the caller skip the ticker entirely and trade nothing.
        print(f"[{strategy_name}] Signal generation FAILED: {type(e).__name__}: {e}")
        return None

def run_paper_trader(tickers, start, end, initial_capital, stop_loss, position_size):
    print(f"\n{'='*50}")
    print(f"QUANTARA PAPER TRADER")
    print(f"Date: {datetime.today().strftime('%Y-%m-%d')}")
    print(f"{'='*50}")

    # Get best strategy per ticker from historical analysis
    print("\nRunning auto selection to find best strategies...")
    selections = auto_select(tickers, start, end, initial_capital, stop_loss, position_size)

    signals = []
    trading_date = None

    for ticker in tickers:
        print(f"\n--- {ticker} ---")
        best_strategy = selections.loc[ticker, "Best_Strategy"]
        print(f"Selected Strategy: {best_strategy}")

        # Full history from config START through today. The ML strategies train
        # on all of it; the crossover strategies only look at the tail, so the
        # extra history is harmless to them.
        df_recent = get_recent_data(ticker, start=start)

        # Take the trading date from the first ticker that returns data. All
        # five share a market calendar, so any of them will do.
        if trading_date is None:
            trading_date = get_trading_date(df_recent)
            if trading_date:
                print(f"Trading date      : {trading_date}")

        # Generate today's signal using best strategy
        signal = generate_current_signal(df_recent, best_strategy, 
                                        initial_capital, stop_loss, position_size)

        current_price = df_recent["Close"].squeeze().iloc[-1]
        print(f"Current Price     : ${current_price:.2f}")

        # None means signal generation failed. Do NOT trade, and do NOT write a
        # row - a row with Signal 0 is indistinguishable from a real SELL/HOLD
        # decision, and every downstream consumer would treat it as one.
        if signal is None:
            print(f"[{ticker}] No signal produced — skipping this ticker "
                  f"entirely (no order, no log row)")
            continue

        print(f"Today's Signal    : {'BUY' if signal == 1 else 'SELL/HOLD'}")

        # Execute on Alpaca
        try:
            client = get_client()
            # Buy & Hold must be genuinely stopless, or it is not buy & hold -
            # it becomes "stopped out at -5%, re-bought the next day", which is
            # a whipsaw strategy wearing a benchmark's name. This mirrors
            # stop_loss=0 in the auto_selector candidate.
            order_result, exit_reason = execute_signal(
                client, ticker, signal, current_price,
                apply_stop_loss=(best_strategy != BUY_AND_HOLD),
            )
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

    log_signals(signals, trading_date=trading_date)

    # Measure the account AFTER all orders for the day have been submitted, so
    # the snapshot reflects the state the trades actually left it in.
    #
    # This is the only place in the project that records ground truth rather
    # than reconstructing it from yfinance closes. It is wrapped defensively
    # and on its own client because a measurement failure must never be able to
    # affect trading - by this point every order is already submitted anyway.
    print(f"\n{'='*50}\nACCOUNT SNAPSHOT\n{'='*50}")
    try:
        log_account_state(get_client(), trading_date=trading_date)
    except Exception as e:
        print(f"[paper_trader] Account logging failed (trading unaffected): "
              f"{type(e).__name__}: {e}")

    return pd.DataFrame(signals).set_index("Ticker")