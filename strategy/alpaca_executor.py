import time
from alpaca.common.exceptions import APIError
from alpaca.trading.client import TradingClient
from alpaca.trading.requests import MarketOrderRequest
from alpaca.trading.enums import OrderSide, TimeInForce
from config import ALPACA_KEY, ALPACA_SECRET, LIVE_POSITION_SIZE, STOP_LOSS
from strategy.ml_signal import build_features, build_target, FEATURE_COLS

def get_client():
    return TradingClient(ALPACA_KEY, ALPACA_SECRET, paper=True)

def get_account(client):
    return client.get_account()

# Statuses meaning the order is DONE and will never fill further. Anything not
# in this set is treated as still live.
#
# The set is deliberately inverted (list what's finished, assume the rest is
# pending) so that an unrecognised or newly-added Alpaca status counts as
# pending. That errs toward skipping a BUY, which costs one missed entry.
# Erring the other way costs a duplicate position.
TERMINAL_ORDER_STATUSES = {
    "filled", "canceled", "cancelled", "expired",
    "rejected", "replaced", "done_for_day",
}


def normalize_status(status):
    """'OrderStatus.ACCEPTED' -> 'accepted'. Also handles a plain 'accepted'.

    alpaca-py stringifies its enums differently across versions and Python
    versions. submit_and_verify() has always done this correctly;
    get_pending_orders() did not, and compared the raw
    'OrderStatus.ACCEPTED' against lowercase literals - so it matched nothing
    and reported zero pending orders no matter what was actually queued.
    """
    return str(status).split(".")[-1].lower()


def get_position(client, ticker):
    """The open position for `ticker`, or None if there genuinely isn't one.

    Raises on any error other than 'no such position'. The previous bare
    `except: return None` meant a network blip looked identical to "flat",
    which is dangerous in both directions: it skips the stop loss on a
    position you really hold, AND it lets a duplicate BUY through.
    """
    try:
        return client.get_open_position(ticker)
    except APIError as e:
        status_code = getattr(e, "status_code", None)
        message = str(e).lower()
        is_missing = (
            status_code == 404
            or "position does not exist" in message
            or "not found" in message
        )
        if is_missing:
            return None
        raise


def get_pending_orders(client, ticker):
    """Live (non-terminal) orders for `ticker`.

    Raises on API failure rather than returning []. Returning an empty list on
    error is what made this a fail-OPEN guard: "I couldn't check" was
    indistinguishable from "nothing is pending", so a duplicate order could be
    submitted. Callers decide what to do when it raises.
    """
    orders = client.get_orders()
    return [
        o for o in orders
        if o.symbol == ticker
        and normalize_status(o.status) not in TERMINAL_ORDER_STATUSES
    ]

def check_stop_loss(position, current_price):
    """
    Returns True if the position has breached the stop loss threshold
    and should be force-sold regardless of the model's signal.
    """
    if position is None:
        return False
    entry_price = float(position.avg_entry_price)
    drawdown = (current_price - entry_price) / entry_price
    return drawdown <= -STOP_LOSS

def submit_and_verify(client, order_request, ticker, action_desc, checks=5, delay=2):
    try:
        order = client.submit_order(order_request)
    except APIError as e:
        print(f"[{ticker}] {action_desc} rejected at submission: {e}")
        return None, False

    latest = order
    for _ in range(checks):
        time.sleep(delay)
        try:
            latest = client.get_order_by_id(order.id)
        except Exception:
            break
        status = str(latest.status).split(".")[-1].lower()
        if status in ("rejected", "canceled", "expired"):
            print(f"[{ticker}] {action_desc} {status.upper()} by Alpaca — no position change")
            return latest, False
        if status in ("filled", "partially_filled"):
            return latest, True

    # Still queued (normal for after-hours orders waiting on next open)
    return latest, True


def execute_signal(client, ticker, signal, price):
    """
    Always returns a (result, reason) tuple. result is None if no order
    was placed. reason is one of "STOP_LOSS", "SIGNAL", or None.
    """
    account = get_account(client)
    portfolio_value = float(account.portfolio_value)
    position = get_position(client, ticker)

    # NOTE: pending orders are deliberately NOT fetched here. This used to run
    # before the stop-loss check, so an orders-endpoint failure would abort the
    # whole function and silently skip a stop loss. The stop loss is the safety
    # mechanism - it must not depend on a call it doesn't need. Pending orders
    # are now fetched only inside the BUY branch, which is the only place they
    # matter.

    # STOP LOSS CHECK — takes priority over the model's signal
    if position is not None and check_stop_loss(position, price):
        entry_price = float(position.avg_entry_price)
        drawdown_pct = (price - entry_price) / entry_price * 100
        shares = float(position.qty)
        order = MarketOrderRequest(
            symbol=ticker,
            qty=shares,
            side=OrderSide.SELL,
            time_in_force=TimeInForce.DAY
        )
        result, ok = submit_and_verify(client, order, ticker, "STOP LOSS SELL")
        if not ok:
            return None, None
        print(f"[{ticker}] STOP LOSS ({STOP_LOSS*100:.0f}%) TRIGGERED — down {drawdown_pct:.2f}% from entry ${entry_price:.2f}. Force SELL {shares} shares @ ~${price:.2f}")
        return result, "STOP_LOSS"

    # BUY logic
    if signal == 1 and position is None:
        # FAIL CLOSED. If we cannot confirm there is no live order already
        # queued, do not buy. A missed entry costs one day of exposure; a
        # duplicate order doubles a position and, at 20% sizing across five
        # tickers, pushes the account onto margin.
        try:
            pending = get_pending_orders(client, ticker)
        except Exception as e:
            print(f"[{ticker}] Could not verify pending orders "
                  f"({type(e).__name__}: {e}) — skipping BUY to avoid a duplicate")
            return None, None

        if pending:
            statuses = ", ".join(normalize_status(o.status) for o in pending)
            print(f"[{ticker}] BUY signal but {len(pending)} live order(s) "
                  f"already queued [{statuses}] — skip")
            return None, None

        # LIVE_POSITION_SIZE is a fraction of TOTAL account equity and all five
        # tickers draw on the same pool, so this must stay at 1/len(TICKERS)
        # or lower to avoid buying on margin. See config.py.
        dollar_amount = portfolio_value * LIVE_POSITION_SIZE
        shares = round(dollar_amount / price, 4)

        if shares <= 0:
            print(f"[{ticker}] Skipping BUY — calculated 0 shares")
            return None, None

        order = MarketOrderRequest(
            symbol=ticker,
            qty=shares,
            side=OrderSide.BUY,
            time_in_force=TimeInForce.DAY
        )
        result, ok = submit_and_verify(client, order, ticker, "BUY")
        if not ok:
            return None, None
        print(f"[{ticker}] BUY {shares} shares @ ~${price:.2f}")
        return result, "SIGNAL"

    # SELL logic (model signal)
    elif signal == 0 and position is not None:
        shares = float(position.qty)
        order = MarketOrderRequest(
            symbol=ticker,
            qty=shares,
            side=OrderSide.SELL,
            time_in_force=TimeInForce.DAY
        )
        result, ok = submit_and_verify(client, order, ticker, "SELL")
        if not ok:
            return None, None
        print(f"[{ticker}] SELL {shares} shares @ ~${price:.2f}")
        return result, "SIGNAL"

    else:
        # Reaching here with signal == 1 now means only "a position already
        # exists" — the pending-order case returns early inside the BUY branch
        # with its own message, so these two are no longer conflated.
        if signal == 1:
            print(f"[{ticker}] BUY signal but position already exists — skip")
        else:
            print(f"[{ticker}] SELL signal but no position — skip")
        return None, None