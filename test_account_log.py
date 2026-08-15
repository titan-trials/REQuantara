"""
Network-free tests for evaluation/account_log.py using a fake Alpaca client.

Alpaca returns numerics as strings and enums as 'OrderSide.BUY', so the stubs
here mimic that faithfully - the parsing is most of what can go wrong.

The leverage case is modelled on the real Version 11 numbers (equity
$12,010.34, exposure $22,907.63, 1.91x) so the warning path is exercised
against a situation known to have actually occurred.

    python test_account_log.py
"""

import csv
import os
import shutil
import sys
import tempfile

import evaluation.account_log as AL

PASS, FAIL = 0, 0


def check(name, ok, detail=""):
    global PASS, FAIL
    if ok:
        PASS += 1
        print(f"  PASS  {name}")
    else:
        FAIL += 1
        print(f"  FAIL  {name} {detail}")


def read_csv(path):
    with open(path, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


# ---------------------------------------------------------------------------
# Stubs
# ---------------------------------------------------------------------------

class StubAccount:
    def __init__(self, equity, cash, long_mv, last_equity=None, buying_power="0"):
        self.equity = str(equity)
        self.last_equity = str(last_equity if last_equity is not None else equity)
        self.cash = str(cash)
        self.long_market_value = str(long_mv)
        self.short_market_value = "0"
        self.buying_power = str(buying_power)


class StubPosition:
    def __init__(self, symbol, qty, entry, current):
        self.symbol = symbol
        self.qty = str(qty)
        self.avg_entry_price = str(entry)
        self.current_price = str(current)
        self.market_value = str(qty * current)
        self.cost_basis = str(qty * entry)
        self.unrealized_pl = str(qty * (current - entry))
        self.unrealized_plpc = str((current - entry) / entry)


class StubOrder:
    def __init__(self, oid, symbol, side, filled_qty, filled_price, status="filled"):
        self.id = oid
        self.symbol = symbol
        self.side = f"OrderSide.{side.upper()}"
        self.status = f"OrderStatus.{status.upper()}"
        self.qty = str(filled_qty)
        self.filled_qty = str(filled_qty)
        self.filled_avg_price = str(filled_price) if filled_price else None
        self.submitted_at = "2026-08-14T20:00:00Z"
        self.filled_at = "2026-08-14T20:00:05Z"
        self.order_type = "OrderType.MARKET"


class StubClient:
    def __init__(self, account, positions, orders):
        self._a, self._p, self._o = account, positions, orders

    def get_account(self):
        return self._a

    def get_all_positions(self):
        return self._p

    def get_orders(self, filter=None):
        return self._o


class BrokenClient:
    def get_account(self):
        raise ConnectionError("simulated Alpaca outage")

    def get_all_positions(self):
        raise ConnectionError("simulated Alpaca outage")

    def get_orders(self, filter=None):
        raise ConnectionError("simulated Alpaca outage")


workdir = tempfile.mkdtemp()
os.chdir(workdir)

# ---------------------------------------------------------------------------
print("\n[1] Healthy account, no leverage")
client = StubClient(
    StubAccount(equity=12010.34, cash=2010.34, long_mv=10000.00, last_equity=11900.00),
    [StubPosition("NVDA", 25.0, 200.0, 220.0), StubPosition("AAPL", 10.0, 300.0, 300.0)],
    [StubOrder("o1", "NVDA", "buy", 25.0, 200.0)],
)
AL.log_account_state(client)

eq = read_csv(AL.EQUITY_LOG)
check("equity_log has one row", len(eq) == 1, f"(got {len(eq)})")
check("equity parsed", eq[0]["Equity"] == "12010.34", eq[0]["Equity"])
check("position count", eq[0]["PositionCount"] == "2", eq[0]["PositionCount"])
check("leverage below 1.0", float(eq[0]["Leverage"]) < 1.0, eq[0]["Leverage"])
check("no phantom margin debt", float(eq[0]["MarginDebt"]) == 0.0, eq[0]["MarginDebt"])
check("daily P&L computed", eq[0]["DailyPnL"] == "110.34", eq[0]["DailyPnL"])

pos = read_csv(AL.POSITIONS_LOG)
check("positions_log has two rows", len(pos) == 2, f"(got {len(pos)})")
check("real avg_entry_price recorded", pos[0]["AvgEntryPrice"] == "200.0",
      pos[0]["AvgEntryPrice"])
check("unrealized P&L", pos[0]["UnrealizedPL"] == "500.0", pos[0]["UnrealizedPL"])

fills = read_csv(AL.FILLS_LOG)
check("one fill logged", len(fills) == 1, f"(got {len(fills)})")
check("side normalised to 'buy'", fills[0]["Side"] == "buy", fills[0]["Side"])
check("notional computed", fills[0]["Notional"] == "5000.0", fills[0]["Notional"])

# ---------------------------------------------------------------------------
print("\n[2] Re-running the same day appends equity but does NOT duplicate fills")
AL.log_account_state(client)
check("equity_log appended", len(read_csv(AL.EQUITY_LOG)) == 2)
check("fills deduped by order id", len(read_csv(AL.FILLS_LOG)) == 1,
      f"(got {len(read_csv(AL.FILLS_LOG))})")

# ---------------------------------------------------------------------------
print("\n[3] Rejected / unfilled orders are NOT recorded as fills")
# This is the Version 11 phantom-position bug: TSLA's Jul 22 re-entry was
# rejected by Alpaca but logged as a real trade.
client_rejected = StubClient(
    StubAccount(equity=12010.34, cash=2010.34, long_mv=10000.00),
    [],
    [StubOrder("o2", "TSLA", "buy", 0.0, None, status="rejected")],
)
AL.log_account_state(client_rejected)
fills = read_csv(AL.FILLS_LOG)
check("rejected order not logged", len(fills) == 1, f"(got {len(fills)})")
check("no TSLA phantom", all(f["Ticker"] != "TSLA" for f in fills))

# ---------------------------------------------------------------------------
print("\n[4] The Version 11 leverage scenario is detected")
# Real numbers from the audit: equity $12,010.34, positions $22,907.63.
client_levered = StubClient(
    StubAccount(equity=12010.34, cash=-10897.29, long_mv=22907.63),
    [StubPosition("NVDA", 100.0, 200.0, 229.0763)],
    [],
)
AL.log_account_state(client_levered)
eq = read_csv(AL.EQUITY_LOG)[-1]
lev = float(eq["Leverage"])
check("leverage ~1.91x detected", abs(lev - 1.9073) < 0.01, f"(got {lev})")
check("margin debt ~$10,897", abs(float(eq["MarginDebt"]) - 10897.29) < 1.0,
      eq["MarginDebt"])
check("negative cash recorded as-is", float(eq["Cash"]) < 0, eq["Cash"])

# ---------------------------------------------------------------------------
print("\n[5] An Alpaca outage degrades gracefully and never raises")
before = len(read_csv(AL.EQUITY_LOG))
try:
    status = AL.log_account_state(BrokenClient())
    check("returned instead of raising", True)
    check("reported error status", status["equity"] == "error", str(status))
except Exception as e:
    check("returned instead of raising", False, f"(raised {type(e).__name__})")
check("no partial row written", len(read_csv(AL.EQUITY_LOG)) == before)

os.chdir("/")
shutil.rmtree(workdir, ignore_errors=True)

print(f"\n{'=' * 50}\n{PASS} passed, {FAIL} failed\n{'=' * 50}")
sys.exit(1 if FAIL else 0)
