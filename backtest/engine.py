"""
Single-ticker backtest engine.

IMPORTANT SCOPE NOTE: this simulates ONE ticker against its own private
`initial_capital`. There is no competition for capital between tickers, so
`position_size` here is a fraction of that one ticker's dedicated pot - which
is why config.BACKTEST_POSITION_SIZE is 1.0 while config.LIVE_POSITION_SIZE is
0.20. They are not the same quantity. See config.py.

EXECUTION MODEL (Version 15). Every decision is made at a bar's CLOSE and
executed at the NEXT bar's OPEN, because that is exactly what happens live:

    21:00 UTC  scheduled job reads today's close, computes a signal,
               submits a DAY market order
    04:00 ET   Alpaca releases the queued order into the pre-market session
    09:33 ET   it fills, a few minutes after the next regular open

Verified against real fills on 2026-08-14 (submitted 08:00 UTC, filled
13:33 UTC). The previous engine decided AND executed at the same close, which
was optimistic everywhere and structurally blind to gap risk in particular: a
stop would trigger and exit at the same price, so an AAPL-style weekend gap
could never cost anything in the backtest.
"""

try:
    from config import TRANSACTION_COST_BPS, EXECUTION_LAG
except ImportError:  # keep the engine importable standalone
    TRANSACTION_COST_BPS, EXECUTION_LAG = 5.0, 1

# Minimum tradeable notional. Alpaca supports fractional shares, so there is no
# whole-share floor, but a position worth less than this is not meaningfully a
# trade and is skipped to avoid dust positions.
MIN_TRADE_NOTIONAL = 1.0


def run_backtest(df, initial_capital, stop_loss, position_size,
                 cost_bps=None, execution_lag=None):
    """Backtest one ticker.

    cost_bps       per-side transaction cost in basis points (5.0 = 0.05%).
                   Applied to both buys and sells. Pass 0 to disable.
    execution_lag  1 = decide at this close, execute at the next open (live
                   behaviour, the default). 0 = decide and execute at the same
                   close (the old behaviour; kept so tests can pin pure
                   accounting without the lag confounding it).
    """
    cost_bps = TRANSACTION_COST_BPS if cost_bps is None else cost_bps
    execution_lag = EXECUTION_LAG if execution_lag is None else execution_lag
    cost_rate = cost_bps / 10_000.0

    # Fill at the open when we have it. Older frames only carried Close/High/Low,
    # so fall back rather than break.
    has_open = "Open" in df.columns

    # stop_loss = 0 means NO STOP, not "stop at 0%".
    #
    # Without this the condition `price < entry_price * (1 - 0)` reduces to
    # `price < entry_price`, which fires on ANY downtick - the exact opposite of
    # stopless. That would have silently wrecked the Buy & Hold candidate, which
    # passes stop_loss=0 precisely to be stopless, turning the benchmark into
    # "sell whenever the price ticks down."
    stop_enabled = stop_loss is not None and stop_loss > 0

    capital = initial_capital
    shares = 0.0
    entry_price = 0.0
    pending = None          # decision made at the previous close
    portfolio_values = []

    for _, row in df.iterrows():
        close = float(row["Close"])
        fill = float(row["Open"]) if (has_open and execution_lag) else close
        signal = row["Signal"]

        # -- 1. Execute what was decided at the previous close ---------------
        if execution_lag and pending:
            if pending == "BUY" and shares == 0:
                shares, capital, entry_price = _buy(capital, fill, position_size,
                                                    cost_rate)
            elif pending == "SELL" and shares > 0:
                capital = _sell(capital, shares, fill, cost_rate)
                shares, entry_price = 0.0, 0.0
            pending = None

        # -- 2. Decide, using this bar's close --------------------------------
        # Stop loss takes priority over the model, matching check_stop_loss()
        # in alpaca_executor.py.
        decision = None
        if stop_enabled and shares > 0 and close < entry_price * (1 - stop_loss):
            decision = "SELL"
        elif shares == 0 and signal == 1:
            decision = "BUY"
        elif shares > 0 and signal == 0:
            decision = "SELL"

        if execution_lag:
            pending = decision
        else:
            # Same-bar execution: the pre-Version-15 behaviour.
            #
            # `stopped` prevents a stop from selling and instantly re-buying at
            # the same close while the signal is still 1 - which made the stop a
            # no-op that only ratcheted entry_price downward. Live cannot do
            # this: check_stop_loss() force-sells and returns.
            stopped = False
            if stop_enabled and shares > 0 and close < entry_price * (1 - stop_loss):
                capital = _sell(capital, shares, close, cost_rate)
                shares, entry_price = 0.0, 0.0
                stopped = True
            if shares == 0 and signal == 1 and not stopped:
                shares, capital, entry_price = _buy(capital, close, position_size,
                                                    cost_rate)
            elif shares > 0 and signal == 0:
                capital = _sell(capital, shares, close, cost_rate)
                shares, entry_price = 0.0, 0.0

        # -- 3. Mark to market at the close -----------------------------------
        portfolio_values.append(capital + shares * close)

    df["Portfolio_Value"] = portfolio_values
    df["Cumulative_Strategy"] = df["Portfolio_Value"] / initial_capital
    df["Market_Return"] = df["Close"].squeeze().pct_change()
    df["Cumulative_Market"] = (1 + df["Market_Return"]).cumprod()

    return df


def _buy(capital, price, position_size, cost_rate):
    """Deploy `position_size` of capital, INCLUSIVE of the cost to get in.

    Dividing by (1 + cost_rate) means the total outlay is exactly the intended
    notional. Sizing off the raw price instead would overdraw at
    position_size = 1.0, since the fee has to come from somewhere.
    """
    if price <= 0:
        return 0.0, capital, 0.0

    budget = capital * position_size
    shares = budget / (price * (1 + cost_rate))
    notional = shares * price

    if notional < MIN_TRADE_NOTIONAL:
        return 0.0, capital, 0.0

    # FRACTIONAL SHARES. This used to be int(risk_amount / price), which floored
    # to whole shares and made the effective position size a function of the
    # share price: at position_size 0.20 with $10k capital a $365 stock got 5
    # shares (18.2%) while a $200 stock got exactly 20.0%, and at 0.02 a $365
    # stock got 0 shares and never traded. That is what made backtest Sharpe
    # appear not to scale with position_size (the V12 JPM anomaly). Live uses
    # fractional shares via Alpaca, so this also removed a backtest/live gap.
    return shares, capital - notional * (1 + cost_rate), price


def _sell(capital, shares, price, cost_rate):
    proceeds = shares * price
    return capital + proceeds * (1 - cost_rate)
