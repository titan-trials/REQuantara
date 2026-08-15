"""
Synthetic-price tests for the Version 15 execution model.

Covers the two things test_engine_synthetic.py deliberately switches off so it
can pin pure accounting: EXECUTION LAG and TRANSACTION COSTS.

Why these exist:

  LAG - the old engine decided AND executed at the same close. Live cannot do
  that. The job runs after the close, submits a DAY market order, and Alpaca
  fills it at the next open (confirmed by real fills on 2026-08-14: submitted
  08:00 UTC, filled 13:33 UTC). Same-bar execution made every backtest
  optimistic, and made gap risk literally invisible - a stop would trigger and
  exit at the identical price, so a weekend gap could never cost anything.

  COSTS - with zero costs the backtest silently prefers high-turnover
  strategies. That biases which strategy auto_selector PICKS, not merely the
  returns it reports.

    python test_execution_model.py
"""

import sys

import pandas as pd

from backtest.engine import run_backtest

PASS, FAIL = 0, 0


def check(name, got, want, tol=1e-6):
    global PASS, FAIL
    if abs(got - want) < tol:
        PASS += 1
        print(f"  PASS  {name}: {got:.4f}")
    else:
        FAIL += 1
        print(f"  FAIL  {name}: got {got:.6f}, expected {want:.6f}")


def check_true(name, condition):
    global PASS, FAIL
    if bool(condition):
        PASS += 1
        print(f"  PASS  {name}")
    else:
        FAIL += 1
        print(f"  FAIL  {name}")


def frame(opens, closes, signals):
    return pd.DataFrame(
        {"Open": opens, "Close": closes, "Signal": signals},
        index=pd.date_range("2020-01-01", periods=len(closes), freq="D"),
    )


# ---------------------------------------------------------------------------
print("\n[1] A signal at today's close fills at TOMORROW's open")
# Signal on bar 0 (close 100). Fill on bar 1 at its OPEN of 110, not its close
# of 120 and not bar 0's close of 100.
#   $10,000 / 110 = 90.909 sh -> at final close 130 -> 90.909 * 130 = 11,818.18
df = run_backtest(frame([100, 110, 120], [100, 120, 130], [1, 1, 1]),
                  10000, 0.99, 1.0, cost_bps=0)
check("flat on the decision bar", df["Portfolio_Value"].iloc[0], 10000.0)
check("filled at the next OPEN, not its close",
      df["Portfolio_Value"].iloc[-1], 10000 / 110 * 130, tol=1e-4)

# ---------------------------------------------------------------------------
print("\n[2] REGRESSION: lag makes an overnight GAP cost real money")
# This is the whole point of the lag. The SELL is decided at a close of 100,
# and only THEN does the price gap down overnight to an open of 80.
#
#   same-bar: sells at that same 100 close      -> loses nothing
#   lagged:   sells at the next bar's 80 open   -> eats the gap, like live
#
# Exactly the AAPL 2026-08-03 scenario: -1.96% on Friday's close, -9.17% by
# Monday's open. The old engine structurally could not see this.
gap = frame(opens=[100, 100, 100, 80],
            closes=[100, 100, 100, 79],
            signals=[1, 1, 0, 0])
lagged = run_backtest(gap.copy(), 10000, 0.99, 1.0, cost_bps=0)
same_bar = run_backtest(gap.copy(), 10000, 0.99, 1.0,
                        cost_bps=0, execution_lag=0)
check("same-bar execution sees NO gap cost",
      same_bar["Portfolio_Value"].iloc[-1], 10000.0)
check("lagged execution pays the gap",
      lagged["Portfolio_Value"].iloc[-1], 8000.0, tol=1.0)
print(f"        same-bar ${same_bar['Portfolio_Value'].iloc[-1]:,.2f}  vs  "
      f"lagged ${lagged['Portfolio_Value'].iloc[-1]:,.2f}"
      f"   <- 20% of equity the old engine never charged you")

# ---------------------------------------------------------------------------
print("\n[3] Stop losses are lagged too - they are decided at a close")
# Entry at bar 1's open (100). Bar 2 closes at 90, breaching the 5% stop.
# The exit fills at bar 3's OPEN of 85, not at the 90 close.
df = run_backtest(frame([100, 100, 95, 85], [100, 100, 90, 84], [1, 1, 1, 1]),
                  10000, 0.05, 1.0, cost_bps=0)
check("exited at the following open", df["Portfolio_Value"].iloc[-1],
      10000 * 85 / 100, tol=1e-4)

# ---------------------------------------------------------------------------
print("\n[4] Transaction costs are charged on both sides")
# Buy and hold, one entry, no exit. Cost is 10 bps = 0.1% of the entry notional.
flat = frame([100] * 4, [100] * 4, [1, 1, 1, 1])
free = run_backtest(flat.copy(), 10000, 0.99, 1.0, cost_bps=0)
charged = run_backtest(flat.copy(), 10000, 0.99, 1.0, cost_bps=10)
check("no cost -> capital intact", free["Portfolio_Value"].iloc[-1], 10000.0)
check("one entry costs ~0.1%", charged["Portfolio_Value"].iloc[-1],
      10000 * (1 - 0.001), tol=0.5)

# ---------------------------------------------------------------------------
print("\n[5] REGRESSION: costs penalise churn, which is the point")
# Same flat price series. One strategy holds; the other flips in and out. With
# zero costs they are identical - which is precisely why a cost-free backtest
# silently favours high-turnover strategies in the auto-selector.
prices = [100] * 12
hold = frame(prices, prices, [1] * 12)
churn = frame(prices, prices, [1, 0] * 6)

hold_free = run_backtest(hold.copy(), 10000, 0.99, 1.0, cost_bps=0)
churn_free = run_backtest(churn.copy(), 10000, 0.99, 1.0, cost_bps=0)
check("with NO costs, churn looks identical to holding",
      churn_free["Portfolio_Value"].iloc[-1],
      hold_free["Portfolio_Value"].iloc[-1], tol=1e-4)

hold_cost = run_backtest(hold.copy(), 10000, 0.99, 1.0, cost_bps=10)
churn_cost = run_backtest(churn.copy(), 10000, 0.99, 1.0, cost_bps=10)
check_true("with costs, churn is strictly worse",
           churn_cost["Portfolio_Value"].iloc[-1]
           < hold_cost["Portfolio_Value"].iloc[-1])
print(f"        hold ${hold_cost['Portfolio_Value'].iloc[-1]:,.2f}  vs  "
      f"churn ${churn_cost['Portfolio_Value'].iloc[-1]:,.2f}")

# ---------------------------------------------------------------------------
print("\n[6] Sizing accounts for the fee, so it never overdraws")
# At position_size 1.0 the entry outlay INCLUDING cost must equal capital
# exactly. Sizing off the raw price would spend more than we have.
df = run_backtest(frame([100] * 3, [100] * 3, [1, 1, 1]),
                  10000, 0.99, 1.0, cost_bps=50)
check_true("cash never goes negative", df["Portfolio_Value"].min() > 0)
check("outlay equals capital net of the fee",
      df["Portfolio_Value"].iloc[-1], 10000 * (1 - 0.005), tol=1.0)

# ---------------------------------------------------------------------------
print("\n[7] Falls back to Close when the frame has no Open column")
# Older cached frames only carried Close/High/Low.
no_open = pd.DataFrame(
    {"Close": [100, 110, 120], "Signal": [1, 1, 1]},
    index=pd.date_range("2020-01-01", periods=3, freq="D"),
)
df = run_backtest(no_open, 10000, 0.99, 1.0, cost_bps=0)
check("still produces a curve", len(df["Portfolio_Value"]), 3)
check("no NaN in the curve", int(df["Portfolio_Value"].isna().sum()), 0)

print(f"\n{'=' * 50}\n{PASS} passed, {FAIL} failed\n{'=' * 50}")
sys.exit(1 if FAIL else 0)
