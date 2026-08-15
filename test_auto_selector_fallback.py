"""
Network-free tests for auto_selector's failure handling.

Verifies the churn fix: a strategy that fails to evaluate must NOT silently
hand the win to the remaining candidates. It must abandon the run and keep the
previous assignment.

    python test_auto_selector_fallback.py
"""

import os
import shutil
import sys
import tempfile

import pandas as pd

import strategy.auto_selector as A

PASS, FAIL = 0, 0


def check(name, ok, detail=""):
    global PASS, FAIL
    if ok:
        PASS += 1
        print(f"  PASS  {name}")
    else:
        FAIL += 1
        print(f"  FAIL  {name} {detail}")


workdir = tempfile.mkdtemp()
os.chdir(workdir)
A.ASSIGNMENTS_FILE = os.path.join("results", "strategy_assignments.json")

GOOD = pd.DataFrame(
    {
        "Best_Strategy": ["Random Forest", "Logistic Regression"],
        "Score": [1.10, 0.95],
        "Sharpe": [1.2, 1.0],
        "Total_Return": [50.0, 30.0],
        "Max_Drawdown": [-10.0, -12.0],
    },
    index=pd.Index(["NVDA", "TSLA"], name="Ticker"),
)

# ---------------------------------------------------------------------------
print("\n[1] Round-trip persistence of known-good assignments")
A.save_assignments(GOOD)
loaded = A.load_last_good_assignments()
check("file written", os.path.exists(A.ASSIGNMENTS_FILE))
check("strategies survive round-trip",
      list(loaded["Best_Strategy"]) == ["Random Forest", "Logistic Regression"],
      str(None if loaded is None else list(loaded["Best_Strategy"])))
check("index preserved", list(loaded.index) == ["NVDA", "TSLA"])

# ---------------------------------------------------------------------------
print("\n[2] A failing candidate abandons the run and keeps the old assignment")
# This is the exact scenario that produced AAPL's 15 one-day flips: one strategy
# blows up, the others evaluate fine. Old code silently dropped the failure.
_orig_strict = A._auto_select_strict


def boom(*args, **kwargs):
    raise A.StrategyEvaluationError("AAPL / EMA Crossover failed: simulated yfinance timeout")


A._auto_select_strict = boom
result = A.auto_select(["NVDA", "TSLA"], "2015-01-01", "2024-01-01", 10000, 0.05, 1.0)
check("returned the previous assignment, unchanged",
      list(result["Best_Strategy"]) == ["Random Forest", "Logistic Regression"],
      str(list(result["Best_Strategy"])))
check("did not overwrite the known-good file",
      list(A.load_last_good_assignments()["Best_Strategy"])
      == ["Random Forest", "Logistic Regression"])

# ---------------------------------------------------------------------------
print("\n[3] Failure with NO prior assignment refuses to trade rather than guess")
os.remove(A.ASSIGNMENTS_FILE)
try:
    A.auto_select(["NVDA"], "2015-01-01", "2024-01-01", 10000, 0.05, 1.0)
    check("raised instead of returning a guess", False, "(no exception raised)")
except RuntimeError as e:
    check("raised RuntimeError", "Refusing to trade" in str(e), str(e)[:80])

A._auto_select_strict = _orig_strict

# ---------------------------------------------------------------------------
print("\n[4] evaluate_rule_based raises (does not swallow) on a bad frame")
try:
    # Frame with no Close column - every strategy must fail loudly.
    A.evaluate_rule_based("FAKE", pd.DataFrame({"Nonsense": [1, 2, 3]}), 10000, 0.05, 1.0)
    check("raised StrategyEvaluationError", False, "(returned normally)")
except A.StrategyEvaluationError:
    check("raised StrategyEvaluationError", True)
except Exception as e:
    check("raised StrategyEvaluationError", False, f"(raised {type(e).__name__} instead)")

os.chdir("/")
shutil.rmtree(workdir, ignore_errors=True)

print(f"\n{'=' * 50}\n{PASS} passed, {FAIL} failed\n{'=' * 50}")
sys.exit(1 if FAIL else 0)
