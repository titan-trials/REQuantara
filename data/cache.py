"""
Local price cache.

THE PROBLEM: a single paper trader run downloads the same unchanging history
over and over. auto_select() pulls 2 frames per ticker, live signal generation
pulls another - 15 downloads per run, ~3,900 a year, for 2015-2024 bars that
were fixed years ago. Every one of those is a chance to fail, and a failed
download inside a bare `except` is what produced AAPL's 15 one-day strategy
flips.

THE CATCH: yfinance history is NOT actually immutable. When a stock pays a
dividend or splits, Yahoo retroactively re-adjusts every prior bar. A naive
"download once, append forever" cache silently drifts away from reality.

THE APPROACH:
  - One file per ticker holding the widest range ever requested. Reads slice
    out whatever the caller asked for, so auto_select (2015-2024) and live
    signal generation (2015-today) share one file.
  - On refresh, re-fetch the last OVERLAP_DAYS and COMPARE them against what
    is cached. If they disagree, a re-adjustment happened and the whole file
    is rebuilt. Self-healing, no manual invalidation.
  - Any error at all falls back to a direct download. The cache is an
    optimisation and must never be a new failure mode.

Cache lives in data/cache/ and is gitignored - committing it would add a new
~850KB blob to the repo on every daily run. On GitHub Actions it is preserved
between runs by actions/cache; a miss just means one slow run.
"""

import json
import os
from datetime import datetime, timedelta

import pandas as pd

CACHE_DIR = os.path.join("data", "cache")
META_FILE = os.path.join(CACHE_DIR, "_meta.json")

# How many recent bars to re-fetch and verify on each refresh. Needs to be long
# enough to cover a weekend plus a holiday.
OVERLAP_DAYS = 7

# Relative price difference above which we assume a split/dividend
# re-adjustment rather than normal noise. Cached and freshly fetched closes for
# the same past date should otherwise be bit-identical.
REVISION_TOLERANCE = 0.001  # 0.1%

# Verify the cache against Yahoo at most once per ticker per day. Without this,
# a request whose range is ALREADY covered by the cache would never re-check -
# so a backtest-only run (2015-2024) would serve pre-split prices indefinitely.
# One verification per ticker per day catches revisions; everything after that
# is a pure cache hit.
MAX_UNVERIFIED_DAYS = 1

COLUMNS = ["Open", "Close", "High", "Low"]

_DISABLED = os.getenv("QUANTARA_NO_CACHE", "").lower() in ("1", "true", "yes")


def _download(ticker, start, end):
    """The only place that actually hits the network. Patched in tests."""
    import yfinance as yf

    df = yf.download(ticker, start=start, end=end, progress=False)
    if df is None or len(df) == 0:
        return pd.DataFrame(columns=COLUMNS)
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    keep = [c for c in COLUMNS if c in df.columns]
    df = df[keep]
    df.columns.name = None
    df.dropna(inplace=True)
    return df


# ---------------------------------------------------------------------------
# cache file plumbing
# ---------------------------------------------------------------------------

def _path(ticker):
    return os.path.join(CACHE_DIR, f"{ticker}.csv")


def _read_meta():
    if not os.path.exists(META_FILE):
        return {}
    try:
        with open(META_FILE, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def _write_meta(meta):
    os.makedirs(CACHE_DIR, exist_ok=True)
    with open(META_FILE, "w", encoding="utf-8") as f:
        json.dump(meta, f, indent=2, sort_keys=True)


def _read_cache(ticker):
    path = _path(ticker)
    if not os.path.exists(path):
        return None
    try:
        df = pd.read_csv(path, index_col=0, parse_dates=True)
        return df if len(df) else None
    except Exception as e:
        print(f"[cache] {ticker}: unreadable cache ({e}), will re-download")
        return None


def _write_cache(ticker, df, requested_start=None):
    os.makedirs(CACHE_DIR, exist_ok=True)
    df.to_csv(_path(ticker))
    meta = _read_meta()
    prev = meta.get(ticker, {})

    # Track the earliest start ever ASKED FOR, separately from the first bar
    # actually returned. They are usually different: START is 2015-01-01, which
    # is New Year's Day, so the first real bar is 2015-01-02. Comparing a
    # request against the first bar would mean `2015-01-01 < 2015-01-02` is
    # always true - so the cache would decide it needed earlier history on
    # every single call and re-download the entire series forever. That made
    # the cache a no-op for the main auto_select path.
    starts = [s for s in (prev.get("requested_start"), requested_start) if s]
    covered_from = min(starts) if starts else df.index[0].strftime("%Y-%m-%d")

    meta[ticker] = {
        "fetched_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "requested_start": covered_from,
        "first_date": df.index[0].strftime("%Y-%m-%d"),
        "last_date": df.index[-1].strftime("%Y-%m-%d"),
        "rows": len(df),
    }
    _write_meta(meta)


def _covered_from(ticker, cached):
    """Earliest date this cache can satisfy, as a Timestamp."""
    stamp = _read_meta().get(ticker, {}).get("requested_start")
    return pd.Timestamp(stamp) if stamp else cached.index[0]


def _slice(df, start, end):
    """Inclusive of `start`, EXCLUSIVE of `end` - matching yfinance."""
    out = df
    if start:
        out = out[out.index >= pd.Timestamp(start)]
    if end:
        out = out[out.index < pd.Timestamp(end)]
    return out.copy()


def _verified_recently(ticker):
    """Has this ticker been checked against Yahoo within MAX_UNVERIFIED_DAYS?"""
    stamp = _read_meta().get(ticker, {}).get("fetched_at")
    if not stamp:
        return False
    try:
        fetched = datetime.strptime(stamp, "%Y-%m-%d %H:%M:%S")
    except ValueError:
        return False
    return (datetime.now() - fetched) < timedelta(days=MAX_UNVERIFIED_DAYS)


def _revision_detected(cached, fresh):
    """True if overlapping dates disagree, i.e. Yahoo re-adjusted history."""
    common = cached.index.intersection(fresh.index)
    if len(common) == 0:
        return False
    a = cached.loc[common, "Close"].astype(float)
    b = fresh.loc[common, "Close"].astype(float)
    denom = b.abs().replace(0, pd.NA)
    return bool(((a - b).abs() / denom > REVISION_TOLERANCE).any())


# ---------------------------------------------------------------------------
# public API
# ---------------------------------------------------------------------------

def load_data_cached(ticker, start, end):
    """Drop-in replacement for the raw yfinance path in data/loader.py."""
    if _DISABLED:
        return _download(ticker, start, end)
    try:
        return _load_cached_strict(ticker, start, end)
    except Exception as e:
        print(f"[cache] {ticker}: falling back to direct download "
              f"({type(e).__name__}: {e})")
        return _download(ticker, start, end)


def _load_cached_strict(ticker, start, end):
    cached = _read_cache(ticker)
    today = pd.Timestamp(datetime.now().date())

    # --- nothing cached, or cached history does not reach far enough back ---
    if cached is None or pd.Timestamp(start) < _covered_from(ticker, cached):
        reason = "no cache" if cached is None else "need earlier history"
        print(f"[cache] {ticker}: full download ({reason})")
        fresh = _download(ticker, start, _far_end(end))
        if len(fresh):
            _write_cache(ticker, fresh, requested_start=str(start))
        return _slice(fresh, start, end)

    wanted_end = min(pd.Timestamp(end), today) if end else today

    # --- cache covers the request AND was verified recently ---
    # Both conditions matter. Range coverage alone is not enough: Yahoo
    # retroactively re-adjusts history on splits and dividends, so a cache that
    # spans the requested dates can still be wrong. Re-verifying once a day
    # catches that without re-downloading on every call.
    covered = cached.index[-1] >= wanted_end - pd.Timedelta(days=1)
    if covered and _verified_recently(ticker):
        return _slice(cached, start, end)

    # --- incremental tail refresh, with overlap verification ---
    tail_start = (cached.index[-1] - pd.Timedelta(days=OVERLAP_DAYS)).strftime("%Y-%m-%d")
    fresh = _download(ticker, tail_start, _far_end(end))

    if len(fresh) == 0:
        # Nothing new (weekend, holiday, or Yahoo hiccup). Serve what we have.
        return _slice(cached, start, end)

    if _revision_detected(cached, fresh):
        print(f"[cache] {ticker}: prices revised (split/dividend) — rebuilding")
        rebuilt = _download(ticker, _covered_from(ticker, cached).strftime("%Y-%m-%d"),
                            _far_end(end))
        if len(rebuilt):
            _write_cache(ticker, rebuilt, requested_start=str(start))
            return _slice(rebuilt, start, end)
        return _slice(cached, start, end)

    merged = pd.concat([cached[~cached.index.isin(fresh.index)], fresh]).sort_index()
    added = len(merged) - len(cached)
    _write_cache(ticker, merged, requested_start=str(start))
    if added:
        print(f"[cache] {ticker}: +{added} new bar(s), {len(merged)} total")
    return _slice(merged, start, end)


def _far_end(end):
    """Always fetch through tomorrow so today's bar is never cut off.

    yfinance treats `end` as exclusive, so passing today can silently drop
    today - the bar live signals are computed from.
    """
    tomorrow = (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d")
    if end is None:
        return tomorrow
    return max(str(end), tomorrow)


def cache_status():
    """Structured cache state, for check_health.py and the dashboard."""
    meta = _read_meta()
    out = []
    for ticker, m in sorted(meta.items()):
        path = _path(ticker)
        out.append({
            "ticker": ticker,
            "rows": m.get("rows", 0),
            "first_date": m.get("first_date", ""),
            "last_date": m.get("last_date", ""),
            "fetched_at": m.get("fetched_at", ""),
            "size_kb": round(os.path.getsize(path) / 1024, 1)
            if os.path.exists(path) else 0,
        })
    return out


def clear_cache(ticker=None):
    """Delete cached data. `ticker=None` clears everything."""
    if not os.path.isdir(CACHE_DIR):
        return 0
    meta = _read_meta()
    targets = [ticker] if ticker else list(meta.keys())
    removed = 0
    for t in targets:
        if os.path.exists(_path(t)):
            os.remove(_path(t))
            removed += 1
        meta.pop(t, None)
    _write_meta(meta)
    return removed


if __name__ == "__main__":
    rows = cache_status()
    if not rows:
        print("Cache is empty.")
    else:
        print(f"{'Ticker':8s} {'Rows':>6s}  {'From':10s} {'To':10s} "
              f"{'Size':>8s}  Fetched")
        for r in rows:
            print(f"{r['ticker']:8s} {r['rows']:>6d}  {r['first_date']:10s} "
                  f"{r['last_date']:10s} {r['size_kb']:>6.1f}KB  {r['fetched_at']}")
