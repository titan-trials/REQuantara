"""
Risk-free rate, for Sharpe.

WHY THIS MATTERS HERE SPECIFICALLY: Sharpe is
`(mean - rf) / std * sqrt(252)`, and this project has always used rf = 0. That
inflates every strategy's Sharpe by roughly `rf / annual_volatility` - and
Sharpe carries the largest weight in `compute_composite_score` (x0.5). So the
omission was not just flattering the numbers, it was influencing WHICH STRATEGY
GETS SELECTED.

The effect is NOT uniform. Because the reduction scales as rf/vol, low-volatility
strategies lose more Sharpe than high-volatility ones. Expect selection to drift
toward more volatile strategies once this is applied. That is the correct
behaviour - Sharpe is meant to reward return earned ABOVE what cash pays - but
it will visibly move results, so it is worth knowing in advance.

A CONSTANT WOULD BE WRONG for this project's window. Over 2015-2024 the
short-term rate went from roughly 0% to roughly 5%. Pricing 2015-2021 at 4%
would penalise it for cash yields that did not exist; pricing 2023-2024 at 0%
would flatter it. So the real series is used.

^IRX is the CBOE 13-week US Treasury Bill yield, quoted as an annualised
percentage (5.25 means 5.25%). It is free on yfinance and flows through the
project's own price cache, so it costs one extra cached series and no extra
downloads after the first per day.
"""

import pandas as pd

TRADING_DAYS = 252
RISK_FREE_TICKER = "^IRX"

# Used when ^IRX cannot be fetched. Not a great answer for any particular year,
# but far better than silently pretending cash pays nothing.
try:
    from config import RISK_FREE_RATE_FALLBACK
except ImportError:
    RISK_FREE_RATE_FALLBACK = 0.04

_warned = False


def _fetch_annual_rate(start, end):
    """Annualised risk-free rate as a Series, or None if unavailable."""
    from data.loader import load_data

    df = load_data(RISK_FREE_TICKER, start, end)
    if df is None or len(df) == 0 or "Close" not in df.columns:
        return None
    # ^IRX quotes percent, not a fraction.
    annual = df["Close"].squeeze().astype(float) / 100.0
    return annual if len(annual) else None


def get_daily_risk_free(index, fallback=None):
    """Daily risk-free rate aligned to `index`.

    Returns a Series the same length as `index`. Never raises - a missing rate
    must not be able to break a backtest.
    """
    global _warned
    fallback = RISK_FREE_RATE_FALLBACK if fallback is None else fallback

    if index is None or len(index) == 0:
        return pd.Series(dtype=float)

    annual = None
    if isinstance(index, pd.DatetimeIndex):
        try:
            pad_start = (index[0] - pd.Timedelta(days=10)).strftime("%Y-%m-%d")
            pad_end = (index[-1] + pd.Timedelta(days=2)).strftime("%Y-%m-%d")
            fetched = _fetch_annual_rate(pad_start, pad_end)
            if fetched is not None:
                # ffill covers market holidays where ^IRX has no print;
                # bfill covers the leading edge before the first quote.
                annual = fetched.reindex(index.union(fetched.index)).ffill()
                annual = annual.reindex(index).ffill().bfill()
                if annual.isna().all():
                    annual = None
        except Exception as e:
            if not _warned:
                print(f"[risk_free] {RISK_FREE_TICKER} unavailable "
                      f"({type(e).__name__}: {e}) — falling back to "
                      f"{fallback:.2%} constant")
                _warned = True
            annual = None

    if annual is None:
        annual = pd.Series(float(fallback), index=index)

    # Geometric, not annual/252. Compounding matters over a decade, and this
    # keeps the daily rate consistent with the sqrt(252) annualisation used
    # on the other side of the ratio.
    return (1.0 + annual) ** (1.0 / TRADING_DAYS) - 1.0


def resolve_daily_risk_free(index, risk_free):
    """Normalise whatever a caller passed into a daily Series aligned to `index`.

    Accepts:
        None    -> fetch ^IRX, falling back to the configured constant
        0       -> genuinely zero, for tests and for reproducing old figures
        float   -> a constant ANNUAL rate
        Series  -> a daily rate, reindexed onto `index`
    """
    if risk_free is None:
        return get_daily_risk_free(index)
    if isinstance(risk_free, pd.Series):
        return risk_free.reindex(index).ffill().bfill().fillna(0.0)
    rate = float(risk_free)
    if rate == 0.0:
        return pd.Series(0.0, index=index)
    return pd.Series((1.0 + rate) ** (1.0 / TRADING_DAYS) - 1.0, index=index)
