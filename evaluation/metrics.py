def calculate_metrics(df, initial_capital):
    total_return_strategy = df["Cumulative_Strategy"].iloc[-1] - 1
    total_return_market = df["Cumulative_Market"].iloc[-1] - 1

    daily_returns = df["Portfolio_Value"].pct_change()
    win_rate = (daily_returns > 0).mean()

    rolling_max = df["Cumulative_Strategy"].cummax()
    drawdown = (df["Cumulative_Strategy"] - rolling_max) / rolling_max
    max_drawdown = drawdown.min()

    final_value = df["Portfolio_Value"].iloc[-1]

    print(f"Initial Capital       : ${initial_capital:,.2f}")
    print(f"Final Portfolio Value : ${final_value:,.2f}")
    print(f"Strategy Total Return : {total_return_strategy:.2%}")
    print(f"Market Total Return   : {total_return_market:.2%}")
    print(f"Win Rate              : {win_rate:.2%}")
    print(f"Max Drawdown          : {max_drawdown:.2%}")

def get_metrics(df, initial_capital):
    total_return_strategy = df["Cumulative_Strategy"].iloc[-1] - 1
    total_return_market = df["Cumulative_Market"].iloc[-1] - 1

    daily_returns = df["Portfolio_Value"].pct_change()
    win_rate = (daily_returns > 0).mean()

    rolling_max = df["Cumulative_Strategy"].cummax()
    drawdown = (df["Cumulative_Strategy"] - rolling_max) / rolling_max
    max_drawdown = drawdown.min()

    sharpe = (daily_returns.mean() / daily_returns.std()) * (252 ** 0.5)

    final_value = df["Portfolio_Value"].iloc[-1]

    return {
        "Total_Return": round(total_return_strategy * 100, 2),
        "Market_Return": round(total_return_market * 100, 2),
        "Win_Rate": round(win_rate * 100, 2),
        "Max_Drawdown": round(max_drawdown * 100, 2),
        "Sharpe_Ratio": round(sharpe, 3),
        "Final_Value": round(final_value, 2)
    }