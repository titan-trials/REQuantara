"""
Autonomous strategy selection.

CHANGE LOG (Aug 2026 - churn fix):
Previously this module wrapped every strategy evaluation in a bare
`except: continue` / `except: pass` and called `load_data()` separately inside
every single strategy branch - 6 yfinance downloads per ticker, 30 per run,
every day. A single transient download failure would silently delete a
candidate strategy from the field, hand the win to whatever else was left, and
move real money. That is the most likely cause of AAPL's 15 one-day
EMA<->RF flips between May and June 2026: the scores are otherwise fully
deterministic (fixed 2015-2024 window, random_state=42), so identical inputs
should have produced identical winners every day.

Now: data is loaded once per ticker per window, every failure is logged
explicitly, and if ANY candidate fails to evaluate the entire selection run is
abandoned in favour of the last known-good assignment. A data hiccup can no
longer trade your account.
"""

import json
import os
import traceback
from datetime import datetime

import pandas as pd

from data.loader import load_data
from indicators.moving_average import compute_sma
from indicators.ema import compute_ema
from indicators.rsi import compute_rsi
from indicators.bollinger import compute_bollinger_bands
from signals.sma_crossover import (
    generate_crossover_signals,
    generate_ema_crossover_signals,
    generate_combined_signals,
)
from signals.bollinger_signal import generate_bollinger_signals
from backtest.engine import run_backtest
from evaluation.metrics import get_metrics
from strategy.ml_signal import run_ml_strategy, run_rf_strategy

ASSIGNMENTS_FILE = os.path.join("results", "strategy_assignments.json")

# Columns auto_select promises to return. paper_trader.py reads Best_Strategy.
SELECTION_COLUMNS = ["Best_Strategy", "Score", "Sharpe", "Total_Return", "Max_Drawdown"]


class StrategyEvaluationError(Exception):
    """Raised when a candidate strategy cannot be evaluated.

    This is deliberately fatal to the selection run. Silently dropping a
    candidate changes which strategy wins, and that moves money.
    """


try:
    from config import MAX_ACCEPTABLE_DRAWDOWN, ALLOW_BUY_AND_HOLD_LIVE
except ImportError:
    MAX_ACCEPTABLE_DRAWDOWN, ALLOW_BUY_AND_HOLD_LIVE = 0.40, False


def select_best(results):
    """Pick a tradeable strategy, subject to a drawdown guardrail.

    Returns (chosen, note). `note` is a string when something unusual happened
    and None otherwise.

    WHY A HARD LIMIT RATHER THAN JUST SCORING IT. compute_composite_score
    weights drawdown at 0.3 while total return is unbounded, so on a name that
    ran 1500% the return term alone contributes 3.0 and drowns everything else.
    TSLA's Buy & Hold scored 3.7365 on a -73.6% drawdown and won outright.
    Recovering from -73.6% requires +279%. A metric that ranks that first is
    answering a different question from the one an investor is asking.
    """
    eligible = list(results)

    if not ALLOW_BUY_AND_HOLD_LIVE:
        eligible = [r for r in eligible if r["Strategy"] != BUY_AND_HOLD]
    if not eligible:
        raise StrategyEvaluationError("no tradeable candidates")

    limit_pct = MAX_ACCEPTABLE_DRAWDOWN * 100
    within = [r for r in eligible if abs(r["Max_Drawdown"]) <= limit_pct]

    if within:
        chosen = max(within, key=lambda r: r["Score"])
        excluded = len(eligible) - len(within)
        note = (f"{excluded} candidate(s) excluded for drawdown worse than "
                f"{limit_pct:.0f}%") if excluded else None
        return chosen, note

    # Nothing clears the bar. Take the least-bad drawdown rather than the
    # highest score, and be loud about it - this means every available strategy
    # on this ticker is riskier than the account is willing to accept.
    chosen = min(eligible, key=lambda r: abs(r["Max_Drawdown"]))
    return chosen, (
        f"*** NO candidate under {limit_pct:.0f}% drawdown. Fell back to "
        f"{chosen['Strategy']} at {chosen['Max_Drawdown']:.1f}% (lowest "
        f"available). Consider not trading this ticker. ***"
    )


def compute_composite_score(metrics):
    sharpe = metrics["Sharpe_Ratio"]
    drawdown = abs(metrics["Max_Drawdown"]) / 100
    total_return = metrics["Total_Return"] / 100

    # Please Note score is on a scale roughly 0 to 2, with higher being better
    # Sharpe contributes 50%, Drawdown contributes 30%, Total Return contributes(Raw Return) 20%
    score = (sharpe * 0.5) + ((1 - drawdown) * 0.3) + (total_return * 0.2)
    return round(score, 4)


# --------------------------------------------------------------------------
# Persistence of last known-good assignments
# --------------------------------------------------------------------------

def load_last_good_assignments():
    """Return the last successfully-computed selection, or None."""
    if not os.path.exists(ASSIGNMENTS_FILE):
        return None
    try:
        with open(ASSIGNMENTS_FILE, "r") as f:
            payload = json.load(f)
        df = pd.DataFrame.from_dict(payload["assignments"], orient="index")
        df.index.name = "Ticker"
        return df[SELECTION_COLUMNS]
    except Exception as e:
        print(f"[auto_select] WARNING: could not read {ASSIGNMENTS_FILE}: {e}")
        return None


def save_assignments(selections_df):
    os.makedirs(os.path.dirname(ASSIGNMENTS_FILE), exist_ok=True)
    payload = {
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "assignments": selections_df[SELECTION_COLUMNS].to_dict(orient="index"),
    }
    with open(ASSIGNMENTS_FILE, "w") as f:
        json.dump(payload, f, indent=2)
    print(f"[auto_select] Saved known-good assignments to {ASSIGNMENTS_FILE}")


# --------------------------------------------------------------------------
# Candidate evaluation
# --------------------------------------------------------------------------

# The name is matched in three places - auto_selector, paper_trader's live
# signal branch, and the stop-loss bypass in the executor - so it lives here.
BUY_AND_HOLD = "Buy & Hold"


def _buy_and_hold_signal(df):
    """Always long. The benchmark every other strategy has to beat."""
    df["Signal"] = 1
    df["Position"] = 1
    return df


RULE_BASED_STRATEGIES = [
    {
        # Added in Version 16. Until now the selector only ever asked "which of
        # my six strategies scores highest?" - never "is any of this better
        # than just buying the stock and doing nothing?". get_metrics has
        # returned Market_Return since day one and nothing read it.
        #
        # NOTE `stop_loss: 0`. This must be genuinely stopless to be a real
        # benchmark. Scored with the usual 5% stop it becomes "always long,
        # stopped out at -5%, re-entered the next bar" - a whipsaw strategy,
        # not buy and hold. That exact mistake invalidated the Round 3 control
        # arm in Version 14.
        "name": BUY_AND_HOLD,
        "build": lambda df: df,
        "signal": _buy_and_hold_signal,
        "stop_loss": 0.0,
    },
    {
        "name": "SMA Crossover",
        "build": lambda df: [compute_sma(df, 20), compute_sma(df, 50)][-1],
        "signal": lambda df: generate_crossover_signals(df, 20, 50),
    },
    {
        "name": "EMA Crossover",
        "build": lambda df: [compute_ema(df, 20), compute_ema(df, 50)][-1],
        "signal": lambda df: generate_ema_crossover_signals(df, 20, 50),
    },
    {
        "name": "SMA + RSI",
        "build": lambda df: [compute_sma(df, 20), compute_sma(df, 50), compute_rsi(df)][-1],
        "signal": lambda df: generate_combined_signals(df, 20, 50),
    },
    {
        "name": "Bollinger Bands",
        "build": lambda df: compute_bollinger_bands(df),
        "signal": generate_bollinger_signals,
    },
]


def evaluate_rule_based(ticker, test_df, initial_capital, stop_loss, position_size):
    """Evaluate every rule-based candidate against a PRE-LOADED test frame.

    `test_df` is loaded once by the caller and copied per strategy - the build
    and signal functions mutate the frame in place (adding SMA_20, Signal, etc),
    so sharing one frame across strategies would leak indicator and signal
    columns between candidates.
    """
    results = []
    for strategy in RULE_BASED_STRATEGIES:
        name = strategy["name"]
        try:
            df = test_df.copy()
            df = strategy["build"](df)
            df = strategy["signal"](df)
            # Buy & Hold overrides the stop to 0 so it is genuinely stopless.
            df = run_backtest(df, initial_capital,
                              strategy.get("stop_loss", stop_loss),
                              position_size)
            metrics = get_metrics(df, initial_capital)
            metrics["Strategy"] = name
            metrics["Score"] = compute_composite_score(metrics)
            results.append(metrics)
        except Exception as e:
            print(f"[auto_select] FAILED {ticker} / {name}: {type(e).__name__}: {e}")
            traceback.print_exc()
            raise StrategyEvaluationError(
                f"{ticker} / {name} failed to evaluate: {type(e).__name__}: {e}"
            ) from e
    return results


def evaluate_ml(ticker, start, end, initial_capital, stop_loss, position_size, full_df=None):
    """Evaluate LR and RF candidates.

    `full_df` is the pre-loaded full-history frame; run_ml_strategy and
    run_rf_strategy accept it so we do not re-download the same data twice more.
    """
    results = []

    ml_candidates = [
        ("Logistic Regression", run_ml_strategy),
        ("Random Forest", run_rf_strategy),
    ]

    for name, fn in ml_candidates:
        try:
            output = fn(
                ticker, start, end, initial_capital, stop_loss, position_size,
                df=None if full_df is None else full_df.copy(),
            )
            metrics = output[1]
            metrics["Strategy"] = name
            metrics["Score"] = compute_composite_score(metrics)
            results.append(metrics)
        except Exception as e:
            print(f"[auto_select] FAILED {ticker} / {name}: {type(e).__name__}: {e}")
            traceback.print_exc()
            raise StrategyEvaluationError(
                f"{ticker} / {name} failed to evaluate: {type(e).__name__}: {e}"
            ) from e

    return results


# --------------------------------------------------------------------------
# Selection
# --------------------------------------------------------------------------

def auto_select(tickers, start, end, initial_capital, stop_loss, position_size):
    """Pick the best strategy per ticker.

    All-or-nothing: if any ticker's candidate field cannot be fully evaluated,
    the whole run is abandoned and the last known-good assignment is returned
    unchanged. Selecting from a partial field is how a transient yfinance
    failure turns into a real trade.
    """
    try:
        return _auto_select_strict(
            tickers, start, end, initial_capital, stop_loss, position_size
        )
    except Exception as e:
        # Deliberately broad. Any failure at all - a failed candidate, a bad
        # download, an unexpected bug - must not be allowed to produce a
        # selection, because a selection moves money.
        print("\n" + "=" * 70)
        print("[auto_select] SELECTION RUN ABANDONED")
        print(f"[auto_select] Reason: {type(e).__name__}: {e}")
        print("=" * 70)

        fallback = load_last_good_assignments()
        if fallback is None:
            raise RuntimeError(
                "Strategy selection failed and there is no last known-good "
                f"assignment in {ASSIGNMENTS_FILE} to fall back to. Refusing to "
                "trade on an incomplete strategy field. Original error: "
                f"{type(e).__name__}: {e}"
            ) from e

        print("[auto_select] Falling back to last known-good assignment:")
        print(fallback.to_string())
        print("[auto_select] No strategy will change on this run.\n")
        return fallback


def _auto_select_strict(tickers, start, end, initial_capital, stop_loss, position_size):
    # Test period is second half of date range
    full_df_probe = load_data(tickers[0], start, end)
    midpoint = len(full_df_probe) // 2
    test_start = str(full_df_probe.index[midpoint].date())
    test_end = str(full_df_probe.index[-1].date())

    print(f"Evaluating on test period: {test_start} to {test_end}")

    selections = []

    for ticker in tickers:
        print(f"\nEvaluating {ticker}...")

        # Two downloads per ticker instead of six. Both are reused (copied) for
        # every candidate strategy below.
        full_df = load_data(ticker, start, end)
        test_df = load_data(ticker, test_start, test_end)

        if full_df is None or len(full_df) == 0:
            raise StrategyEvaluationError(f"{ticker}: empty full-history frame")
        if test_df is None or len(test_df) == 0:
            raise StrategyEvaluationError(f"{ticker}: empty test-window frame")

        all_results = []
        all_results.extend(
            evaluate_rule_based(ticker, test_df, initial_capital, stop_loss, position_size)
        )
        all_results.extend(
            evaluate_ml(ticker, start, end, initial_capital, stop_loss, position_size,
                        full_df=full_df)
        )

        expected = len(RULE_BASED_STRATEGIES) + 2
        if len(all_results) != expected:
            raise StrategyEvaluationError(
                f"{ticker}: expected {expected} candidates, got {len(all_results)}"
            )

        results_df = pd.DataFrame(all_results)
        best, note = select_best(all_results)
        if note:
            print(f"[auto_select] {ticker}: {note}")

        # The benchmark comparison is the most useful line the selector prints,
        # whether or not Buy & Hold is eligible to trade.
        bh = next((r for r in all_results if r["Strategy"] == BUY_AND_HOLD), None)
        if bh is not None and best["Strategy"] != BUY_AND_HOLD:
            gap = best["Total_Return"] - bh["Total_Return"]
            print(f"[auto_select] {ticker}: vs Buy & Hold  "
                  f"{gap:+.1f} pts return, "
                  f"Sharpe {best['Sharpe_Ratio'] - bh['Sharpe_Ratio']:+.3f}, "
                  f"drawdown {best['Max_Drawdown']:.1f}% vs {bh['Max_Drawdown']:.1f}%")

        # Surface near-ties. A margin this small means the winner is noise, and
        # noise-driven winners are what produce day-to-day strategy churn.
        ranked = results_df.sort_values("Score", ascending=False)
        if len(ranked) > 1:
            margin = ranked.iloc[0]["Score"] - ranked.iloc[1]["Score"]
            if margin < 0.05:
                print(
                    f"[auto_select] NOTE {ticker}: {ranked.iloc[0]['Strategy']} beat "
                    f"{ranked.iloc[1]['Strategy']} by only {margin:.4f} - "
                    "this selection is effectively a coin flip."
                )

        selections.append({
            "Ticker": ticker,
            "Best_Strategy": best["Strategy"],
            "Score": best["Score"],
            "Sharpe": best["Sharpe_Ratio"],
            "Total_Return": best["Total_Return"],
            "Max_Drawdown": best["Max_Drawdown"],
        })

        print(f"Winner: {best['Strategy']} (Score: {best['Score']})")

    final_df = pd.DataFrame(selections).set_index("Ticker")
    save_assignments(final_df)
    return final_df
