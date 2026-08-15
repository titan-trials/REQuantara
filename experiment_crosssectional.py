"""
Cross-sectional ranking: a structurally different hypothesis.

WHY THIS IS NOT JUST ANOTHER STRATEGY TEST

Everything that failed in Versions 16 and 17 asked the same question:
"should I be IN stock X today?" That is TIME-SERIES TIMING, and its failure mode
is now understood - being wrong means sitting in cash, which forfeits the equity
risk premium. The market's upward drift is what generates return, so every day
out of it is a guaranteed cost that a random signal cannot pay for.

This asks a different question: "of my 33 stocks, which look best RIGHT NOW?"
The portfolio is ALWAYS FULLY INVESTED. The drift is never given up. The only
bet is on RELATIVE ranking - and if the ranking is worthless, the result should
land on the universe average rather than far below it.

That difference matters. Cross-sectional momentum (Jegadeesh & Titman, 1993) is
among the most replicated anomalies in finance, and it is a ranking effect, not
a timing effect.

THE CONTROLS, WHICH MATTER MORE THAN THE SIGNALS

  RANDOM SELECTION. Pick N stocks at random each rebalance, repeat 1,000 times,
  and build the distribution. This is the honest null. An earlier script used a
  Binomial(n, 0.5) baseline, which was wrong precisely because a timing rule
  does not face a coin flip - it faces the drift. Simulating the actual null
  removes the need to reason about what chance "should" look like.

  TOP MINUS BOTTOM. Buy the highest-ranked, short the lowest. If the signal
  carries information, this spread should be positive even when the long-only
  version does not beat the index. If the spread is ~0, the ranking is noise.

  EQUAL-WEIGHT UNIVERSE as the benchmark - not one stock's buy & hold. The
  question is whether ranking beats owning everything.

NO LOOK-AHEAD: the signal at each rebalance date uses only data up to that date,
and the position is held forward to the next one.

    python experiment_crosssectional.py
"""

import warnings

warnings.filterwarnings("ignore")

import os
import sys

import numpy as np
import pandas as pd

from config import START, TRANSACTION_COST_BPS
from data.loader import load_data

OUT_CSV = "results/experiment_crosssectional.csv"

# The 33 hindsight-free tickers from Version 17. The ORIGINAL five (NVDA, TSLA,
# AAPL, JPM, IBM) are deliberately excluded: they were chosen in 2026 knowing
# how they did, and momentum would simply select them and look brilliant. That
# is the survivorship trap this whole line of work exists to avoid.
UNIVERSE = [
    "SO", "DUK", "AEP", "ED", "XEL", "KHC", "GIS", "CAG", "CPB", "SJM",
    "T", "VZ", "PARA", "BMY", "PFE", "CVS", "VTRS", "MMM", "EMR", "DOV",
    "OKE", "DOW", "LYB", "MOS", "NEM", "O", "VTR", "KIM", "BXP", "HST",
    "F", "LEG", "INTC",
]

TOP_N = 8              # roughly the top quartile of 33
REBALANCE = "ME"       # month end
RANDOM_TRIALS = 1000
TRADING_MONTHS = 12


def build_panel():
    """Monthly close prices, tickers as columns."""
    series = {}
    for i, t in enumerate(UNIVERSE, 1):
        print(f"  [{i:2d}/{len(UNIVERSE)}] {t:6s}", end=" ", flush=True)
        try:
            df = load_data(t, START, None)
            if df is None or len(df) < 400:
                print("skip — insufficient history")
                continue
            series[t] = df["Close"].squeeze()
            print(f"{len(df)} bars")
        except Exception as e:
            print(f"skip — {type(e).__name__}")
    panel = pd.DataFrame(series).sort_index()
    return panel.resample(REBALANCE).last()


# ---------------------------------------------------------------------------
# SIGNALS. Each returns a DataFrame of ranks aligned to the monthly panel.
# Every one uses ONLY data up to and including the rebalance date.
# ---------------------------------------------------------------------------

def momentum_12_1(monthly):
    """Classic cross-sectional momentum: 12-month return, skipping last month.

    The skip matters. The most recent month exhibits short-term REVERSAL, which
    works against momentum, so the standard construction excludes it.
    """
    return (monthly.shift(1) / monthly.shift(12)) - 1


def momentum_6_1(monthly):
    return (monthly.shift(1) / monthly.shift(6)) - 1


def reversal_1m(monthly):
    """Short-term reversal: buy last month's LOSERS."""
    return -((monthly / monthly.shift(1)) - 1)


def low_volatility(monthly):
    """The low-vol anomaly: buy the calmest names."""
    return -monthly.pct_change().rolling(12).std()


SIGNALS = {
    "Momentum 12-1": momentum_12_1,
    "Momentum 6-1": momentum_6_1,
    "Reversal 1M": reversal_1m,
    "Low Volatility": low_volatility,
}


def backtest_selection(monthly, picks_by_date, cost_rate):
    """Chain monthly returns for a sequence of equal-weight selections."""
    fwd = monthly.pct_change().shift(-1)      # return from t to t+1
    equity, prev = [1.0], set()
    for date in picks_by_date.index:
        picks = picks_by_date.loc[date]
        if not picks:
            equity.append(equity[-1])
            continue
        r = fwd.loc[date, list(picks)].dropna()
        gross = r.mean() if len(r) else 0.0
        turnover = len(set(picks) ^ prev) / max(len(picks), 1)
        equity.append(equity[-1] * (1 + gross) * (1 - turnover * cost_rate))
        prev = set(picks)
    return pd.Series(equity[1:], index=picks_by_date.index)


def select_top(scores, n):
    """Per-date list of the n highest-scoring available tickers."""
    out = {}
    for date, row in scores.iterrows():
        valid = row.dropna()
        out[date] = list(valid.nlargest(n).index) if len(valid) >= n else []
    return pd.Series(out)


def stats(equity, months_per_year=TRADING_MONTHS):
    rets = equity.pct_change().dropna()
    if len(rets) < 2:
        return dict(total=0.0, cagr=0.0, sharpe=0.0, maxdd=0.0)
    years = len(rets) / months_per_year
    total = equity.iloc[-1] / equity.iloc[0] - 1
    cagr = (equity.iloc[-1] / equity.iloc[0]) ** (1 / years) - 1 if years > 0 else 0
    sharpe = (rets.mean() / rets.std()) * np.sqrt(months_per_year) if rets.std() else 0
    dd = (equity / equity.cummax() - 1).min()
    return dict(total=total * 100, cagr=cagr * 100, sharpe=sharpe, maxdd=dd * 100)


def main():
    print("Building monthly price panel...")
    monthly = build_panel()
    if monthly.shape[1] < 10:
        print("Not enough tickers.")
        return 1

    cost_rate = TRANSACTION_COST_BPS / 10_000.0
    print(f"\n{monthly.shape[1]} tickers, {len(monthly)} months "
          f"({monthly.index[0].date()} to {monthly.index[-1].date()})")
    print(f"Holding top {TOP_N}, rebalanced monthly, {TRANSACTION_COST_BPS:.0f}bps "
          f"per side on turnover\n")

    # --- benchmark: own everything, equal weight -------------------------
    fwd = monthly.pct_change().shift(-1)
    bench_eq = (1 + fwd.mean(axis=1).fillna(0)).cumprod()
    bench = stats(bench_eq)

    # --- random control: the honest null ----------------------------------
    print(f"Simulating {RANDOM_TRIALS} random selections for the null...")
    rng = np.random.default_rng(42)
    dates = monthly.index[12:-1]
    randoms = []
    for _ in range(RANDOM_TRIALS):
        picks = pd.Series({d: list(rng.choice(
            monthly.loc[d].dropna().index,
            size=min(TOP_N, monthly.loc[d].dropna().size), replace=False))
            for d in dates})
        randoms.append(stats(backtest_selection(monthly, picks, cost_rate)))
    rand_df = pd.DataFrame(randoms)

    # --- signals ----------------------------------------------------------
    rows = []
    for name, fn in SIGNALS.items():
        scores = fn(monthly).loc[dates]
        long_eq = backtest_selection(monthly, select_top(scores, TOP_N), cost_rate)
        short_eq = backtest_selection(monthly, select_top(-scores, TOP_N), cost_rate)
        s, b = stats(long_eq), stats(short_eq)
        pct = (rand_df["cagr"] < s["cagr"]).mean() * 100
        rows.append({"Signal": name, **{f"long_{k}": v for k, v in s.items()},
                     "bottom_cagr": b["cagr"], "spread": s["cagr"] - b["cagr"],
                     "pctile_vs_random": pct})

    df = pd.DataFrame(rows)
    os.makedirs("results", exist_ok=True)
    df.to_csv(OUT_CSV, index=False)
    report(df, bench, rand_df)
    return 0


def report(df, bench, rand_df):
    print("\n" + "=" * 78)
    print("RESULTS — annualised (CAGR)")
    print("=" * 78)
    print(f"{'Signal':18s} {'CAGR':>8s} {'Sharpe':>8s} {'MaxDD':>8s} "
          f"{'vs bench':>9s} {'%ile vs random':>15s}")
    print("-" * 78)
    for _, r in df.sort_values("long_cagr", ascending=False).iterrows():
        print(f"{r['Signal']:18s} {r['long_cagr']:>7.2f}% {r['long_sharpe']:>8.2f} "
              f"{r['long_maxdd']:>7.1f}% {r['long_cagr'] - bench['cagr']:>+8.2f}% "
              f"{r['pctile_vs_random']:>14.0f}%")
    print("-" * 78)
    print(f"{'EQUAL-WEIGHT ALL':18s} {bench['cagr']:>7.2f}% {bench['sharpe']:>8.2f} "
          f"{bench['maxdd']:>7.1f}%   <- own everything, never rank")

    print("\n" + "-" * 78)
    print(f"RANDOM SELECTION — the true null ({len(rand_df)} trials)")
    print("-" * 78)
    print(f"  mean CAGR {rand_df['cagr'].mean():6.2f}%   "
          f"5th {np.percentile(rand_df['cagr'], 5):6.2f}%   "
          f"95th {np.percentile(rand_df['cagr'], 95):6.2f}%")
    print("  A signal must clear the 95th percentile to be distinguishable from")
    print("  picking stocks out of a hat. This replaces the guessed 50% baseline")
    print("  used in earlier experiments, which was wrong.")

    print("\n" + "-" * 78)
    print("TOP MINUS BOTTOM — does the ranking carry ANY information?")
    print("-" * 78)
    print(f"{'Signal':18s} {'top':>8s} {'bottom':>8s} {'spread':>9s}")
    for _, r in df.iterrows():
        verdict = ("informative" if r["spread"] > 2 else
                   "backwards" if r["spread"] < -2 else "no information")
        print(f"{r['Signal']:18s} {r['long_cagr']:>7.2f}% {r['bottom_cagr']:>7.2f}% "
              f"{r['spread']:>+8.2f}%   {verdict}")
    print("  A real ranking signal beats its own inverse. A spread near zero")
    print("  means the ordering is noise, whatever the long-only column says.")

    print("\n" + "=" * 78)
    print("VERDICT")
    print("=" * 78)
    p95 = np.percentile(rand_df["cagr"], 95)
    winners = df[(df["pctile_vs_random"] >= 95) &
                 (df["long_cagr"] > bench["cagr"]) & (df["spread"] > 2)]
    if len(winners):
        print("Signals clearing ALL THREE bars (beat benchmark, beat 95% of random,")
        print("positive top-minus-bottom spread):\n")
        for _, r in winners.iterrows():
            print(f"   {r['Signal']}: {r['long_cagr']:.2f}% CAGR vs "
                  f"{bench['cagr']:.2f}% benchmark, spread {r['spread']:+.2f}%")
        print("\nThis is the first thing in the project to survive a proper test.")
        print("Next: a different universe and a different period before believing it.")
    else:
        near = df[df["long_cagr"] > bench["cagr"]]
        if len(near):
            print("Some signals beat the equal-weight benchmark but did NOT clear")
            print(f"all three bars (95th pct of random = {p95:.2f}% CAGR, and a")
            print("positive top-minus-bottom spread):\n")
            for _, r in near.iterrows():
                print(f"   {r['Signal']}: {r['long_cagr']:.2f}% CAGR, "
                      f"{r['pctile_vs_random']:.0f}th pctile, "
                      f"spread {r['spread']:+.2f}%")
            print("\nBeating the benchmark while sitting inside the random")
            print("distribution means the selection did not do the work.")
        else:
            print("No signal beat simply owning the whole universe equally.")
            print()
            print("Note what this does NOT say. Cross-sectional ranking is always")
            print("fully invested, so unlike Versions 16-17 the failure is not")
            print("about giving up market drift. It is that these particular")
            print("rankings do not order these 33 stocks usefully.")
    print(f"\nFull results: {OUT_CSV}")
    print("=" * 78)


if __name__ == "__main__":
    sys.exit(main())
