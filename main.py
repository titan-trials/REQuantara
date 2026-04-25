from data.loader import load_data
from indicators.moving_average import compute_sma
from signals.sma_crossover import generate_crossover_signals
from backtest.engine import run_backtest
from evaluation.metrics import calculate_metrics
from plots.visualizer import plot_results
from config import SLOW_WINDOW, TICKER, START, END, FAST_WINDOW


# Run Quantara
df = load_data(TICKER, START, END)
df = compute_sma(df, FAST_WINDOW)
df = compute_sma(df, SLOW_WINDOW)
df = generate_crossover_signals(df, FAST_WINDOW, SLOW_WINDOW)
df = run_backtest(df)
calculate_metrics(df)
plot_results(df)
