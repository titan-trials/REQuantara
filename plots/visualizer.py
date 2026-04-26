import matplotlib.pyplot as plt

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