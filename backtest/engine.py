def run_backtest(df):
    df["Market_Return"] = df["Close"].squeeze().pct_change()
    df["Strategy_Return"] = df["Market_Return"] * df["Position"]
    df["Cumulative_Market"] = (1 + df["Market_Return"]).cumprod()
    df["Cumulative_Strategy"] = (1 + df["Strategy_Return"]).cumprod()
    return df