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

def get_position(client, ticker):
    try:
        return client.get_open_position(ticker)
    except:
        return None

def get_pending_orders(client, ticker):
    try:
        orders = client.get_orders()
        return [o for o in orders if o.symbol == ticker and 
                str(o.status) in ["accepted", "pending_new", "new"]]
    except:
        return []

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
    pending = get_pending_orders(client, ticker)

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
    if signal == 1 and position is None and not pending:
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
        if signal == 1:
            print(f"[{ticker}] BUY signal but position/order exists — skip")
        else:
            print(f"[{ticker}] SELL signal but no position — skip")
        return None, None