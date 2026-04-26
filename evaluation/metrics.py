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