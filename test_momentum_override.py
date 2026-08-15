"""
Network-free tests for strategy/momentum_override.py.

The override is a candidate for shipping to live trading. It should not ship
without tests that pin its behaviour to its documented description - the
Version 12 implementation passed a 9-of-9 consistency check while doing
something materially different from what it claimed.

    python test_momentum_override.py
"""

import sys

import pandas as pd

from strategy.momentum_override import apply_override

PASS, FAIL = 0, 0


def check(name, got, want):
    global PASS, FAIL
    if got == want:
        PASS += 1
        print(f"  PASS  {name}")
    else:
        FAIL += 1
        print(f"  FAIL  {name}\n          got  {got}\n          want {want}")


def run(close, rsi, sig, trigger=70, trail=0.05, legacy=False):
    df = pd.DataFrame({"Close": close, "RSI": rsi, "Signal": sig})
    held = apply_override(df, trigger, trail, legacy=legacy)
    return list(df["Signal"]), held


# ---------------------------------------------------------------------------
print("\n[1] Core behaviour: holds through a momentum run, exits below the peak")
# Runs 100 -> 150, then falls. Peak 150, 5% trail -> exit when below 142.5.
# Model wants out at index 2; override should hold to index 6 (148 >= 142.5)
# and release at index 7 (140 < 142.5).
out, held = run(
    close=[100, 110, 120, 130, 140, 150, 148, 140, 130, 120],
    rsi=[50, 60, 72, 75, 78, 80, 76, 70, 60, 50],
    sig=[1, 1, 0, 0, 0, 0, 0, 0, 0, 0],
)
check("holds the run then releases", out, [1, 1, 1, 1, 1, 1, 1, 0, 0, 0])
check("days held", held, 5)

# ---------------------------------------------------------------------------
print("\n[2] Does not engage when RSI is below the trigger")
out, held = run(
    close=[100, 110, 120, 130, 140, 150, 148, 140, 130, 120],
    rsi=[50] * 10,
    sig=[1, 1, 0, 0, 0, 0, 0, 0, 0, 0],
)
check("signal untouched", out, [1, 1, 0, 0, 0, 0, 0, 0, 0, 0])
check("days held", held, 0)

# ---------------------------------------------------------------------------
print("\n[3] REGRESSION (Bug 1): does not engage on an unprofitable position")
# Position opens at 100 and falls to 10 with RSI pinned at 80. The documented
# rule requires the position to be PROFITABLE. Version 12 held 8 of 9 bars here
# because `entry` was never initialised and close > 0.0 is always true.
out, held = run(
    close=[100, 90, 80, 70, 60, 50, 40, 30, 20, 10],
    rsi=[80] * 10,
    sig=[1, 1, 0, 0, 0, 0, 0, 0, 0, 0],
)
check("never engages on a losing position", out, [1, 1, 0, 0, 0, 0, 0, 0, 0, 0])
check("days held", held, 0)

print("       (legacy mode reproduces the Version 12 bug, for comparison)")
out_legacy, held_legacy = run(
    close=[100, 90, 80, 70, 60, 50, 40, 30, 20, 10],
    rsi=[80] * 10,
    sig=[1, 1, 0, 0, 0, 0, 0, 0, 0, 0],
    legacy=True,
)
check("legacy still holds 8 bars (bug preserved)", held_legacy, 8)

# ---------------------------------------------------------------------------
print("\n[4] REGRESSION (Bug 2): the trailing stop does not ratchet downward")
# Profitable entry, runs to 150, then falls steadily. The stop must fire ONCE
# and stay out - not release and immediately re-engage at each lower price.
out, held = run(
    close=[100, 150, 140, 130, 120, 110, 100, 90, 80, 70],
    rsi=[80] * 10,
    sig=[1, 0, 0, 0, 0, 0, 0, 0, 0, 0],
)
check("exits once and stays out", out, [1, 1, 0, 0, 0, 0, 0, 0, 0, 0])
check("days held", held, 1)

out_legacy, held_legacy = run(
    close=[100, 150, 140, 130, 120, 110, 100, 90, 80, 70],
    rsi=[80] * 10,
    sig=[1, 0, 0, 0, 0, 0, 0, 0, 0, 0],
    legacy=True,
)
check("legacy ratchets down instead of exiting", held_legacy > 1, True)

# ---------------------------------------------------------------------------
print("\n[5] A wider trail holds longer than a narrower one")
args = dict(
    close=[100, 110, 120, 130, 140, 150, 145, 138, 130, 120],
    rsi=[80] * 10,
    sig=[1, 1, 0, 0, 0, 0, 0, 0, 0, 0],
)
_, held_3 = run(**args, trail=0.03)
_, held_8 = run(**args, trail=0.08)
check("trail 8% holds at least as long as trail 3%", held_8 >= held_3, True)

# ---------------------------------------------------------------------------
print("\n[6] Never invents a position out of nothing")
# Model flat throughout: the override suspends SELLS, it must not create BUYS.
out, held = run(
    close=[100, 110, 120, 130, 140, 150, 148, 140, 130, 120],
    rsi=[80] * 10,
    sig=[0] * 10,
)
check("stays flat", out, [0] * 10)
check("days held", held, 0)

print(f"\n{'=' * 50}\n{PASS} passed, {FAIL} failed\n{'=' * 50}")
sys.exit(1 if FAIL else 0)
