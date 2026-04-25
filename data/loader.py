import yfinance as yf
import pandas as pd

def load_data(ticker, start, end):
    df = yf.download(ticker, start=start, end=end)
    df.columns = df.columns.get_level_values(0)
    df = df[["Close"]]
    df.columns.name = None
    df.dropna(inplace=True)
    return df