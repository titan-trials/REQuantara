"""
Cross-sectional momentum on a large universe — the deciding test.

WHERE THIS SITS
Two hypotheses have been falsified: per-stock market timing (Versions 16-17)
and pairwise indicator combinations. A third - cross-sectional momentum -
passed its first test and 2 of 3 robustness checks on 33 tickers.

The one failure was the parameter grid: only 50% of cells beat the benchmark,
short of the 60% bar. But the failure was not scattered. It sat entirely in the
SMALL portfolios:

    top 3:  1/5 cells beat        top 8:  4/5 cells beat
    top 5:  1/5 cells beat        top 12: 4/5 cells beat

with a plausible mechanism: picking 3 names from a 33-stock universe is so
concentrated that single-stock noise drowns any ranking signal. Real momentum
research uses deciles of universes with hundreds of names.

THAT EXPLANATION IS POST-HOC, WHICH IS WHY THIS SCRIPT EXISTS. Noticing a
pattern after seeing results and then excluding the inconvenient cells is
precisely how false positives are manufactured. The honest move is to state it
as a prediction and test it on fresh data:

    IF the concentration story is right, the SAME pattern should reproduce
    here - small portfolios failing, larger ones working - on a completely
    different universe.

    IF it does not reproduce, it was pattern-matching on noise, and the
    momentum result should be dropped.

WHAT ELSE THE BIGGER UNIVERSE FIXES
  - PERCENTILE SELECTION. With 148 names, "top 10%" is ~15 stocks and "top 30%"
    is ~44. Portfolio size scales with the universe instead of being an
    arbitrary count, which is how the academic literature does it.
  - SURVIVORSHIP. 33 hand-written names is thin, and momentum is specifically
    flattered by a universe missing its casualties. This list is deliberately
    loaded with decliners: INTC, PARA, GPS, M, KSS, XRX, HPQ, WBD, VTRS, LEG,
    CCL, F, KHC, BXP, SLG, HPE, WDC, FE.
  - A FRESH SAMPLE. The 33 were used to generate the hypothesis. These are new.

Still not a true point-in-time universe - companies that delisted entirely are
absent, and the list was written from memory. Better, not clean.

    python experiment_momentum_large.py

First run downloads ~148 tickers (a few minutes). Cached afterwards.
"""

import warnings

warnings.filterwarnings("ignore")

import os
import sys

import numpy as np
import pandas as pd

from config import START
from data.loader import load_data
from experiment_crosssectional import backtest_selection, stats

OUT_CSV = "results/experiment_momentum_large.csv"

UNIVERSE = [
    # Utilities
    "SO", "DUK", "AEP", "ED", "XEL", "WEC", "ES", "PPL", "FE", "CMS", "DTE", "AEE",
    # Consumer staples
    "KO", "PEP", "PG", "CL", "KMB", "GIS", "CAG", "CPB", "SJM", "HRL",
    "MKC", "CHD", "CLX", "MO", "PM", "TAP", "KHC", "SYY",
    # Energy
    "XOM", "CVX", "COP", "EOG", "SLB", "OXY", "PSX", "VLO", "MPC", "OKE",
    "WMB", "KMI",
    # Materials
    "DOW", "LYB", "APD", "SHW", "NEM", "FCX", "MOS", "CF", "IP", "NUE",
    # Industrials
    "MMM", "GE", "HON", "CAT", "DE", "EMR", "ITW", "DOV", "PH", "ETN",
    "CMI", "FDX", "UPS", "LMT", "UNP", "CSX",
    # Healthcare
    "JNJ", "PFE", "MRK", "ABBV", "BMY", "AMGN", "GILD", "CVS", "CI", "HUM",
    "MDT", "ABT", "TMO", "DHR", "ZBH", "VTRS",
    # Financials
    "JPM", "BAC", "WFC", "C", "GS", "MS", "USB", "PNC", "TFC", "SCHW",
    "AXP", "BK", "ALL", "MET",
    # REITs
    "O", "SPG", "PSA", "VTR", "WELL", "KIM", "REG", "FRT", "BXP", "SLG",
    "HST", "DLR",
    # Consumer discretionary
    "MCD", "SBUX", "NKE", "TGT", "LOW", "HD", "TJX", "ROST", "GPS", "M",
    "KSS", "BBY", "F", "GM", "CCL", "RCL",
    # Technology
    "INTC", "IBM", "CSCO", "ORCL", "TXN", "QCOM", "MU", "HPQ", "HPE",
    "XRX", "WDC", "STX", "NTAP", "JNPR",
    # Communications
    "T", "VZ", "PARA", "WBD", "OMC", "IPG", "EA", "TTWO",
]

LOOKBACKS = [3, 6, 9, 12, 18]
PERCENTILES = [0.10, 0.20, 0.30, 0.40]
COSTS_BPS = [5, 15, 30]
RANDOM_TRIALS = 500
MIN_HISTORY = 400


def build_panel():
    series, failed = {}, []
    for i, t in enumerate(UNIVERSE, 1):
        if i % 25 == 0 or i == len(UNIVERSE):
            print(f"  {i}/{len(UNIVERSE)} loaded ({len(series)} usable)")
        try:
            df = load_data(t, START, None)
            if df is None or len(df) < MIN_HISTORY:
                failed.append(t)
                continue
            series[t] = df["Close"].squeeze()
        except Exception:
            failed.append(t)
    panel = pd.DataFrame(series).sort_index().resample("ME").last()
    return panel, failed


def momentum(monthly, lookback, skip=1):
    return (monthly.shift(skip) / monthly.shift(lookback)) - 1


def select_pct(scores, pct):
    """Top `pct` fraction of whatever is available on each date."""
    out = {}
    for date, row in scores.iterrows():
        valid = row.dropna()
        n = max(1, int(round(len(valid) * pct)))
        out[date] = list(valid.nlargest(n).index) if len(valid) >= 10 else []
    return pd.Series(out)


def benchmark(monthly, dates):
    fwd = monthly.pct_change().shift(-1).loc[dates]
    return stats((1 + fwd.mean(axis=1).fillna(0)).cumprod())


def main():
    print(f"Loading {len(UNIVERSE)} tickers...")
    monthly, failed = build_panel()
    if monthly.shape[1] < 50:
        print("Not enough tickers loaded.")
        return 1

    dates = monthly.index[max(LOOKBACKS):-1]
    bench = benchmark(monthly, dates)
    cost = 0.0005

    print(f"\n{monthly.shape[1]} usable tickers, {len(dates)} rebalances "
          f"({dates[0].date()} to {dates[-1].date()})")
    if failed:
        print(f"Unavailable ({len(failed)}): {', '.join(failed)}")
    print(f"Equal-weight benchmark: {bench['cagr']:.2f}% CAGR, "
          f"Sharpe {bench['sharpe']:.2f}, MaxDD {bench['maxdd']:.1f}%")

    rows = []

    # --- grid ------------------------------------------------------------
    print("\n" + "=" * 78)
    print("LOOKBACK x PORTFOLIO SIZE (as % of universe)")
    print("=" * 78)
    print(f"CAGR, benchmark = {bench['cagr']:.2f}%\n")
    sizes = [f"top {int(p*100)}% (~{int(round(monthly.shape[1]*p))})"
             for p in PERCENTILES]
    print("lookback " + "".join(f"{s:>15s}" for s in sizes))
    print("-" * (9 + 15 * len(PERCENTILES)))
    for lb in LOOKBACKS:
        line = f"{lb:>5d}mo   "
        for p in PERCENTILES:
            sc = momentum(monthly, lb).loc[dates]
            s = stats(backtest_selection(monthly, select_pct(sc, p), cost))
            rows.append({"test": "grid", "lookback": lb, "pct": p, **s})
            line += f"{s['cagr']:>13.2f}%" + ("*" if s["cagr"] > bench["cagr"] else " ")
        print(line)

    grid = pd.DataFrame([r for r in rows if r["test"] == "grid"])
    frac = (grid["cagr"] > bench["cagr"]).mean()
    print(f"\n* = beat benchmark.  {int((grid['cagr'] > bench['cagr']).sum())}"
          f"/{len(grid)} = {frac:.0%} of cells")

    # --- does the concentration pattern reproduce? ------------------------
    print("\n" + "=" * 78)
    print("THE PREDICTION: do SMALL portfolios fail and LARGER ones work?")
    print("=" * 78)
    by_pct = grid.groupby("pct").apply(
        lambda g: (g["cagr"] > bench["cagr"]).sum(), include_groups=False)
    for p in PERCENTILES:
        n_names = int(round(monthly.shape[1] * p))
        print(f"  top {int(p*100):>2d}% (~{n_names:>3d} names):  "
              f"{by_pct[p]}/{len(LOOKBACKS)} cells beat benchmark")
    small = by_pct[PERCENTILES[0]]
    large = by_pct[PERCENTILES[-1]]
    reproduced = large > small
    print(f"\n  Pattern {'REPRODUCED' if reproduced else 'did NOT reproduce'} "
          f"— smallest {small}/{len(LOOKBACKS)}, largest {large}/{len(LOOKBACKS)}")
    if not reproduced:
        print("  -> the concentration explanation was pattern-matching on noise.")

    # --- random control ---------------------------------------------------
    print(f"\nSimulating {RANDOM_TRIALS} random selections...")
    rng = np.random.default_rng(42)
    n_pick = max(1, int(round(monthly.shape[1] * 0.20)))
    rand = []
    for _ in range(RANDOM_TRIALS):
        picks = pd.Series({d: list(rng.choice(
            monthly.loc[d].dropna().index,
            size=min(n_pick, monthly.loc[d].dropna().size), replace=False))
            for d in dates})
        rand.append(stats(backtest_selection(monthly, picks, cost)))
    rand_df = pd.DataFrame(rand)
    p95 = np.percentile(rand_df["cagr"], 95)

    # --- sub-period + costs, at top 20% -----------------------------------
    half = len(dates) // 2
    print("\n" + "=" * 78)
    print("SUB-PERIOD (top 20%)")
    print("=" * 78)
    print(f"{'period':13s} {'span':26s} {'mom 6':>8s} {'mom 12':>8s} {'bench':>8s}")
    print("-" * 78)
    sub_ok = True
    for label, dd in (("first half", dates[:half]), ("second half", dates[half:])):
        b = benchmark(monthly, dd)
        s6 = stats(backtest_selection(monthly, select_pct(momentum(monthly, 6).loc[dd], 0.20), cost))
        s12 = stats(backtest_selection(monthly, select_pct(momentum(monthly, 12).loc[dd], 0.20), cost))
        rows.append({"test": "subperiod", "period": label, "lookback": 6, "pct": 0.20, **s6})
        sub_ok &= s6["cagr"] > b["cagr"]
        print(f"{label:13s} {str(dd[0].date()) + ' to ' + str(dd[-1].date()):26s} "
              f"{s6['cagr']:>7.2f}% {s12['cagr']:>7.2f}% {b['cagr']:>7.2f}%")

    print("\n" + "=" * 78)
    print("TRANSACTION COSTS (mom 6, top 20%)")
    print("=" * 78)
    cost_ok = False
    for c in COSTS_BPS:
        s = stats(backtest_selection(monthly, select_pct(momentum(monthly, 6).loc[dates], 0.20), c / 10_000))
        rows.append({"test": "cost", "lookback": 6, "pct": 0.20, "cost_bps": c, **s})
        if c == 30:
            cost_ok = s["cagr"] > bench["cagr"]
        print(f"  {c:>2d} bps:  {s['cagr']:>6.2f}% CAGR   "
              f"{s['cagr'] - bench['cagr']:>+6.2f}% vs bench")

    pd.DataFrame(rows).to_csv(OUT_CSV, index=False)
    verdict(grid, bench, rand_df, p95, frac, reproduced, sub_ok, cost_ok)
    print(f"\nFull results: {OUT_CSV}")
    return 0


def verdict(grid, bench, rand_df, p95, frac, reproduced, sub_ok, cost_ok):
    best = grid.loc[grid["cagr"].idxmax()]
    print("\n" + "=" * 78)
    print("RANDOM CONTROL")
    print("=" * 78)
    print(f"  {len(rand_df)} random selections: mean {rand_df['cagr'].mean():.2f}%, "
          f"95th percentile {p95:.2f}%")
    print(f"  best momentum cell: {best['cagr']:.2f}% "
          f"(lookback {int(best['lookback'])}mo, top {int(best['pct']*100)}%)")

    checks = [
        (f"plateau across parameters ({frac:.0%} of cells beat benchmark)", frac >= 0.60),
        ("concentration pattern reproduced", reproduced),
        ("works in BOTH sub-periods", sub_ok),
        ("survives 30bps costs", cost_ok),
        (f"best cell clears 95th pct of random ({p95:.2f}%)", best["cagr"] > p95),
    ]
    print("\n" + "=" * 78)
    print("VERDICT")
    print("=" * 78)
    for label, ok in checks:
        print(f"  [{'PASS' if ok else 'FAIL'}]  {label}")
    passed = sum(ok for _, ok in checks)

    print()
    if passed == 5:
        print("ALL FIVE PASSED on a fresh 148-name universe.")
        print()
        print("Cross-sectional momentum is real in this data, survives realistic")
        print("costs, holds in both halves of the sample, and does not depend on")
        print("a lucky parameter. This is a genuine finding.")
        print()
        print("Remaining caveats, which are not small: the universe is still not")
        print("point-in-time (fully delisted companies are absent), it is one")
        print("market over one decade, and momentum is known to suffer periodic")
        print("severe crashes that this sample may not contain.")
    elif passed >= 3:
        print(f"{passed} of 5 passed. Real but qualified - the failing checks are")
        print("exactly where the result is fragile, and are what to investigate.")
    else:
        print(f"Only {passed} of 5 passed. The momentum result does not hold up")
        print("on a larger, fresher universe.")
        print()
        print("Consistent with everything else in this project: the 33-ticker")
        print("result was the sample, not the market.")


if __name__ == "__main__":
    sys.exit(main())
