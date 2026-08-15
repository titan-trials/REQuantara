"""
Do PAIRS of indicators work where single indicators failed?

THE HYPOTHESIS. Version 17 showed six single strategies all losing to buy &
hold across 33 tickers. A reasonable response is "maybe the indicators are fine
but need to be combined" - EMA crossover confirmed by ADX, SMA crossover
filtered by RSI, and so on. This tests every pairing.

THE TRAP THIS SCRIPT IS BUILT TO AVOID. Testing ~60 combinations and reporting
the best one is the purest form of the multiple-comparisons error. With 60
worthless combinations, the best will look excellent purely by luck. Version 17
already measured this effect once: best-of-7 beat a single benchmark 87.5% of
the time under no skill at all.

Three defences:

  1. NO PER-TICKER PICKING. Each combination is applied uniformly to every
     ticker. A real edge shows up broadly, not on cherry-picked names.
  2. DISCOVERY / CONFIRMATION SPLIT ON TICKERS. Combinations are ranked on the
     discovery half. The confirmation half is never looked at until the
     candidates are already chosen. A combo that only works on discovery was
     luck; that is the entire point of holding tickers back.
  3. SIMULATED NULL. The script simulates what the BEST of N worthless
     combinations would score, so "our winner got 14/17" can be compared
     against "pure chance gets 14/17 too" rather than being assumed impressive.

RECORDED PREDICTION (written before the first run, so it cannot be quietly
revised afterwards): this will fail. These are still price-derived indicators
performing per-stock market timing, which is the hypothesis Version 17
falsified. What would change that view is a combination winning 20+ of 33 in
CONFIRMATION, not discovery.

    python experiment_combos.py
"""

import warnings

warnings.filterwarnings("ignore")

import itertools
import os
import sys

import numpy as np
import pandas as pd

from backtest.engine import run_backtest
from config import INITIAL_CAPITAL, STOP_LOSS, BACKTEST_POSITION_SIZE, START
from data.loader import load_data
from evaluation.metrics import get_metrics
from strategy.ml_signal import build_features

OUT_CSV = "results/experiment_combos.csv"
MIN_ROWS = 500

# Tickers from Version 17. Split alternately into discovery / confirmation so
# the two halves have a similar sector mix rather than, say, all the utilities
# landing on one side.
TICKERS = [
    "SO", "DUK", "AEP", "ED", "XEL", "KHC", "GIS", "CAG", "CPB", "SJM",
    "T", "VZ", "PARA", "BMY", "PFE", "CVS", "VTRS", "MMM", "EMR", "DOV",
    "OKE", "DOW", "LYB", "MOS", "NEM", "O", "VTR", "KIM", "BXP", "HST",
    "F", "LEG", "INTC",
]
DISCOVERY = TICKERS[0::2]
CONFIRMATION = TICKERS[1::2]


# ---------------------------------------------------------------------------
# CONDITIONS
#
# Each returns a boolean Series. A combination is two of these ANDed together -
# "be long only when BOTH are true". Deliberately includes contradictory and
# nonsensical pairings; the point is to cover the space, not to only test ideas
# that sound clever.
# ---------------------------------------------------------------------------
CONDITIONS = {
    "sma_cross":       lambda d: d["SMA_20"] > d["SMA_50"],
    "ema_cross":       lambda d: d["EMA_20"] > d["EMA_50"],
    "above_sma20":     lambda d: d["Price_vs_SMA20"] > 0,
    "above_sma50":     lambda d: d["Price_vs_SMA50"] > 0,
    "mom20_positive":  lambda d: d["Momentum_20"] > 0,
    "mom5_positive":   lambda d: d["Momentum_5"] > 0,
    "rsi_bullish":     lambda d: d["RSI"] > 50,
    "rsi_not_hot":     lambda d: d["RSI"] < 70,
    "rsi_oversold":    lambda d: d["RSI"] < 30,
    "bb_lower_half":   lambda d: d["BB_position"] < 0.5,
    "bb_upper_half":   lambda d: d["BB_position"] > 0.5,
    "adx_trending":    lambda d: d["ADX_14"] > 25,
    "adx_quiet":       lambda d: d["ADX_14"] < 20,
    "low_vol":         lambda d: d["Volatility_20"] < d["Volatility_20"].rolling(100).median(),
    "rsi_rising":      lambda d: d["RSI_slope"] > 0,
    "mom_accelerating": lambda d: d["Mom_accel"] > 0,
}


def build_ticker_frame(ticker):
    full = load_data(ticker, START, None)
    if full is None or len(full) < MIN_ROWS:
        raise ValueError(f"only {0 if full is None else len(full)} bars")
    d = build_features(full).dropna()
    if len(d) < MIN_ROWS // 2:
        raise ValueError(f"only {len(d)} bars after indicator warm-up")
    # Second half, matching the Version 17 test period so numbers are comparable.
    return d.iloc[len(d) // 2:].copy()


def score(frame, signal, stop_loss=STOP_LOSS):
    d = frame.copy()
    d["Signal"] = signal.astype(int).values
    d = run_backtest(d, INITIAL_CAPITAL, stop_loss, BACKTEST_POSITION_SIZE)
    return get_metrics(d, INITIAL_CAPITAL)


def simulate_null(n_combos, n_tickers, trials=20000, seed=0):
    """What does the BEST of `n_combos` worthless combos score by luck?"""
    rng = np.random.default_rng(seed)
    draws = rng.binomial(n_tickers, 0.5, size=(trials, n_combos))
    best = draws.max(axis=1)
    return best.mean(), np.percentile(best, 95)


def main():
    combos = list(itertools.combinations(CONDITIONS, 2))
    print(f"{len(CONDITIONS)} conditions -> {len(combos)} pairwise combinations")
    print(f"{len(DISCOVERY)} discovery tickers, {len(CONFIRMATION)} confirmation "
          f"(held back until candidates are chosen)\n")

    frames, bh = {}, {}
    for i, ticker in enumerate(TICKERS, 1):
        print(f"  [{i:2d}/{len(TICKERS)}] {ticker:6s}", end=" ", flush=True)
        try:
            f = build_ticker_frame(ticker)
            frames[ticker] = f
            bh[ticker] = score(f, pd.Series(1, index=f.index), stop_loss=0.0)
            print(f"{len(f):5d} bars | B&H Sharpe {bh[ticker]['Sharpe_Ratio']:>6.3f}")
        except Exception as e:
            print(f"SKIP — {type(e).__name__}: {e}")

    if not frames:
        print("No usable tickers.")
        return 1

    print(f"\nEvaluating {len(combos)} combinations on {len(frames)} tickers "
          f"({len(combos) * len(frames):,} backtests)...")

    rows = []
    for n, (a, b) in enumerate(combos, 1):
        if n % 20 == 0:
            print(f"  {n}/{len(combos)}")
        for ticker, f in frames.items():
            sig = CONDITIONS[a](f) & CONDITIONS[b](f)
            days_long = int(sig.sum())
            if days_long < 10:          # never trades; nothing to measure
                continue
            m = score(f, sig)
            rows.append({
                "Combo": f"{a} + {b}", "A": a, "B": b, "Ticker": ticker,
                "Set": "discovery" if ticker in DISCOVERY else "confirmation",
                "Sharpe": m["Sharpe_Ratio"], "Return": m["Total_Return"],
                "MaxDD": m["Max_Drawdown"],
                "BH_Sharpe": bh[ticker]["Sharpe_Ratio"],
                "BH_Return": bh[ticker]["Total_Return"],
                "Beat_BH": m["Sharpe_Ratio"] > bh[ticker]["Sharpe_Ratio"],
                "Pct_Days_Long": round(days_long / len(f) * 100, 1),
            })

    df = pd.DataFrame(rows)
    os.makedirs("results", exist_ok=True)
    df.to_csv(OUT_CSV, index=False)
    report(df, len(combos))
    return 0


def report(df, n_combos):
    disc = df[df.Set == "discovery"]
    conf = df[df.Set == "confirmation"]
    n_disc = disc.Ticker.nunique()
    n_conf = conf.Ticker.nunique()

    agg = (disc.groupby("Combo")
           .agg(wins=("Beat_BH", "sum"), n=("Beat_BH", "size"),
                mean_sharpe=("Sharpe", "mean"), mean_ret=("Return", "mean"),
                mean_dd=("MaxDD", "mean"), pct_long=("Pct_Days_Long", "mean"))
           .sort_values("wins", ascending=False))

    exp_best, p95 = simulate_null(n_combos, n_disc)

    print("\n" + "=" * 78)
    print(f"DISCOVERY — {n_disc} tickers, {n_combos} combinations")
    print("=" * 78)
    print(f"{'Combination':42s} {'wins':>7s} {'Sharpe':>8s} {'return':>9s} {'DD':>8s}")
    print("-" * 78)
    for combo, r in agg.head(12).iterrows():
        print(f"{combo:42s} {int(r.wins):>3d}/{int(r.n):<3d} {r.mean_sharpe:>8.3f} "
              f"{r.mean_ret:>8.1f}% {r.mean_dd:>7.1f}%")

    print("-" * 78)
    print(f"NULL: with {n_combos} WORTHLESS combos and {n_disc} tickers, the best")
    print(f"      would score {exp_best:.1f}/{n_disc} on average by pure luck")
    print(f"      (95th percentile: {p95:.0f}/{n_disc})")
    best_wins = int(agg.iloc[0].wins)
    print(f"OURS: best scored {best_wins}/{n_disc}", end="  ")
    print("-> INDISTINGUISHABLE FROM LUCK" if best_wins <= p95
          else "-> above the luck threshold, worth confirming")

    top = list(agg.head(5).index)
    print("\n" + "=" * 78)
    print(f"CONFIRMATION — top 5 from discovery, tested on {n_conf} HELD-BACK tickers")
    print("=" * 78)
    print("This is the only table that matters. Discovery finds candidates;")
    print("confirmation is the first time these tickers have been touched.\n")
    print(f"{'Combination':42s} {'disc':>8s} {'CONF':>9s} {'Sharpe':>8s} {'vs B&H':>8s}")
    print("-" * 78)

    survivors = []
    for combo in top:
        c = conf[conf.Combo == combo]
        if c.empty:
            continue
        wins = int(c.Beat_BH.sum())
        d_wins = int(agg.loc[combo, "wins"])
        gap = c.Sharpe.mean() - c.BH_Sharpe.mean()
        held = wins > len(c) / 2
        survivors.append((combo, wins, len(c), gap, held))
        print(f"{combo:42s} {d_wins:>4d}/{n_disc:<3d} {wins:>4d}/{len(c):<4d} "
              f"{c.Sharpe.mean():>8.3f} {gap:>+8.3f}  "
              f"{'HELD UP' if held else 'collapsed'}")

    print("\n" + "=" * 78)
    print("VERDICT")
    print("=" * 78)
    held = [s for s in survivors if s[4]]
    if held:
        print(f"{len(held)} of {len(survivors)} candidates beat B&H on a majority")
        print("of held-back tickers:")
        for combo, w, n, gap, _ in held:
            print(f"   {combo}  ({w}/{n}, Sharpe {gap:+.3f} vs B&H)")
        print("\nWorth a proper look. Next step is a THIRD untouched sample -")
        print("surviving one confirmation set is encouraging, not conclusive.")
    else:
        print("NOTHING SURVIVED CONFIRMATION.")
        print()
        print("Every combination that looked good on discovery collapsed on the")
        print("held-back tickers. That is the signature of overfitting: the")
        print("winners were whichever combos happened to suit those particular")
        print("stocks over that particular window.")
        print()
        print("Consistent with Version 17. Pairing price indicators does not fix")
        print("a problem that is not about the indicators - it is about daily")
        print("price data on large-caps not containing a tradeable timing signal.")

    print(f"\nFull grid: {OUT_CSV}")
    print("=" * 78)


if __name__ == "__main__":
    sys.exit(main())
