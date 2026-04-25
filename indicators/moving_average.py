def compute_sma(df, window):
    close = df["Close"].squeeze()
    df[f"SMA_{window}"] = close.rolling(window=window).mean()
    return df