import matplotlib.pyplot as plt
import pandas as pd
from strategy.paper_trader import get_recent_data, generate_current_signal
from strategy.ml_signal import build_features, build_target
from indicators.rsi import compute_rsi
from indicators.bollinger import compute_bollinger_bands
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import StandardScaler




def plot_results(df):
    fig, (ax1, ax2, ax3) = plt.subplots(3, 1, figsize=(12, 14), sharex=True)

    # Top panel - cumulative returns
    ax1.plot(df["Cumulative_Market"], label="Buy & Hold", color="blue")
    ax1.plot(df["Cumulative_Strategy"], label="Strategy", color="orange")
    ax1.set_title("Quantara — Strategy vs Buy & Hold (NVDA)")
    ax1.set_ylabel("Cumulative Return")
    ax1.legend()
    ax1.grid(True)

    # Middle panel - price and indicators
    ax2.plot(df["Close"].squeeze(), label="NVDA Close", color="gray", alpha=0.5)
    if "EMA_20" in df.columns:
        ax2.plot(df["EMA_20"], label="EMA 20 (Fast)", color="green")
        ax2.plot(df["EMA_50"], label="EMA 50 (Slow)", color="red")
    if "SMA_20" in df.columns:
        ax2.plot(df["SMA_20"], label="SMA 20 (Fast)", color="green", linestyle="--")
        ax2.plot(df["SMA_50"], label="SMA 50 (Slow)", color="red", linestyle="--")
    ax2.set_title("Price vs Indicators")
    ax2.set_ylabel("Price")
    ax2.legend()
    ax2.grid(True)

    # Bottom panel - RSI
    ax3.plot(df["RSI"], label="RSI (14)", color="purple")
    ax3.axhline(y=70, color="red", linestyle="--", alpha=0.7, label="Overbought (70)")
    ax3.axhline(y=30, color="green", linestyle="--", alpha=0.7, label="Oversold (30)")
    ax3.set_title("RSI")
    ax3.set_xlabel("Date")
    ax3.set_ylabel("RSI")
    ax3.legend()
    ax3.grid(True)

    plt.tight_layout()
    plt.show()



def plot_diagnostic(ticker, initial_capital, stop_loss, position_size):

    # Load recent data and build features
    df = get_recent_data(ticker, lookback_days=300)
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
    signals = model.predict(X_scaled)

    df["Signal"] = signals
    close = df["Close"].squeeze()

    # Build buy/sell marker series
    buy_signals = close.where(df["Signal"] == 1)
    sell_signals = close.where(df["Signal"] == 0)

    fig, (ax1, ax2, ax3) = plt.subplots(3, 1, figsize=(14, 12), sharex=True)

    # Top panel - price with signal markers
    ax1.plot(close, label=f"{ticker} Close", color="blue", alpha=0.7)
    ax1.scatter(buy_signals.index, buy_signals, 
                color="green", marker="^", s=50, label="BUY Signal", zorder=5)
    ax1.scatter(sell_signals.index, sell_signals,
                color="red", marker="v", s=50, label="SELL Signal", zorder=5)
    ax1.set_title(f"{ticker} — LR Signal Diagnostic")
    ax1.set_ylabel("Price")
    ax1.legend()
    ax1.grid(True)

    # Middle panel - RSI
    ax2.plot(df["RSI"], label="RSI (14)", color="purple")
    ax2.axhline(y=70, color="red", linestyle="--", alpha=0.7, label="Overbought (70)")
    ax2.axhline(y=30, color="green", linestyle="--", alpha=0.7, label="Oversold (30)")
    ax2.set_ylabel("RSI")
    ax2.legend()
    ax2.grid(True)

    # Bottom panel - BB_position
    ax3.plot(df["BB_position"], label="BB Position", color="orange")
    ax3.axhline(y=1.0, color="red", linestyle="--", alpha=0.7, label="Upper Band")
    ax3.axhline(y=0.0, color="green", linestyle="--", alpha=0.7, label="Lower Band")
    ax3.axhline(y=0.5, color="gray", linestyle="--", alpha=0.5, label="Midpoint")
    ax3.set_ylabel("BB Position")
    ax3.set_xlabel("Date")
    ax3.legend()
    ax3.grid(True)

    plt.tight_layout()
    plt.show()