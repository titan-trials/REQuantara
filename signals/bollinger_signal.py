def generate_bollinger_signals(df):
    price = df["Close"].squeeze()

    df["Signal"] = 0
    df.loc[price < df["Lower"].squeeze(), "Signal"] = 1
    df.loc[price > df["Upper"].squeeze(), "Signal"] = 0
    df["Position"] = df["Signal"].shift(1)
    return df