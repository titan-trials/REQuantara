"""
Does per-stock strategy selection actually work, or is it just picking the
biggest number out of seven?

THE QUESTION BEHIND THIS SCRIPT
Auto-selection is built on a reasonable premise: different stocks have
different character, so different strategies should suit them. A range-bound
name should suit Bollinger Bands; a trending one should suit a crossover. If
that premise holds, the strategy chosen on OLD data should keep working on NEW
data.

There are two ways to end up with a different winner on every ticker:

  (a) REAL      - the stock's character determines the fit, that character is
                  stable, and the choice therefore persists out of sample.
  (b) LUCK      - you tried seven things and kept the largest number, and next
                  period a different one wins.

They produce identical-looking tables. The ONLY way to separate them is to pick
on one period and score on the next. An earlier version of this script picked
the winner using the very period it then scored, which made (a) and (b)
indistinguishable by construction.

WHAT THIS RUNS, PER TICKER
  TRAIN = first 50% of available history
  TEST  = second 50%

  1. Score every strategy on TRAIN. Pick the best by composite score. This is
     exactly what auto_selector does live - it fits on history and deploys
     forward.
  2. Score that SAME strategy on TEST, against stopless Buy & Hold on TEST.
     This is the honest number.
  3. Also record the best strategy ON TEST - the cheating number - so the size
     of the selection bias is visible rather than assumed.

READING THE TWO NULLS (this is the part that matters)
  HONEST  - one strategy committed in advance vs one benchmark. With no skill
            at all this wins about 50% of the time. Beating 50% by a clear
            margin is evidence.
  CHEATING- best of seven vs one benchmark. With no skill this wins about 7/8 =
            87.5% of the time, because the maximum of seven draws usually beats
            a single draw. A "3 of 4" headline under this rule is BELOW chance.

ML strategies fit their own model internally on the first half of whatever they
are given, so scoring them on TEST means training on TRAIN and predicting TEST -
which is the correct arrangement without any special handling.

    python experiment_basket.py
"""

import warnings

warnings.filterwarnings("ignore")

import contextlib
import io
import os
import sys

import pandas as pd

from config import INITIAL_CAPITAL, STOP_LOSS, BACKTEST_POSITION_SIZE, START
from data.loader import load_data
from strategy.auto_selector import BUY_AND_HOLD, evaluate_rule_based, evaluate_ml

# ---------------------------------------------------------------------------
# THE BASKET
#
# HONESTY NOTE: this is not a true random sample. Any list written from memory
# is contaminated by knowing which companies did well - that is survivorship
# bias, and it is what made the original five tickers useless as a test.
#
# Two things are done to counteract it:
#   1. Deliberate sector spread - utilities, staples, REITs, telecom, energy,
#      materials, healthcare, industrials. Sectors nobody picks for their chart.
#   2. Deliberate inclusion of KNOWN DECLINERS and sideways names (INTC, WBA,
#      PARA, KHC, MMM, T, VZ, BXP, LEG...). A list of companies that merely
#      still exist and did fine is exactly the bias being tested for.
#
# The gold standard would be a point-in-time index constituent list, including
# companies later delisted. That is not available here, so treat this as
# "much better than the original five" rather than "unbiased".
# ---------------------------------------------------------------------------
BASKET = [
    # Utilities - boring by construction
    "SO", "DUK", "AEP", "ED", "XEL",
    # Consumer staples - many went sideways or fell
    "KHC", "GIS", "CAG", "CPB", "K", "SJM",
    # Telecom / media - notable decliners
    "T", "VZ", "PARA",
    # Healthcare - mixed
    "BMY", "PFE", "CVS", "VTRS",
    # Industrials
    "MMM", "EMR", "DOV",
    # Energy / materials
    "OKE", "DOW", "LYB", "MOS", "NEM",
    # REITs - includes office, which was crushed
    "O", "VTR", "KIM", "BXP", "HST",
    # Consumer / retail / other decliners
    "F", "WBA", "LEG", "INTC",
]

MIN_ROWS = 500
OUT_CSV = "results/experiment_basket.csv"


@contextlib.contextmanager
def quiet():
    """Silence the per-strategy prints - 36 tickers x 2 periods is unreadable."""
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        yield


def score_all(ticker, period_df, fit_df):
    """Every candidate scored over one period. Returns {strategy: metrics}.

    `period_df` is the window rule-based strategies are scored on.
    `fit_df`    is the history handed to the ML strategies; they split it 50/50
                internally, so passing history that ENDS at the period's end
                means they train on everything before it and predict it.
    """
    out = {}
    with quiet():
        for m in evaluate_rule_based(ticker, period_df, INITIAL_CAPITAL,
                                     STOP_LOSS, BACKTEST_POSITION_SIZE):
            out[m["Strategy"]] = m
        for m in evaluate_ml(ticker, START, None, INITIAL_CAPITAL, STOP_LOSS,
                             BACKTEST_POSITION_SIZE, full_df=fit_df):
            out[m["Strategy"]] = m
    return out


def evaluate_ticker(ticker):
    full = load_data(ticker, START, None)
    if full is None or len(full) < MIN_ROWS:
        raise ValueError(f"only {0 if full is None else len(full)} bars "
                         f"(need {MIN_ROWS})")

    mid = len(full) // 2
    train_df = full.iloc[:mid].copy()
    test_df = full.iloc[mid:].copy()

    # TRAIN: rule-based scored on the first half; ML fits inside the first half.
    train = score_all(ticker, train_df, train_df)
    # TEST: rule-based scored on the second half; ML trains on the first half
    # (its internal 50/50 split of the full history) and predicts the second.
    test = score_all(ticker, test_df, full)

    picked = max(train.values(), key=lambda m: m["Score"])["Strategy"]
    return {
        "ticker": ticker,
        "picked_on_train": picked,
        "train": train,
        "test": test,
        "first": full.index[0].date(),
        "last": full.index[-1].date(),
        "split": full.index[mid].date(),
    }


def main():
    records, failures, per_ticker = [], [], []

    for i, ticker in enumerate(BASKET, 1):
        print(f"[{i:2d}/{len(BASKET)}] {ticker:6s} ", end="", flush=True)
        try:
            r = evaluate_ticker(ticker)
        except Exception as e:
            print(f"SKIP — {type(e).__name__}: {e}")
            failures.append((ticker, f"{type(e).__name__}"))
            continue

        test, picked = r["test"], r["picked_on_train"]
        if BUY_AND_HOLD not in test or picked not in test:
            print("SKIP — incomplete candidate set")
            failures.append((ticker, "incomplete"))
            continue

        bh = test[BUY_AND_HOLD]
        honest = test[picked]
        active_test = {k: v for k, v in test.items() if k != BUY_AND_HOLD}
        cheating = max(active_test.values(), key=lambda m: m["Sharpe_Ratio"])

        honest_win = honest["Sharpe_Ratio"] > bh["Sharpe_Ratio"]
        cheat_win = cheating["Sharpe_Ratio"] > bh["Sharpe_Ratio"]
        persisted = picked == cheating["Strategy"]

        per_ticker.append({
            "Ticker": ticker, "Picked_On_Train": picked,
            "Picked_Test_Sharpe": honest["Sharpe_Ratio"],
            "Picked_Test_Return": honest["Total_Return"],
            "Picked_Test_MaxDD": honest["Max_Drawdown"],
            "BH_Test_Sharpe": bh["Sharpe_Ratio"],
            "BH_Test_Return": bh["Total_Return"],
            "BH_Test_MaxDD": bh["Max_Drawdown"],
            "Best_On_Test": cheating["Strategy"],
            "Best_Test_Sharpe": cheating["Sharpe_Ratio"],
            "Honest_Win": honest_win, "Cheating_Win": cheat_win,
            "Persisted": persisted,
        })
        for period, block in (("train", r["train"]), ("test", r["test"])):
            for name, m in block.items():
                records.append({"Ticker": ticker, "Period": period,
                                "Strategy": name, **m})

        print(f"picked {picked:20s} -> test Sharpe {honest['Sharpe_Ratio']:>6.3f} "
              f"vs B&H {bh['Sharpe_Ratio']:>6.3f}  "
              f"{'WIN ' if honest_win else 'lose'}"
              f"{'  [persisted]' if persisted else ''}")

    if not per_ticker:
        print("\nNothing evaluated.")
        return 1

    os.makedirs("results", exist_ok=True)
    pd.DataFrame(records).to_csv(OUT_CSV, index=False)
    summary(pd.DataFrame(per_ticker), failures)
    return 0


def summary(df, failures):
    n = len(df)
    honest = int(df["Honest_Win"].sum())
    cheating = int(df["Cheating_Win"].sum())
    persisted = int(df["Persisted"].sum())

    print("\n" + "=" * 78)
    print(f"RESULTS — {n} tickers")
    print("=" * 78)

    print(f"\n1. HONEST  (strategy picked on TRAIN, scored on TEST)")
    print(f"   beat buy & hold on {honest}/{n} = {honest/n:.0%}")
    print(f"   no-skill baseline: 50%  (one committed choice vs one benchmark)")
    edge = honest / n - 0.50
    print(f"   edge over chance: {edge:+.0%}")

    print(f"\n2. CHEATING  (best strategy chosen using TEST itself)")
    print(f"   beat buy & hold on {cheating}/{n} = {cheating/n:.0%}")
    print(f"   no-skill baseline: 88%  (max of 7 draws vs 1 draw)")
    print(f"   edge over chance: {cheating/n - 0.875:+.0%}")
    print(f"   -> the gap between 1 and 2 IS the selection bias, measured")

    print(f"\n3. PERSISTENCE  (did the TRAIN winner also win on TEST?)")
    print(f"   {persisted}/{n} = {persisted/n:.0%}")
    print(f"   no-skill baseline: ~14%  (1 in 7 by chance)")
    print(f"   This is the direct test of whether per-stock strategy fitting")
    print(f"   is real. High = stocks have stable character worth fitting to.")
    print(f"   At chance = the winner is whichever candidate got lucky.")

    print(f"\n4. DRAWDOWN  (does trading hurt less than holding?)")
    better_dd = int((df["Picked_Test_MaxDD"] > df["BH_Test_MaxDD"]).sum())
    print(f"   picked strategy had a shallower drawdown on {better_dd}/{n} "
          f"= {better_dd/n:.0%}")
    print(f"   mean drawdown: picked {df['Picked_Test_MaxDD'].mean():.1f}%  "
          f"vs  B&H {df['BH_Test_MaxDD'].mean():.1f}%")

    print(f"\n5. RETURN  (mean over the test period)")
    print(f"   picked {df['Picked_Test_Return'].mean():>8.1f}%   "
          f"B&H {df['BH_Test_Return'].mean():>8.1f}%")

    print("\n" + "-" * 78)
    print("MOST-PICKED STRATEGIES ON TRAIN")
    print("-" * 78)
    for name, count in df["Picked_On_Train"].value_counts().items():
        sub = df[df["Picked_On_Train"] == name]
        print(f"  {name:22s} picked {count:2d}x   "
              f"won {int(sub['Honest_Win'].sum())}/{count} on test")

    print("\n" + "-" * 78)
    print("PER TICKER")
    print("-" * 78)
    print(f"{'Ticker':7s} {'Picked on train':22s} {'test Sh':>8s} {'B&H Sh':>7s} "
          f"{'test DD':>8s} {'B&H DD':>7s}  result")
    for _, r in df.iterrows():
        print(f"{r['Ticker']:7s} {r['Picked_On_Train']:22s} "
              f"{r['Picked_Test_Sharpe']:>8.3f} {r['BH_Test_Sharpe']:>7.3f} "
              f"{r['Picked_Test_MaxDD']:>7.1f}% {r['BH_Test_MaxDD']:>6.1f}%  "
              f"{'WIN' if r['Honest_Win'] else 'lose'}")

    if failures:
        print(f"\nSkipped: {', '.join(f'{t} ({w})' for t, w in failures)}")

    print("\n" + "=" * 78)
    print("HOW TO JUDGE THIS")
    print("=" * 78)
    print("Line 1 is the number that matters. Anything near 50% means the")
    print("selection is not adding value, however good individual tickers look.")
    print("Line 3 tells you WHY: if a strategy chosen on history does not stay")
    print("the right choice, then per-stock fitting is fitting to noise.")
    print("Line 4 can be genuinely good even when 1 and 3 are not - sitting in")
    print("cash part of the time reduces drawdown whether or not it adds return.")
    print(f"\nFull grid: {OUT_CSV}")
    print("=" * 78)


if __name__ == "__main__":
    sys.exit(main())
