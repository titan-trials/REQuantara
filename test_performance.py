import pandas as pd
from evaluation.performance import build_trade_segments, ticker_summary, win_loss_stats, drawdown_tracker, signal_quality_score, signal_quality_weekly, detect_problems



log = pd.read_csv("results/paper_trading_log.csv")
log["Timestamp"] = pd.to_datetime(log["Timestamp"])
log["Signal"] = pd.to_numeric(log["Signal"], errors="coerce").fillna(0).astype(int)

segments = build_trade_segments(log)
summary = ticker_summary(segments, log)
drawdown = drawdown_tracker(log)
quality = signal_quality_score(log)


print(segments)
print(ticker_summary(segments, log))
print(win_loss_stats(segments))
print(drawdown_tracker(log))
print(signal_quality_score(log))
#print(signal_quality_weekly(log).to_string())
problems = detect_problems(summary, drawdown, quality)
for p in problems:
    print(f"[{p['Severity']}] {p['Ticker']}: {p['Message']}")