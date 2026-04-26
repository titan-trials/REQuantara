from data.loader import load_data
from indicators.moving_average import compute_sma
from signals.sma_crossover import generate_crossover_signals
from backtest.engine import run_backtest
from evaluation.metrics import calculate_metrics
from plots.visualizer import plot_results
from config import TICKER, START, END, FAST_WINDOW, SLOW_WINDOW, INITIAL_CAPITAL, STOP_LOSS, POSITION_SIZE

# Run Quantara
df = load_data(TICKER, START, END)
df = compute_sma(df, FAST_WINDOW)
df = compute_sma(df, SLOW_WINDOW)
df = generate_crossover_signals(df, FAST_WINDOW, SLOW_WINDOW)
df = run_backtest(df, INITIAL_CAPITAL, STOP_LOSS, POSITION_SIZE)
calculate_metrics(df, INITIAL_CAPITAL)
plot_results(df)