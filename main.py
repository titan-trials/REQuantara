from data.loader import load_data
from indicators.moving_average import compute_sma
from signals.sma_crossover import generate_signals
from backtest.engine import run_backtest
from evaluation.metrics import calculate_metrics
from plots.visualizer import plot_results
from config import TICKER, START, END, WINDOW


# Run Quantara
df = load_data(TICKER, START, END)
df = compute_sma(df, WINDOW)
df = generate_signals(df, WINDOW)
df = run_backtest(df)
calculate_metrics(df)
plot_results(df)