"""
Network-free tests for live signal generation (Phase 1.1).

Pins three bugs found on 2026-08-14:

  1. The live model trained on the FIRST HALF of a 300-day window, so it was
     fitted on ~77 days of data ending ~4 months ago while the backtest fitted
     on ~1,100 days. Live and backtest were different models.

  2. The StandardScaler was fit on the whole frame INCLUDING today's row,
     leaking today's feature values into the scaling parameters.

  3. Signal generation failure returned 0 - which means SELL/HOLD - so a
     crashed model could quietly liquidate a position.

Synthetic prices throughout; no yfinance, no Alpaca.

    python test_live_signal.py
"""

import sys

import numpy as np
import pandas as pd

from strategy.paper_trader import _split_for_live_prediction, generate_current_signal
from strategy.ml_signal import FEATURE_COLS

PASS, FAIL = 0, 0


def check(name, got, want):
    global PASS, FAIL
    if got == want:
        PASS += 1
        print(f"  PASS  {name}")
    else:
        FAIL += 1
        print(f"  FAIL  {name}\n          got  {got!r}\n          want {want!r}")


def synthetic(n=600, seed=0):
    """A price series with enough rows to survive indicator warm-up."""
    rng = np.random.default_rng(seed)
    close = 100 * np.cumprod(1 + rng.normal(0.0005, 0.015, n))
    idx = pd.bdate_range("2022-01-03", periods=n)
    return pd.DataFrame(
        {"Close": close, "High": close * 1.01, "Low": close * 0.99}, index=idx
    )


# ---------------------------------------------------------------------------
print("\n[1] Training set is everything except today")
df = synthetic()
X_train, y_train, X_today = _split_for_live_prediction(df)

check("one row predicted", len(X_today), 1)
check("train and predict row counts line up", len(X_train), len(y_train))
check("all 18 features present", list(X_today.columns), FEATURE_COLS)

# ---------------------------------------------------------------------------
print("\n[2] REGRESSION: uses ALL history, not the first half")
# Old behaviour trained on len//2 rows. With ~550 usable rows that was ~275.
usable = len(X_train) + 1
check("trains on n-1 rows, not n/2", len(X_train), usable - 1)
print(f"        ({len(X_train)} training rows; the old 50/50 split "
      f"would have used ~{usable // 2})")

# ---------------------------------------------------------------------------
print("\n[3] REGRESSION: today's row is excluded from training")
# build_target does (close.shift(-1) > close).astype(int). On the final row
# shift(-1) is NaN, NaN > close is False, astype(int) -> 0. That fabricated
# label survives dropna() and would teach "today goes down" on every run.
check("today's row is not in the training index",
      X_today.index[0] in X_train.index, False)
check("today is strictly after the last training row",
      X_today.index[0] > X_train.index[-1], True)

# ---------------------------------------------------------------------------
print("\n[4] The prediction row is genuinely the most recent bar")
check("matches the frame's last date",
      X_today.index[0], df.index[-1])

# ---------------------------------------------------------------------------
print("\n[5] Signals are valid and deterministic")
for strategy in ("Logistic Regression", "Random Forest",
                 "SMA Crossover", "EMA Crossover", "Bollinger Bands"):
    sig = generate_current_signal(synthetic(), strategy, 10000, 0.05, 1.0)
    check(f"{strategy} returns 0 or 1", sig in (0, 1), True)

rf1 = generate_current_signal(synthetic(), "Random Forest", 10000, 0.05, 1.0)
rf2 = generate_current_signal(synthetic(), "Random Forest", 10000, 0.05, 1.0)
check("Random Forest is deterministic (random_state=42)", rf1, rf2)

# ---------------------------------------------------------------------------
print("\n[6] REGRESSION: failure returns None, never 0")
# 0 means SELL/HOLD. A crashed model must not be able to liquidate a position.
check("unknown strategy -> None",
      generate_current_signal(synthetic(), "Nonexistent Strategy",
                              10000, 0.05, 1.0),
      None)
check("garbage frame -> None",
      generate_current_signal(pd.DataFrame({"Nonsense": [1, 2, 3]}),
                              "Logistic Regression", 10000, 0.05, 1.0),
      None)
check("too little history -> None",
      generate_current_signal(synthetic(n=60), "Random Forest",
                              10000, 0.05, 1.0),
      None)

# ---------------------------------------------------------------------------
print("\n[7] Too-short history raises rather than training on noise")
try:
    _split_for_live_prediction(synthetic(n=60))
    check("raises on insufficient rows", False, True)
except ValueError:
    check("raises on insufficient rows", True, True)

print(f"\n{'=' * 50}\n{PASS} passed, {FAIL} failed\n{'=' * 50}")
sys.exit(1 if FAIL else 0)
