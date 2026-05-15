import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

st.set_page_config(page_title="Quantara Dashboard", layout="wide", page_icon="📈")

# ── Hardcoded backtest results (Versions 1-7, 2015-2024) ──────────────────────

MULTI_STRATEGY = pd.DataFrame([
    {"Ticker": "NVDA", "Strategy": "EMA Crossover",    "Return_%": 138.72, "Sharpe": 0.973, "MaxDD_%": -36.77},
    {"Ticker": "NVDA", "Strategy": "Bollinger Bands",  "Return_%":  21.47, "Sharpe": 0.820, "MaxDD_%":  -9.94},
    {"Ticker": "NVDA", "Strategy": "SMA Crossover",    "Return_%":  88.41, "Sharpe": 0.807, "MaxDD_%": -39.69},
    {"Ticker": "AAPL", "Strategy": "EMA Crossover",    "Return_%":  44.30, "Sharpe": 0.766, "MaxDD_%": -13.20},
    {"Ticker": "JPM",  "Strategy": "SMA Crossover",    "Return_%":  34.08, "Sharpe": 0.755, "MaxDD_%": -13.00},
    {"Ticker": "NVDA", "Strategy": "SMA+RSI Combined", "Return_%":  59.09, "Sharpe": 0.725, "MaxDD_%": -37.44},
    {"Ticker": "AAPL", "Strategy": "SMA+RSI Combined", "Return_%":  26.70, "Sharpe": 0.706, "MaxDD_%": -14.26},
    {"Ticker": "AAPL", "Strategy": "SMA Crossover",    "Return_%":  34.28, "Sharpe": 0.703, "MaxDD_%": -15.66},
    {"Ticker": "TSLA", "Strategy": "EMA Crossover",    "Return_%": 107.15, "Sharpe": 0.702, "MaxDD_%": -43.15},
    {"Ticker": "JPM",  "Strategy": "SMA+RSI Combined", "Return_%":  23.58, "Sharpe": 0.629, "MaxDD_%":  -9.46},
    {"Ticker": "TSLA", "Strategy": "SMA Crossover",    "Return_%":  68.52, "Sharpe": 0.606, "MaxDD_%": -31.35},
    {"Ticker": "TSLA", "Strategy": "SMA+RSI Combined", "Return_%":  30.50, "Sharpe": 0.437, "MaxDD_%": -27.70},
    {"Ticker": "JPM",  "Strategy": "Bollinger Bands",  "Return_%":   9.49, "Sharpe": 0.357, "MaxDD_%":  -8.44},
    {"Ticker": "JPM",  "Strategy": "EMA Crossover",    "Return_%":  10.61, "Sharpe": 0.305, "MaxDD_%": -15.21},
    {"Ticker": "TSLA", "Strategy": "Bollinger Bands",  "Return_%":   7.86, "Sharpe": 0.300, "MaxDD_%":  -8.45},
    {"Ticker": "AAPL", "Strategy": "Bollinger Bands",  "Return_%":   5.25, "Sharpe": 0.288, "MaxDD_%":  -4.14},
])

ML_RESULTS = pd.DataFrame([
    {"Ticker": "TSLA", "LR_Sharpe": 1.252, "RF_Sharpe": 0.675, "Better": "LR"},
    {"Ticker": "AAPL", "LR_Sharpe": 0.760, "RF_Sharpe": 0.928, "Better": "RF"},
    {"Ticker": "NVDA", "LR_Sharpe": 0.707, "RF_Sharpe": 0.850, "Better": "RF"},
    {"Ticker": "IBM",  "LR_Sharpe": 0.680, "RF_Sharpe": 0.887, "Better": "RF"},
    {"Ticker": "JPM",  "LR_Sharpe": 0.043, "RF_Sharpe": 0.405, "Better": "RF"},
])

AUTO_SELECT = pd.DataFrame([
    {"Ticker": "TSLA", "Best_Strategy": "Logistic Regression", "Score": 1.1713, "Sharpe": 1.018, "Return_%": 236.07, "MaxDD_%": -36.60},
    {"Ticker": "NVDA", "Best_Strategy": "EMA Crossover",       "Score": 1.1044, "Sharpe": 1.062, "Return_%": 191.86, "MaxDD_%": -36.77},
    {"Ticker": "IBM",  "Best_Strategy": "Random Forest",       "Score": 1.0240, "Sharpe": 1.243, "Return_%":  65.71, "MaxDD_%":  -9.65},
    {"Ticker": "AAPL", "Best_Strategy": "EMA Crossover",       "Score": 0.8541, "Sharpe": 0.917, "Return_%":  67.43, "MaxDD_%": -13.09},
    {"Ticker": "JPM",  "Best_Strategy": "SMA Crossover",       "Score": 0.7898, "Sharpe": 0.874, "Return_%":  45.92, "MaxDD_%": -13.03},
])

TICKER_COLORS = {
    "NVDA": "#76b900",
    "TSLA": "#e31937",
    "AAPL": "#555555",
    "JPM":  "#003087",
    "IBM":  "#1f70c1",
}

# ── Data loader ───────────────────────────────────────────────────────────────

@st.cache_data(ttl=60)
def load_log():
    df = pd.read_csv("results/paper_trading_log.csv")
    df.columns = df.columns.str.strip()
    df["Timestamp"] = pd.to_datetime(df["Timestamp"])
    df["Date"] = df["Timestamp"].dt.date
    df["Signal"] = df["Signal"].astype(int)
    df["Price"] = pd.to_numeric(df["Price"], errors="coerce")
    return df.sort_values("Timestamp")


# ── Header ────────────────────────────────────────────────────────────────────

st.title("📈 Quantara Dashboard")
st.caption("Paper trading signals · Backtest results · Strategy selection · ML performance")

try:
    log = load_log()
    load_error = False
except Exception as e:
    st.error(f"Could not load paper_trading_log.csv: {e}")
    log = pd.DataFrame()
    load_error = True

# KPI cards — latest signal per ticker
if not load_error and not log.empty:
    latest = log.sort_values("Timestamp").groupby("Ticker").last().reset_index()
    cols = st.columns(len(latest))
    for col, (_, row) in zip(cols, latest.iterrows()):
        action = row.get("Action", "BUY" if row["Signal"] == 1 else "SELL")
        color = "#00c853" if row["Signal"] == 1 else "#d50000"
        col.markdown(
            f"""
            <div style='border:1px solid {color};border-radius:8px;padding:12px 10px;text-align:center'>
                <div style='font-size:1.1rem;font-weight:700;color:#e0e0e0'>{row['Ticker']}</div>
                <div style='font-size:1.5rem;font-weight:800;color:{color}'>{action}</div>
                <div style='font-size:0.9rem;color:#9e9e9e'>${row['Price']:.2f}</div>
                <div style='font-size:0.75rem;color:#616161'>{row['Strategy']}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
    st.markdown("---")

# ── Tabs ──────────────────────────────────────────────────────────────────────

tab1, tab2, tab3, tab4 = st.tabs(
    ["📋 Paper Trader", "📊 Strategy Performance", "🏆 Auto Selection", "🤖 ML Results"]
)

# ─────────────────────────────────────────────────────────────────────────────
# TAB 1 — Paper Trader
# ─────────────────────────────────────────────────────────────────────────────
with tab1:
    if load_error or log.empty:
        st.info("No paper trading data available.")
    else:
        st.subheader("Price History with Signals")

        ticker_sel = st.selectbox("Ticker", sorted(log["Ticker"].unique()), key="pt_ticker")
        tdf = log[log["Ticker"] == ticker_sel].copy()

        fig = go.Figure()

        # Price line
        fig.add_trace(go.Scatter(
            x=tdf["Timestamp"], y=tdf["Price"],
            mode="lines",
            name="Price",
            line=dict(color=TICKER_COLORS.get(ticker_sel, "#888"), width=2),
        ))

        # BUY markers
        buys = tdf[tdf["Signal"] == 1]
        fig.add_trace(go.Scatter(
            x=buys["Timestamp"], y=buys["Price"],
            mode="markers",
            name="BUY",
            marker=dict(symbol="triangle-up", size=12, color="#00c853"),
        ))

        # SELL markers
        sells = tdf[tdf["Signal"] == 0]
        fig.add_trace(go.Scatter(
            x=sells["Timestamp"], y=sells["Price"],
            mode="markers",
            name="SELL",
            marker=dict(symbol="triangle-down", size=12, color="#d50000"),
        ))

        fig.update_layout(
            height=400,
            xaxis_title="Date",
            yaxis_title="Price ($)",
            legend=dict(orientation="h", y=1.08),
            margin=dict(l=0, r=0, t=30, b=0),
            hovermode="x unified",
        )
        st.plotly_chart(fig, use_container_width=True)

        # Signal log table
        st.subheader("Signal Log")
        display = (
            tdf[["Timestamp", "Strategy", "Action", "Price", "Signal"]]
            .sort_values("Timestamp", ascending=False)
            .reset_index(drop=True)
        )
        display["Price"] = display["Price"].map("${:.2f}".format)

        def color_action(val):
            color = "#00c853" if val == "BUY" else "#d50000"
            return f"color: {color}; font-weight: bold"

        st.dataframe(
            display.style.map(color_action, subset=["Action"]),
            use_container_width=True,
            hide_index=True,
        )

        # Signal breakdown
        st.subheader("Signal Distribution")
        counts = tdf["Action"].value_counts().reset_index()
        counts.columns = ["Action", "Count"]
        bar = px.bar(
            counts, x="Action", y="Count",
            color="Action",
            color_discrete_map={"BUY": "#00c853", "SELL": "#d50000", "HOLD": "#ffd600"},
            text="Count",
        )
        bar.update_layout(showlegend=False, height=280, margin=dict(l=0, r=0, t=10, b=0))
        st.plotly_chart(bar, use_container_width=True)

# ─────────────────────────────────────────────────────────────────────────────
# TAB 2 — Strategy Performance
# ─────────────────────────────────────────────────────────────────────────────
with tab2:
    st.subheader("Multi-Strategy Backtest Results (2015–2024)")
    st.caption("Sorted by Sharpe Ratio · Test period only (walk-forward split)")

    ticker_filter = st.multiselect(
        "Filter by Ticker",
        options=sorted(MULTI_STRATEGY["Ticker"].unique()),
        default=sorted(MULTI_STRATEGY["Ticker"].unique()),
        key="ms_ticker",
    )
    filtered = MULTI_STRATEGY[MULTI_STRATEGY["Ticker"].isin(ticker_filter)].sort_values("Sharpe", ascending=False)

    def style_sharpe(val):
        if val >= 0.8:
            return "color: #00c853; font-weight: bold"
        elif val >= 0.5:
            return "color: #ffd600"
        return "color: #d50000"

    def style_dd(val):
        if val > -10:
            return "color: #00c853"
        elif val > -20:
            return "color: #ffd600"
        return "color: #d50000"

    st.dataframe(
        filtered.style
            .map(style_sharpe, subset=["Sharpe"])
            .map(style_dd, subset=["MaxDD_%"])
            .format({"Return_%": "{:.2f}%", "Sharpe": "{:.3f}", "MaxDD_%": "{:.2f}%"}),
        use_container_width=True,
        hide_index=True,
    )

    col_a, col_b = st.columns(2)

    with col_a:
        st.markdown("**Sharpe Ratio by Strategy & Ticker**")
        fig_sh = px.bar(
            filtered.sort_values("Sharpe", ascending=True),
            x="Sharpe", y="Ticker",
            color="Strategy",
            orientation="h",
            barmode="group",
            height=380,
        )
        fig_sh.update_layout(margin=dict(l=0, r=0, t=10, b=0), legend=dict(font=dict(size=10)))
        st.plotly_chart(fig_sh, use_container_width=True)

    with col_b:
        st.markdown("**Return vs Max Drawdown**")
        fig_rd = px.scatter(
            filtered,
            x="MaxDD_%", y="Return_%",
            color="Ticker",
            symbol="Strategy",
            size_max=12,
            hover_data=["Strategy", "Sharpe"],
            color_discrete_map=TICKER_COLORS,
            height=380,
        )
        fig_rd.update_layout(
            margin=dict(l=0, r=0, t=10, b=0),
            xaxis_title="Max Drawdown (%)",
            yaxis_title="Total Return (%)",
        )
        st.plotly_chart(fig_rd, use_container_width=True)

# ─────────────────────────────────────────────────────────────────────────────
# TAB 3 — Auto Selection
# ─────────────────────────────────────────────────────────────────────────────
with tab3:
    st.subheader("Auto-Selected Best Strategy per Ticker")
    st.caption("Composite Score = Sharpe×0.5 + (1−|MaxDD|)×0.3 + Return×0.2  |  Score > 1.0 = genuinely good")

    def style_score(val):
        if val >= 1.0:
            return "color: #00c853; font-weight: bold"
        elif val >= 0.5:
            return "color: #ffd600"
        return "color: #d50000"

    st.dataframe(
        AUTO_SELECT.sort_values("Score", ascending=False).style
            .map(style_score, subset=["Score"])
            .format({"Score": "{:.4f}", "Sharpe": "{:.3f}", "Return_%": "{:.2f}%", "MaxDD_%": "{:.2f}%"}),
        use_container_width=True,
        hide_index=True,
    )

    col_c, col_d = st.columns(2)

    with col_c:
        st.markdown("**Composite Score**")
        fig_score = px.bar(
            AUTO_SELECT.sort_values("Score", ascending=True),
            x="Score", y="Ticker",
            orientation="h",
            color="Score",
            color_continuous_scale=["#d50000", "#ffd600", "#00c853"],
            range_color=[0.5, 1.3],
            text=AUTO_SELECT.sort_values("Score", ascending=True)["Best_Strategy"],
            height=300,
        )
        fig_score.add_vline(x=1.0, line_dash="dash", line_color="#888", annotation_text="1.0 threshold")
        fig_score.update_layout(margin=dict(l=0, r=0, t=10, b=0), coloraxis_showscale=False)
        st.plotly_chart(fig_score, use_container_width=True)

    with col_d:
        st.markdown("**Sharpe vs Return (auto-selected strategies)**")
        fig_as = px.scatter(
            AUTO_SELECT,
            x="Sharpe", y="Return_%",
            text="Ticker",
            size="Score",
            color="Ticker",
            color_discrete_map=TICKER_COLORS,
            hover_data=["Best_Strategy", "MaxDD_%"],
            height=300,
        )
        fig_as.update_traces(textposition="top center")
        fig_as.update_layout(margin=dict(l=0, r=0, t=10, b=0), showlegend=False)
        st.plotly_chart(fig_as, use_container_width=True)

# ─────────────────────────────────────────────────────────────────────────────
# TAB 4 — ML Results
# ─────────────────────────────────────────────────────────────────────────────
with tab4:
    st.subheader("ML Model Comparison: Logistic Regression vs Random Forest")
    st.caption("Walk-forward split · 14 features · Sharpe on test period")

    st.markdown("**Key finding:** RF dominates stable, data-rich stocks · LR dominates highly volatile ones")

    def style_better(val):
        return "color: #00c853; font-weight: bold"

    st.dataframe(
        ML_RESULTS.style
            .map(style_better, subset=["Better"])
            .format({"LR_Sharpe": "{:.3f}", "RF_Sharpe": "{:.3f}"}),
        use_container_width=True,
        hide_index=True,
    )

    ml_long = ML_RESULTS.melt(
        id_vars=["Ticker", "Better"],
        value_vars=["LR_Sharpe", "RF_Sharpe"],
        var_name="Model",
        value_name="Sharpe",
    )
    ml_long["Model"] = ml_long["Model"].str.replace("_Sharpe", "")

    fig_ml = px.bar(
        ml_long,
        x="Ticker", y="Sharpe",
        color="Model",
        barmode="group",
        color_discrete_map={"LR": "#1f70c1", "RF": "#76b900"},
        text_auto=".3f",
        height=380,
    )
    fig_ml.update_layout(
        margin=dict(l=0, r=0, t=10, b=0),
        legend_title="Model",
        yaxis_title="Sharpe Ratio",
    )
    st.plotly_chart(fig_ml, use_container_width=True)

    st.info(
        "Neural network deferred — insufficient daily data (~625 training days) to outperform simpler models.",
        icon="ℹ️",
    )
