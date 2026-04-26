# Version 1 - Price vs SMA signal
def generate_signals(df, window):
    df["Signal"] = (df["Close"].squeeze() > df[f"SMA_{window}"].squeeze()).astype(int)
    df["Position"] = df["Signal"].shift(1)
    return df

# Version 2 - Dual SMA crossover signal
def generate_crossover_signals(df, fast_window, slow_window):
    fast_col = f"SMA_{fast_window}"
    slow_col = f"SMA_{slow_window}"

    # Debugging prints
    # print("Columns inside function:", df.columns.tolist())
    # print("Looking for:", fast_col, slow_col)
    
    df["Signal"] = (df[fast_col].squeeze() > df[slow_col].squeeze()).astype(int)
    df["Position"] = df["Signal"].shift(1)
    return df

# Version 2 - EMA crossover signal
def generate_ema_crossover_signals(df, fast_window, slow_window):
    fast_col = f"EMA_{fast_window}"
    slow_col = f"EMA_{slow_window}"

    df["Signal"] = (df[fast_col].squeeze() > df[slow_col].squeeze()).astype(int)
    df["Position"] = df["Signal"].shift(1)
    return df

# Version 3 - Dual SMA crossover + RSI filter
def generate_combined_signals(df, fast_window, slow_window, rsi_high=70, rsi_low=30):
    fast_col = f"SMA_{fast_window}"
    slow_col = f"SMA_{slow_window}"

    sma_signal = df[fast_col].squeeze() > df[slow_col].squeeze()
    rsi_signal = df["RSI"] < rsi_high

    df["Signal"] = (sma_signal & rsi_signal).astype(int)
    df["Position"] = df["Signal"].shift(1)
    return df