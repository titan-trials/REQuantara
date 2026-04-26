def run_backtest(df, initial_capital, stop_loss, position_size):
    capital = initial_capital
    shares = 0
    entry_price = 0
    portfolio_values = []

    for date, row in df.iterrows():
        price = row["Close"]
        signal = row["Signal"]

        # Check stop loss if we hold a position
        if shares > 0:
            if price < entry_price * (1 - stop_loss):
                capital += shares * price
                shares = 0
                entry_price = 0

        # Check signal
        if shares == 0 and signal == 1:
            risk_amount = capital * position_size
            shares_to_buy = int(risk_amount / price)
            if shares_to_buy > 0:
                capital -= shares_to_buy * price
                shares = shares_to_buy
                entry_price = price

        elif shares > 0 and signal == 0:
            capital += shares * price
            shares = 0
            entry_price = 0

        portfolio_values.append(capital + shares * price)

    df["Portfolio_Value"] = portfolio_values
    df["Cumulative_Strategy"] = df["Portfolio_Value"] / initial_capital
    df["Market_Return"] = df["Close"].squeeze().pct_change()
    df["Cumulative_Market"] = (1 + df["Market_Return"]).cumprod()

    return df