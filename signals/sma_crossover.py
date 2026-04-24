def generate_signals(df, window):
    df["Signal"] = (df["Close"].squeeze() > df[f"SMA_{window}"].squeeze()).astype(int)
    df["Position"] = df["Signal"].shift(1)
    return df