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

def build_features(df):
    df = compute_sma(df, 20)
    df = compute_sma(df, 50)
    df = compute_ema(df, 20)
    df = compute_ema(df, 50)
    df = compute_rsi(df)
    df = compute_bollinger_bands(df)
    
    close = df["Close"].squeeze()
    
    df["EMA_gap"] = df["EMA_20"].squeeze() - df["EMA_50"].squeeze()
    df["BB_position"] = (close - df["Lower"].squeeze()) / (df["Upper"].squeeze() - df["Lower"].squeeze())
    df["Momentum_5"] = close.pct_change(5)
    df["Momentum_10"] = close.pct_change(10)
    
    return df

def build_target(df):
    close = df["Close"].squeeze()
    df["Target"] = (close.shift(-1) > close).astype(int)
    return df

def run_ml_strategy(ticker, start, end, initial_capital, stop_loss, position_size):
    df = load_data(ticker, start, end)
    df = build_features(df)
    df = build_target(df)
    df = df.dropna()
    
    feature_cols = ["EMA_gap", "RSI", "BB_position", "Momentum_5", "Momentum_10"]
    
    X = df[feature_cols]
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

    coefficients = pd.Series(model.coef_[0], index=feature_cols)
    print("\nModel Feature Weights:")
    print(coefficients.sort_values(ascending=False))
    
    return df_test, metrics, model, feature_cols, scaler

from sklearn.ensemble import RandomForestClassifier

def run_rf_strategy(ticker, start, end, initial_capital, stop_loss, position_size):
    df = load_data(ticker, start, end)
    df = build_features(df)
    df = build_target(df)
    df = df.dropna()
    
    feature_cols = ["EMA_gap", "RSI", "BB_position", "Momentum_5", "Momentum_10"]
    
    X = df[feature_cols]
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
    
    importances = pd.Series(model.feature_importances_, index=feature_cols)
    
    print(f"\n--- RANDOM FOREST RESULTS: {ticker} ---")
    print(f"Test Total Return  : {metrics['Total_Return']}%")
    print(f"Test Sharpe        : {metrics['Sharpe_Ratio']}")
    print(f"Test Win Rate      : {metrics['Win_Rate']}%")
    print(f"Test Max Drawdown  : {metrics['Max_Drawdown']}%")
    print(f"\nFeature Importances:")
    print(importances.sort_values(ascending=False))
    
    return df_test, metrics, model, feature_cols