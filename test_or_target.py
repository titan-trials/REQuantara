"""
Standalone test of the volatility-scaled 3-class target (Path D).
Touches nothing in the live pipeline — imports build_features only.

Baseline to beat (16-feat, binary target, POSITION_SIZE 0.50):
  LR: NVDA 0.928  TSLA 1.111  AAPL 1.091  JPM 0.118  IBM 0.496
  RF: NVDA 1.332  TSLA 0.728  AAPL 0.968  JPM 0.445  IBM 0.724
"""
import warnings
warnings.filterwarnings("ignore")
import pandas as pd
import numpy as np
from sklearn.linear_model import LogisticRegression
from sklearn.ensemble import RandomForestClassifier
from sklearn.preprocessing import StandardScaler

from data.loader import load_data
from strategy.ml_signal import build_features, FEATURE_COLS
from backtest.engine import run_backtest
from evaluation.metrics import get_metrics
from config import TICKERS, START, END, INITIAL_CAPITAL, STOP_LOSS

POSITION_SIZE = 0.50   # match the 0.50 baseline for a fair comparison
TC = 0.0005            # ~5bps one-way


def build_target_or(df, theta, vol_window=20):
    """
    Three-class volatility-scaled target.
      +1  next return exceeds  theta*sigma + 2*TC   (big up move)
      -1  next return below   -(theta*sigma + 2*TC) (big down move)
       0  everything else                            (do nothing)
    sigma uses only data up to t, so no lookahead.
    """
    close = df["Close"].squeeze()
    rets = close.pct_change()
    sigma = rets.rolling(vol_window).std()
    thresh = theta * sigma + 2 * TC
    nxt = rets.shift(-1)
    df["Target"] = np.where(nxt > thresh, 1, np.where(nxt < -thresh, -1, 0))
    df.loc[thresh.isna(), "Target"] = np.nan   # drop warm-up rows
    return df


def run_or(ticker, model_name, theta, conf):
    df = load_data(ticker, START, END)
    df = build_features(df)
    df = build_target_or(df, theta)
    df = df.dropna()
    if len(df) < 200:
        return None

    X, y = df[FEATURE_COLS], df["Target"].astype(int)
    mid = len(df) // 2
    X_tr, X_te, y_tr = X.iloc[:mid], X.iloc[mid:], y.iloc[:mid]

    if y_tr.nunique() < 2 or 1 not in set(y_tr):
        return None   # no big-up examples to learn from

    if model_name == "LR":
        sc = StandardScaler()
        X_tr_s, X_te_s = sc.fit_transform(X_tr), sc.transform(X_te)
        model = LogisticRegression(max_iter=1000, class_weight="balanced")
        model.fit(X_tr_s, y_tr)
        proba = model.predict_proba(X_te_s)
    else:
        model = RandomForestClassifier(
            n_estimators=100, random_state=42, class_weight="balanced")
        model.fit(X_tr, y_tr)
        proba = model.predict_proba(X_te)

    # long only when the model expects a big UP move with enough confidence
    idx_up = list(model.classes_).index(1)
    signals = (proba[:, idx_up] > conf).astype(int)

    df_te = df.iloc[mid:].copy()
    df_te["Signal"] = signals
    df_te["Position"] = df_te["Signal"].shift(1)
    df_te = run_backtest(df_te, INITIAL_CAPITAL, STOP_LOSS, POSITION_SIZE)
    m = get_metrics(df_te, INITIAL_CAPITAL)

    days_in = int(df_te["Position"].fillna(0).sum())
    flips = int((df_te["Signal"].diff().abs() > 0).sum())
    return m["Sharpe_Ratio"], m["Total_Return"], m["Max_Drawdown"], days_in, len(df_te), flips


BASE = {"LR": {"NVDA":0.928,"TSLA":1.111,"AAPL":1.091,"JPM":0.118,"IBM":0.496},
        "RF": {"NVDA":1.332,"TSLA":0.728,"AAPL":0.968,"JPM":0.445,"IBM":0.724}}

for model_name in ("LR", "RF"):
    print(f"\n{'='*78}\n{model_name} — volatility-scaled 3-class target\n{'='*78}")
    for theta in (1.0, 1.5, 2.0):
        for conf in (0.4, 0.5, 0.6):
            print(f"\n--- theta={theta}  confidence>{conf} ---")
            print(f"{'Tkr':<6}{'Sharpe':<9}{'base':<9}{'delta':<10}"
                  f"{'Return':<10}{'MaxDD':<10}{'in mkt':<9}{'trades'}")
            for tk in TICKERS:
                r = run_or(tk, model_name, theta, conf)
                if r is None:
                    print(f"{tk:<6}(insufficient class balance)")
                    continue
                sh, ret, dd, din, tot, flips = r
                b = BASE[model_name][tk]
                print(f"{tk:<6}{sh:<9.3f}{b:<9}{sh-b:+.3f}    "
                      f"{ret:<10.2f}{dd:<10.2f}{din}/{tot:<5}{flips}")