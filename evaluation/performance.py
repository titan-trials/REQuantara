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