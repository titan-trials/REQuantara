import pandas as pd
import numpy as np
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import StandardScaler
from data.loader import load_data
from indicators.moving_average import compute_sma
from indicators.ema import compute_ema
from indicators.rsi import compute_rsi
from indicators.bollinger import compute_bollinger_bands
from backtest.engine import run_backtest
from evaluation.metrics import get_metrics
from sklearn.ensemble import RandomForestClassifier

FEATURE_COLS = [
    "EMA_gap", "RSI", "BB_position", "Momentum_5", "Momentum_10",
    "Momentum_20", "Momentum_30", "RSI_slope", "Volatility_10",
    "Volatility_20", "SMA_gap", "Price_vs_SMA20", "Price_vs_SMA50",
    "BB_width", "Mom_accel", "ADX_14", "Ret_vol_norm", "RSI_x_trend"
]

def build_features(df):
    df = compute_sma(df, 20)
    df = compute_sma(df, 50)
    df = compute_ema(df, 20)
    df = compute_ema(df, 50)
    df = compute_rsi(df)
    df = compute_bollinger_bands(df)
    
    close = df["Close"].squeeze()
    high = df["High"].squeeze()
    low = df["Low"].squeeze()
    
    # Existing features
    df["EMA_gap"] = df["EMA_20"].squeeze() - df["EMA_50"].squeeze()
    df["BB_position"] = (close - df["Lower"].squeeze()) / (df["Upper"].squeeze() - df["Lower"].squeeze())
    df["Momentum_5"] = close.pct_change(5)
    df["Momentum_10"] = close.pct_change(10)
    df["Momentum_20"] = close.pct_change(20)
    df["Momentum_30"] = close.pct_change(30)
    df["RSI_slope"] = df["RSI"].diff(3)
    df["Volatility_10"] = close.pct_change().rolling(10).std()
    df["Volatility_20"] = close.pct_change().rolling(20).std()
    df["SMA_gap"] = df["SMA_20"].squeeze() - df["SMA_50"].squeeze()
    df["Price_vs_SMA20"] = (close - df["SMA_20"].squeeze()) / df["SMA_20"].squeeze()
    df["Price_vs_SMA50"] = (close - df["SMA_50"].squeeze()) / df["SMA_50"].squeeze()
    df["BB_width"] = (df["Upper"].squeeze() - df["Lower"].squeeze()) / df["BB_SMA"].squeeze()

    # Momentum features 
    # Momentum acceleration: is 10-day momentum itself increasing or decreasing?
    mom_10 = close.pct_change(10)
    df["Mom_accel"] = mom_10 - mom_10.shift(5)

    # ADX_14: trend strength, direction-agnostic
    prev_close = close.shift(1)
    tr = pd.concat([
        high - low,
        (high - prev_close).abs(),
        (low - prev_close).abs()
    ], axis=1).max(axis=1)

    up_move = high.diff()
    down_move = -low.diff()
    plus_dm = up_move.where((up_move > down_move) & (up_move > 0), 0.0)
    minus_dm = down_move.where((down_move > up_move) & (down_move > 0), 0.0)

    atr = tr.rolling(14).mean()
    plus_di = 100 * (plus_dm.rolling(14).mean() / atr)
    minus_di = 100 * (minus_dm.rolling(14).mean() / atr)
    dx = 100 * (plus_di - minus_di).abs() / (plus_di + minus_di)
    df["ADX_14"] = dx.rolling(14).mean()

    # --- Path C: volatility-normalized return ---
    # "How extreme is today's move relative to this stock's own recent normal?"
    # Guard against near-zero vol producing exploding values.
    vol20 = df["Volatility_20"].replace(0, pd.NA)
    df["Ret_vol_norm"] = (close.pct_change() / vol20).clip(-10, 10)

    # --- Path A: interaction features ---
    # ADX scaled to roughly 0-1 so the products stay interpretable.
    adx_norm = (df["ADX_14"] / 50).clip(0, 1)
    # Large positive only when RSI is high AND trend is strong (riding a real trend).
    # Near zero when ADX is low regardless of RSI (RSI isn't informative right now).
    df["RSI_x_trend"] = (df["RSI"] - 50) * adx_norm

    return df

def build_target(df):
    close = df["Close"].squeeze()
    df["Target"] = (close.shift(-1) > close).astype(int)
    return df

def run_ml_strategy(ticker, start, end, initial_capital, stop_loss, position_size, df=None):
    # `df` lets callers pass a pre-loaded frame instead of forcing another
    # yfinance download. auto_selector uses this to cut 6 downloads per ticker
    # down to 2. Callers must pass a copy - build_features mutates in place.
    if df is None:
        df = load_data(ticker, start, end)
    df = build_features(df)
    df = build_target(df)
    df = df.dropna()
    
    
    X = df[FEATURE_COLS]
    y = df["Target"]
    
    midpoint = len(df) // 2
    
    X_train = X.iloc[:midpoint]
    X_test = X.iloc[midpoint:]
    y_train = y.iloc[:midpoint]
    
    scaler = StandardScaler()
    X_train_scaled = scaler.fit_transform(X_train)
    X_test_scaled = scaler.transform(X_test)
    
    model = LogisticRegression()
    model.fit(X_train_scaled, y_train)
    
    test_signals = model.predict(X_test_scaled)
    
    df_test = df.iloc[midpoint:].copy()
    df_test["Signal"] = test_signals
    df_test["Position"] = df_test["Signal"].shift(1)
    
    df_test = run_backtest(df_test, initial_capital, stop_loss, position_size)
    metrics = get_metrics(df_test, initial_capital)
    
    print(f"\n--- ML STRATEGY RESULTS: {ticker} ---")
    print(f"Test Total Return  : {metrics['Total_Return']}%")
    print(f"Test Sharpe        : {metrics['Sharpe_Ratio']}")
    print(f"Test Win Rate      : {metrics['Win_Rate']}%")
    print(f"Test Max Drawdown  : {metrics['Max_Drawdown']}%")

    coefficients = pd.Series(model.coef_[0], index=FEATURE_COLS)
    print("\nModel Feature Weights:")
    print(coefficients.sort_values(ascending=False))
    
    return df_test, metrics, model, FEATURE_COLS, scaler

def run_rf_strategy(ticker, start, end, initial_capital, stop_loss, position_size, df=None):
    # See run_ml_strategy - optional pre-loaded frame, must be a copy.
    if df is None:
        df = load_data(ticker, start, end)
    df = build_features(df)
    df = build_target(df)
    df = df.dropna()
    
    X = df[FEATURE_COLS]
    y = df["Target"]
    
    midpoint = len(df) // 2
    
    X_train = X.iloc[:midpoint]
    X_test = X.iloc[midpoint:]
    y_train = y.iloc[:midpoint]
    
    model = RandomForestClassifier(n_estimators=100, random_state=42)
    model.fit(X_train, y_train)
    
    test_signals = model.predict(X_test)
    
    df_test = df.iloc[midpoint:].copy()
    df_test["Signal"] = test_signals
    df_test["Position"] = df_test["Signal"].shift(1)
    
    df_test = run_backtest(df_test, initial_capital, stop_loss, position_size)
    metrics = get_metrics(df_test, initial_capital)
    
    importances = pd.Series(model.feature_importances_, index=FEATURE_COLS)
    
    print(f"\n--- RANDOM FOREST RESULTS: {ticker} ---")
    print(f"Test Total Return  : {metrics['Total_Return']}%")
    print(f"Test Sharpe        : {metrics['Sharpe_Ratio']}")
    print(f"Test Win Rate      : {metrics['Win_Rate']}%")
    print(f"Test Max Drawdown  : {metrics['Max_Drawdown']}%")
    print(f"\nFeature Importances:")
    print(importances.sort_values(ascending=False))
    
    return df_test, metrics, model, FEATURE_COLS