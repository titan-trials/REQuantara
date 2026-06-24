import pandas as pd
import numpy as np
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import StandardScaler
from xgboost import XGBClassifier
from data.loader import load_data
from indicators.moving_average import compute_sma
from indicators.ema import compute_ema
from indicators.rsi import compute_rsi
from indicators.bollinger import compute_bollinger_bands
from backtest.engine import run_backtest
from evaluation.metrics import get_metrics
from sklearn.ensemble import RandomForestClassifier

def build_features(df):
    df = compute_sma(df, 20)
    df = compute_sma(df, 50)
    df = compute_ema(df, 20)
    df = compute_ema(df, 50)
    df = compute_rsi(df)
    df = compute_bollinger_bands(df)
    
    close = df["Close"].squeeze()
    
    # Existing features
    df["EMA_gap"] = df["EMA_20"].squeeze() - df["EMA_50"].squeeze()
    df["BB_position"] = (close - df["Lower"].squeeze()) / (df["Upper"].squeeze() - df["Lower"].squeeze())
    df["Momentum_5"] = close.pct_change(5)
    df["Momentum_10"] = close.pct_change(10)
    
    # New features
    df["Momentum_20"] = close.pct_change(20)
    df["Momentum_30"] = close.pct_change(30)
    df["RSI_slope"] = df["RSI"].diff(3)
    df["Volatility_10"] = close.pct_change().rolling(10).std()
    df["Volatility_20"] = close.pct_change().rolling(20).std()
    df["SMA_gap"] = df["SMA_20"].squeeze() - df["SMA_50"].squeeze()
    df["Price_vs_SMA20"] = (close - df["SMA_20"].squeeze()) / df["SMA_20"].squeeze()
    df["Price_vs_SMA50"] = (close - df["SMA_50"].squeeze()) / df["SMA_50"].squeeze()
    df["BB_width"] = (df["Upper"].squeeze() - df["Lower"].squeeze()) / df["BB_SMA"].squeeze()
    
    return df

# def build_target(df):
#     close = df["Close"].squeeze()
#     df["Target"] = (close.shift(-1) > close).astype(int)
#     return df
# Note on why changing the buildtarget fuc 
# Target = 1 if the close price 5 candles later is at least 0.2% higher
#Target  =0 otherwise 
def build_target(df, horizon=5, threshold=0.002):
    close = df["Close"].squeeze()

    future_return = (close.shift(-horizon) - close) / close

    df["Future_Return"] = future_return
    df["Target"] = np.where(
        future_return.isna(),
        np.nan,
        (future_return > threshold).astype(int)
    )

    return df

def run_ml_strategy(ticker, start, end, initial_capital, stop_loss, position_size):
    df = load_data(ticker, start, end)
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
    y = df["Target"].astype(int)
    
    midpoint = len(df) // 2
    horizon = 5
    train_end = midpoint - horizon

    X_train = X.iloc[:train_end]
    X_test = X.iloc[midpoint:]
    y_train = y.iloc[:train_end]
    
    scaler = StandardScaler()
    X_train_scaled = scaler.fit_transform(X_train)
    X_test_scaled = scaler.transform(X_test)
    
    model = LogisticRegression()
    model.fit(X_train_scaled, y_train)
    
    probs = model.predict_proba(X_test_scaled)[:, 1]
    test_signals = (probs > 0.55).astype(int)
    
    df_test = df.iloc[midpoint:].copy()
    df_test["Signal"] = test_signals
    df_test["Position"] = df_test["Signal"].shift(1).fillna(0)
    
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

def run_rf_strategy(ticker, start, end, initial_capital, stop_loss, position_size):
    df = load_data(ticker, start, end)
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
    y = df["Target"].astype(int)
    
    midpoint = len(df) // 2
    horizon = 5
    train_end = midpoint - horizon

    X_train = X.iloc[:train_end]
    X_test = X.iloc[midpoint:]
    y_train = y.iloc[:train_end]
    
    model = RandomForestClassifier(n_estimators=100, random_state=42)
    model.fit(X_train, y_train)
    
    probs = model.predict_proba(X_test)[:, 1]
    test_signals = (probs > 0.55).astype(int)
    
    df_test = df.iloc[midpoint:].copy()
    df_test["Signal"] = test_signals
    df_test["Position"] = df_test["Signal"].shift(1).fillna(0)
    
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

def run_xgb_strategy(ticker, start, end, initial_capital, stop_loss, position_size):
    df = load_data(ticker, start, end)
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
    y = df["Target"].astype(int)

    midpoint = len(df) // 2
    horizon = 5
    train_end = midpoint - horizon

    X_train = X.iloc[:train_end]
    X_test = X.iloc[midpoint:]
    y_train = y.iloc[:train_end]
    model = XGBClassifier(
        n_estimators=800,
        learning_rate=0.02,
        max_depth=2,
        min_child_weight=5,
        gamma=0.1,
        subsample=0.8,
        colsample_bytree=0.8,
        reg_alpha=0.05,
        reg_lambda=2.0,
        objective="binary:logistic",
        eval_metric="logloss",
        random_state=42,
        n_jobs=-1
    )

    model.fit(X_train, y_train)

    probs = model.predict_proba(X_test)[:, 1]

    df_test = df.iloc[midpoint:].copy()
    df_test["Prediction_Prob"] = probs
    df_test["Signal"] = (df_test["Prediction_Prob"] > 0.52).astype(int)
    df_test["Position"] = df_test["Signal"].shift(1).fillna(0)

    df_test = run_backtest(df_test, initial_capital, stop_loss, position_size)
    metrics = get_metrics(df_test, initial_capital)

    print(f"\n--- XGBOOST STRATEGY RESULTS: {ticker} ---")
    print(f"Test Total Return  : {metrics['Total_Return']}%")
    print(f"Test Sharpe        : {metrics['Sharpe_Ratio']}")
    print(f"Test Win Rate      : {metrics['Win_Rate']}%")
    print(f"Test Max Drawdown  : {metrics['Max_Drawdown']}%")

    importances = pd.Series(model.feature_importances_, index=feature_cols)

    print("\nXGBoost Feature Importances:")
    print(importances.sort_values(ascending=False))

    return df_test, metrics, model, feature_cols
