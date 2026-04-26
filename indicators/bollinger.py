def compute_bollinger_bands(df, window=20, num_std=2):
    close = df["Close"].squeeze()
    sma = close.rolling(window=window).mean()
    std = close.rolling(window=window).std()
    df["BB_SMA"] = sma
    df["Upper"] = sma + (num_std * std)
    df["Lower"] = sma - (num_std * std)
    return df