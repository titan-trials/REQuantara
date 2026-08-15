"""
Network-free tests for strategy/alpaca_executor.py order guards.

These pin two fail-OPEN bugs found on 2026-08-14, both of which could place a
duplicate order or skip a stop loss:

  1. get_pending_orders() compared str(o.status) - which alpaca-py renders as
     'OrderStatus.ACCEPTED' - against lowercase literals like 'accepted'. It
     matched nothing, so the duplicate-order guard reported zero pending
     orders regardless of what was actually queued.

  2. Both get_position() and get_pending_orders() used bare excepts that
     returned None / [] on failure, making "the API call failed" look
     identical to "you hold nothing" and "nothing is queued".

    python test_alpaca_executor.py
"""

import sys

from alpaca.common.exceptions import APIError

import strategy.alpaca_executor as EX

PASS, FAIL = 0, 0


def check(name, got, want):
    global PASS, FAIL
    if got == want:
        PASS += 1
        print(f"  PASS  {name}")
    else:
        FAIL += 1
        print(f"  FAIL  {name}\n          got  {got!r}\n          want {want!r}")


class StubOrder:
    def __init__(self, symbol, status):
        self.symbol = symbol
        self.status = status


class StubClient:
    def __init__(self, orders=None, position=None, position_error=None):
        self._orders = orders or []
        self._position = position
        self._position_error = position_error

    def get_orders(self):
        return self._orders

    def get_open_position(self, ticker):
        if self._position_error:
            raise self._position_error
        return self._position


class BrokenOrdersClient(StubClient):
    def get_orders(self):
        raise ConnectionError("simulated Alpaca outage")


# ---------------------------------------------------------------------------
print("\n[1] Status normalization handles every rendering alpaca-py produces")
check("enum repr", EX.normalize_status("OrderStatus.ACCEPTED"), "accepted")
check("plain string", EX.normalize_status("accepted"), "accepted")
check("uppercase", EX.normalize_status("FILLED"), "filled")
check("underscored enum", EX.normalize_status("OrderStatus.PENDING_NEW"), "pending_new")

# ---------------------------------------------------------------------------
print("\n[2] REGRESSION: enum-style statuses are seen as pending")
# This is the exact failure. Before the fix this returned [] and the guard
# waved a duplicate BUY straight through.
client = StubClient(orders=[StubOrder("NVDA", "OrderStatus.ACCEPTED")])
check("accepted order detected", len(EX.get_pending_orders(client, "NVDA")), 1)

client = StubClient(orders=[StubOrder("NVDA", "OrderStatus.NEW")])
check("new order detected", len(EX.get_pending_orders(client, "NVDA")), 1)

client = StubClient(orders=[StubOrder("NVDA", "OrderStatus.PARTIALLY_FILLED")])
check("partially filled counts as live",
      len(EX.get_pending_orders(client, "NVDA")), 1)

# ---------------------------------------------------------------------------
print("\n[3] Finished orders are NOT counted as pending")
for status in ("OrderStatus.FILLED", "OrderStatus.CANCELED",
               "OrderStatus.EXPIRED", "OrderStatus.REJECTED",
               "OrderStatus.REPLACED", "OrderStatus.DONE_FOR_DAY"):
    client = StubClient(orders=[StubOrder("NVDA", status)])
    check(f"{EX.normalize_status(status)} is terminal",
          len(EX.get_pending_orders(client, "NVDA")), 0)

# ---------------------------------------------------------------------------
print("\n[4] Unknown statuses count as PENDING, not terminal")
# Errs toward skipping a buy rather than duplicating a position.
client = StubClient(orders=[StubOrder("NVDA", "OrderStatus.SOME_FUTURE_STATE")])
check("unrecognised status treated as live",
      len(EX.get_pending_orders(client, "NVDA")), 1)

# ---------------------------------------------------------------------------
print("\n[5] Other tickers' orders are ignored")
client = StubClient(orders=[
    StubOrder("TSLA", "OrderStatus.ACCEPTED"),
    StubOrder("AAPL", "OrderStatus.NEW"),
])
check("NVDA sees none of them", len(EX.get_pending_orders(client, "NVDA")), 0)
check("TSLA sees its own", len(EX.get_pending_orders(client, "TSLA")), 1)

# ---------------------------------------------------------------------------
print("\n[6] REGRESSION: API failure raises instead of reporting 'nothing pending'")
try:
    EX.get_pending_orders(BrokenOrdersClient(), "NVDA")
    check("raises on outage", False, True)
except ConnectionError:
    check("raises on outage", True, True)
except Exception as e:
    check("raises on outage", f"wrong type {type(e).__name__}", True)

# ---------------------------------------------------------------------------
print("\n[7] get_position distinguishes 'flat' from 'API broke'")
check("real position returned",
      EX.get_position(StubClient(position="POSITION"), "NVDA"), "POSITION")

missing = APIError('{"code":40410000,"message":"position does not exist"}')
check("'position does not exist' -> None",
      EX.get_position(StubClient(position_error=missing), "NVDA"), None)

try:
    EX.get_position(StubClient(position_error=ConnectionError("outage")), "NVDA")
    check("outage raises instead of looking flat", False, True)
except ConnectionError:
    check("outage raises instead of looking flat", True, True)
except Exception as e:
    check("outage raises instead of looking flat",
          f"wrong type {type(e).__name__}", True)

print(f"\n{'=' * 50}\n{PASS} passed, {FAIL} failed\n{'=' * 50}")
sys.exit(1 if FAIL else 0)
