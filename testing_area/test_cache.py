"""
Network-free tests for data/cache.py.

`_download` is patched throughout, so nothing here touches Yahoo. The point is
to prove the cache is a pure optimisation: same data out, fewer downloads, and
a fallback path that cannot turn a cache problem into a pipeline failure.

    python test_cache.py
"""

import os
import shutil
import sys
import tempfile

import pandas as pd

import data.cache as C

PASS, FAIL = 0, 0
CALLS = []


def check(name, got, want):
    global PASS, FAIL
    if got == want:
        PASS += 1
        print(f"  PASS  {name}")
    else:
        FAIL += 1
        print(f"  FAIL  {name}\n          got  {got!r}\n          want {want!r}")


def make_bars(start, periods, base=100.0, step=1.0):
    idx = pd.bdate_range(start, periods=periods)
    close = [base + i * step for i in range(periods)]
    return pd.DataFrame(
        {"Close": close,
         "High": [c * 1.01 for c in close],
         "Low": [c * 0.99 for c in close]},
        index=idx,
    )


FULL = make_bars("2026-01-01", 60)


def fake_download(ticker, start, end):
    CALLS.append((ticker, str(start), str(end)))
    df = FULL
    if start:
        df = df[df.index >= pd.Timestamp(start)]
    if end:
        df = df[df.index < pd.Timestamp(end)]
    return df.copy()


workdir = tempfile.mkdtemp()
os.chdir(workdir)
C._download = fake_download

# ---------------------------------------------------------------------------
print("\n[1] First call downloads and writes a cache file")
CALLS.clear()
df1 = C.load_data_cached("NVDA", "2026-01-01", "2026-03-01")
check("one download", len(CALLS), 1)
check("cache file written", os.path.exists(C._path("NVDA")), True)
check("rows returned", len(df1), len(FULL[FULL.index < pd.Timestamp("2026-03-01")]))

# ---------------------------------------------------------------------------
print("\n[2] Second identical call serves from cache — zero downloads")
CALLS.clear()
df2 = C.load_data_cached("NVDA", "2026-01-01", "2026-03-01")
check("no downloads", len(CALLS), 0)
check("same index", df1.index.equals(df2.index), True)
# Not .equals() - a CSV round-trip loses a few ULPs of float precision. What
# matters is that no price is materially different.
worst = float((df1 - df2).abs().max().max())
check("prices match to well within a cent", worst < 1e-6, True)
print(f"        (worst round-trip difference: {worst:.2e})")

# ---------------------------------------------------------------------------
print("\n[3] A NARROWER range is sliced from the same cache — no download")
CALLS.clear()
narrow = C.load_data_cached("NVDA", "2026-02-01", "2026-02-15")
check("no downloads", len(CALLS), 0)
check("respects start", narrow.index[0] >= pd.Timestamp("2026-02-01"), True)
check("end is exclusive", narrow.index[-1] < pd.Timestamp("2026-02-15"), True)

# ---------------------------------------------------------------------------
print("\n[4] This is the real win: auto_select + live share one cache file")
# auto_select asks for 2015-2024, live asks for 2015-today. Under the old code
# that was 3 separate downloads per ticker per run.
CALLS.clear()
C.load_data_cached("NVDA", "2026-01-01", "2026-02-01")
C.load_data_cached("NVDA", "2026-01-01", "2026-03-01")
C.load_data_cached("NVDA", "2026-01-15", "2026-02-20")
check("three requests, zero downloads", len(CALLS), 0)

# ---------------------------------------------------------------------------
print("\n[5] Needing EARLIER history than cached triggers a full re-download")
CALLS.clear()
C.load_data_cached("NVDA", "2025-06-01", "2026-03-01")
check("re-downloaded", len(CALLS), 1)

# ---------------------------------------------------------------------------
print("\n[6] REGRESSION: a split/dividend revision rebuilds the cache")
# Yahoo retroactively re-adjusts history on dividends and splits. A naive
# append-only cache would drift permanently out of sync.
C.clear_cache()
CALLS.clear()
C.load_data_cached("AAPL", "2026-01-01", "2026-02-01")
cached_before = C._read_cache("AAPL")["Close"].iloc[0]

FULL_ADJUSTED = FULL.copy()
FULL_ADJUSTED[["Close", "High", "Low"]] *= 0.5  # 2:1 split re-adjustment
_orig = FULL


def adjusted_download(ticker, start, end):
    CALLS.append((ticker, str(start), str(end)))
    df = FULL_ADJUSTED
    if start:
        df = df[df.index >= pd.Timestamp(start)]
    if end:
        df = df[df.index < pd.Timestamp(end)]
    return df.copy()


C._download = adjusted_download
CALLS.clear()

# Force the once-a-day verification to be due. Without this the cache would
# consider itself fresh and skip the check - which is exactly the gap this
# behaviour was added to close.
_meta = C._read_meta()
_meta["AAPL"]["fetched_at"] = "2020-01-01 00:00:00"
C._write_meta(_meta)

after = C.load_data_cached("AAPL", "2026-01-01", "2026-03-20")
cached_after = C._read_cache("AAPL")["Close"].iloc[0]

check("revision detected and cache rebuilt",
      round(cached_after, 4), round(cached_before * 0.5, 4))
check("returned data reflects the adjustment",
      round(after["Close"].iloc[0], 4), round(cached_before * 0.5, 4))

C._download = fake_download

# ---------------------------------------------------------------------------
print("\n[7] Incremental tail refresh appends without a full re-download")
C.clear_cache()
FULL = make_bars("2026-01-01", 40)
C.load_data_cached("IBM", "2026-01-01", "2026-02-20")
rows_before = len(C._read_cache("IBM"))

FULL = make_bars("2026-01-01", 60)   # 20 new bars appear
CALLS.clear()
C.load_data_cached("IBM", "2026-01-01", "2026-03-20")
rows_after = len(C._read_cache("IBM"))

check("new bars appended", rows_after > rows_before, True)
check("only the tail was fetched, not 2015-onward",
      CALLS[0][1] >= "2026-02", True)

# ---------------------------------------------------------------------------
print("\n[8] A broken cache falls back to a direct download, never raises")


def boom_read(ticker):
    raise IOError("simulated corrupt cache")


_orig_read = C._read_cache
C._read_cache = boom_read
try:
    out = C.load_data_cached("NVDA", "2026-01-01", "2026-02-01")
    check("returned data anyway", len(out) > 0, True)
except Exception as e:
    check("returned data anyway", f"raised {type(e).__name__}", True)
C._read_cache = _orig_read

# ---------------------------------------------------------------------------
print("\n[9] QUANTARA_NO_CACHE bypasses everything")
C._DISABLED = True
CALLS.clear()
C.load_data_cached("NVDA", "2026-01-01", "2026-02-01")
check("went straight to download", len(CALLS), 1)
C._DISABLED = False

# ---------------------------------------------------------------------------
print("\n[10] A stale cache is re-verified even when the range is covered")
# The gap this closes: range coverage alone is not enough, because Yahoo can
# rewrite history under a cache that spans the right dates.
C.clear_cache()
FULL = make_bars("2026-01-01", 60)
C._download = fake_download
C.load_data_cached("JPM", "2026-01-01", "2026-02-01")

CALLS.clear()
C.load_data_cached("JPM", "2026-01-01", "2026-02-01")
check("fresh cache is not re-verified", len(CALLS), 0)

meta = C._read_meta()
meta["JPM"]["fetched_at"] = "2020-01-01 00:00:00"
C._write_meta(meta)
CALLS.clear()
C.load_data_cached("JPM", "2026-01-01", "2026-02-01")
check("stale cache IS re-verified", len(CALLS) >= 1, True)

# ---------------------------------------------------------------------------
print("\n[11] REGRESSION: a start on a non-trading day still counts as covered")
# The real bug this caused: config START is 2015-01-01, which is New Year's Day.
# The first actual bar is 2015-01-02. Comparing the request against the first
# BAR meant `2015-01-01 < 2015-01-02` was always true, so every single call
# decided it needed earlier history and re-downloaded the whole series. The
# cache was a complete no-op for the auto_select path.
C.clear_cache()
FULL = make_bars("2026-01-02", 40)      # first bar is the 2nd, not the 1st
C._download = fake_download

C.load_data_cached("META", "2026-01-01", "2026-02-01")   # ask from the 1st
CALLS.clear()
C.load_data_cached("META", "2026-01-01", "2026-02-01")   # ask again
check("second identical request does NOT re-download", len(CALLS), 0)

CALLS.clear()
C.load_data_cached("META", "2026-01-01", "2026-01-20")
check("narrower request also served from cache", len(CALLS), 0)

# Genuinely needing earlier data must still trigger a re-download.
CALLS.clear()
C.load_data_cached("META", "2025-01-01", "2026-02-01")
check("a genuinely earlier start DOES re-download", len(CALLS) >= 1, True)

# ---------------------------------------------------------------------------
print("\n[12] cache_status reports usable metadata")
status = C.cache_status()
check("reports at least one ticker", len(status) > 0, True)
check("has the fields the dashboard needs",
      all(k in status[0] for k in
          ("ticker", "rows", "first_date", "last_date", "fetched_at")), True)

os.chdir("/")
shutil.rmtree(workdir, ignore_errors=True)

print(f"\n{'=' * 50}\n{PASS} passed, {FAIL} failed\n{'=' * 50}")
sys.exit(1 if FAIL else 0)
