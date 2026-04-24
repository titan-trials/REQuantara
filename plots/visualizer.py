import matplotlib.pyplot as plt

def plot_results(df):
    plt.figure(figsize=(12, 6))
    plt.plot(df["Cumulative_Market"], label="Buy & Hold", color="blue")
    plt.plot(df["Cumulative_Strategy"], label="SMA Strategy", color="orange")
    plt.title("Quantara — Strategy vs Buy & Hold (NVDA)")
    plt.xlabel("Date")
    plt.ylabel("Cumulative Return")
    plt.legend()
    plt.grid(True)
    plt.tight_layout()
    plt.show()