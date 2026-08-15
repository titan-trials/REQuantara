"""
Performance metrics for a completed backtest.

Two changes in Version 16 worth knowing about:

1. SHARPE NOW SUBTRACTS A RISK-FREE RATE. It never did. Sharpe is the largest
   term in compute_composite_score (x0.5), so this changes which strategy gets
   selected, not merely what gets reported. See evaluation/risk_free.py.

2. `Win_Rate` IS GONE, RENAMED TO `Up_Day_Rate`. It was never a win rate. It
   counted the fraction of DAYS the portfolio value rose, with every day spent
   in cash counting as a loss - which is why it read ~25-30% next to a genuine
   trade-level win rate of 56.3% from win_loss_stats(). Two different numbers
   wearing the same name.
"""

from evaluation.risk_free import TRADING_DAYS, resolve_daily_risk_free


def _core(df, initial_capital, risk_free=None):
    total_return_strategy = df["Cumulative_Strategy"].iloc[-1] - 1
    total_return_market = df["Cumulative_Market"].iloc[-1] - 1

    daily_returns = df["Portfolio_Value"].pct_change()

    # Fraction of days the portfolio rose. NOT a win rate - days in cash are
    # flat and count against it.
    up_day_rate = (daily_returns > 0).mean()

    rolling_max = df["Cumulative_Strategy"].cummax()
    drawdown = (df["Cumulative_Strategy"] - rolling_max) / rolling_max
    max_drawdown = drawdown.min()

    rf_daily = resolve_daily_risk_free(df.index, risk_free)
    excess = (daily_returns - rf_daily).dropna()

    std = excess.std()
    sharpe = (excess.mean() / std) * (TRADING_DAYS ** 0.5) if std and std > 0 else 0.0

    return {
        "total_return_strategy": total_return_strategy,
        "total_return_market": total_return_market,
        "up_day_rate": up_day_rate,
        "max_drawdown": max_drawdown,
        "sharpe": sharpe,
        "final_value": df["Portfolio_Value"].iloc[-1],
    }


def calculate_metrics(df, initial_capital, risk_free=None):
    m = _core(df, initial_capital, risk_free)
    vs_market = m["total_return_strategy"] - m["total_return_market"]

    print(f"Initial Capital       : ${initial_capital:,.2f}")
    print(f"Final Portfolio Value : ${m['final_value']:,.2f}")
    print(f"Strategy Total Return : {m['total_return_strategy']:.2%}")
    print(f"Buy & Hold Return     : {m['total_return_market']:.2%}")
    print(f"Vs Buy & Hold         : {vs_market:+.2%}")
    print(f"Up-Day Rate           : {m['up_day_rate']:.2%}  (days risen, NOT a win rate)")
    print(f"Max Drawdown          : {m['max_drawdown']:.2%}")


def get_metrics(df, initial_capital, risk_free=None):
    m = _core(df, initial_capital, risk_free)

    return {
        "Total_Return": round(m["total_return_strategy"] * 100, 2),
        "Market_Return": round(m["total_return_market"] * 100, 2),
        # Strategy return minus simply holding the ticker over the same window.
        # Negative means the strategy destroyed value versus doing nothing -
        # a comparison this project never surfaced before Version 16.
        "Vs_Market": round(
            (m["total_return_strategy"] - m["total_return_market"]) * 100, 2
        ),
        "Up_Day_Rate": round(m["up_day_rate"] * 100, 2),
        "Max_Drawdown": round(m["max_drawdown"] * 100, 2),
        "Sharpe_Ratio": round(m["sharpe"], 3),
        "Final_Value": round(m["final_value"], 2),
    }
