"""
Walk-forward validation of the Version 12 momentum override, on the corrected
Version 13 engine.

WHY THIS EXISTS
Version 12 found that the override improved TSLA-on-RF in 9 of 9 parameter
configurations. That result was produced on a SINGLE 50/50 split, at
POSITION_SIZE 0.50, on a 19-feature set, using an engine that floored to whole
shares and had a stop loss that re-bought on the same bar. All four of those
things are now different. The Version 12 numbers are void - not merely
unvalidated.

Version 10's lesson, in the project's own words: "a convincing single-window
result is exactly when to be most suspicious." The NVDA false positive looked
clean and would have shipped without a second check.

WHAT THIS DOES
For every (ticker, model, window) it trains ONCE and applies all 9 override
configurations to the same predictions. The override is a post-hoc rewrite of
the signal vector - it does not change the model - so refitting per config (as
the original mom_override.py did, 450 times) is pure waste.

Four windows, all starting 2015-01-01, ending 2024/2023/2022/2021. NOTE these
are four different total-history lengths each internally split 50/50, NOT four
independent disjoint train/test periods. Same caveat as Version 10.

THE BAR TO CLEAR
Not "average delta is positive". The override should only be considered for a
given ticker+model if it improves in the large majority of cells AND holds up
in every window. Consistency across parameter values and across windows is what
separates a real effect from a lucky cell - that is the entire lesson of
Versions 10 and 12.

    python override_walk_forward.py

Runtime is a few minutes, dominated by yfinance downloads.
"""

import warnings

warnings.filterwarnings("ignore")

import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import StandardScaler

from backtest.engine import run_backtest
from config import INITIAL_CAPITAL, STOP_LOSS, BACKTEST_POSITION_SIZE, TICKERS
from data.loader import load_data
from evaluation.metrics import get_metrics
from strategy.ml_signal import build_features, build_target, FEATURE_COLS
from strategy.momentum_override import apply_override, apply_trailing_stop_only

FULL_START = "2015-01-01"
WINDOW_ENDS = ["2024-01-01", "2023-01-01", "2022-01-01", "2021-01-01"]
# ---------------------------------------------------------------------------
# ROUND 2 GRID (Aug 2026)
#
# Round 1 used RSI (65, 70, 75) x trail (3%, 5%, 8%) and came back MONOTONIC:
# every best cell sat on the boundary (RSI 65, trail 8%), meaning the optimum
# was never bracketed. Round 2 extends past that boundary in both directions to
# find whether an interior maximum exists at all.
#
# RSI trigger 0 is CONTROL ARM A: `rsi > 0` is always true, so the RSI
# condition is disabled while everything else about the rule stays identical.
# If arm A matches the RSI-gated cells, RSI is doing no work.
# ---------------------------------------------------------------------------
RSI_TRIGGERS = (0, 50, 55, 60, 65)      # 0 = control arm A (no RSI condition)
TRAILS = (0.08, 0.12, 0.15, 0.20)
MODELS = ("LR", "RF")

# Round 1 values, kept so the previous run stays reproducible:
#   RSI_TRIGGERS = (65, 70, 75); TRAILS = (0.03, 0.05, 0.08)

OUT_CSV = "results/override_walk_forward.csv"


def prepare(ticker, end):
    """Load, build features, split. Returns (df, midpoint) or raises."""
    df = load_data(ticker, FULL_START, end)
    df = build_features(df)
    df = build_target(df)
    df = df.dropna()
    if len(df) < 200:
        raise ValueError(f"{ticker} @ {end}: only {len(df)} usable rows")
    return df, len(df) // 2


def fit_predict(df, mid, model_name):
    """Train once, return test-set predictions."""
    X, y = df[FEATURE_COLS], df["Target"]
    if model_name == "LR":
        scaler = StandardScaler()
        X_train = scaler.fit_transform(X.iloc[:mid])
        X_test = scaler.transform(X.iloc[mid:])
        model = LogisticRegression(max_iter=1000).fit(X_train, y.iloc[:mid])
        return model.predict(X_test)
    model = RandomForestClassifier(n_estimators=100, random_state=42)
    model.fit(X.iloc[:mid], y.iloc[:mid])
    return model.predict(X.iloc[mid:])


def score(df, mid, predictions, rsi_trigger=None, trail=None, legacy=False):
    """Backtest a prediction vector, optionally with the override applied."""
    d = df.iloc[mid:].copy()
    d["Signal"] = predictions
    # `is not None`, NOT truthiness. rsi_trigger == 0 is the control arm that
    # disables the RSI gate, and `if rsi_trigger:` silently skipped it - making
    # the control return the baseline and report a delta of exactly 0.000.
    held = (apply_override(d, rsi_trigger, trail, legacy=legacy)
            if rsi_trigger is not None else 0)
    d = run_backtest(d, INITIAL_CAPITAL, STOP_LOSS, BACKTEST_POSITION_SIZE)
    m = get_metrics(d, INITIAL_CAPITAL)
    return m["Sharpe_Ratio"], m["Total_Return"], m["Max_Drawdown"], held


def main():
    rows = []
    control_rows = []

    for ticker in TICKERS:
        for end in WINDOW_ENDS:
            try:
                df, mid = prepare(ticker, end)
            except Exception as e:
                print(f"SKIP {ticker} @ {end}: {type(e).__name__}: {e}")
                continue

            for model_name in MODELS:
                try:
                    preds = fit_predict(df, mid, model_name)
                except Exception as e:
                    print(f"SKIP {ticker}/{model_name} @ {end}: {type(e).__name__}: {e}")
                    continue

                b_sh, b_ret, b_dd, _ = score(df, mid, preds)

                # BUY & HOLD BENCHMARK. The override improves monotonically as
                # it holds longer, and its limit case is "never sell". On
                # NVDA/AAPL/TSLA over 2015-2024 that limit IS buy & hold, on
                # names that rose enormously. If B&H beats every arm, the
                # "edge" is just "trade less on stocks that went up 10x" - a
                # property of the sample, not of the rule.
                d_bh = df.iloc[mid:].copy()
                d_bh["Signal"] = 1
                # stop_loss=0 — MUST be stopless to be a real benchmark.
                #
                # The Round 3 run passed STOP_LOSS (0.05), so "buy & hold" was
                # actually "always long, stopped out at -5%, re-entered the
                # next bar" - a whipsaw strategy, not a hold. Every Round 3
                # B&H figure was measuring the wrong thing.
                d_bh = run_backtest(d_bh, INITIAL_CAPITAL, 0.0,
                                    BACKTEST_POSITION_SIZE)
                m_bh = get_metrics(d_bh, INITIAL_CAPITAL)
                control_rows.append({
                    "Ticker": ticker, "Model": model_name, "WindowEnd": end,
                    "Arm": "buy_and_hold", "Trail": None,
                    "Base_Sharpe": b_sh, "New_Sharpe": m_bh["Sharpe_Ratio"],
                    "Delta_Sharpe": round(m_bh["Sharpe_Ratio"] - b_sh, 4),
                    # Recorded so this is comparable to Version 11's
                    # return-based live finding, not only on Sharpe.
                    "Base_Return": b_ret, "New_Return": m_bh["Total_Return"],
                    "Delta_Return": round(m_bh["Total_Return"] - b_ret, 4),
                    "Base_MaxDD": b_dd, "New_MaxDD": m_bh["Max_Drawdown"],
                    "Delta_MaxDD": round(m_bh["Max_Drawdown"] - b_dd, 4),
                    "Days_Held": len(d_bh),
                })

                # CONTROL ARM B: ignore the model's exits entirely, exit only on
                # a trailing stop. Recorded once per trail width per window.
                for trail in TRAILS:
                    d = df.iloc[mid:].copy()
                    d["Signal"] = preds
                    held_b = apply_trailing_stop_only(d, trail)
                    d = run_backtest(d, INITIAL_CAPITAL, STOP_LOSS,
                                     BACKTEST_POSITION_SIZE)
                    mb = get_metrics(d, INITIAL_CAPITAL)
                    control_rows.append({
                        "Ticker": ticker, "Model": model_name, "WindowEnd": end,
                        "Arm": "trail_only", "Trail": trail,
                        "Base_Sharpe": b_sh, "New_Sharpe": mb["Sharpe_Ratio"],
                        "Delta_Sharpe": round(mb["Sharpe_Ratio"] - b_sh, 4),
                        "Base_Return": b_ret, "New_Return": mb["Total_Return"],
                        "Delta_Return": round(mb["Total_Return"] - b_ret, 4),
                        "Base_MaxDD": b_dd, "New_MaxDD": mb["Max_Drawdown"],
                        "Delta_MaxDD": round(mb["Max_Drawdown"] - b_dd, 4),
                        "Days_Held": held_b,
                    })

                for rsi_t in RSI_TRIGGERS:
                    for trail in TRAILS:
                        sh, ret, dd, held = score(df, mid, preds, rsi_t, trail)
                        # Also score the Version 12 implementation, so the report
                        # can say whether that result depended on its two bugs.
                        l_sh, _, _, l_held = score(
                            df, mid, preds, rsi_t, trail, legacy=True
                        )
                        rows.append({
                            "Ticker": ticker,
                            "Model": model_name,
                            "WindowEnd": end,
                            "RSI_Trigger": rsi_t,
                            "Trail": trail,
                            "Base_Sharpe": b_sh,
                            "New_Sharpe": sh,
                            "Delta_Sharpe": round(sh - b_sh, 4),
                            "Legacy_Sharpe": l_sh,
                            "Legacy_Delta": round(l_sh - b_sh, 4),
                            "Base_Return": b_ret,
                            "New_Return": ret,
                            "Base_MaxDD": b_dd,
                            "New_MaxDD": dd,
                            "Delta_MaxDD": round(dd - b_dd, 4),
                            "Days_Held": held,
                            "Legacy_Days_Held": l_held,
                        })

                print(f"  {ticker:5s} {model_name}  {end[:4]}  "
                      f"base Sharpe {b_sh:6.3f}  "
                      f"override avg {np.mean([r['New_Sharpe'] for r in rows if r['Ticker'] == ticker and r['Model'] == model_name and r['WindowEnd'] == end]):6.3f}")

    if not rows:
        print("\nNo results produced - every window failed to load.")
        return

    results = pd.DataFrame(rows)
    controls = pd.DataFrame(control_rows)
    import os
    os.makedirs("results", exist_ok=True)
    results.to_csv(OUT_CSV, index=False)
    controls.to_csv(OUT_CSV.replace(".csv", "_controls.csv"), index=False)
    print(f"\nFull grid written to {OUT_CSV} ({len(results)} rows)")
    print(f"Control arm B written to {OUT_CSV.replace('.csv', '_controls.csv')} "
          f"({len(controls)} rows)")

    report(results, controls)
    report_controls(results, controls)


def report(results, controls=None):
    print("\n" + "=" * 78)
    print("VERDICT BY TICKER + MODEL")
    print("=" * 78)
    print("IMPORTANT: 'avg d' is measured against the ML MODEL's own baseline.")
    print("That baseline can itself lose badly to buy & hold, in which case a")
    print("large positive delta only means the override dragged a losing")
    print("strategy part of the way back toward doing nothing. The 'vs B&H'")
    print("column is the one that decides whether anything here is worth having.")
    print("cells    = config-window combinations improved, out of the full grid (configs x 4 windows)")
    print("windows  = windows where the override's AVERAGE delta was positive, out of 4")
    print("ddelta   = mean change in max drawdown (negative = deeper drawdown)")
    print()
    print()
    print(f"{'Ticker':6s} {'Model':5s} {'cells':>7s} {'windows':>8s} "
          f"{'avg d':>8s} {'vs B&H':>8s} {'ddelta':>8s}  verdict")
    print("-" * 86)

    def bh_delta(ticker, model):
        """The buy & hold arm's own delta over the same baseline."""
        if controls is None or not len(controls):
            return None
        rows = controls[(controls.Ticker == ticker)
                        & (controls.Model == model)
                        & (controls.Arm == "buy_and_hold")]["Delta_Sharpe"]
        return float(rows.mean()) if len(rows) else None

    verdicts = []
    for (ticker, model), g in results.groupby(["Ticker", "Model"]):
        cells = int((g["Delta_Sharpe"] > 0).sum())
        total = len(g)
        per_window = g.groupby("WindowEnd")["Delta_Sharpe"].mean()
        windows_pos = int((per_window > 0).sum())
        avg_delta = g["Delta_Sharpe"].mean()
        worst_window = per_window.min()
        dd_delta = g["Delta_MaxDD"].mean()

        bh = bh_delta(ticker, model)

        # Deliberately demanding. Version 12's TSLA result was 9/9 on ONE window;
        # the whole point of this harness is that one window is not evidence.
        #
        # And beating the model's own baseline is NOT sufficient. If buy & hold
        # beats the override over the same window, the override is not an edge -
        # it is a slightly less bad way of losing to doing nothing.
        if bh is not None and avg_delta < bh:
            verdict = "LOSES TO BUY & HOLD - not an edge"
        elif cells >= 0.8 * total and windows_pos == 4 and avg_delta > 0.05:
            verdict = "ADOPT - beats B&H, consistent across all windows"
        elif cells >= 0.6 * total and windows_pos >= 3:
            verdict = "PROMISING - retest, do not ship"
        elif avg_delta > 0:
            verdict = "NOISE - positive on average, not consistent"
        else:
            verdict = "REJECT"

        verdicts.append((ticker, model, verdict))
        bh_str = f"{bh:>8.3f}" if bh is not None else f"{'n/a':>8s}"
        print(f"{ticker:6s} {model:5s} {cells:>4d}/{total:<2d} {windows_pos:>6d}/4 "
              f"{avg_delta:>8.3f} {bh_str} {dd_delta:>8.2f}  {verdict}")

    print("\n" + "=" * 78)
    print("PER-WINDOW DETAIL (mean Sharpe delta)")
    print("=" * 78)
    pivot = results.pivot_table(
        index=["Ticker", "Model"], columns="WindowEnd",
        values="Delta_Sharpe", aggfunc="mean",
    ).round(3)
    print(pivot.to_string())

    print("\n" + "=" * 78)
    print("SENSITIVITY TO PARAMETERS (mean Sharpe delta, pooled across windows)")
    print("=" * 78)
    print("A real effect should be broadly positive across this whole grid.")
    print("Strength in one or two cells is the signature of a false positive.")
    grid = results.pivot_table(
        index=["Ticker", "Model"], columns=["RSI_Trigger", "Trail"],
        values="Delta_Sharpe", aggfunc="mean",
    ).round(3)
    print(grid.to_string())

    print("\n" + "=" * 78)
    print("CORRECTED RULE vs THE VERSION 12 IMPLEMENTATION")
    print("=" * 78)
    print("V12's override had two bugs (see strategy/momentum_override.py): it")
    print("engaged on unprofitable positions, and its trailing stop ratcheted down")
    print("instead of exiting. If 'legacy' wins here, the V12 result was an artefact")
    print("of holding losers longer - which is a leverage-on-losses effect, not an")
    print("edge, and would be actively dangerous live.")
    print()
    print(f"{'Ticker':6s} {'Model':5s} {'corrected d':>12s} {'legacy d':>10s} "
          f"{'held':>6s} {'legacy held':>12s}")
    print("-" * 78)
    for (ticker, model), g in results.groupby(["Ticker", "Model"]):
        print(f"{ticker:6s} {model:5s} {g['Delta_Sharpe'].mean():>12.3f} "
              f"{g['Legacy_Delta'].mean():>10.3f} "
              f"{g['Days_Held'].mean():>6.0f} {g['Legacy_Days_Held'].mean():>12.0f}")

    adopt = [f"{t}/{m}" for t, m, v in verdicts if v.startswith("ADOPT")]
    print("\n" + "=" * 78)
    if adopt:
        print(f"ADOPT candidates: {', '.join(adopt)}")
        print("Before shipping, check these are the models actually assigned live.")
        print("Version 12 shipped nothing precisely because the wins were on models")
        print("that were not live and the live model (NVDA/RF) got worse.")
    else:
        print("No ticker+model cleared the bar. The override does not survive")
        print("walk-forward on the corrected engine.")
    print("=" * 78)


def report_controls(results, controls):
    """Answer the only question that matters: is the RSI condition doing work?"""
    print("\n" + "=" * 78)
    print("DOES THE RSI CONDITION DO ANY WORK?")
    print("=" * 78)
    print("Arm A  = the same rule with the RSI gate disabled (RSI_Trigger = 0).")
    print("Arm B  = model exits ignored completely; exit only on a trailing stop.")
    print("If A matches the gated cells, the RSI condition is decorative.")
    print("If B matches or beats both, the model's exit signal has no value at all")
    print("and the honest conclusion is 'replace the exit rule', not 'add an override'.")
    print()

    gated = results[results["RSI_Trigger"] > 0]
    arm_a = results[results["RSI_Trigger"] == 0]

    print("B&H    = buy & hold. The override's limit case as the trail widens.")
    print("         If B&H wins, the gradient is survivorship bias, not an edge.")
    print()
    print(f"{'Ticker':6s} {'Model':5s} {'gated d':>9s} {'armA d':>9s} "
          f"{'armB d':>9s} {'B&H d':>9s} {'winner':>7s}  interpretation")
    print("-" * 90)

    for (ticker, model), g in gated.groupby(["Ticker", "Model"]):
        a = arm_a[(arm_a.Ticker == ticker) & (arm_a.Model == model)]["Delta_Sharpe"]
        def arm(name):
            if not len(controls):
                return pd.Series(dtype=float)
            return controls[(controls.Ticker == ticker)
                            & (controls.Model == model)
                            & (controls.Arm == name)]["Delta_Sharpe"]

        b = arm("trail_only")
        bh = arm("buy_and_hold")
        gd = g["Delta_Sharpe"].mean()
        ad = a.mean() if len(a) else float("nan")
        bd = b.mean() if len(b) else float("nan")
        hd = bh.mean() if len(bh) else float("nan")

        cands = [("gated", gd), ("armA", ad), ("armB", bd), ("B&H", hd)]
        cands = [(n, v) for n, v in cands if v == v]  # drop NaN
        best = max(cands, key=lambda t: t[1])[0] if cands else "?"

        if best == "B&H":
            interp = "BUY & HOLD WINS - no edge here"
        elif best == "armB":
            interp = "exit signal has NO value"
        elif best == "armA":
            interp = "RSI gate is decorative"
        elif gd - max([v for n, v in cands if n != "gated"] or [0]) < 0.03:
            interp = "gate adds ~nothing"
        else:
            interp = "RSI gate genuinely helps"

        print(f"{ticker:6s} {model:5s} {gd:>9.3f} {ad:>9.3f} {bd:>9.3f} "
              f"{hd:>9.3f} {best:>7s}  {interp}")

    print("\n" + "-" * 78)
    print("PARAMETER SURFACE - does the RSI gate do anything?")
    print("-" * 78)
    surface = results.pivot_table(
        index="RSI_Trigger", columns="Trail", values="Delta_Sharpe", aggfunc="mean"
    ).round(3)
    print(surface.to_string())

    # RSI_Trigger 0 is CONTROL ARM A - the gate switched off. It is NOT a
    # parameter value, and including it in "where is the maximum?" is what made
    # an earlier version of this report announce an interior maximum when the
    # surface was in fact flat: the best gated cell beat the no-gate control by
    # 0.008, which is noise.
    control = surface.loc[0].mean() if 0 in surface.index else None
    gated = surface.drop(index=0, errors="ignore")

    if gated.empty:
        print("\nNo gated cells to compare.")
        print("=" * 78)
        return

    flat = gated.stack()
    best_rsi, best_trail = flat.idxmax()
    best = flat.max()

    print(f"\nBest GATED cell:   RSI {best_rsi}, trail {best_trail:.0%}  "
          f"-> {best:+.3f}")
    if control is not None:
        edge = best - control
        print(f"No-gate control:   RSI 0 (gate disabled)         -> {control:+.3f}")
        print(f"What the gate buys you:                             {edge:+.3f}")
        if edge < 0.05:
            print("\n*** THE RSI GATE IS DOING NOTHING. ***")
            print("The gated grid does not meaningfully beat the same rule with the")
            print("gate switched off. Whatever is working here, it is the trailing")
            print("stop - not the momentum condition the rule is named after.")
        else:
            print("\nThe gate earns its place - gated beats no-gate by a real margin.")

    gated_rsis = [r for r in RSI_TRIGGERS if r != 0]
    on_edge = (best_rsi in (min(gated_rsis), max(gated_rsis))
               or best_trail in (min(TRAILS), max(TRAILS)))
    if on_edge:
        print("\nNOTE: the best gated cell sits on the edge of the tested grid, so")
        print("the optimum has still not been bracketed.")
    print("=" * 78)


if __name__ == "__main__":
    main()
