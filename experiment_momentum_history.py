"""
Momentum over 26 years — the test that includes the crashes.

WHY THIS IS THE IMPORTANT ONE. Every momentum result so far comes from
2016-2026, and that sample contains NO momentum crash. The worst year was 2019
at -8.4%, which is a lagging bull market, not a crash. A real momentum crash is
-30% to -50% relative.

Testing a strategy only over a period that excludes its known failure mode is
not testing it. This run goes back to 2000 and includes:

    2000-2002   dot-com collapse
    2008        financial crisis
    2009        THE WORST MOMENTUM CRASH ON RECORD - the March 2009 bottom was
                followed by a violent rally in the most beaten-down names,
                exactly what a momentum portfolio holds least of. Academic
                studies put the loss at -50% or worse in a few months.
    2020        COVID crash and rebound

If momentum survives 2009 as a drawdown rather than a wipeout, the edge is
credible. If 2009 destroys it, that is the single most important thing to know
before ever considering it seriously.

ON SURVIVORSHIP, WHICH CUTS THE OTHER WAY HERE. The universe is companies that
still exist in 2026, so firms that went bankrupt between 2000 and 2026 are
missing. That normally flatters a backtest - but note the direction for THIS
test. Momentum ranks collapsing companies LAST and avoids them; the equal-weight
benchmark holds them all the way down. Removing them helps the BENCHMARK more
than it helps momentum. So survivorship bias works AGAINST the result being
measured, which makes a positive finding harder to dismiss.

Tickers also list at different times (ABBV 2013, PM 2008, DOW 2019, KHC 2015).
The universe therefore grows over time, which is handled naturally: ranking
happens across whatever is available on each date, and the benchmark uses the
same set.

    python experiment_momentum_history.py

First run downloads 26 years for ~148 tickers. Several minutes. Cached after.
"""

import warnings

warnings.filterwarnings("ignore")

import os
import sys

import numpy as np
import pandas as pd

from data.loader import load_data
from experiment_momentum_large import UNIVERSE, momentum, select_pct
from experiment_momentum_years import monthly_returns, bench_returns, annual, cagr

HISTORY_START = "2000-01-01"      # NOT config.START - that governs live trading
OUT_CSV = "results/experiment_momentum_history.csv"
LOOKBACKS = [3, 6, 9, 12, 18]
PERCENTILES = [0.10, 0.20, 0.30, 0.40]
RANDOM_TRIALS = 300
COST = 0.0005

# Periods where momentum is documented to have crashed. Listed in advance so
# the analysis is not "find the bad year, then explain it".
KNOWN_CRASH_YEARS = {2009: "worst momentum crash on record (March 2009 bottom)",
                     2002: "dot-com capitulation",
                     2020: "COVID rebound led by beaten-down names"}


def build_long_panel():
    series, failed = {}, []
    for i, t in enumerate(UNIVERSE, 1):
        if i % 25 == 0 or i == len(UNIVERSE):
            print(f"  {i}/{len(UNIVERSE)} ({len(series)} usable)")
        try:
            df = load_data(t, HISTORY_START, None)
            if df is None or len(df) < 250:
                failed.append(t)
                continue
            series[t] = df["Close"].squeeze()
        except Exception:
            failed.append(t)
    return pd.DataFrame(series).sort_index().resample("ME").last(), failed


def max_drawdown(returns):
    eq = (1 + returns).cumprod()
    return (eq / eq.cummax() - 1).min() * 100


def main():
    print(f"Loading {len(UNIVERSE)} tickers from {HISTORY_START}...")
    monthly, failed = build_long_panel()
    dates = monthly.index[max(LOOKBACKS):-1]

    counts = monthly.loc[dates].notna().sum(axis=1)
    print(f"\n{monthly.shape[1]} tickers, {len(dates)} rebalances "
          f"({dates[0].date()} to {dates[-1].date()})")
    print(f"universe size: {counts.iloc[0]:.0f} in {dates[0].year} -> "
          f"{counts.iloc[-1]:.0f} in {dates[-1].year}")
    if failed:
        print(f"unavailable ({len(failed)}): {', '.join(failed)}")

    mom = monthly_returns(monthly, select_pct(momentum(monthly, 6).loc[dates], 0.20), COST)
    bench = bench_returns(monthly, dates)
    common = mom.index.intersection(bench.index)
    mom, bench = mom.loc[common], bench.loc[common]

    print(f"\n{'':22s} {'CAGR':>8s} {'MaxDD':>9s} {'best yr':>9s} {'worst yr':>9s}")
    print("-" * 62)
    am, ab = annual(mom), annual(bench)
    print(f"{'momentum (6mo, top20%)':22s} {cagr(mom):>7.2f}% {max_drawdown(mom):>8.1f}% "
          f"{am.max():>8.1f}% {am.min():>8.1f}%")
    print(f"{'equal-weight all':22s} {cagr(bench):>7.2f}% {max_drawdown(bench):>8.1f}% "
          f"{ab.max():>8.1f}% {ab.min():>8.1f}%")
    print(f"{'EDGE':22s} {cagr(mom) - cagr(bench):>+7.2f}%")

    # --- year by year -----------------------------------------------------
    print("\n" + "=" * 78)
    print("YEAR BY YEAR")
    print("=" * 78)
    years = sorted(set(am.index) & set(ab.index))
    rows, wins = [], 0
    for y in years:
        d = am[y] - ab[y]
        wins += d > 0
        note = ""
        if y in KNOWN_CRASH_YEARS:
            note = f"  <-- {KNOWN_CRASH_YEARS[y]}"
        print(f"{y:6d} {am[y]:>9.1f}% {ab[y]:>9.1f}% {d:>+9.1f}%{note}")
        rows.append({"Year": y, "Momentum": am[y], "Benchmark": ab[y], "Diff": d})
    print("-" * 78)
    print(f"momentum beat the benchmark in {wins}/{len(years)} years")

    df = pd.DataFrame(rows)

    # --- did the known crashes actually hurt? -----------------------------
    print("\n" + "=" * 78)
    print("THE CRASH YEARS — flagged in advance, not chosen after the fact")
    print("=" * 78)
    crash_hit = {}
    for y, why in sorted(KNOWN_CRASH_YEARS.items()):
        if y in am.index:
            d = am[y] - ab[y]
            crash_hit[y] = d
            print(f"  {y}: momentum {am[y]:>7.1f}%  benchmark {ab[y]:>7.1f}%  "
                  f"{d:>+7.1f}%   {why}")
    worst_crash = min(crash_hit.values()) if crash_hit else 0.0

    # --- decade stability -------------------------------------------------
    print("\n" + "=" * 78)
    print("BY PERIOD — is the edge spread out or concentrated?")
    print("=" * 78)
    periods = [("2000-2009", 2000, 2009), ("2010-2019", 2010, 2019),
               ("2020-2026", 2020, 2026)]
    print(f"{'period':12s} {'momentum':>10s} {'benchmark':>11s} {'edge':>8s} {'years won':>11s}")
    print("-" * 60)
    period_edges = []
    for label, a, b in periods:
        m = mom[(mom.index.year >= a) & (mom.index.year <= b)]
        n = bench[(bench.index.year >= a) & (bench.index.year <= b)]
        if len(m) < 12:
            print(f"{label:12s} {'insufficient data':>32s}")
            continue
        e = cagr(m) - cagr(n)
        period_edges.append(e)
        sub = df[(df.Year >= a) & (df.Year <= b)]
        print(f"{label:12s} {cagr(m):>9.2f}% {cagr(n):>10.2f}% {e:>+7.2f}% "
              f"{int((sub.Diff > 0).sum()):>6d}/{len(sub):<4d}")

    # --- parameter grid ---------------------------------------------------
    print("\n" + "=" * 78)
    print("PARAMETER GRID over 26 years (CAGR)")
    print("=" * 78)
    print("lookback " + "".join(f"{'top ' + str(int(p*100)) + '%':>12s}" for p in PERCENTILES))
    print("-" * (9 + 12 * len(PERCENTILES)))
    grid = []
    for lb in LOOKBACKS:
        line = f"{lb:>5d}mo   "
        for p in PERCENTILES:
            r = monthly_returns(monthly, select_pct(momentum(monthly, lb).loc[dates], p), COST)
            c = cagr(r.loc[r.index.intersection(bench.index)])
            grid.append({"lookback": lb, "pct": p, "cagr": c})
            line += f"{c:>10.2f}%" + ("*" if c > cagr(bench) else " ")
        print(line)
    gdf = pd.DataFrame(grid)
    frac = (gdf["cagr"] > cagr(bench)).mean()
    print(f"\n* = beat benchmark ({cagr(bench):.2f}%).  "
          f"{int((gdf['cagr'] > cagr(bench)).sum())}/{len(gdf)} = {frac:.0%}")

    # --- size-matched random ---------------------------------------------
    print(f"\nSimulating {RANDOM_TRIALS} size-matched random selections...")
    rng = np.random.default_rng(11)
    n_pick = max(1, int(round(counts.mean() * 0.20)))
    sims = []
    for _ in range(RANDOM_TRIALS):
        picks = pd.Series({d: list(rng.choice(
            monthly.loc[d].dropna().index,
            size=min(n_pick, monthly.loc[d].dropna().size), replace=False))
            for d in dates})
        r = monthly_returns(monthly, picks, COST)
        sims.append(cagr(r.loc[r.index.intersection(bench.index)]))
    p95 = np.percentile(sims, 95)
    print(f"  random ~{n_pick} names: mean {np.mean(sims):.2f}%, 95th {p95:.2f}%")
    print(f"  momentum: {cagr(mom):.2f}%  ->  "
          f"{'clears' if cagr(mom) > p95 else 'DOES NOT clear'}")

    os.makedirs("results", exist_ok=True)
    df.to_csv(OUT_CSV, index=False)
    verdict(df, mom, bench, frac, p95, worst_crash, period_edges, wins, len(years))
    print(f"\nFull results: {OUT_CSV}")
    return 0


def verdict(df, mom, bench, frac, p95, worst_crash, period_edges, wins, n_years):
    print("\n" + "=" * 78)
    print("VERDICT")
    print("=" * 78)
    checks = [
        (f"positive edge over 26 years ({cagr(mom) - cagr(bench):+.2f}%)",
         cagr(mom) > cagr(bench)),
        (f"beats 95th pct of size-matched random ({p95:.2f}%)", cagr(mom) > p95),
        (f"parameter plateau ({frac:.0%} of grid)", frac >= 0.60),
        (f"wins a majority of years ({wins}/{n_years})", wins > n_years / 2),
        ("positive in EVERY period tested",
         len(period_edges) >= 2 and all(e > 0 for e in period_edges)),
        (f"survived the crash years (worst {worst_crash:+.1f}%)", worst_crash > -25),
    ]
    for label, ok in checks:
        print(f"  [{'PASS' if ok else 'FAIL'}]  {label}")
    passed = sum(ok for _, ok in checks)

    print()
    if passed >= 5:
        print(f"{passed} of 6 over 26 years INCLUDING the crash periods.")
        print()
        print("This is a real, documented effect showing up in your own data.")
        print("You have not discovered something new - cross-sectional momentum")
        print("is one of the most replicated findings in finance - you have")
        print("independently recovered it, which is the harder and more")
        print("convincing thing for a project like this to do.")
        print()
        print("What it is NOT: a licence to trade. Momentum crashes are violent")
        print("and the next one will not announce itself. The sensible next step")
        print("is a market-level trend overlay tested specifically on the crash")
        print("years, which is what those periods are now available for.")
    elif passed >= 3:
        print(f"{passed} of 6. The edge exists but is uneven across regimes.")
        print("Look at which periods failed - that is where the strategy breaks,")
        print("and it is more informative than the aggregate number.")
    else:
        print(f"Only {passed} of 6 over the full history.")
        print()
        print("The 2016-2026 result did not survive a longer sample containing")
        print("the crash periods. That means it was the decade, not the effect -")
        print("and it is exactly why testing a strategy over a window that")
        print("excludes its known failure mode proves nothing.")


if __name__ == "__main__":
    sys.exit(main())
