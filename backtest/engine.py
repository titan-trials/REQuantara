"""
Single-ticker backtest engine.

IMPORTANT SCOPE NOTE: this simulates ONE ticker against its own private
`initial_capital`. There is no competition for capital between tickers, so
`position_size` here is a fraction of that one ticker's dedicated pot - which
is why config.BACKTEST_POSITION_SIZE is 1.0 while config.LIVE_POSITION_SIZE is
0.20. They are not the same quantity. See config.py.
"""

# Minimum tradeable notional. Alpaca supports fractional shares, so there is no
# whole-share floor, but a position worth less than this is not meaningfully a
# trade and is skipped to avoid dust positions.
MIN_TRADE_NOTIONAL = 1.0


def run_backtest(df, initial_capital, stop_loss, position_size):
    capital = initial_capital
    shares = 0.0
    entry_price = 0.0
    portfolio_values = []

    for date, row in df.iterrows():
        price = row["Close"]
        signal = row["Signal"]
        stopped_this_bar = False

        # Check stop loss if we hold a position
        if shares > 0:
            if price < entry_price * (1 - stop_loss):
                capital += shares * price
                shares = 0.0
                entry_price = 0.0
                stopped_this_bar = True

        # Check signal
        #
        # `not stopped_this_bar` matters. Without it, a stop that fires while the
        # strategy signal is still 1 sells and instantly re-buys at the SAME
        # close on the SAME bar, which does nothing except reset entry_price
        # lower. The stop then never removes exposure - a position could ride
        # 100 -> 80 through two "triggers" while staying fully invested the
        # whole way down, and every backtest drawdown number was computed under
        # that assumption.
        #
        # Live behaviour is different and is what this now matches:
        # check_stop_loss() in alpaca_executor.py force-sells and returns, so
        # the position is flat until at least the next scheduled run.
        if shares == 0 and signal == 1 and not stopped_this_bar:
            risk_amount = capital * position_size
            # FRACTIONAL SHARES. This used to be int(risk_amount / price), which
            # floored to whole shares. That made the *effective* position size a
            # function of the share price: at position_size 0.20 with $10k
            # capital, a $365 stock got 5 shares = 18.2% invested while a $200
            # stock got exactly 20.0%, and at position_size 0.02 a $365 stock got
            # 0 shares and never traded at all. That price-dependent distortion is
            # what made backtest Sharpe appear not to scale with position_size
            # (the JPM +0.379 anomaly noted in Version 12). Live execution uses
            # fractional shares via Alpaca, so this also removes a real
            # backtest/live mismatch.
            shares_to_buy = risk_amount / price
            if shares_to_buy * price >= MIN_TRADE_NOTIONAL:
                capital -= shares_to_buy * price
                shares = shares_to_buy
                entry_price = price

        elif shares > 0 and signal == 0:
            capital += shares * price
            shares = 0.0
            entry_price = 0.0

        portfolio_values.append(capital + shares * price)

    df["Portfolio_Value"] = portfolio_values
    df["Cumulative_Strategy"] = df["Portfolio_Value"] / initial_capital
    df["Market_Return"] = df["Close"].squeeze().pct_change()
    df["Cumulative_Market"] = (1 + df["Market_Return"]).cumprod()

    return df
