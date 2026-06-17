import pandas as pd

def build_trade_segments(log: pd.DataFrame) -> pd.DataFrame:
    """
    Walks the paper trading log chronologically per ticker and builds
    trade segments. A segment closes when:
      - strategy changes, OR
      - signal flips from BUY (1) to SELL (0) within the same strategy

    Returns a DataFrame with one row per segment:
    Ticker, Strategy, Entry_Date, Entry_Price, Exit_Date, Exit_Price,
    Duration_Days, PnL, PnL_Pct, Status (CLOSED/OPEN)
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

            if open_segment is None:
                # No open position — start one only if signal is BUY
                if signal == 1:
                    open_segment = {
                        "Ticker": ticker,
                        "Strategy": strategy,
                        "Entry_Date": ts,
                        "Entry_Price": price,
                    }
                continue

            # We have an open segment
            if strategy != open_segment["Strategy"]:
                # Strategy changed — close current segment at this price
                segments.append(_close_segment(open_segment, ts, price, status="CLOSED"))
                # Start new segment if new strategy says BUY
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
                # SELL signal — close the segment
                segments.append(_close_segment(open_segment, ts, price, status="CLOSED"))
                open_segment = None

        # End of ticker's data — if still open, mark as OPEN (unrealized)
        if open_segment is not None:
            last_row = tdf.iloc[-1]
            segments.append(_close_segment(
                open_segment, last_row["Timestamp"], last_row["Price"], status="OPEN"
            ))

    return pd.DataFrame(segments)


def _close_segment(open_segment, exit_date, exit_price, status):
    entry_price = open_segment["Entry_Price"]
    pnl_pct = ((exit_price - entry_price) / entry_price) * 100
    pnl_dollar = pnl_pct / 100 * 2000  # $2k per ticker assumption
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

#Dont Impment this function yet not statstically significant with current data, but will be useful as we gather more data over time to see if signal quality is improving or degrading.
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


def detect_problems(summary, drawdown, quality, stop_loss=0.05):
    """
    Scans ticker-level performance data and flags issues in plain English.
    Returns a list of dicts: {Ticker, Severity, Message}
    """
    flags = []

    for _, row in summary.iterrows():
        ticker = row["Ticker"]

        # Check 1 — strategy switching
        if row["Switch_Flag"]:
            flags.append({
                "Ticker": ticker,
                "Severity": "WARNING",
                "Message": f"{ticker} has switched strategy {row['Strategy_Switches']} time(s) — signal instability detected."
            })

        # Check 2 — stop loss breach using current drawdown
        dd_row = drawdown[drawdown["Ticker"] == ticker]
        if not dd_row.empty:
            current_dd = dd_row["Current_Drawdown_Pct"].values[0]
            if current_dd <= -stop_loss * 100:
                flags.append({
                    "Ticker": ticker,
                    "Severity": "CRITICAL",
                    "Message": f"{ticker} is down {current_dd:.1f}% from its peak — beyond the {stop_loss*100:.0f}% stop loss threshold."
                })

        # Check 3 — signal accuracy below coin flip baseline
        q_row = quality[quality["Ticker"] == ticker]
        if not q_row.empty:
            acc = q_row["Accuracy_Pct"].values[0]
            checked = q_row["Buy_Signals_Checked"].values[0]
            if acc < 50 and checked >= 10:  # only flag if enough samples to be meaningful
                flags.append({
                    "Ticker": ticker,
                    "Severity": "WARNING",
                    "Message": f"{ticker} signal accuracy is {acc:.1f}% on {checked} checked signals — worse than a coin flip."
                })

    if not flags:
        flags.append({
            "Ticker": "—",
            "Severity": "OK",
            "Message": "No issues detected across all tickers."
        })

    return flags



