def compute_sma(df, window):
    df[f"SMA_{window}"] = df["Close"].rolling(window=window).mean()
    return df