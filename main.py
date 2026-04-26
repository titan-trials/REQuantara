from strategy.optimizer import optimize_ema_crossover
from config import START, END, INITIAL_CAPITAL, STOP_LOSS, POSITION_SIZE

result = optimize_ema_crossover("NVDA", START, END, INITIAL_CAPITAL, STOP_LOSS, POSITION_SIZE)