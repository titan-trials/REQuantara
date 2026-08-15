"""
Network-free tests for trading-date logging.

The bug this pins: logs were stamped with `datetime.now()`, the date the
script happened to run, rather than the date of the market data it acted on.
The scheduled job fires at 21:00 UTC and any manual run after ~20:00 ET rolls
past UTC midnight - which is how Friday 2026-08-14's closing prices ended up
recorded on Saturday 2026-08-15.

    python test_trading_date.py
"""

import csv
import os
import shutil
import sys
import tempfile
from datetime import datetime

import pandas as pd

import evaluation.account_log as AL
from strategy.paper_trader import get_trading_date, log_signals

PASS, FAIL = 0, 0


def check(name, got, want):
    global PASS, FAIL
    if got == want:
        PASS += 1
        print(f"  PASS  {name}")
    else:
        FAIL += 1
        print(f"  FAIL  {name}\n          got  {got!r}\n          want {want!r}")


def bars(dates):
    return pd.DataFrame({"Close": [1.0] * len(dates)}, index=pd.to_datetime(dates))


# ---------------------------------------------------------------------------
print("\n[1] Trading date comes from the LAST bar of data")
check("normal week",
      get_trading_date(bars(["2026-08-12", "2026-08-13", "2026-08-14"])),
      "2026-08-14")
check("single bar", get_trading_date(bars(["2026-08-14"])), "2026-08-14")

# ---------------------------------------------------------------------------
print("\n[2] REGRESSION: Friday's data never lands on Saturday")
# The exact 2026-08-14 scenario: a run at 19:14 PDT is 02:14 UTC on Saturday
# the 15th. The data's last bar is still Friday the 14th.
friday = bars(["2026-08-13", "2026-08-14"])
check("last bar is Friday", get_trading_date(friday), "2026-08-14")
check("2026-08-15 is a Saturday (premise check)",
      datetime(2026, 8, 15).strftime("%A"), "Saturday")

# ---------------------------------------------------------------------------
print("\n[3] Empty / missing data returns None so callers can fall back")
check("empty frame", get_trading_date(bars([])), None)
check("None input", get_trading_date(None), None)

# ---------------------------------------------------------------------------
print("\n[4] log_signals writes the trading date, not today's date")
workdir = tempfile.mkdtemp()
os.chdir(workdir)

rows = [{"Ticker": "NVDA", "Strategy": "EMA Crossover", "Signal": 1,
         "Price": 225.16, "Action": "BUY", "Exit_Reason": "SIGNAL"}]
log_signals(rows, trading_date="2026-08-14")

with open("results/paper_trading_log.csv", newline="") as f:
    logged = list(csv.DictReader(f))[0]["Timestamp"]

check("date component is the trading date", logged[:10], "2026-08-14")
check("time component is the actual run time",
      logged[11:13], datetime.now().strftime("%H"))
check("does NOT use today's date",
      logged.startswith(datetime.now().strftime("%Y-%m-%d")),
      datetime.now().strftime("%Y-%m-%d") == "2026-08-14")

# ---------------------------------------------------------------------------
print("\n[5] account_log honours the trading date too")


class StubAccount:
    equity = "12120.89"
    last_equity = "12013.92"
    cash = "877.75"
    long_market_value = "11243.14"
    short_market_value = "0"
    buying_power = "27840.21"


class StubPosition:
    symbol = "JPM"
    qty = "14.6847"
    avg_entry_price = "328.5512"
    current_price = "362.84"
    market_value = "5328.20"
    cost_basis = "4824.68"
    unrealized_pl = "503.52"
    unrealized_plpc = "0.10436"


class StubClient:
    def get_account(self):
        return StubAccount()

    def get_all_positions(self):
        return [StubPosition()]

    def get_orders(self, filter=None):
        return []


AL.log_account_state(StubClient(), trading_date="2026-08-14")

with open(AL.EQUITY_LOG, newline="") as f:
    eq = list(csv.DictReader(f))[0]
with open(AL.POSITIONS_LOG, newline="") as f:
    pos = list(csv.DictReader(f))[0]

check("equity_log Date", eq["Date"], "2026-08-14")
check("equity_log Timestamp date", eq["Timestamp"][:10], "2026-08-14")
check("positions_log Date", pos["Date"], "2026-08-14")
check("leverage still computed", round(float(eq["Leverage"]), 2), 0.93)

# ---------------------------------------------------------------------------
print("\n[6] Fallback to the clock when there is no market data")
log_signals(rows, log_file="results/fallback.csv", trading_date=None)
with open("results/fallback.csv", newline="") as f:
    fb = list(csv.DictReader(f))[0]["Timestamp"]
check("falls back to today", fb[:10], datetime.now().strftime("%Y-%m-%d"))

os.chdir("/")
shutil.rmtree(workdir, ignore_errors=True)

print(f"\n{'=' * 50}\n{PASS} passed, {FAIL} failed\n{'=' * 50}")
sys.exit(1 if FAIL else 0)
