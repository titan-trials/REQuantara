from data.loader import load_data
from indicators.moving_average import compute_sma
from indicators.bollinger import compute_bollinger_bands
from indicators.rsi import compute_rsi
from signals.sma_crossover import generate_combined_signals, generate_ema_crossover_signals
from signals.bollinger_signal import generate_bollinger_signals
from indicators.ema import compute_ema
from backtest.engine import run_backtest
from evaluation.metrics import calculate_metrics
from plots.visualizer import plot_results
from config import TICKER, START, END, FAST_WINDOW, SLOW_WINDOW, INITIAL_CAPITAL, STOP_LOSS, POSITION_SIZE, EMA_FAST, EMA_SLOW

# Run Quantara
df = load_data(TICKER, START, END)
#df = compute_sma(df, FAST_WINDOW)
#df = compute_sma(df, SLOW_WINDOW)
#df = compute_ema(df, EMA_FAST)
#df = compute_ema(df, EMA_SLOW)
df = compute_rsi(df)
df = compute_bollinger_bands(df)
df = generate_bollinger_signals(df)
#df = generate_combined_signals(df, FAST_WINDOW, SLOW_WINDOW)
#df = generate_ema_crossover_signals(df, EMA_FAST, EMA_SLOW)
df = run_backtest(df, INITIAL_CAPITAL, STOP_LOSS, POSITION_SIZE)
calculate_metrics(df, INITIAL_CAPITAL)
plot_results(df)