def compute_ema(df, window):
    close = df["Close"].squeeze()
    df[f"EMA_{window}"] = close.ewm(span=window, adjust=False).mean()
    return df