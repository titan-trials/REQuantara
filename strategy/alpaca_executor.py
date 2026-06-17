from alpaca.trading.client import TradingClient
from alpaca.trading.requests import MarketOrderRequest
from alpaca.trading.enums import OrderSide, TimeInForce
from config import ALPACA_KEY, ALPACA_SECRET, POSITION_SIZE, STOP_LOSS

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


def execute_signal(client, ticker, signal, price):
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
        result = client.submit_order(order)
        print(f"[{ticker}] STOP LOSS TRIGGERED — down {drawdown_pct:.2f}% from entry ${entry_price:.2f}. Force SELL {shares} shares @ ~${price:.2f}")
        return result

    # BUY logic
    if signal == 1 and position is None and not pending:
        dollar_amount = portfolio_value * POSITION_SIZE
        shares = round(dollar_amount / price, 4)

        if shares <= 0:
            print(f"[{ticker}] Skipping BUY — calculated 0 shares")
            return None

        order = MarketOrderRequest(
            symbol=ticker,
            qty=shares,
            side=OrderSide.BUY,
            time_in_force=TimeInForce.DAY
        )
        result = client.submit_order(order)
        print(f"[{ticker}] BUY {shares} shares @ ~${price:.2f}")
        return result

    # SELL logic (model signal)
    elif signal == 0 and position is not None:
        shares = float(position.qty)
        order = MarketOrderRequest(
            symbol=ticker,
            qty=shares,
            side=OrderSide.SELL,
            time_in_force=TimeInForce.DAY
        )
        result = client.submit_order(order)
        print(f"[{ticker}] SELL {shares} shares @ ~${price:.2f}")
        return result

    else:
        if signal == 1:
            print(f"[{ticker}] BUY signal but position/order exists — skip")
        else:
            print(f"[{ticker}] SELL signal but no position — skip")
        return None