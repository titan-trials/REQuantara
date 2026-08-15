import pandas as pd

from data.cache import load_data_cached


def load_data(ticker, start, end):
    """Daily Close/High/Low bars for `ticker` over [start, end).

    Now served through data/cache.py. The signature and return shape are
    unchanged, so every existing caller benefits without modification - which
    matters, because a single paper trader run used to make ~15 separate
    yfinance calls for largely identical data.

    Set QUANTARA_NO_CACHE=1 to bypass the cache entirely.
    """
    df = load_data_cached(ticker, start, end)

    # Defensive: keep the exact contract callers already rely on. squeeze() is
    # used throughout the project because of pandas column-shape strictness, so
    # the column layout here must stay stable.
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    keep = [c for c in ["Open", "Close", "High", "Low"] if c in df.columns]
    df = df[keep]
    df.columns.name = None
    df = df.dropna()
    return df
