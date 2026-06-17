import pandas as pd
from evaluation.performance import build_trade_segments, ticker_summary, win_loss_stats

log = pd.read_csv("results/paper_trading_log.csv")
log["Timestamp"] = pd.to_datetime(log["Timestamp"])
log["Signal"] = pd.to_numeric(log["Signal"], errors="coerce").fillna(0).astype(int)

segments = build_trade_segments(log)
print(segments)

print(ticker_summary(segments, log))
print(win_loss_stats(segments))