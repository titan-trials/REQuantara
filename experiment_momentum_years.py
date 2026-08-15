"""
Year by year: is the weak first half a 2020 momentum crash, or a real flaw?

THE ONE FAILURE LEFT. On 144 tickers, momentum passed the parameter plateau
(80% of cells), survived 30bps costs, and beat random selection - but the edge
was lopsided:

    2016-2021   momentum 13.48%   benchmark 13.55%   (a tie)
    2021-2026   momentum 19.11%   benchmark 12.17%   (+7 points)

Half the sample shows no benefit. That is either fatal or well known, and the
two look identical in a half-and-half split.

THE COMPETING EXPLANATIONS
  (a) KNOWN FEATURE. Momentum suffers periodic violent crashes, and 2020 was
      among the worst ever recorded: the March-June rebound was led by the most
      beaten-down names, exactly what a momentum portfolio is short of. If this
      is the story, ONE year should be catastrophic and the years around it fine.
  (b) FATAL FLAW. The effect is simply recent, and 2016-2021 shows nothing. If
      this is the story, weakness is spread across many years and removing any
      single one changes little.

These make different predictions, so the data can separate them.

ALSO FIXED HERE: the earlier random control used 29-name portfolios while the
best momentum cell held 14. Smaller portfolios have higher variance, so that
comparison was not apples-to-apples. Every portfolio size now gets its own
size-matched control.

    python experiment_momentum_years.py
"""

import warnings

warnings.filterwarnings("ignore")

import os
import sys

import numpy as np
import pandas as pd

from experiment_momentum_large import (
    UNIVERSE, LOOKBACKS, build_panel, momentum, select_pct,
)

OUT_CSV = "results/experiment_momentum_years.csv"
COST = 0.0005
RANDOM_TRIALS = 400


def monthly_returns(monthly, picks_by_date, cost_rate=COST):
    """Return series labelled by the month the return was EARNED in.

    `fwd.loc[t]` is the return from t to t+1, so it belongs to month t+1.
    Labelling it t would push January's performance into December and smear
    every year boundary.
    """
    fwd = monthly.pct_change().shift(-1)
    idx = list(picks_by_date.index)
    out, prev = {}, set()
    for i, date in enumerate(idx):
        picks = picks_by_date.loc[date]
        earned_at = idx[i + 1] if i + 1 < len(idx) else None
        if earned_at is None:
            break
        if not picks:
            out[earned_at] = 0.0
            continue
        r = fwd.loc[date, list(picks)].dropna()
        gross = r.mean() if len(r) else 0.0
        turnover = len(set(picks) ^ prev) / max(len(picks), 1)
        out[earned_at] = (1 + gross) * (1 - turnover * cost_rate) - 1
        prev = set(picks)
    return pd.Series(out)


def bench_returns(monthly, dates):
    fwd = monthly.pct_change().shift(-1)
    idx = list(dates)
    out = {}
    for i, d in enumerate(idx[:-1]):
        out[idx[i + 1]] = fwd.loc[d].mean()
    return pd.Series(out).fillna(0.0)


def annual(series):
    return series.groupby(series.index.year).apply(lambda r: (1 + r).prod() - 1) * 100


def cagr(series):
    if len(series) < 2:
        return 0.0
    years = len(series) / 12
    return ((1 + series).prod() ** (1 / years) - 1) * 100


def main():
    print(f"Loading {len(UNIVERSE)} tickers (cached)...")
    monthly, failed = build_panel()
    dates = monthly.index[max(LOOKBACKS):-1]
    print(f"{monthly.shape[1]} tickers, {len(dates)} rebalances\n")

    mom6 = monthly_returns(monthly, select_pct(momentum(monthly, 6).loc[dates], 0.20))
    mom9 = monthly_returns(monthly, select_pct(momentum(monthly, 9).loc[dates], 0.10))
    bench = bench_returns(monthly, dates)

    a6, a9, ab = annual(mom6), annual(mom9), annual(bench)
    years = sorted(set(a6.index) & set(ab.index))

    print("=" * 78)
    print("YEAR BY YEAR — momentum vs owning everything equally")
    print("=" * 78)
    print(f"{'year':6s} {'mom 6/20%':>11s} {'mom 9/10%':>11s} {'benchmark':>11s} "
          f"{'mom6 - bench':>13s}")
    print("-" * 78)
    rows, wins = [], 0
    for y in years:
        d6 = a6[y] - ab[y]
        wins += d6 > 0
        flag = "  <-- momentum crash" if d6 < -10 else ""
        print(f"{y:6d} {a6[y]:>10.1f}% {a9.get(y, float('nan')):>10.1f}% "
              f"{ab[y]:>10.1f}% {d6:>+12.1f}%{flag}")
        rows.append({"Year": y, "Mom6_20pct": a6[y],
                     "Mom9_10pct": a9.get(y), "Benchmark": ab[y], "Diff": d6})
    print("-" * 78)
    print(f"momentum beat the benchmark in {wins}/{len(years)} years")

    df = pd.DataFrame(rows)
    worst = df.loc[df["Diff"].idxmin()]
    best = df.loc[df["Diff"].idxmax()]
    print(f"worst year: {int(worst.Year)} ({worst.Diff:+.1f}%)   "
          f"best year: {int(best.Year)} ({best.Diff:+.1f}%)")

    # --- (a) vs (b): does removing the worst year change the story? ------
    print("\n" + "=" * 78)
    print("IS IT ONE BAD YEAR, OR BROAD WEAKNESS?")
    print("=" * 78)
    wy = int(worst.Year)
    ex6 = mom6[mom6.index.year != wy]
    exb = bench[bench.index.year != wy]

    print(f"{'':28s} {'momentum':>10s} {'benchmark':>11s} {'edge':>8s}")
    print("-" * 62)
    print(f"{'all years':28s} {cagr(mom6):>9.2f}% {cagr(bench):>10.2f}% "
          f"{cagr(mom6) - cagr(bench):>+7.2f}%")
    print(f"{'excluding ' + str(wy):28s} {cagr(ex6):>9.2f}% {cagr(exb):>10.2f}% "
          f"{cagr(ex6) - cagr(exb):>+7.2f}%")

    # first half with and without the worst year
    half = len(mom6) // 2
    f6, fb = mom6.iloc[:half], bench.iloc[:half]
    f6x = f6[f6.index.year != wy]
    fbx = fb[fb.index.year != wy]
    print(f"{'first half':28s} {cagr(f6):>9.2f}% {cagr(fb):>10.2f}% "
          f"{cagr(f6) - cagr(fb):>+7.2f}%")
    print(f"{'first half excl. ' + str(wy):28s} {cagr(f6x):>9.2f}% "
          f"{cagr(fbx):>10.2f}% {cagr(f6x) - cagr(fbx):>+7.2f}%")

    losing_years = int((df["Diff"] < 0).sum())
    one_year_story = (worst["Diff"] < -8
                      and (cagr(f6x) - cagr(fbx)) > 1.0
                      and losing_years <= len(years) / 2)

    # --- size-matched random controls ------------------------------------
    print("\n" + "=" * 78)
    print("SIZE-MATCHED RANDOM CONTROLS (fixing the earlier mismatch)")
    print("=" * 78)
    rng = np.random.default_rng(7)
    print(f"{'portfolio':18s} {'momentum':>10s} {'random 95th':>13s} {'clears?':>9s}")
    print("-" * 55)
    matched = {}
    for pct, lb in ((0.10, 9), (0.20, 6)):
        n_pick = max(1, int(round(monthly.shape[1] * pct)))
        sims = []
        for _ in range(RANDOM_TRIALS):
            picks = pd.Series({d: list(rng.choice(
                monthly.loc[d].dropna().index,
                size=min(n_pick, monthly.loc[d].dropna().size), replace=False))
                for d in dates})
            sims.append(cagr(monthly_returns(monthly, picks)))
        p95 = np.percentile(sims, 95)
        got = cagr(monthly_returns(
            monthly, select_pct(momentum(monthly, lb).loc[dates], pct)))
        matched[pct] = got > p95
        print(f"top {int(pct*100):>2d}% ({n_pick:>3d} names) {got:>9.2f}% "
              f"{p95:>12.2f}% {'YES' if got > p95 else 'no':>9s}")

    os.makedirs("results", exist_ok=True)
    df.to_csv(OUT_CSV, index=False)

    print("\n" + "=" * 78)
    print("VERDICT")
    print("=" * 78)
    if one_year_story:
        print(f"ONE BAD YEAR, NOT BROAD WEAKNESS.")
        print()
        print(f"{wy} cost momentum {worst['Diff']:.1f} points against the benchmark.")
        print(f"Remove that single year and the first half goes from")
        print(f"{cagr(f6) - cagr(fb):+.2f}% to {cagr(f6x) - cagr(fbx):+.2f}% versus the benchmark.")
        print(f"Momentum beat the benchmark in {wins} of {len(years)} years.")
        print()
        if wy == 2020:
            print("2020 is the textbook momentum crash - the March-June rebound was")
            print("led by the most beaten-down names, which a momentum portfolio")
            print("holds least of. This is a DOCUMENTED feature of the strategy,")
            print("not a defect in the test.")
        print()
        print("Read carefully: this does not make momentum safe. It means the")
        print("weakness is concentrated crash risk rather than absence of edge -")
        print("and those crashes are violent, real, and will happen again.")
    else:
        print("BROAD WEAKNESS, NOT ONE BAD YEAR.")
        print()
        print(f"momentum lost in {losing_years} of {len(years)} years, and removing")
        print(f"the worst ({wy}) leaves the first half at "
              f"{cagr(f6x) - cagr(fbx):+.2f}% versus the benchmark.")
        print()
        print("The edge is concentrated in recent years rather than being")
        print("interrupted by a known crash. That is much harder to trust: it")
        print("could be a genuine regime, or it could be that the recent period")
        print("simply suited this signal.")

    print(f"\nsize-matched random control: "
          f"{sum(matched.values())}/{len(matched)} portfolio sizes cleared it")
    print(f"\nFull results: {OUT_CSV}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
