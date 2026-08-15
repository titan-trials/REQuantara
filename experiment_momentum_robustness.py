"""
Is the momentum result real, or did lookback=6 get lucky?

WHY THIS EXISTS. experiment_crosssectional.py found Momentum 6-1 clearing every
bar: 11.16% CAGR vs a 4.90% equal-weight benchmark, better than all 1,000
random selections, and a +12.28% top-minus-bottom spread. That is the first
thing in this project to survive a proper test.

But the ACADEMICALLY STANDARD construction is 12-1, and it only reached the
64th percentile. The version that worked is the non-standard one. A result that
lives at a single parameter value is usually a parameter that got lucky - this
project has seen that exact pattern before, in Version 12's momentum override,
where the effect existed only at the edge of the tested grid.

THE PRINCIPLE. A real effect has a PLATEAU: neighbouring parameter values work
too, because the underlying phenomenon does not care about the exact number. An
overfit result has a SPIKE: one cell works and its neighbours do not.

FOUR WAYS TO KILL IT

  1. LOOKBACK SWEEP - 3, 6, 9, 12, 18 months. Plateau or spike?
  2. PORTFOLIO SIZE SWEEP - top 3, 5, 8, 12. If only top-8 works, it is noise.
  3. SUB-PERIOD SPLIT - first half vs second half of the sample. An effect
     concentrated in one regime is a regime observation, not a strategy.
  4. COST SENSITIVITY - 5, 15, 30 bps. Monthly rebalancing on mid-caps at 5bps
     is optimistic; the edge must survive realistic friction.

Passing all four does not make it true. It makes it worth testing on a
different universe, which is the next step regardless of what this says.

    python experiment_momentum_robustness.py
"""

import warnings

warnings.filterwarnings("ignore")

import os
import sys

import numpy as np
import pandas as pd

from experiment_crosssectional import (
    UNIVERSE, REBALANCE, build_panel, backtest_selection, select_top, stats,
)

OUT_CSV = "results/experiment_momentum_robustness.csv"

LOOKBACKS = [3, 6, 9, 12, 18]
TOP_NS = [3, 5, 8, 12]
COSTS_BPS = [5, 15, 30]


def momentum(monthly, lookback, skip=1):
    """Return over `lookback` months, skipping the most recent `skip`.

    The skip is standard: the most recent month shows short-term reversal,
    which works against momentum.
    """
    return (monthly.shift(skip) / monthly.shift(lookback)) - 1


def run(monthly, lookback, top_n, cost_bps, dates=None):
    if dates is None:
        dates = monthly.index[max(LOOKBACKS):-1]
    scores = momentum(monthly, lookback).loc[dates]
    eq = backtest_selection(monthly, select_top(scores, top_n),
                            cost_bps / 10_000.0)
    return stats(eq)


def benchmark(monthly, dates):
    fwd = monthly.pct_change().shift(-1).loc[dates]
    return stats((1 + fwd.mean(axis=1).fillna(0)).cumprod())


def main():
    print("Building monthly price panel...")
    monthly = build_panel()
    if monthly.shape[1] < 10:
        print("Not enough tickers.")
        return 1

    dates = monthly.index[max(LOOKBACKS):-1]
    bench = benchmark(monthly, dates)
    print(f"\n{monthly.shape[1]} tickers, {len(dates)} rebalances "
          f"({dates[0].date()} to {dates[-1].date()})")
    print(f"Equal-weight benchmark: {bench['cagr']:.2f}% CAGR, "
          f"Sharpe {bench['sharpe']:.2f}, MaxDD {bench['maxdd']:.1f}%\n")

    rows = []

    # --- 1 + 2. lookback x portfolio size --------------------------------
    print("=" * 78)
    print("1+2. LOOKBACK x PORTFOLIO SIZE — plateau or spike?")
    print("=" * 78)
    print("CAGR, benchmark = {:.2f}%\n".format(bench["cagr"]))
    header = "lookback " + "".join(f"{'top ' + str(n):>10s}" for n in TOP_NS)
    print(header)
    print("-" * len(header))
    for lb in LOOKBACKS:
        line = f"{lb:>5d}mo   "
        for n in TOP_NS:
            s = run(monthly, lb, n, 5, dates)
            rows.append({"test": "grid", "lookback": lb, "top_n": n,
                         "cost_bps": 5, **s})
            beat = s["cagr"] - bench["cagr"]
            line += f"{s['cagr']:>8.2f}%" + ("*" if beat > 0 else " ")
        print(line)
    print("\n* = beat the equal-weight benchmark")
    print("A real effect fills most of this grid. One starred cell is a spike.")

    grid = pd.DataFrame([r for r in rows if r["test"] == "grid"])
    beat_frac = (grid["cagr"] > bench["cagr"]).mean()
    print(f"\nCells beating benchmark: {int((grid['cagr'] > bench['cagr']).sum())}"
          f"/{len(grid)} = {beat_frac:.0%}")

    # --- 3. sub-period ----------------------------------------------------
    print("\n" + "=" * 78)
    print("3. SUB-PERIOD — is the effect concentrated in one regime?")
    print("=" * 78)
    half = len(dates) // 2
    periods = [("first half", dates[:half]), ("second half", dates[half:])]
    print(f"{'period':14s} {'span':26s} {'mom 6-1':>9s} {'mom 12-1':>9s} "
          f"{'bench':>9s}")
    print("-" * 78)
    for label, dd in periods:
        b = benchmark(monthly, dd)
        s6 = run(monthly, 6, 8, 5, dd)
        s12 = run(monthly, 12, 8, 5, dd)
        rows.append({"test": "subperiod", "period": label, "lookback": 6,
                     "top_n": 8, "cost_bps": 5, **s6})
        span = f"{dd[0].date()} to {dd[-1].date()}"
        print(f"{label:14s} {span:26s} {s6['cagr']:>8.2f}% {s12['cagr']:>8.2f}% "
              f"{b['cagr']:>8.2f}%")
    print("\nWorking in only ONE half means it is a regime observation.")

    # --- 4. costs ---------------------------------------------------------
    print("\n" + "=" * 78)
    print("4. TRANSACTION COSTS — does the edge survive friction?")
    print("=" * 78)
    print(f"{'bps/side':>10s} {'mom 6-1 CAGR':>14s} {'vs bench':>10s}")
    print("-" * 40)
    for c in COSTS_BPS:
        s = run(monthly, 6, 8, c, dates)
        rows.append({"test": "cost", "lookback": 6, "top_n": 8,
                     "cost_bps": c, **s})
        print(f"{c:>8d}   {s['cagr']:>13.2f}% {s['cagr'] - bench['cagr']:>+9.2f}%")

    df = pd.DataFrame(rows)
    os.makedirs("results", exist_ok=True)
    df.to_csv(OUT_CSV, index=False)

    verdict(grid, bench, monthly, dates)
    print(f"\nFull results: {OUT_CSV}")
    return 0


def verdict(grid, bench, monthly, dates):
    print("\n" + "=" * 78)
    print("VERDICT")
    print("=" * 78)

    beat = grid["cagr"] > bench["cagr"]
    frac = beat.mean()

    half = len(dates) // 2
    s6_first = run(monthly, 6, 8, 5, dates[:half])
    s6_second = run(monthly, 6, 8, 5, dates[half:])
    b_first = benchmark(monthly, dates[:half])
    b_second = benchmark(monthly, dates[half:])
    both_halves = (s6_first["cagr"] > b_first["cagr"]
                   and s6_second["cagr"] > b_second["cagr"])

    s30 = run(monthly, 6, 8, 30, dates)
    survives_costs = s30["cagr"] > bench["cagr"]

    checks = [
        (f"plateau across parameters ({frac:.0%} of grid beat benchmark)",
         frac >= 0.60),
        ("works in BOTH sub-periods", both_halves),
        ("survives 30bps costs", survives_costs),
    ]
    for label, ok in checks:
        print(f"  [{'PASS' if ok else 'FAIL'}]  {label}")

    passed = sum(ok for _, ok in checks)
    print()
    if passed == 3:
        print("All three robustness checks passed. This is now the strongest")
        print("result in the project by a wide margin.")
        print()
        print("It is still ONE universe over ONE period, and the tickers were")
        print("written from memory, so survivorship is not fully controlled.")
        print("The next test is a DIFFERENT universe - ideally a few hundred")
        print("names, including delisted ones. Nothing should be traded on this")
        print("until that runs.")
    elif passed == 2:
        print("Two of three passed. Promising but not settled - the failing")
        print("check is where to look, because that is where the result is")
        print("resting on something fragile.")
    else:
        print("The momentum result does NOT survive robustness testing.")
        print()
        print("Consistent with everything else in this project: an effect that")
        print("exists at one parameter value and vanishes at its neighbours was")
        print("the parameter fitting the sample, not a property of the market.")
        print("Same shape as Version 12's momentum override.")


if __name__ == "__main__":
    sys.exit(main())
