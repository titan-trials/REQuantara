"""
Synthetic-price unit tests for backtest/engine.py.

No network, no yfinance, no market data. Every expected value here is computed
by hand so the engine's accounting is pinned down independently of whatever
Yahoo happens to return today. Run with:

    python test_engine_synthetic.py

These exist because run_backtest is the single function every strategy result
in the project depends on, and until now it had no tests at all - which is how
the whole-share flooring bug survived long enough to be mistaken for a
"Sharpe is not scale-invariant" mystery in Version 12.
"""

import sys

import pandas as pd

from backtest.engine import run_backtest

PASS, FAIL = 0, 0


def check(name, got, want, tol=1e-6):
    global PASS, FAIL
    ok = abs(got - want) < tol
    if ok:
        PASS += 1
        print(f"  PASS  {name}: {got:.6f}")
    else:
        FAIL += 1
        print(f"  FAIL  {name}: got {got:.6f}, expected {want:.6f}")


# Existing assertions below pin ACCOUNTING (sizing, stop timing, fractional
# shares). They run with execution_lag=0 and cost_bps=0 so the new V15
# execution model does not confound what they were written to verify.
# The lag and cost behaviour get their own tests in test_execution_model.py.
def bt(df, capital, stop, size, **kw):
    kw.setdefault('execution_lag', 0)
    kw.setdefault('cost_bps', 0)
    return run_backtest(df, capital, stop, size, **kw)


def frame(prices, signals):
    return pd.DataFrame(
        {"Close": prices, "Signal": signals},
        index=pd.date_range("2020-01-01", periods=len(prices), freq="D"),
    )


# ---------------------------------------------------------------------------
print("\n[1] Full-size buy and hold, no stop, price doubles")
# 100% of $10,000 at $100 = 100 shares. Price -> $200. Final = $20,000.
df = bt(frame([100, 120, 150, 200], [1, 1, 1, 1]), 10000, 0.05, 1.0)
check("final portfolio value", df["Portfolio_Value"].iloc[-1], 20000.0)
check("cumulative strategy", df["Cumulative_Strategy"].iloc[-1], 2.0)

# ---------------------------------------------------------------------------
print("\n[2] Half-size buy and hold, price doubles")
# 50% of $10,000 = $5,000 at $100 = 50 shares, $5,000 stays in cash.
# Price -> $200 => 50 * 200 + 5000 = $15,000.
df = bt(frame([100, 120, 150, 200], [1, 1, 1, 1]), 10000, 0.05, 0.5)
check("final portfolio value", df["Portfolio_Value"].iloc[-1], 15000.0)

# ---------------------------------------------------------------------------
print("\n[3] Stop loss fires at exactly -5% and does NOT re-buy on the same bar")
# Buy 100 sh @ $100. Day 2 $96 vs floor 100*0.95=95 -> 96 > 95, hold.
# Day 3 $94 < 95 -> stop fires, sell 100 sh @ $94 = $9,400, stay flat this bar.
# Day 4 signal is still 1 and we are flat, so re-enter at $80 with $9,400.
df = bt(frame([100, 96, 94, 80], [1, 1, 1, 1]), 10000, 0.05, 1.0)
check("cash preserved on stop bar", df["Portfolio_Value"].iloc[2], 9400.0)
check("re-entry on the NEXT bar, not the same one", df["Portfolio_Value"].iloc[-1], 9400.0)

print("\n[3b] REGRESSION: stop must actually remove exposure")
# The old engine sold and re-bought at the same close on the same bar, so the
# stop only reset entry_price lower and the position stayed fully invested all
# the way down. Here price falls 100 -> 60 with the signal pinned at 1.
# Correct: stop at 94 (-6%), flat that bar, re-enter next bar at 70, ride to 60.
#   9400 -> re-enter at 70 -> 9400 * (60/70) = 8057.14
# Old (broken) behaviour compounded straight through and ended far lower.
df = bt(frame([100, 94, 70, 60], [1, 1, 1, 1]), 10000, 0.05, 1.0)
check("stop genuinely removed exposure for one bar",
      df["Portfolio_Value"].iloc[-1], 9400.0 * (60.0 / 70.0), tol=1e-4)

# ---------------------------------------------------------------------------
print("\n[4] Signal exit realises the gain")
# Buy 100 sh @ $100, sell on signal 0 at $130 => $13,000.
df = bt(frame([100, 110, 130, 130], [1, 1, 0, 0]), 10000, 0.05, 1.0)
check("final portfolio value", df["Portfolio_Value"].iloc[-1], 13000.0)

# ---------------------------------------------------------------------------
print("\n[5] REGRESSION: results are invariant to share PRICE LEVEL")
# This is the bug that broke position-size scaling. Two tickers with identical
# percentage paths but different absolute prices must produce identical returns.
# Under the old int() flooring they did not.
cheap = [20.0, 22.0, 26.0, 30.0]
pricey = [p * 18.25 for p in cheap]  # $365-ish, like JPM
for ps in (0.02, 0.05, 0.20, 0.50, 1.0):
    a = bt(frame(cheap, [1, 1, 1, 1]), 10000, 0.05, ps)
    b = bt(frame(pricey, [1, 1, 1, 1]), 10000, 0.05, ps)
    ra = a["Cumulative_Strategy"].iloc[-1]
    rb = b["Cumulative_Strategy"].iloc[-1]
    check(f"price-level invariance @ position_size={ps}", rb, ra)

# ---------------------------------------------------------------------------
print("\n[6] REGRESSION: return scales linearly with position_size")
# Price +50%. At position_size p, portfolio gain must be exactly 0.5 * p.
# Old behaviour: a $365 stock at p=0.02 bought ZERO shares and returned 0.0.
for ps in (0.02, 0.05, 0.20, 0.50, 1.0):
    df = bt(frame([365.0, 400.0, 500.0, 547.5], [1, 1, 1, 1]), 10000, 0.05, ps)
    got = df["Cumulative_Strategy"].iloc[-1] - 1.0
    check(f"gain @ position_size={ps}", got, 0.5 * ps)

# ---------------------------------------------------------------------------
print("\n[7] Dust guard: sub-$1 notional is skipped, not bought")
df = bt(frame([100.0, 200.0], [1, 1]), 10.0, 0.05, 0.05)  # $0.50 notional
check("stays in cash", df["Portfolio_Value"].iloc[-1], 10.0)

# ---------------------------------------------------------------------------
print(f"\n{'=' * 50}\n{PASS} passed, {FAIL} failed\n{'=' * 50}")
sys.exit(1 if FAIL else 0)
