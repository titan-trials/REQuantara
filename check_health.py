"""
Quantara health check.

One command that answers "is everything okay" without needing to know where to
look. Reads only the CSVs in results/ - no network, no Alpaca, no market data,
so it is always safe to run.

    python check_health.py

DESIGN NOTE: every check returns a structured dict rather than printing, and
`run_health_checks()` returns the full list. That is deliberate - the Streamlit
dashboard can import and render these directly:

    from check_health import run_health_checks
    for c in run_health_checks():
        st.metric(c["name"], c["status"], c["detail"])

`main()` is only a CLI renderer over the same data.

Statuses:
    PASS     verified good
    WARN     worth a look, not broken
    FAIL     something is wrong
    PENDING  not enough data yet to judge
    INFO     context, no judgement
"""

import csv
import json
import os
import sys
from collections import defaultdict
from datetime import datetime, timedelta

RESULTS = "results"
SIGNAL_LOG = os.path.join(RESULTS, "paper_trading_log.csv")
EQUITY_LOG = os.path.join(RESULTS, "equity_log.csv")
POSITIONS_LOG = os.path.join(RESULTS, "positions_log.csv")
FILLS_LOG = os.path.join(RESULTS, "fills.csv")
ASSIGNMENTS = os.path.join(RESULTS, "strategy_assignments.json")

LEVERAGE_WARN = 1.05          # matches account_log.py's warning threshold
POSITION_TOLERANCE = 1.25     # flag a position >25% above its target weight
STALE_RUN_DAYS = 3            # no run in this many days is suspicious

# Date the wall-clock-timestamp bug was fixed (V14). Rows before this can
# legitimately carry a weekend date, because they were stamped with
# datetime.now() and any run past UTC midnight rolled onto the next day.
# Those are history. A weekend row dated AFTER this is a real regression.
WALL_CLOCK_FIX_DATE = "2026-08-14"


def _read(path):
    if not os.path.exists(path):
        return None
    try:
        with open(path, newline="", encoding="utf-8") as f:
            return list(csv.DictReader(f))
    except Exception:
        return None


def _f(value, default=0.0):
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _result(name, status, detail, data=None):
    return {"name": name, "status": status, "detail": detail, "data": data or {}}


# ---------------------------------------------------------------------------
# checks
# ---------------------------------------------------------------------------

def check_files_present():
    expected = {
        "paper_trading_log.csv": SIGNAL_LOG,
        "equity_log.csv": EQUITY_LOG,
        "positions_log.csv": POSITIONS_LOG,
        "fills.csv": FILLS_LOG,
        "strategy_assignments.json": ASSIGNMENTS,
    }
    missing = [n for n, p in expected.items() if not os.path.exists(p)]
    if not missing:
        return _result("Log files", "PASS", "all 5 present")
    # The three account files only appear after a paper trader run.
    account_files = {"equity_log.csv", "positions_log.csv", "fills.csv"}
    if set(missing) <= account_files:
        return _result("Log files", "PENDING",
                       f"missing {', '.join(missing)} - written on the first "
                       f"paper trader run", {"missing": missing})
    return _result("Log files", "FAIL", f"missing {', '.join(missing)}",
                   {"missing": missing})


def check_leverage():
    rows = _read(EQUITY_LOG)
    if not rows:
        return _result("Leverage", "PENDING", "no equity_log.csv yet")

    latest = rows[-1]
    lev = _f(latest.get("Leverage"))
    debt = _f(latest.get("MarginDebt"))
    equity = _f(latest.get("Equity"))
    data = {"leverage": lev, "margin_debt": debt, "equity": equity,
            "date": latest.get("Date", "")}

    if lev > LEVERAGE_WARN:
        return _result("Leverage", "FAIL",
                       f"{lev:.2f}x - ${debt:,.0f} borrowed against "
                       f"${equity:,.0f} equity", data)
    return _result("Leverage", "PASS",
                   f"{lev:.2f}x, no margin debt (threshold {LEVERAGE_WARN}x)", data)


def check_position_sizing():
    """Position weights vs the live target. Catches un-rebalanced legacy sizes."""
    rows = _read(POSITIONS_LOG)
    if not rows:
        return _result("Position sizing", "PENDING", "no positions_log.csv yet")

    try:
        from config import LIVE_POSITION_SIZE, TICKERS
        target_pct = LIVE_POSITION_SIZE * 100
        n_tickers = len(TICKERS)
    except Exception:
        target_pct, n_tickers = 20.0, 5

    latest_ts = rows[-1]["Timestamp"]
    current = [r for r in rows if r["Timestamp"] == latest_ts]

    over = [(r["Ticker"], _f(r.get("PctOfEquity")))
            for r in current
            if _f(r.get("PctOfEquity")) > target_pct * POSITION_TOLERANCE]

    # What total exposure would look like if every ticker were this size.
    worst = max((_f(r.get("PctOfEquity")) for r in current), default=0.0)
    implied = worst * n_tickers / 100

    data = {"target_pct": target_pct,
            "positions": {r["Ticker"]: _f(r.get("PctOfEquity")) for r in current},
            "implied_full_exposure": implied}

    if over:
        listed = ", ".join(f"{t} {p:.0f}%" for t, p in over)
        return _result("Position sizing", "FAIL",
                       f"{listed} vs {target_pct:.0f}% target - legacy sizes, "
                       f"no rebalancing logic ({implied:.1f}x if all "
                       f"{n_tickers} were this size)", data)
    return _result("Position sizing", "PASS",
                   f"all within tolerance of the {target_pct:.0f}% target", data)


def check_assignment_consistency():
    """strategy_assignments.json should match the strategies actually traded."""
    log = _read(SIGNAL_LOG)
    if not log or not os.path.exists(ASSIGNMENTS):
        return _result("Strategy assignments", "PENDING", "not enough data")

    try:
        assigns = json.load(open(ASSIGNMENTS))["assignments"]
    except Exception as e:
        return _result("Strategy assignments", "FAIL",
                       f"could not read {ASSIGNMENTS}: {e}")

    latest_ts = log[-1]["Timestamp"]
    latest = {r["Ticker"]: r["Strategy"] for r in log if r["Timestamp"] == latest_ts}

    mismatched = [t for t, v in assigns.items()
                  if latest.get(t) != v.get("Best_Strategy")]
    data = {"expected": {t: v.get("Best_Strategy") for t, v in assigns.items()},
            "actual": latest}

    if mismatched:
        return _result("Strategy assignments", "WARN",
                       f"{', '.join(mismatched)} differ from the saved "
                       f"assignment - expected right after a fallback run", data)
    return _result("Strategy assignments", "PASS",
                   f"all {len(assigns)} match what was traded", data)


def check_strategy_churn(recent_days=21):
    """One-day strategy flips are the churn signature the V13 fix targeted.

    A flip that lasts exactly one day and reverts cannot come from a genuine
    change in a fixed-window, fixed-seed backtest. It means a candidate
    silently vanished from the field - the bare-except bug.
    """
    log = _read(SIGNAL_LOG)
    if not log:
        return _result("Strategy churn", "PENDING", "no signal log")

    per = defaultdict(list)
    for r in log:
        per[r["Ticker"]].append((r.get("Timestamp", ""), r.get("Strategy", "")))

    cutoff = (datetime.now() - timedelta(days=recent_days)).strftime("%Y-%m-%d")

    total_flips, recent_flips, detail = 0, 0, {}
    for ticker, seq in per.items():
        flips = [seq[i][0] for i in range(1, len(seq) - 1)
                 if seq[i][1] != seq[i - 1][1] and seq[i + 1][1] == seq[i - 1][1]]
        total_flips += len(flips)
        rec = [t for t in flips if t >= cutoff]
        recent_flips += len(rec)
        if flips:
            detail[ticker] = {"all_time": len(flips), "recent": len(rec)}

    data = {"one_day_flips_all_time": total_flips,
            "one_day_flips_recent": recent_flips,
            "window_days": recent_days, "per_ticker": detail}

    if recent_flips:
        return _result("Strategy churn", "FAIL",
                       f"{recent_flips} one-day flip(s) in the last "
                       f"{recent_days} days - the V13 fix is not holding", data)
    return _result("Strategy churn", "PASS",
                   f"0 one-day flips in the last {recent_days} days "
                   f"({total_flips} historically, pre-fix)", data)


def check_run_freshness():
    log = _read(SIGNAL_LOG)
    if not log:
        return _result("Run freshness", "PENDING", "no signal log")

    last = log[-1].get("Timestamp", "")[:10]
    try:
        age = (datetime.now() - datetime.strptime(last, "%Y-%m-%d")).days
    except ValueError:
        return _result("Run freshness", "WARN", f"unparseable timestamp {last!r}")

    data = {"last_run_date": last, "age_days": age}
    if age > STALE_RUN_DAYS:
        return _result("Run freshness", "FAIL",
                       f"last run {last} ({age} days ago) - check the Actions "
                       f"tab; scheduled workflows auto-disable after 60 days "
                       f"of repo inactivity", data)
    return _result("Run freshness", "PASS", f"last run {last} ({age}d ago)", data)


def check_missed_days():
    """Weekdays with no logged run. Approximate - does not know market holidays."""
    log = _read(SIGNAL_LOG)
    if not log:
        return _result("Missed runs", "PENDING", "no signal log")

    dates = sorted({r.get("Timestamp", "")[:10] for r in log if r.get("Timestamp")})
    try:
        start = datetime.strptime(dates[0], "%Y-%m-%d")
        end = datetime.strptime(dates[-1], "%Y-%m-%d")
    except ValueError:
        return _result("Missed runs", "WARN", "unparseable dates in log")

    # A weekend-dated row is a pre-fix run that actually covered the preceding
    # Friday (stamped after UTC midnight). Roll it back so it does not show up
    # as BOTH a phantom weekend day and a phantom missing weekday - which is
    # exactly what happened to 2026-05-01 / 2026-05-02.
    have = set()
    rolled = []
    for d in dates:
        try:
            dt = datetime.strptime(d, "%Y-%m-%d")
        except ValueError:
            continue
        if dt.weekday() >= 5:
            back = dt - timedelta(days=dt.weekday() - 4)
            have.add(back.strftime("%Y-%m-%d"))
            rolled.append(f"{d}->{back:%Y-%m-%d}")
        else:
            have.add(d)

    missing, day = [], start
    while day <= end:
        if day.weekday() < 5 and day.strftime("%Y-%m-%d") not in have:
            missing.append(day.strftime("%Y-%m-%d"))
        day += timedelta(days=1)

    data = {"missing": missing, "count": len(missing), "rolled_back": rolled}
    note = f" ({len(rolled)} weekend-dated run(s) rolled back to Friday)" if rolled else ""

    if len(missing) > 3:
        return _result("Missed runs", "WARN",
                       f"{len(missing)} weekdays with no run{note} - some are "
                       f"market holidays: {', '.join(missing[-5:])}", data)
    if missing:
        return _result("Missed runs", "INFO",
                       f"{len(missing)} weekday(s) with no run{note}: "
                       f"{', '.join(missing)} - check against market holidays", data)
    return _result("Missed runs", "PASS", f"no gaps in weekday coverage{note}", data)


def check_weekend_dates():
    """Regression guard for the V14 wall-clock-date bug.

    Logs were stamped with datetime.now(), so a run late enough to cross UTC
    midnight recorded Friday's prices on Saturday.
    """
    historical, regressions = set(), set()
    for label, path in (("signals", SIGNAL_LOG), ("equity", EQUITY_LOG),
                        ("positions", POSITIONS_LOG)):
        for r in _read(path) or []:
            stamp = (r.get("Timestamp") or "")[:10]
            try:
                if datetime.strptime(stamp, "%Y-%m-%d").weekday() >= 5:
                    (regressions if stamp >= WALL_CLOCK_FIX_DATE
                     else historical).add(f"{label}:{stamp}")
            except ValueError:
                continue

    data = {"historical": sorted(historical), "regressions": sorted(regressions),
            "fix_date": WALL_CLOCK_FIX_DATE}

    if regressions:
        return _result("Weekend-dated rows", "FAIL",
                       f"{len(regressions)} row(s) dated on a weekend AFTER the "
                       f"{WALL_CLOCK_FIX_DATE} fix - regression: "
                       f"{', '.join(sorted(regressions)[:4])}", data)
    if historical:
        return _result("Weekend-dated rows", "INFO",
                       f"{len(historical)} pre-fix row group(s) on a weekend "
                       f"({', '.join(sorted(historical)[:3])}) - known history "
                       f"from the wall-clock bug, not a regression", data)
    return _result("Weekend-dated rows", "PASS", "no weekend-dated rows")


def check_slippage():
    """Signal price vs actual fill price. Informational - this is real money."""
    fills = _read(FILLS_LOG)
    log = _read(SIGNAL_LOG)
    if not fills or not log:
        return _result("Slippage", "PENDING", "need both fills.csv and the signal log")

    # Most recent signalled price per ticker, to compare against its fill.
    signalled = {}
    for r in log:
        if r.get("Exit_Reason"):
            signalled.setdefault(r["Ticker"], []).append(
                (r.get("Timestamp", ""), _f(r.get("Price"))))

    diffs, detail = [], []
    for f in fills:
        tk = f.get("Ticker")
        fill_price = _f(f.get("FilledAvgPrice"))
        hist = signalled.get(tk)
        if not hist or fill_price <= 0:
            continue
        # Compare against the most recent signal at or before the fill date.
        fill_day = (f.get("FilledAt") or "")[:10]
        prior = [p for ts, p in hist if ts[:10] <= fill_day and p > 0]
        if not prior:
            continue
        sig = prior[-1]
        pct = (fill_price - sig) / sig * 100
        diffs.append(pct)
        detail.append({"ticker": tk, "side": f.get("Side"),
                       "signalled": sig, "filled": fill_price, "pct": round(pct, 3)})

    if not diffs:
        return _result("Slippage", "PENDING", "no matched signal/fill pairs yet")

    avg = sum(diffs) / len(diffs)
    return _result("Slippage", "INFO",
                   f"{len(diffs)} matched fill(s), mean {avg:+.2f}% vs signal price",
                   {"mean_pct": round(avg, 3), "fills": detail})


CHECKS = [
    check_files_present,
    check_run_freshness,
    check_leverage,
    check_position_sizing,
    check_assignment_consistency,
    check_strategy_churn,
    check_missed_days,
    check_weekend_dates,
    check_slippage,
]


def run_health_checks():
    """Run everything. Never raises - a broken check reports itself as FAIL."""
    out = []
    for fn in CHECKS:
        try:
            out.append(fn())
        except Exception as e:
            out.append(_result(fn.__name__, "FAIL",
                               f"check itself errored: {type(e).__name__}: {e}"))
    return out


ICONS = {"PASS": "[ OK ]", "WARN": "[WARN]", "FAIL": "[FAIL]",
         "PENDING": "[ .. ]", "INFO": "[INFO]"}


def main():
    results = run_health_checks()
    width = max(len(r["name"]) for r in results)

    print("=" * 72)
    print(f"QUANTARA HEALTH CHECK - {datetime.now():%Y-%m-%d %H:%M}")
    print("=" * 72)
    for r in results:
        print(f"{ICONS.get(r['status'], '[????]')}  {r['name']:<{width}}  {r['detail']}")

    counts = defaultdict(int)
    for r in results:
        counts[r["status"]] += 1
    print("-" * 72)
    print("  ".join(f"{k}: {v}" for k, v in sorted(counts.items()) if v))
    print("=" * 72)

    return 1 if counts["FAIL"] else 0


if __name__ == "__main__":
    sys.exit(main())
