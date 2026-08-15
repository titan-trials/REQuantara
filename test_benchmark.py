"""
Network-free tests for the Version 16 benchmark work.

Three things, all of which the project got wrong before:

  1. Sharpe subtracted no risk-free rate. It is the largest term in
     compute_composite_score (x0.5), so this was influencing which strategy got
     SELECTED, not just what was reported.

  2. `Win_Rate` was never a win rate - it counted the fraction of DAYS the
     portfolio rose, with cash days counting as losses. Renamed Up_Day_Rate.

  3. Buy & Hold was never a candidate, and the one time it was used as a
     control arm it was scored WITH a 5% stop - making it "always long, stopped
     out, re-entered next bar", a whipsaw strategy rather than a hold.

    python test_benchmark.py
"""

import sys

import pandas as pd

from backtest.engine import run_backtest
from evaluation.metrics import get_metrics
from evaluation.risk_free import resolve_daily_risk_free, TRADING_DAYS
from strategy.auto_selector import BUY_AND_HOLD, RULE_BASED_STRATEGIES

PASS, FAIL = 0, 0


def check(name, got, want, tol=1e-6):
    global PASS, FAIL
    ok = (abs(got - want) < tol) if isinstance(want, (int, float)) else (got == want)
    if ok:
        PASS += 1
        print(f"  PASS  {name}")
    else:
        FAIL += 1
        print(f"  FAIL  {name}\n          got  {got!r}\n          want {want!r}")


def check_true(name, condition):
    global PASS, FAIL
    if bool(condition):
        PASS += 1
        print(f"  PASS  {name}")
    else:
        FAIL += 1
        print(f"  FAIL  {name}")


def frame(prices, signals):
    return pd.DataFrame(
        {"Open": prices, "Close": prices, "Signal": signals},
        index=pd.bdate_range("2020-01-01", periods=len(prices)),
    )


# ---------------------------------------------------------------------------
print("\n[1] A risk-free rate lowers Sharpe, and zero reproduces the old figure")
# Needs real variance - a perfectly smooth exponential has std ~= 0, which
# makes Sharpe explode to ~1e14 and hides whatever you were trying to measure.
import numpy as np
_rng = np.random.default_rng(7)
# Drift must dominate the noise, or the sign of Sharpe is a coin flip over a
# short sample: at drift 0.0008 and vol 0.012 the standard error of the mean
# over 120 days is larger than the drift itself.
rising = list(100 * np.cumprod(1 + _rng.normal(0.0020, 0.010, 250)))
df = run_backtest(frame(rising, [1] * 250), 10000, 0.99, 1.0,
                  cost_bps=0, execution_lag=0)

zero = get_metrics(df.copy(), 10000, risk_free=0)["Sharpe_Ratio"]
four = get_metrics(df.copy(), 10000, risk_free=0.04)["Sharpe_Ratio"]

check_true("rf=0 gives a positive Sharpe", zero > 0)
check_true("a 4% rate reduces it", four < zero)
print(f"        rf=0 -> {zero:.3f}   rf=4% -> {four:.3f}")

# ---------------------------------------------------------------------------
print("\n[2] The penalty scales as rf/volatility, so LOW-vol loses more Sharpe")
# This is the part that shifts selection. A quiet strategy is hurt more than a
# volatile one, because the same cash yield is a bigger share of its return.
quiet = list(100 * np.cumprod(1 + _rng.normal(0.0006, 0.004, 250)))   # ~6% ann vol
wild = list(100 * np.cumprod(1 + _rng.normal(0.0006, 0.030, 250)))    # ~48% ann vol

q = run_backtest(frame(quiet, [1] * 250), 10000, 0.99, 1.0,
                 cost_bps=0, execution_lag=0)
w = run_backtest(frame(wild, [1] * 250), 10000, 0.99, 1.0,
                 cost_bps=0, execution_lag=0)

q_drop = (get_metrics(q.copy(), 10000, risk_free=0)["Sharpe_Ratio"]
          - get_metrics(q.copy(), 10000, risk_free=0.04)["Sharpe_Ratio"])
w_drop = (get_metrics(w.copy(), 10000, risk_free=0)["Sharpe_Ratio"]
          - get_metrics(w.copy(), 10000, risk_free=0.04)["Sharpe_Ratio"])
check_true("low-vol Sharpe falls further than high-vol", q_drop > w_drop)
print(f"        low-vol drop {q_drop:.3f}   high-vol drop {w_drop:.3f}")

# ---------------------------------------------------------------------------
print("\n[3] resolve_daily_risk_free handles every input form")
idx = pd.bdate_range("2020-01-01", periods=10)
check("explicit zero", float(resolve_daily_risk_free(idx, 0).sum()), 0.0)
check("constant annual compounds geometrically",
      float(resolve_daily_risk_free(idx, 0.04).iloc[0]),
      (1.04 ** (1 / TRADING_DAYS)) - 1)
series = pd.Series(0.001, index=idx)
check("a Series is passed through",
      float(resolve_daily_risk_free(idx, series).iloc[0]), 0.001)

# ---------------------------------------------------------------------------
print("\n[4] Metrics expose the benchmark, and Win_Rate is gone")
m = get_metrics(df.copy(), 10000, risk_free=0)
check_true("Market_Return present", "Market_Return" in m)
check_true("Vs_Market present", "Vs_Market" in m)
check_true("Up_Day_Rate present", "Up_Day_Rate" in m)
check_true("Win_Rate REMOVED", "Win_Rate" not in m)
check("Vs_Market is strategy minus market",
      m["Vs_Market"], round(m["Total_Return"] - m["Market_Return"], 2), tol=0.02)

# ---------------------------------------------------------------------------
print("\n[5] Buy & Hold is registered as a candidate")
names = [s["name"] for s in RULE_BASED_STRATEGIES]
check_true("present in the candidate list", BUY_AND_HOLD in names)
bh = next(s for s in RULE_BASED_STRATEGIES if s["name"] == BUY_AND_HOLD)
check("scored with stop_loss = 0", bh["stop_loss"], 0.0)

built = bh["signal"](bh["build"](frame([100, 90, 80, 70], [0, 0, 0, 0])))
check_true("always signals long", (built["Signal"] == 1).all())

# ---------------------------------------------------------------------------
print("\n[6] REGRESSION: a stopped 'buy & hold' is NOT buy & hold")
# The Round 3 control arm passed STOP_LOSS=0.05. On a series that dips 6% and
# recovers, that exits at the bottom and re-enters higher - the opposite of
# holding. Stopless must simply track the asset.
dip = [100, 100, 93, 100, 110]
stopless = run_backtest(frame(dip, [1] * 5), 10000, 0.0, 1.0,
                        cost_bps=0, execution_lag=0)
stopped = run_backtest(frame(dip, [1] * 5), 10000, 0.05, 1.0,
                       cost_bps=0, execution_lag=0)

check("true B&H simply tracks the asset",
      stopless["Portfolio_Value"].iloc[-1], 11000.0, tol=1.0)
check_true("the stopped version is worse",
           stopped["Portfolio_Value"].iloc[-1]
           < stopless["Portfolio_Value"].iloc[-1])
print(f"        stopless ${stopless['Portfolio_Value'].iloc[-1]:,.2f}  vs  "
      f"stopped ${stopped['Portfolio_Value'].iloc[-1]:,.2f}")

# ---------------------------------------------------------------------------
print("\n[7] Live Buy & Hold always returns 1, and bypasses the stop")
from strategy.paper_trader import generate_current_signal
import inspect
from strategy.alpaca_executor import execute_signal

falling = pd.DataFrame(
    {"Open": [100, 90, 80], "Close": [100, 90, 80],
     "High": [101, 91, 81], "Low": [99, 89, 79]},
    index=pd.bdate_range("2020-01-01", periods=3),
)
check("signals long even while falling",
      generate_current_signal(falling, BUY_AND_HOLD, 10000, 0.05, 1.0), 1)
check_true("execute_signal accepts apply_stop_loss",
           "apply_stop_loss" in inspect.signature(execute_signal).parameters)
check("and it defaults to ON for every other strategy",
      inspect.signature(execute_signal).parameters["apply_stop_loss"].default,
      True)

print(f"\n{'=' * 50}\n{PASS} passed, {FAIL} failed\n{'=' * 50}")
sys.exit(1 if FAIL else 0)
