import pandas as pd
from data.loader import load_data
from strategy.ml_signal import build_features

df = load_data("TSLA", "2015-01-01", "2024-01-01")
df = build_features(df)

print(df.columns.tolist())
print()

print(df[["Close", "Streak", "Mom_accel", "ADX_14"]].tail(40))

print()
print("NaN counts in new features:")
print(df[["Streak", "Mom_accel", "ADX_14"]].isna().sum())


#TSLA Dig
print()
print("=== Streak distribution (full TSLA history) ===")
print(f"Max positive streak: {df['Streak'].max()}")
print(f"Max negative streak: {df['Streak'].min()}")
print(f"Mean absolute streak: {df['Streak'].abs().mean():.2f}")
print()
print("Top 10 longest streaks (by absolute value):")
top_streaks = df.reindex(df["Streak"].abs().sort_values(ascending=False).index).head(10)
print(top_streaks[["Close", "Streak"]])

print()
print("=== ADX_14 distribution ===")
print(df["ADX_14"].describe())


##IBM Dig

df = load_data("IBM", "2015-01-01", "2024-01-01")
df = build_features(df)

print(df[["Close", "Streak", "Mom_accel", "ADX_14"]].tail(40))

print()
print("NaN counts in new features:")
print(df[["Streak", "Mom_accel", "ADX_14"]].isna().sum())

print()
print("=== Streak distribution (full IBM history) ===")
print(f"Max positive streak: {df['Streak'].max()}")
print(f"Max negative streak: {df['Streak'].min()}")
print(f"Mean absolute streak: {df['Streak'].abs().mean():.2f}")
print()
print("Top 10 longest streaks (by absolute value):")
top_streaks = df.reindex(df["Streak"].abs().sort_values(ascending=False).index).head(10)
print(top_streaks[["Close", "Streak"]])

print()
print("=== ADX_14 distribution ===")
print(df["ADX_14"].describe())