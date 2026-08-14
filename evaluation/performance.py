import pandas as pd
from config import STOP_LOSS

KNOWN_EXIT_REASON_OVERRIDES = {
    ("NVDA", "2026-06-24 22:13:42"): "STOP_LOSS",
}

def build_trade_segments(log: pd.DataFrame) -> pd.DataFrame:
    """
    Walks the paper trading log chronologically per ticker and builds
    trade segments. A segment closes when:
      - strategy changes, OR
      - signal flips from BUY (1) to SELL (0) within the same strategy

    Returns a DataFrame with one row per segment:
    Ticker, Strategy, Entry_Date, Entry_Price, Exit_Date, Exit_Price,
    Duration_Days, PnL, PnL_Pct, Status (CLOSED/OPEN), Exit_Reason
    """
    segments = []

    for ticker in log["Ticker"].unique():
        tdf = log[log["Ticker"] == ticker].sort_values("Timestamp").reset_index(drop=True)

        open_segment = None

        for _, row in tdf.iterrows():
            strategy = row["Strategy"]
            signal = row["Signal"]
            price = row["Price"]
            ts = row["Timestamp"]
            exit_reason = row.get("Exit_Reason", "")

            if open_segment is None:
                if signal == 1:
                    open_segment = {
                        "Ticker": ticker,
                        "Strategy": strategy,
                        "Entry_Date": ts,
                        "Entry_Price": price,
                    }
                continue

            if strategy != open_segment["Strategy"]:
                segments.append(_close_segment(open_segment, ts, price, status="CLOSED", exit_reason=exit_reason))
                if signal == 1:
                    open_segment = {
                        "Ticker": ticker,
                        "Strategy": strategy,
                        "Entry_Date": ts,
                        "Entry_Price": price,
                    }
                else:
                    open_segment = None
                continue

            if signal == 0:
                segments.append(_close_segment(open_segment, ts, price, status="CLOSED", exit_reason=exit_reason))
                open_segment = None

        if open_segment is not None:
            last_row = tdf.iloc[-1]
            segments.append(_close_segment(
                open_segment, last_row["Timestamp"], last_row["Price"], status="OPEN", exit_reason=""
            ))

    return pd.DataFrame(segments)


def _close_segment(open_segment, exit_date, exit_price, status, exit_reason=""):
    entry_price = open_segment["Entry_Price"]
    pnl_pct = ((exit_price - entry_price) / entry_price) * 100
    pnl_dollar = pnl_pct / 100 * 2000
    duration = (exit_date - open_segment["Entry_Date"]).days

    return {
        "Ticker": open_segment["Ticker"],
        "Strategy": open_segment["Strategy"],
        "Entry_Date": open_segment["Entry_Date"],
        "Entry_Price": entry_price,
        "Exit_Date": exit_date,
        "Exit_Price": exit_price,
        "Duration_Days": duration,
        "PnL": pnl_dollar,
        "PnL_Pct": pnl_pct,
        "Status": status,
        "Exit_Reason": exit_reason if exit_reason else "SIGNAL",
    }


def ticker_summary(segments: pd.DataFrame, log: pd.DataFrame) -> pd.DataFrame:
    """
    Rolls up trade segments into one row per ticker:
    total PnL (realized + open marked separately), trade count, switch count
    """
    summaries = []

    for ticker in segments["Ticker"].unique():
        tseg = segments[segments["Ticker"] == ticker]
        closed = tseg[tseg["Status"] == "CLOSED"]
        open_seg = tseg[tseg["Status"] == "OPEN"]

        realized_pnl = closed["PnL"].sum()
        unrealized_pnl = open_seg["PnL"].sum() if not open_seg.empty else 0
        total_pnl = realized_pnl + unrealized_pnl

        # Count actual distinct strategies that ever appeared for this ticker
        # in the raw log, not just the ones recorded as segment entries
        strategies_used = log[log["Ticker"] == ticker]["Strategy"].nunique()
        is_open = not open_seg.empty

        summaries.append({
            "Ticker": ticker,
            "Total_PnL": total_pnl,
            "Realized_PnL": realized_pnl,
            "Unrealized_PnL": unrealized_pnl,
            "Is_Open": is_open,
            "Trade_Count": len(closed),
            "Strategy_Switches": strategies_used - 1,
            "Switch_Flag": strategies_used > 1,
        })

    return pd.DataFrame(summaries)


def win_loss_stats(segments: pd.DataFrame) -> dict:
    """Win/loss statistics across all CLOSED trade segments."""
    closed = segments[segments["Status"] == "CLOSED"]
    if closed.empty:
        return {"win_rate": 0, "avg_win": 0, "avg_loss": 0, "total_trades": 0}

    wins = closed[closed["PnL"] > 0]
    losses = closed[closed["PnL"] <= 0]

    return {
        "win_rate": len(wins) / len(closed) * 100,
        "avg_win": wins["PnL"].mean() if not wins.empty else 0,
        "avg_loss": losses["PnL"].mean() if not losses.empty else 0,
        "total_trades": len(closed),
        "biggest_win": closed["PnL"].max(),
        "biggest_loss": closed["PnL"].min(),
    }


def drawdown_tracker(log: pd.DataFrame) -> pd.DataFrame:
    """
    For each ticker, tracks the running peak price since tracking began
    and calculates current drawdown from that peak.
    """
    results = []

    for ticker in log["Ticker"].unique():
        tdf = log[log["Ticker"] == ticker].sort_values("Timestamp")
        prices = tdf["Price"].values

        running_peak = prices[0]
        max_drawdown = 0
        peak_price = prices[0]
        peak_date = tdf["Timestamp"].iloc[0]

        for i, price in enumerate(prices):
            if price > running_peak:
                running_peak = price
                peak_price = price
                peak_date = tdf["Timestamp"].iloc[i]
            drawdown = (price - running_peak) / running_peak * 100
            if drawdown < max_drawdown:
                max_drawdown = drawdown

        current_price = prices[-1]
        current_drawdown = (current_price - running_peak) / running_peak * 100

        results.append({
            "Ticker": ticker,
            "Peak_Price": running_peak,
            "Peak_Date": peak_date,
            "Current_Price": current_price,
            "Current_Drawdown_Pct": current_drawdown,
            "Max_Drawdown_Pct": max_drawdown,
        })

    return pd.DataFrame(results)


def signal_quality_score(log: pd.DataFrame) -> pd.DataFrame:
    """
    For each ticker, checks every BUY signal and whether the price
    increased on the next available signal (next trading day).
    Returns accuracy per ticker plus overall breakdown.
    """
    results = []

    for ticker in log["Ticker"].unique():
        tdf = log[log["Ticker"] == ticker].sort_values("Timestamp").reset_index(drop=True)

        correct = 0
        total_checked = 0

        for i in range(len(tdf) - 1):
            current_signal = tdf.loc[i, "Signal"]
            current_price = tdf.loc[i, "Price"]
            next_price = tdf.loc[i + 1, "Price"]

            if current_signal == 1:  # BUY signal
                total_checked += 1
                if next_price > current_price:
                    correct += 1

        accuracy = (correct / total_checked * 100) if total_checked > 0 else 0

        results.append({
            "Ticker": ticker,
            "Buy_Signals_Checked": total_checked,
            "Correct_Next_Day_Up": correct,
            "Accuracy_Pct": accuracy,
        })

    return pd.DataFrame(results)

#Didn't implement this function yet not statstically significant with current data, but will be useful as we gather more data over time to see if signal quality is improving or degrading.
def signal_quality_weekly(log: pd.DataFrame) -> pd.DataFrame:
    """
    Breaks signal quality score into weekly buckets per ticker,
    so we can see if accuracy is trending up or down over time.
    """
    results = []

    for ticker in log["Ticker"].unique():
        tdf = log[log["Ticker"] == ticker].sort_values("Timestamp").reset_index(drop=True)
        tdf["Week"] = tdf["Timestamp"].dt.to_period("W").apply(lambda r: r.start_time)

        for week, wdf in tdf.groupby("Week"):
            wdf = wdf.reset_index(drop=True)
            correct = 0
            total_checked = 0

            for i in range(len(wdf) - 1):
                if wdf.loc[i, "Signal"] == 1:
                    total_checked += 1
                    if wdf.loc[i + 1, "Price"] > wdf.loc[i, "Price"]:
                        correct += 1

            # Also need to check across week boundary using the full series
            # so we don't lose the last day's comparison within tdf
            accuracy = (correct / total_checked * 100) if total_checked > 0 else None

            results.append({
                "Ticker": ticker,
                "Week_Start": week,
                "Buy_Signals": total_checked,
                "Correct": correct,
                "Weekly_Accuracy_Pct": accuracy,
            })

    return pd.DataFrame(results)


def detect_problems(summary, drawdown, quality, log, stop_loss=STOP_LOSS):
    """
    Scans ticker-level performance data and flags issues in plain English.

    Each flag carries temporal context, but the three check types have
    genuinely different time semantics and are dated accordingly:
      - strategy switches: discrete dated events that can recur
      - drawdown breach:   a current condition, dated by when the peak was set
      - signal accuracy:   a rolling aggregate over a date range

    Returns list of dicts: {Ticker, Severity, Message, When, Detail}
    """
    flags = []

    for _, row in summary.iterrows():
        ticker = row["Ticker"]
        tdf = log[log["Ticker"] == ticker].sort_values("Timestamp").reset_index(drop=True)
        if tdf.empty:
            continue

        latest_ts = tdf["Timestamp"].iloc[-1]

        # --- Check 1: strategy switching (discrete, dated, recurring) ---
        switches, prev = [], None
        for _, r in tdf.iterrows():
            if prev is not None and r["Strategy"] != prev:
                switches.append((r["Timestamp"], prev, r["Strategy"]))
            prev = r["Strategy"]

        if switches:
            last_ts = switches[-1][0]
            recent = " · ".join(
                f"{ts.strftime('%b %d')}: {a} → {b}" for ts, a, b in switches[-3:]
            )
            more = f" (+{len(switches) - 3} earlier)" if len(switches) > 3 else ""
            flags.append({
                "Ticker": ticker,
                "Severity": "WARNING",
                "Message": f"{ticker} has switched strategy {len(switches)} time(s) — signal instability detected.",
                "When": last_ts,
                "Detail": f"Most recent: {recent}{more}",
            })

        # --- Check 2: drawdown past stop loss threshold (current condition) ---
        dd_row = drawdown[drawdown["Ticker"] == ticker]
        if not dd_row.empty:
            current_dd = dd_row["Current_Drawdown_Pct"].values[0]
            if current_dd <= -stop_loss * 100:
                peak_date = pd.to_datetime(dd_row["Peak_Date"].values[0])
                peak_price = dd_row["Peak_Price"].values[0]
                days_since = (latest_ts - peak_date).days
                flags.append({
                    "Ticker": ticker,
                    "Severity": "CRITICAL",
                    "Message": f"{ticker} is down {abs(current_dd):.1f}% from its peak — beyond the {stop_loss*100:.0f}% stop loss threshold.",
                    "When": peak_date,
                    "Detail": f"Peak ${peak_price:.2f} set {peak_date.strftime('%b %d, %Y')} · {days_since} days ago, still below it",
                })

        # --- Check 3: signal accuracy (rolling aggregate over a range) ---
        q_row = quality[quality["Ticker"] == ticker]
        if not q_row.empty:
            acc = q_row["Accuracy_Pct"].values[0]
            checked = q_row["Buy_Signals_Checked"].values[0]
            if acc < 50 and checked >= 10:
                first_ts = tdf["Timestamp"].iloc[0]
                flags.append({
                    "Ticker": ticker,
                    "Severity": "WARNING",
                    "Message": f"{ticker} signal accuracy is {acc:.1f}% on {checked} checked signals — worse than a coin flip.",
                    "When": latest_ts,
                    "Detail": f"Measured across {first_ts.strftime('%b %d')} – {latest_ts.strftime('%b %d, %Y')} · rolling, not a single event",
                })

    if not flags:
        flags.append({
            "Ticker": "—", "Severity": "OK",
            "Message": "No issues detected across all tickers.",
            "When": None, "Detail": "",
        })

    return flags

def build_event_feed(segments: pd.DataFrame, summary: pd.DataFrame, log: pd.DataFrame) -> list:
    """
    Builds a chronological, narrated feed of trading events: closed trades
    (with reason), new entries, and strategy switches. Returns a list of
    dicts sorted most-recent-first, each with Date, Ticker, EventType, Message.
    """
    events = []

    # Closed trade exits
    closed = segments[segments["Status"] == "CLOSED"]
    for _, row in closed.iterrows():
        ticker = row["Ticker"]
        pnl = row["PnL"]
        exit_reason = row["Exit_Reason"]
        override_key = (ticker, str(row["Exit_Date"]))
        if override_key in KNOWN_EXIT_REASON_OVERRIDES:
            exit_reason = KNOWN_EXIT_REASON_OVERRIDES[override_key]
        exit_price = row["Exit_Price"]
        entry_price = row["Entry_Price"]
        strategy = row["Strategy"]

        if exit_reason == "STOP_LOSS":
            drawdown_pct = (exit_price - entry_price) / entry_price * 100
            message = (
                f"{ticker} sold @ ${exit_price:.2f} — stop loss "
                f"({STOP_LOSS*100:.0f}%) triggered (down {abs(drawdown_pct):.1f}% "
                f"from your ${entry_price:.2f} entry). You realized a "
                f"{'loss' if pnl < 0 else 'gain'} of ${abs(pnl):.0f} on this position."
            )
            severity = "CRITICAL"
        else:
            verb = "gained" if pnl >= 0 else "lost"
            message = (
                f"{ticker} sold @ ${exit_price:.2f} — {strategy} signal "
                f"flipped to SELL. You {verb} ${abs(pnl):.0f} on this position."
            )
            severity = "POSITIVE" if pnl >= 0 else "NEGATIVE"

        events.append({
            "Date": row["Exit_Date"],
            "Ticker": ticker,
            "EventType": "EXIT",
            "Severity": severity,
            "Message": message,
        })

    # New entries (every segment's start, OPEN or CLOSED)
    for _, row in segments.iterrows():
        ticker = row["Ticker"]
        entry_price = row["Entry_Price"]
        strategy = row["Strategy"]
        message = f"{ticker} bought @ ${entry_price:.2f} — {strategy} signal flipped to BUY."
        events.append({
            "Date": row["Entry_Date"],
            "Ticker": ticker,
            "EventType": "ENTRY",
            "Severity": "NEUTRAL",
            "Message": message,
        })

    # Strategy switches: detect by walking the raw log per ticker
    for ticker in log["Ticker"].unique():
        tdf = log[log["Ticker"] == ticker].sort_values("Timestamp").reset_index(drop=True)
        prev_strategy = None
        for _, row in tdf.iterrows():
            strategy = row["Strategy"]
            if prev_strategy is not None and strategy != prev_strategy:
                message = f"{ticker}'s auto-selected strategy switched from {prev_strategy} to {strategy}."
                events.append({
                    "Date": row["Timestamp"],
                    "Ticker": ticker,
                    "EventType": "SWITCH",
                    "Severity": "WARNING",
                    "Message": message,
                })
            prev_strategy = strategy

    events_df = pd.DataFrame(events).sort_values("Date", ascending=False)
    return events_df.to_dict("records")

def reconcile_open_segments(segments, positions):
    """
    The CSV can believe a position is open when the real order was rejected,
    or hold a stale entry price when the actual fill differed. This function reconciles the CSV's open segments with the actual Alpaca positions.
    """
    if not positions:
        return segments

    live = {p.symbol: p for p in positions}
    rows = []

    for _, row in segments.iterrows():
        if row["Status"] != "OPEN":
            rows.append(row)
            continue

        pos = live.get(row["Ticker"])
        if pos is None:
            continue  # CSV thinks it's open, Alpaca disagrees — drop it

        entry = float(pos.avg_entry_price)
        current = float(pos.current_price)

        row = row.copy()
        row["Entry_Price"] = entry
        row["Exit_Price"] = current
        row["PnL"] = float(pos.unrealized_pl)
        row["PnL_Pct"] = (current - entry) / entry * 100
        rows.append(row)

    return pd.DataFrame(rows) if rows else segments.iloc[0:0]