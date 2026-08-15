"""
Momentum override - Version 12 single-window grid.

SUPERSEDED by override_walk_forward.py. This script tests a single 50/50 split,
which Version 10 and Version 12 both established is not sufficient evidence to
act on. Kept because it is the script that produced the Version 12 results
recorded in CONTEXT.md. For any new decision, use the walk-forward harness.

The override rule itself now lives in strategy/momentum_override.py so the two
scripts cannot drift apart.
"""
import warnings; warnings.filterwarnings("ignore")
import pandas as pd, numpy as np
from data.loader import load_data
from strategy.ml_signal import build_features, build_target, FEATURE_COLS
from sklearn.linear_model import LogisticRegression
from sklearn.ensemble import RandomForestClassifier
from sklearn.preprocessing import StandardScaler
from backtest.engine import run_backtest
from evaluation.metrics import get_metrics
from config import TICKERS, START, END, INITIAL_CAPITAL, STOP_LOSS, BACKTEST_POSITION_SIZE
from strategy.momentum_override import apply_override


def run(ticker, model_name, rsi_trigger=None, trail=None):
    df = load_data(ticker, START, END)
    df = build_features(df); df = build_target(df); df = df.dropna()
    X, y = df[FEATURE_COLS], df["Target"]
    mid = len(df)//2
    if model_name == "LR":
        sc = StandardScaler()
        Xtr, Xte = sc.fit_transform(X.iloc[:mid]), sc.transform(X.iloc[mid:])
        m = LogisticRegression(max_iter=1000).fit(Xtr, y.iloc[:mid])
        pred = m.predict(Xte)
    else:
        m = RandomForestClassifier(n_estimators=100, random_state=42).fit(X.iloc[:mid], y.iloc[:mid])
        pred = m.predict(X.iloc[mid:])

    d = df.iloc[mid:].copy(); d["Signal"] = pred
    n = apply_override(d, rsi_trigger, trail) if rsi_trigger else 0
    d["Position"] = d["Signal"].shift(1)
    d = run_backtest(d, INITIAL_CAPITAL, STOP_LOSS, BACKTEST_POSITION_SIZE)
    r = get_metrics(d, INITIAL_CAPITAL)
    return r["Sharpe_Ratio"], r["Total_Return"], r["Max_Drawdown"], n


for model_name in ("LR", "RF"):
    print(f"\n{'='*70}\n{model_name}\n{'='*70}")
    for tk in TICKERS:
        b_sh, b_ret, b_dd, _ = run(tk, model_name)
        print(f"\n{tk}  baseline: Sharpe {b_sh:.3f}  ret {b_ret:.1f}%  dd {b_dd:.1f}%")
        for rsi_t in (65, 70, 75):
            for trail in (0.03, 0.05, 0.08):
                sh, ret, dd, n = run(tk, model_name, rsi_t, trail)
                flag = " *" if sh > b_sh else ""
                print(f"   RSI>{rsi_t} trail {trail*100:.0f}%: "
                      f"Sharpe {sh:.3f} ({sh-b_sh:+.3f})  ret {ret:>7.1f}%  "
                      f"dd {dd:>6.1f}%  held {n}d{flag}")