def calculate_metrics(df):
    total_return_strategy = df["Cumulative_Strategy"].iloc[-1] - 1
    total_return_market = df["Cumulative_Market"].iloc[-1] - 1

    strategy_days = df["Position"] == 1
    win_rate = (df.loc[strategy_days, "Strategy_Return"] > 0).mean()

    rolling_max = df["Cumulative_Strategy"].cummax()
    drawdown = (df["Cumulative_Strategy"] - rolling_max) / rolling_max
    max_drawdown = drawdown.min()

    print(f"Strategy Total Return : {total_return_strategy:.2%}")
    print(f"Market Total Return   : {total_return_market:.2%}")
    print(f"Win Rate              : {win_rate:.2%}")
    print(f"Max Drawdown          : {max_drawdown:.2%}")