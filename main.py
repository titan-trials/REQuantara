# ============================================================
# Quantara - Main Entry Point
# Set MODE to control what runs
# Options: "compare", "optimize", "ml", "rf", "auto", "paper"
# ============================================================

MODE = "optimize"  

# Config
from config import TICKERS, START, END, INITIAL_CAPITAL, STOP_LOSS, POSITION_SIZE

# Strategy
from strategy.runner import run_all_strategies
from strategy.optimizer import optimize_all_tickers
from strategy.ml_signal import run_ml_strategy, run_rf_strategy
from strategy.auto_selector import auto_select
from strategy.paper_trader import run_paper_trader

# Evaluation
from evaluation.exporter import export_results

# Visualization
from plots.visualizer import plot_diagnostic


if MODE == "compare":
    results = run_all_strategies(TICKERS, START, END, INITIAL_CAPITAL, STOP_LOSS, POSITION_SIZE)
    print(results.to_string())
    export_results(results, "strategy_comparison")

elif MODE == "optimize":
    opt_summary = optimize_all_tickers(TICKERS, START, END, INITIAL_CAPITAL, STOP_LOSS, POSITION_SIZE)
    print(opt_summary.to_string())
    export_results(opt_summary, "optimization_summary")

elif MODE == "ml":
    for ticker in TICKERS:
        run_ml_strategy(ticker, START, END, INITIAL_CAPITAL, STOP_LOSS, POSITION_SIZE)

elif MODE == "rf":
    for ticker in TICKERS:
        run_rf_strategy(ticker, START, END, INITIAL_CAPITAL, STOP_LOSS, POSITION_SIZE)

elif MODE == "auto":
    selections = auto_select(TICKERS, START, END, INITIAL_CAPITAL, STOP_LOSS, POSITION_SIZE)
    print("\n--- QUANTARA AUTO SELECTION ---")
    print(selections.to_string())
    export_results(selections, "auto_selection")

elif MODE == "paper":
    signals = run_paper_trader(TICKERS, START, END, INITIAL_CAPITAL, STOP_LOSS, POSITION_SIZE)
    print("\n--- TODAY'S SIGNALS ---")
    print(signals.to_string())

elif MODE == "diagnostic":
    plot_diagnostic("IBM", INITIAL_CAPITAL, STOP_LOSS, POSITION_SIZE)