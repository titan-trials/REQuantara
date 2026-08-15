"""
Account measurement layer.

Everything else in this project RECONSTRUCTS account state by replaying signal
rows against yfinance closes. That reconstruction is why the ~1.91x leverage
went unnoticed for three months, why a rejected order became a phantom position,
and why `reconcile_open_segments()` had to exist at all. yfinance closes are not
what Alpaca filled at, and a signal log is not a record of what happened to the
money.

This module measures instead. It appends three CSVs per run, straight from the
Alpaca API:

  results/equity_log.csv     one row per run  - account-level truth
  results/positions_log.csv  one row per open position per run
  results/fills.csv          one row per actual execution, deduped by order id

DESIGN RULE: nothing in here may ever break a trading run. Every public entry
point swallows its own exceptions and returns a status string. Losing a day of
measurement is an inconvenience; failing to place or exit a trade is not.
"""

import csv
import os
from datetime import datetime, timedelta

RESULTS_DIR = "results"
EQUITY_LOG = os.path.join(RESULTS_DIR, "equity_log.csv")
POSITIONS_LOG = os.path.join(RESULTS_DIR, "positions_log.csv")
FILLS_LOG = os.path.join(RESULTS_DIR, "fills.csv")

EQUITY_FIELDS = [
    "Timestamp", "Date", "Equity", "LastEquity", "DailyPnL", "DailyPnLPct",
    "Cash", "BuyingPower", "LongMarketValue", "ShortMarketValue",
    "PositionCount", "GrossExposure", "Leverage", "MarginDebt",
]

POSITION_FIELDS = [
    "Timestamp", "Date", "Ticker", "Qty", "AvgEntryPrice", "CurrentPrice",
    "MarketValue", "CostBasis", "UnrealizedPL", "UnrealizedPLPct",
    "PctOfEquity",
]

FILL_FIELDS = [
    "OrderId", "Ticker", "Side", "SubmittedAt", "FilledAt", "Status",
    "Qty", "FilledQty", "FilledAvgPrice", "Notional", "OrderType",
]


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

def _f(value, default=0.0):
    """Alpaca returns numerics as strings, and Nones for unset fields."""
    if value is None:
        return default
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _s(value):
    """Enum-ish values stringify as 'OrderSide.BUY'; keep only the tail."""
    if value is None:
        return ""
    return str(value).split(".")[-1].lower()


def _append_row(path, fieldnames, row):
    os.makedirs(RESULTS_DIR, exist_ok=True)
    is_new = not os.path.exists(path) or os.path.getsize(path) == 0
    with open(path, "a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        if is_new:
            writer.writeheader()
        writer.writerow(row)


def _existing_order_ids():
    """Order ids already recorded, so re-runs never duplicate a fill."""
    if not os.path.exists(FILLS_LOG):
        return set()
    try:
        with open(FILLS_LOG, "r", newline="", encoding="utf-8") as f:
            return {row["OrderId"] for row in csv.DictReader(f) if row.get("OrderId")}
    except Exception as e:
        print(f"[account_log] WARNING: could not read {FILLS_LOG}: {e}")
        return set()


# ---------------------------------------------------------------------------
# equity + positions
# ---------------------------------------------------------------------------

def log_equity_and_positions(client):
    """Snapshot account equity and every open position. Returns a status string."""
    try:
        account = client.get_account()
        positions = client.get_all_positions()
    except Exception as e:
        print(f"[account_log] SKIPPED equity/positions: {type(e).__name__}: {e}")
        return "error"

    now = datetime.now()
    timestamp = now.strftime("%Y-%m-%d %H:%M:%S")
    date = now.strftime("%Y-%m-%d")

    equity = _f(getattr(account, "equity", None))
    last_equity = _f(getattr(account, "last_equity", None))
    cash = _f(getattr(account, "cash", None))
    long_mv = _f(getattr(account, "long_market_value", None))
    short_mv = _f(getattr(account, "short_market_value", None))

    # Gross exposure is what actually matters for the leverage question. If it
    # exceeds equity, the difference is borrowed - that is precisely the
    # condition that went undetected from April to August 2026, when the
    # negative Cash figure was dismissed as an Alpaca display quirk.
    gross_exposure = abs(long_mv) + abs(short_mv)
    if not gross_exposure and positions:
        gross_exposure = sum(abs(_f(getattr(p, "market_value", None))) for p in positions)

    leverage = (gross_exposure / equity) if equity else 0.0
    margin_debt = max(0.0, gross_exposure - equity)

    daily_pnl = equity - last_equity if last_equity else 0.0
    daily_pnl_pct = (daily_pnl / last_equity * 100) if last_equity else 0.0

    _append_row(EQUITY_LOG, EQUITY_FIELDS, {
        "Timestamp": timestamp,
        "Date": date,
        "Equity": round(equity, 2),
        "LastEquity": round(last_equity, 2),
        "DailyPnL": round(daily_pnl, 2),
        "DailyPnLPct": round(daily_pnl_pct, 4),
        "Cash": round(cash, 2),
        "BuyingPower": round(_f(getattr(account, "buying_power", None)), 2),
        "LongMarketValue": round(long_mv, 2),
        "ShortMarketValue": round(short_mv, 2),
        "PositionCount": len(positions),
        "GrossExposure": round(gross_exposure, 2),
        "Leverage": round(leverage, 4),
        "MarginDebt": round(margin_debt, 2),
    })

    for p in positions:
        market_value = _f(getattr(p, "market_value", None))
        _append_row(POSITIONS_LOG, POSITION_FIELDS, {
            "Timestamp": timestamp,
            "Date": date,
            "Ticker": getattr(p, "symbol", ""),
            "Qty": _f(getattr(p, "qty", None)),
            "AvgEntryPrice": round(_f(getattr(p, "avg_entry_price", None)), 4),
            "CurrentPrice": round(_f(getattr(p, "current_price", None)), 4),
            "MarketValue": round(market_value, 2),
            "CostBasis": round(_f(getattr(p, "cost_basis", None)), 2),
            "UnrealizedPL": round(_f(getattr(p, "unrealized_pl", None)), 2),
            "UnrealizedPLPct": round(_f(getattr(p, "unrealized_plpc", None)) * 100, 4),
            "PctOfEquity": round((market_value / equity * 100), 4) if equity else 0.0,
        })

    # Loud, because this is the check that would have caught Version 11's
    # leverage bug on day one instead of after three months.
    if leverage > 1.05:
        print(f"[account_log] *** LEVERAGE WARNING: {leverage:.2f}x "
              f"(exposure ${gross_exposure:,.2f} vs equity ${equity:,.2f}, "
              f"implied margin debt ${margin_debt:,.2f}) ***")

    print(f"[account_log] Equity ${equity:,.2f} | {len(positions)} positions | "
          f"exposure ${gross_exposure:,.2f} | leverage {leverage:.2f}x")
    return "ok"


# ---------------------------------------------------------------------------
# fills
# ---------------------------------------------------------------------------

def log_fills(client, lookback_days=7):
    """Record actual executions. Returns a status string.

    Deliberately looks back further than one day and dedupes on order id, so a
    missed run (three of which are already known to have happened - May 1,
    Jun 18, Aug 6 2026) backfills on the next successful run instead of leaving
    a permanent hole.
    """
    try:
        orders = _fetch_recent_orders(client, lookback_days)
    except Exception as e:
        print(f"[account_log] SKIPPED fills: {type(e).__name__}: {e}")
        return "error"

    known = _existing_order_ids()
    new_count = 0

    for o in orders:
        order_id = str(getattr(o, "id", "") or "")
        if not order_id or order_id in known:
            continue

        filled_qty = _f(getattr(o, "filled_qty", None))
        filled_price = _f(getattr(o, "filled_avg_price", None))

        # Only executions. Rejected/canceled/expired orders never moved money,
        # and logging them as fills is the Version 11 phantom-position bug.
        if filled_qty <= 0 or filled_price <= 0:
            continue

        _append_row(FILLS_LOG, FILL_FIELDS, {
            "OrderId": order_id,
            "Ticker": getattr(o, "symbol", ""),
            "Side": _s(getattr(o, "side", None)),
            "SubmittedAt": str(getattr(o, "submitted_at", "") or ""),
            "FilledAt": str(getattr(o, "filled_at", "") or ""),
            "Status": _s(getattr(o, "status", None)),
            "Qty": _f(getattr(o, "qty", None)),
            "FilledQty": filled_qty,
            "FilledAvgPrice": round(filled_price, 4),
            "Notional": round(filled_qty * filled_price, 2),
            "OrderType": _s(getattr(o, "order_type", None) or getattr(o, "type", None)),
        })
        known.add(order_id)
        new_count += 1

    print(f"[account_log] Logged {new_count} new fill(s) "
          f"from the last {lookback_days} days")
    return "ok"


def _fetch_recent_orders(client, lookback_days):
    """Ask for closed orders, degrading to an unfiltered call if the SDK differs."""
    after = datetime.now() - timedelta(days=lookback_days)
    try:
        from alpaca.trading.requests import GetOrdersRequest
        from alpaca.trading.enums import QueryOrderStatus
        req = GetOrdersRequest(status=QueryOrderStatus.CLOSED, after=after, limit=500)
        return client.get_orders(filter=req)
    except Exception:
        # Older/newer alpaca-py signatures, or a stub client in tests.
        return client.get_orders()


# ---------------------------------------------------------------------------
# entry point
# ---------------------------------------------------------------------------

def log_account_state(client, lookback_days=7):
    """Log everything. Never raises - a logging failure must not stop trading."""
    try:
        equity_status = log_equity_and_positions(client)
        fills_status = log_fills(client, lookback_days=lookback_days)
        return {"equity": equity_status, "fills": fills_status}
    except Exception as e:
        print(f"[account_log] Unexpected failure, continuing anyway: "
              f"{type(e).__name__}: {e}")
        return {"equity": "error", "fills": "error"}
