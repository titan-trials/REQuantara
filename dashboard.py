import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime

st.set_page_config(
    page_title="Quantara",
    layout="wide",
    page_icon="⚡",
    initial_sidebar_state="collapsed"
)

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&family=JetBrains+Mono:wght@400;500&display=swap');

html, body, [class*="css"] {
    font-family: 'Inter', sans-serif;
    background-color: #0a0e1a;
    color: #cbd5e1;
}
.stApp { background-color: #0a0e1a; }
#MainMenu, footer, header { visibility: hidden; }
.block-container { padding: 2rem 2.5rem; max-width: 100%; }

/* Tabs */
.stTabs [data-baseweb="tab-list"] {
    background: #0f1629;
    border-radius: 8px;
    padding: 4px;
    gap: 2px;
    border: 1px solid #1e2d4a;
}
.stTabs [data-baseweb="tab"] {
    background: transparent;
    border-radius: 6px;
    color: #94a3b8;
    font-family: 'Inter', sans-serif;
    font-size: 13px;
    font-weight: 500;
    padding: 8px 20px;
    letter-spacing: 0.3px;
}
.stTabs [aria-selected="true"] {
    background: #1e2d4a !important;
    color: #e2e8f0 !important;
}

/* Metrics */
[data-testid="metric-container"] {
    background: #0f1629;
    border: 1px solid #1e2d4a;
    border-radius: 10px;
    padding: 20px;
}
[data-testid="metric-container"] label {
    color: #94a3b8 !important;
    font-size: 11px !important;
    font-weight: 600 !important;
    letter-spacing: 1.5px !important;
    text-transform: uppercase !important;
}
[data-testid="metric-container"] [data-testid="stMetricValue"] {
    font-family: 'JetBrains Mono', monospace !important;
    font-size: 1.6rem !important;
    color: #e2e8f0 !important;
    font-weight: 500 !important;
}

/* Cards */
.q-card {
    background: #0f1629;
    border: 1px solid #1e2d4a;
    border-radius: 10px;
    padding: 20px 24px;
    margin-bottom: 16px;
}
.q-label {
    font-size: 10px;
    font-weight: 700;
    letter-spacing: 2px;
    text-transform: uppercase;
    color: #94a3b8;
    margin-bottom: 12px;
}
.q-ticker {
    font-family: 'JetBrains Mono', monospace;
    font-size: 13px;
    font-weight: 500;
    letter-spacing: 1px;
}
.q-mono {
    font-family: 'JetBrains Mono', monospace;
}

/* Signal cards */
.sig-card {
    border-radius: 10px;
    padding: 20px 16px;
    text-align: center;
    border: 1px solid;
}
</style>
""", unsafe_allow_html=True)

# ── Static data ────────────────────────────────────────────────────────────────
MULTI_STRATEGY = pd.DataFrame([
    {"Ticker":"NVDA","Strategy":"EMA Crossover","Return_%":138.72,"Sharpe":0.973,"MaxDD_%":-36.77},
    {"Ticker":"NVDA","Strategy":"Bollinger Bands","Return_%":21.47,"Sharpe":0.820,"MaxDD_%":-9.94},
    {"Ticker":"NVDA","Strategy":"SMA Crossover","Return_%":88.41,"Sharpe":0.807,"MaxDD_%":-39.69},
    {"Ticker":"AAPL","Strategy":"EMA Crossover","Return_%":44.30,"Sharpe":0.766,"MaxDD_%":-13.20},
    {"Ticker":"JPM","Strategy":"SMA Crossover","Return_%":34.08,"Sharpe":0.755,"MaxDD_%":-13.00},
    {"Ticker":"NVDA","Strategy":"SMA+RSI Combined","Return_%":59.09,"Sharpe":0.725,"MaxDD_%":-37.44},
    {"Ticker":"AAPL","Strategy":"SMA+RSI Combined","Return_%":26.70,"Sharpe":0.706,"MaxDD_%":-14.26},
    {"Ticker":"AAPL","Strategy":"SMA Crossover","Return_%":34.28,"Sharpe":0.703,"MaxDD_%":-15.66},
    {"Ticker":"TSLA","Strategy":"EMA Crossover","Return_%":107.15,"Sharpe":0.702,"MaxDD_%":-43.15},
    {"Ticker":"JPM","Strategy":"SMA+RSI Combined","Return_%":23.58,"Sharpe":0.629,"MaxDD_%":-9.46},
    {"Ticker":"TSLA","Strategy":"SMA Crossover","Return_%":68.52,"Sharpe":0.606,"MaxDD_%":-31.35},
    {"Ticker":"TSLA","Strategy":"SMA+RSI Combined","Return_%":30.50,"Sharpe":0.437,"MaxDD_%":-27.70},
    {"Ticker":"JPM","Strategy":"Bollinger Bands","Return_%":9.49,"Sharpe":0.357,"MaxDD_%":-8.44},
    {"Ticker":"JPM","Strategy":"EMA Crossover","Return_%":10.61,"Sharpe":0.305,"MaxDD_%":-15.21},
    {"Ticker":"TSLA","Strategy":"Bollinger Bands","Return_%":7.86,"Sharpe":0.300,"MaxDD_%":-8.45},
    {"Ticker":"AAPL","Strategy":"Bollinger Bands","Return_%":5.25,"Sharpe":0.288,"MaxDD_%":-4.14},
])

AUTO_SELECT = pd.DataFrame([
    {"Ticker":"TSLA","Best_Strategy":"Logistic Regression","Score":1.1713,"Sharpe":1.018,"Return_%":236.07,"MaxDD_%":-36.60},
    {"Ticker":"NVDA","Best_Strategy":"EMA Crossover","Score":1.1044,"Sharpe":1.062,"Return_%":191.86,"MaxDD_%":-36.77},
    {"Ticker":"IBM","Best_Strategy":"Random Forest","Score":1.0240,"Sharpe":1.243,"Return_%":65.71,"MaxDD_%":-9.65},
    {"Ticker":"AAPL","Best_Strategy":"EMA Crossover","Score":0.8541,"Sharpe":0.917,"Return_%":67.43,"MaxDD_%":-13.09},
    {"Ticker":"JPM","Best_Strategy":"SMA Crossover","Score":0.7898,"Sharpe":0.874,"Return_%":45.92,"MaxDD_%":-13.03},
])

ML_RESULTS = pd.DataFrame([
    {"Ticker":"TSLA","LR_Sharpe":1.252,"RF_Sharpe":0.675,"Better":"LR"},
    {"Ticker":"AAPL","LR_Sharpe":0.760,"RF_Sharpe":0.928,"Better":"RF"},
    {"Ticker":"NVDA","LR_Sharpe":0.707,"RF_Sharpe":0.850,"Better":"RF"},
    {"Ticker":"IBM","LR_Sharpe":0.680,"RF_Sharpe":0.887,"Better":"RF"},
    {"Ticker":"JPM","LR_Sharpe":0.043,"RF_Sharpe":0.405,"Better":"RF"},
])

TICKER_COLORS = {
    "NVDA": "#76b900",
    "TSLA": "#e05252",
    "AAPL": "#94a3b8",
    "JPM":  "#4fc3f7",
    "IBM":  "#818cf8",
}

ENTRY_PRICES = {
    "NVDA": 213.17,
    "TSLA": 376.02,
    "AAPL": 270.71,
    "JPM":  311.45,
    "IBM":  233.04,
}

def plot_cfg():
    return dict(
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(family="Inter", color="#94a3b8", size=11),
        margin=dict(l=0, r=0, t=20, b=0),
        xaxis=dict(gridcolor="#1e2d4a", linecolor="#1e2d4a"),
        yaxis=dict(gridcolor="#1e2d4a", linecolor="#1e2d4a"),
    )

# ── Data loader ────────────────────────────────────────────────────────────────
@st.cache_data(ttl=300)
def load_log():
    df = pd.read_csv("results/paper_trading_log.csv")
    df.columns = df.columns.str.strip()
    df["Timestamp"] = pd.to_datetime(df["Timestamp"], format="mixed")
    df["Date"] = df["Timestamp"].dt.date
    df["Signal"] = pd.to_numeric(df["Signal"], errors="coerce").fillna(0).astype(int)
    df["Price"] = pd.to_numeric(df["Price"], errors="coerce")
    return df.sort_values("Timestamp")

# ── Header ─────────────────────────────────────────────────────────────────────
st.markdown("""
<div style='display:flex;align-items:center;justify-content:space-between;
            padding-bottom:24px;border-bottom:1px solid #1e2d4a;margin-bottom:28px'>
    <div>
        <div style='font-family:JetBrains Mono,monospace;font-size:22px;
                    color:#e2e8f0;letter-spacing:4px;font-weight:500'>
            QUANTARA
        </div>
        <div style='font-size:12px;color:#94a3b8;margin-top:4px;letter-spacing:0.5px'>
            Quantitative Trading Intelligence · Daily Signal System
        </div>
    </div>
    <div style='display:flex;align-items:center;gap:8px'>
        <div style='width:7px;height:7px;background:#69f0ae;border-radius:50%;
                    box-shadow:0 0 6px #69f0ae'></div>
        <span style='font-family:JetBrains Mono,monospace;font-size:11px;
                     color:#69f0ae;letter-spacing:1px'>LIVE</span>
    </div>
</div>
""", unsafe_allow_html=True)

# ── Load data ──────────────────────────────────────────────────────────────────
try:
    log = load_log()
    load_error = False
except Exception as e:
    st.error(f"Could not load paper trading log: {e}")
    log = pd.DataFrame()
    load_error = True

# ── Signal cards ───────────────────────────────────────────────────────────────
if not load_error and not log.empty:
    latest = log.groupby("Ticker").last().reset_index()
    
    st.markdown("<div class='q-label'>Current Signals</div>", unsafe_allow_html=True)
    cols = st.columns(5)
    
    for col, ticker in zip(cols, ["NVDA", "TSLA", "AAPL", "JPM", "IBM"]):
        row = latest[latest["Ticker"] == ticker]
        if row.empty:
            continue
        row = row.iloc[0]
        
        signal = row["Signal"]
        price = row["Price"]
        strategy = row["Strategy"]
        action = "BUY" if signal == 1 else "SELL"
        
        entry = ENTRY_PRICES.get(ticker, price)
        pnl_pct = ((price - entry) / entry) * 100
        
        border_color = "#69f0ae" if signal == 1 else "#e05252"
        signal_color = "#69f0ae" if signal == 1 else "#e05252"
        pnl_color = "#69f0ae" if pnl_pct >= 0 else "#e05252"
        pnl_prefix = "+" if pnl_pct >= 0 else ""
        tc = TICKER_COLORS.get(ticker, "#94a3b8")
        
        col.markdown(f"""
        <div style='background:#0f1629;border:1px solid {border_color}33;
                    border-radius:10px;padding:18px 14px;text-align:center'>
            <div style='font-family:JetBrains Mono,monospace;font-size:15px;
                        color:{tc};font-weight:600;letter-spacing:2px;
                        margin-bottom:10px'>{ticker}</div>
            <div style='font-family:JetBrains Mono,monospace;font-size:22px;
                        font-weight:700;color:{signal_color};
                        margin-bottom:8px'>{action}</div>
            <div style='font-family:JetBrains Mono,monospace;font-size:13px;
                        color:#e2e8f0;margin-bottom:4px'>${price:.2f}</div>
            <div style='font-size:12px;color:{pnl_color};font-family:JetBrains Mono,monospace;
                        margin-bottom:8px'>{pnl_prefix}{pnl_pct:.1f}% since entry</div>
            <div style='font-size:10px;color:#94a3b8;letter-spacing:0.5px'>{strategy}</div>
        </div>
        """, unsafe_allow_html=True)

    st.markdown("<div style='height:28px'></div>", unsafe_allow_html=True)

# ── Tabs ───────────────────────────────────────────────────────────────────────
tab1, tab2, tab3, tab4 = st.tabs([
    "📈  Paper Trader",
    "📊  Strategy Results", 
    "🏆  Auto Selection",
    "🤖  ML Analysis"
])

# ══════════════════════════════════════════════════════════════════════════════
# TAB 1 — PAPER TRADER
# ══════════════════════════════════════════════════════════════════════════════
with tab1:
    if load_error or log.empty:
        st.info("No paper trading data available.")
    else:
        # Performance since entry
        st.markdown("<div class='q-label'>Performance Since Entry (Apr 29)</div>",
                    unsafe_allow_html=True)
        
        latest_prices = log.groupby("Ticker")["Price"].last()
        perf_data = []
        for ticker, entry in ENTRY_PRICES.items():
            if ticker in latest_prices.index:
                current = latest_prices[ticker]
                pnl_pct = ((current - entry) / entry) * 100
                pnl_dollar = (current - entry) / entry * 2000
                perf_data.append({
                    "Ticker": ticker,
                    "Entry": entry,
                    "Current": current,
                    "Return %": pnl_pct,
                    "P&L ($2k position)": pnl_dollar
                })
        
        perf_df = pd.DataFrame(perf_data)
        
        cols = st.columns(5)
        for col, (_, row) in zip(cols, perf_df.iterrows()):
            pnl = row["Return %"]
            color = "#69f0ae" if pnl >= 0 else "#e05252"
            prefix = "+" if pnl >= 0 else ""
            col.metric(
                row["Ticker"],
                f"{prefix}{pnl:.1f}%",
                f"${row['P&L ($2k position)']:+.0f}"
            )
        
        st.markdown("<div style='height:20px'></div>", unsafe_allow_html=True)

        # Price chart
        st.markdown("<div class='q-label'>Price History</div>", unsafe_allow_html=True)
        
        ticker_sel = st.selectbox(
            "Select Ticker",
            sorted(log["Ticker"].unique()),
            label_visibility="collapsed"
        )
        
        tdf = log[log["Ticker"] == ticker_sel].copy()
        tc = TICKER_COLORS.get(ticker_sel, "#94a3b8")
        
        fig = go.Figure()
        fig.add_trace(go.Scatter(
            x=tdf["Timestamp"], y=tdf["Price"],
            mode="lines",
            name="Price",
            line=dict(color=tc, width=2),
        ))
        
        buys = tdf[tdf["Signal"] == 1]
        sells = tdf[tdf["Signal"] == 0]
        
        fig.add_trace(go.Scatter(
            x=buys["Timestamp"], y=buys["Price"],
            mode="markers", name="BUY",
            marker=dict(symbol="triangle-up", size=10, color="#69f0ae"),
        ))
        fig.add_trace(go.Scatter(
            x=sells["Timestamp"], y=sells["Price"],
            mode="markers", name="SELL",
            marker=dict(symbol="triangle-down", size=10, color="#e05252"),
        ))
        
        entry_price = ENTRY_PRICES.get(ticker_sel)
        if entry_price:
            fig.add_hline(
                y=entry_price,
                line_dash="dash",
                line_color="#94a3b8",
                annotation_text=f"Entry ${entry_price}",
                annotation_font_color="#94a3b8",
                annotation_font_size=10,
            )
        
        fig.update_layout(
            **plot_cfg(),
            height=380,
            xaxis_title=None,
            yaxis_title="Price ($)",
            legend=dict(orientation="h", y=1.08),
            hovermode="x unified",
        )
        st.plotly_chart(fig, use_container_width=True)

        # Signal log
        st.markdown("<div class='q-label'>Signal Log</div>", unsafe_allow_html=True)
        
        display = (
            tdf[["Timestamp", "Strategy", "Action", "Price", "Signal"]]
            .sort_values("Timestamp", ascending=False)
            .reset_index(drop=True)
        )
        display["Price"] = display["Price"].map("${:.2f}".format)
        display["Timestamp"] = display["Timestamp"].dt.strftime("%Y-%m-%d %H:%M")

        def color_action(val):
            color = "#69f0ae" if val == "BUY" else "#e05252"
            return f"color: {color}; font-weight: 600"

        for _, row in display.iterrows():
            action = row["Action"]
            ac = "#69f0ae" if action == "BUY" else "#e05252"
            st.markdown(f"""
            <div style='background:#0f1629;border:1px solid #1e2d4a;border-radius:8px;
                        padding:12px 16px;margin-bottom:6px;display:flex;
                        justify-content:space-between;align-items:center'>
                <div style='font-family:JetBrains Mono,monospace;font-size:11px;
                            color:#94a3b8'>{row['Timestamp']}</div>
                <div style='font-size:12px;color:#94a3b8'>{row['Strategy']}</div>
                <div style='font-family:JetBrains Mono,monospace;font-size:13px;
                            font-weight:600;color:{ac}'>{action}</div>
                <div style='font-family:JetBrains Mono,monospace;font-size:13px;
                            color:#e2e8f0'>{row['Price']}</div>
            </div>
            """, unsafe_allow_html=True)

# ══════════════════════════════════════════════════════════════════════════════
# TAB 2 — STRATEGY RESULTS
# ══════════════════════════════════════════════════════════════════════════════
with tab2:
    st.markdown("<div class='q-label'>Multi-Strategy Backtest · 2015–2024</div>",
                unsafe_allow_html=True)

    ticker_filter = st.multiselect(
        "Filter by Ticker",
        options=sorted(MULTI_STRATEGY["Ticker"].unique()),
        default=sorted(MULTI_STRATEGY["Ticker"].unique()),
    )
    filtered = MULTI_STRATEGY[
        MULTI_STRATEGY["Ticker"].isin(ticker_filter)
    ].sort_values("Sharpe", ascending=False)

    def style_sharpe(val):
        if val >= 0.8: return "color: #69f0ae; font-weight: 600"
        elif val >= 0.5: return "color: #fbbf24"
        return "color: #e05252"

    def style_dd(val):
        if val > -10: return "color: #69f0ae"
        elif val > -20: return "color: #fbbf24"
        return "color: #e05252"

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
        st.markdown("<div class='q-label' style='margin-top:20px'>Sharpe by Strategy</div>",
                    unsafe_allow_html=True)
        fig = px.bar(
            filtered.sort_values("Sharpe", ascending=True),
            x="Sharpe", y="Ticker", color="Strategy",
            orientation="h", barmode="group", height=340,
        )
        fig.update_layout(**plot_cfg())
        st.plotly_chart(fig, use_container_width=True)

    with col_b:
        st.markdown("<div class='q-label' style='margin-top:20px'>Return vs Drawdown</div>",
                    unsafe_allow_html=True)
        fig = px.scatter(
            filtered, x="MaxDD_%", y="Return_%",
            color="Ticker", symbol="Strategy",
            hover_data=["Strategy", "Sharpe"],
            color_discrete_map=TICKER_COLORS,
            height=340,
        )
        fig.update_layout(
            **plot_cfg(),
            xaxis_title="Max Drawdown (%)",
            yaxis_title="Total Return (%)",
        )
        st.plotly_chart(fig, use_container_width=True)

# ══════════════════════════════════════════════════════════════════════════════
# TAB 3 — AUTO SELECTION
# ══════════════════════════════════════════════════════════════════════════════
with tab3:
    st.markdown("<div class='q-label'>Auto-Selected Best Strategy per Ticker</div>",
                unsafe_allow_html=True)
    st.caption("Score = Sharpe×0.5 + (1−|MaxDD|)×0.3 + Return×0.2  ·  Score > 1.0 = genuinely good")

    def style_score(val):
        if val >= 1.0: return "color: #69f0ae; font-weight: 600"
        elif val >= 0.5: return "color: #fbbf24"
        return "color: #e05252"

    st.dataframe(
        AUTO_SELECT.sort_values("Score", ascending=False).style
            .map(style_score, subset=["Score"])
            .format({
                "Score": "{:.4f}",
                "Sharpe": "{:.3f}",
                "Return_%": "{:.2f}%",
                "MaxDD_%": "{:.2f}%"
            }),
        use_container_width=True,
        hide_index=True,
    )

    col_c, col_d = st.columns(2)
    with col_c:
        st.markdown("<div class='q-label' style='margin-top:20px'>Composite Score</div>",
                    unsafe_allow_html=True)
        fig = px.bar(
            AUTO_SELECT.sort_values("Score", ascending=True),
            x="Score", y="Ticker", orientation="h",
            color="Score",
            color_continuous_scale=["#e05252", "#fbbf24", "#69f0ae"],
            range_color=[0.5, 1.3],
            text=AUTO_SELECT.sort_values("Score", ascending=True)["Best_Strategy"],
            height=280,
        )
        fig.add_vline(x=1.0, line_dash="dash", line_color="#94a3b8",
                      annotation_text="1.0 threshold",
                      annotation_font_color="#94a3b8",
                      annotation_font_size=10)
        fig.update_layout(**plot_cfg(), coloraxis_showscale=False)
        st.plotly_chart(fig, use_container_width=True)

    with col_d:
        st.markdown("<div class='q-label' style='margin-top:20px'>Sharpe vs Return</div>",
                    unsafe_allow_html=True)
        fig = px.scatter(
            AUTO_SELECT, x="Sharpe", y="Return_%",
            text="Ticker", size="Score",
            color="Ticker",
            color_discrete_map=TICKER_COLORS,
            hover_data=["Best_Strategy", "MaxDD_%"],
            height=280,
        )
        fig.update_traces(textposition="top center")
        fig.update_layout(**plot_cfg(), showlegend=False)
        st.plotly_chart(fig, use_container_width=True)

# ══════════════════════════════════════════════════════════════════════════════
# TAB 4 — ML ANALYSIS
# ══════════════════════════════════════════════════════════════════════════════
with tab4:
    st.markdown("<div class='q-label'>ML Model Comparison · LR vs Random Forest</div>",
                unsafe_allow_html=True)
    st.caption("Walk-forward split · 14 features · Sharpe on unseen test period")

    st.dataframe(
        ML_RESULTS.style.format({
            "LR_Sharpe": "{:.3f}",
            "RF_Sharpe": "{:.3f}"
        }),
        use_container_width=True,
        hide_index=True,
    )

    ml_long = ML_RESULTS.melt(
        id_vars=["Ticker", "Better"],
        value_vars=["LR_Sharpe", "RF_Sharpe"],
        var_name="Model", value_name="Sharpe"
    )
    ml_long["Model"] = ml_long["Model"].str.replace("_Sharpe", "")

    fig = px.bar(
        ml_long, x="Ticker", y="Sharpe",
        color="Model", barmode="group",
        color_discrete_map={"LR": "#4fc3f7", "RF": "#76b900"},
        text_auto=".3f", height=340,
    )
    fig.update_layout(**plot_cfg(), legend_title="Model", yaxis_title="Sharpe Ratio")
    st.plotly_chart(fig, use_container_width=True)

    st.markdown("<div style='height:16px'></div>", unsafe_allow_html=True)
    
    col1, col2 = st.columns(2)
    with col1:
        st.markdown("""
        <div class='q-card'>
            <div class='q-label'>Key Finding</div>
            <div style='font-size:13px;line-height:1.8;color:#94a3b8'>
                <b style='color:#e05252'>RF dominates</b> stable, data-rich stocks — AAPL, NVDA, IBM, JPM<br><br>
                <b style='color:#4fc3f7'>LR dominates</b> highly volatile momentum stocks — TSLA<br><br>
                More training data (2015 vs 2020 start) significantly improves all models.
            </div>
        </div>
        """, unsafe_allow_html=True)
    with col2:
        st.markdown("""
        <div class='q-card'>
            <div class='q-label'>Why No Neural Network</div>
            <div style='font-size:13px;line-height:1.8;color:#94a3b8'>
                Daily closes give ~625 training samples per ticker.<br><br>
                Neural networks need 10,000+ samples to outperform simpler models.<br><br>
                NN deferred to Quantara NN (minute data project).
            </div>
        </div>
        """, unsafe_allow_html=True)

    st.markdown("""
    <div class='q-card' style='margin-top:4px'>
        <div class='q-label'>14 Engineered Features</div>
        <div style='font-family:JetBrains Mono,monospace;font-size:11px;
                    color:#94a3b8;line-height:2.2;letter-spacing:0.5px'>
            EMA_gap · RSI · BB_position · Momentum_5 · Momentum_10 · Momentum_20 · 
            Momentum_30 · RSI_slope · Volatility_10 · Volatility_20 · SMA_gap · 
            Price_vs_SMA20 · Price_vs_SMA50 · BB_width
        </div>
    </div>
    """, unsafe_allow_html=True)