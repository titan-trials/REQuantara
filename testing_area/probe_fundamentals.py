"""
What fundamental data is actually available, and how far back?

Run this BEFORE building any fundamental strategy. It answers questions that
determine whether the experiment is even possible:

  - Which statement fields exist, and for how many of our tickers?
  - How many quarters of history? (yfinance is typically ~4-5 years, which
    caps any backtest window regardless of how much price history we have.)
  - Do we get PERIOD END DATES? Without them there is no way to apply a
    reporting lag, and without a reporting lag the whole exercise is invalid.

WHY THE LAG MATTERS SO MUCH. `yf.Ticker(x).info` returns TODAY's P/E. Using
today's P/E to make a 2019 decision is look-ahead bias of the most destructive
kind - it will produce a spectacular backtest that is entirely fictional. A
company's Q4 numbers are not public until the 10-K files, typically 60-90 days
after the quarter ends. Any honest fundamental backtest must only use figures
that were actually published at the time.

This script does NOT trade anything or make claims. It reports what exists so
the real experiment can be designed against reality instead of assumptions.

    python probe_fundamentals.py
"""

import warnings

warnings.filterwarnings("ignore")

import sys
from collections import Counter

import pandas as pd

PROBE_TICKERS = ["SO", "KHC", "T", "PFE", "MMM", "OKE", "O", "F", "INTC", "NEM"]

# Fields needed to build the standard value/quality ratios. Names vary between
# yfinance versions and between companies, so several aliases are checked.
WANTED = {
    "Net Income":       ["Net Income", "NetIncome", "Net Income Common Stockholders"],
    "Total Revenue":    ["Total Revenue", "TotalRevenue", "Operating Revenue"],
    "Total Equity":     ["Stockholders Equity", "Total Stockholder Equity",
                         "StockholdersEquity", "Common Stock Equity"],
    "Total Assets":     ["Total Assets", "TotalAssets"],
    "Total Debt":       ["Total Debt", "TotalDebt", "Long Term Debt"],
    "Shares Out":       ["Share Issued", "Ordinary Shares Number",
                         "Common Stock Shares Outstanding"],
    "Operating Income": ["Operating Income", "OperatingIncome", "EBIT"],
    "Free Cash Flow":   ["Free Cash Flow", "FreeCashFlow"],
}


def find_field(index, aliases):
    idx = {str(i).strip().lower(): str(i) for i in index}
    for alias in aliases:
        if alias.lower() in idx:
            return idx[alias.lower()]
    return None


def probe(ticker):
    import yfinance as yf

    t = yf.Ticker(ticker)
    out = {"ticker": ticker, "fields": {}, "errors": []}

    for label, attr in (("income", "quarterly_financials"),
                        ("balance", "quarterly_balance_sheet"),
                        ("cashflow", "quarterly_cashflow")):
        try:
            df = getattr(t, attr)
            if df is None or df.empty:
                out["errors"].append(f"{label}: empty")
                continue
            cols = sorted(pd.to_datetime(df.columns))
            out[f"{label}_quarters"] = len(cols)
            out[f"{label}_from"] = cols[0].date()
            out[f"{label}_to"] = cols[-1].date()
            for want, aliases in WANTED.items():
                found = find_field(df.index, aliases)
                if found and want not in out["fields"]:
                    out["fields"][want] = f"{label}:{found}"
        except Exception as e:
            out["errors"].append(f"{label}: {type(e).__name__}: {e}")

    try:
        info = t.info or {}
        out["info_pe"] = info.get("trailingPE")
        out["info_pb"] = info.get("priceToBook")
        out["info_margin"] = info.get("profitMargins")
    except Exception as e:
        out["errors"].append(f"info: {type(e).__name__}")

    return out


def main():
    print("=" * 78)
    print("FUNDAMENTAL DATA PROBE")
    print("=" * 78)
    print("Checking what yfinance actually provides before anything is built.\n")

    results, field_counts = [], Counter()
    for i, ticker in enumerate(PROBE_TICKERS, 1):
        print(f"[{i:2d}/{len(PROBE_TICKERS)}] {ticker:6s}", end=" ", flush=True)
        try:
            r = probe(ticker)
        except Exception as e:
            print(f"FAILED — {type(e).__name__}: {e}")
            continue
        results.append(r)
        for f in r["fields"]:
            field_counts[f] += 1
        q = r.get("income_quarters", 0)
        span = (f"{r.get('income_from', '?')} to {r.get('income_to', '?')}"
                if q else "no income statement")
        print(f"{q:2d} quarters | {span} | {len(r['fields'])}/{len(WANTED)} fields")

    if not results:
        print("\nNothing retrieved. Fundamental strategies are not possible "
              "with this data source.")
        return 1

    print("\n" + "-" * 78)
    print("FIELD AVAILABILITY")
    print("-" * 78)
    n = len(results)
    for want in WANTED:
        c = field_counts.get(want, 0)
        mark = "OK  " if c == n else ("PART" if c else "MISS")
        print(f"  [{mark}] {want:20s} {c}/{n} tickers")

    quarters = [r.get("income_quarters", 0) for r in results]
    med_q = sorted(quarters)[len(quarters) // 2] if quarters else 0
    years = med_q / 4

    print("\n" + "-" * 78)
    print("HISTORY DEPTH — this is the binding constraint")
    print("-" * 78)
    print(f"  median quarters available : {med_q}  (~{years:.1f} years)")
    print(f"  range                     : {min(quarters)} to {max(quarters)}")
    print()
    if years < 3:
        print("  VERDICT: too short. With a reporting lag and a train/test split")
        print("  there is not enough here for an honest backtest. Any result")
        print("  would rest on a handful of rebalances.")
    elif years < 6:
        print("  VERDICT: workable but thin. Enough for a cross-sectional test")
        print("  with quarterly rebalancing, but NOT enough to also split")
        print("  train/test by time. Hold out TICKERS instead, as in")
        print("  experiment_combos.py.")
    else:
        print("  VERDICT: enough history for a proper test.")

    print("\n" + "-" * 78)
    print("LOOK-AHEAD WARNING")
    print("-" * 78)
    print("  Period end dates are available, so a reporting lag CAN be applied.")
    print("  It must be. `info` returns today's P/E, and using it to make a 2019")
    print("  decision manufactures a fake result. Any figure for a quarter ending")
    print("  Dec 31 should be treated as unknown until roughly March 31.")
    print()
    sample = results[0]
    print(f"  Example — today's snapshot for {sample['ticker']}:")
    print(f"    trailing P/E {sample.get('info_pe')}   "
          f"P/B {sample.get('info_pb')}   margin {sample.get('info_margin')}")
    print("    ^ these are TODAY only. Useful for a live screen, useless for")
    print("      a backtest.")

    errs = [(r["ticker"], e) for r in results for e in r["errors"]]
    if errs:
        print("\n" + "-" * 78)
        print(f"ISSUES ({len(errs)})")
        print("-" * 78)
        for t, e in errs[:12]:
            print(f"  {t:6s} {e}")

    print("\n" + "=" * 78)
    print("Paste this output back and the real experiment gets designed")
    print("against what actually exists.")
    print("=" * 78)
    return 0


if __name__ == "__main__":
    sys.exit(main())
