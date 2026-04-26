import pandas as pd
from datetime import datetime
import os

def export_results(df, filename_prefix="quantara"):
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"results/{filename_prefix}_{timestamp}.xlsx"
    
    os.makedirs("results", exist_ok=True)
    
    with pd.ExcelWriter(filename, engine="openpyxl") as writer:
        df.to_excel(writer, sheet_name="Results")
    
    print(f"Results exported to: {filename}")
    return filename

def export_optimization(opt_result, ticker, filename_prefix="optimization"):
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"results/{filename_prefix}_{ticker}_{timestamp}.xlsx"
    
    os.makedirs("results", exist_ok=True)
    
    with pd.ExcelWriter(filename, engine="openpyxl") as writer:
        summary = pd.DataFrame([{
            "Ticker": ticker,
            "Fast_Window": opt_result["best_params"][0],
            "Slow_Window": opt_result["best_params"][1],
            "Train_Sharpe": opt_result["train_sharpe"],
            "Test_Sharpe": opt_result["test_metrics"]["Sharpe_Ratio"],
            "Test_Return": opt_result["test_metrics"]["Total_Return"],
            "Test_MaxDrawdown": opt_result["test_metrics"]["Max_Drawdown"],
            "Overfit_Gap": round(opt_result["train_sharpe"] - opt_result["test_metrics"]["Sharpe_Ratio"], 3)
        }])
        summary.to_excel(writer, sheet_name="Summary", index=False)
        opt_result["all_results"].to_excel(writer, sheet_name="All_Combinations", index=False)
    
    print(f"Optimization exported to: {filename}")
    return filename