from alpaca.trading.client import TradingClient
from alpaca.trading.requests import MarketOrderRequest, GetAssetsRequest
from alpaca.trading.enums import OrderSide, TimeInForce, AssetClass
from config import ALPACA_KEY, ALPACA_SECRET, ALPACA_BASE_URL, POSITION_SIZE

def get_client():
    return TradingClient(ALPACA_KEY, ALPACA_SECRET, paper=True)

def get_account(client):
    return client.get_account()

def get_position(client, ticker):
    try:
        return client.get_open_position(ticker)
    except:
        return None

def execute_signal(client, ticker, signal, price):
    account = get_account(client)
    portfolio_value = float(account.portfolio_value)
    position = get_position(client, ticker)

    # BUY logic
    if signal == 1 and position is None:
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

    # SELL logic
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
            print(f"[{ticker}] BUY signal but already holding — skip")
        else:
            print(f"[{ticker}] SELL signal but no position — skip")
        return None