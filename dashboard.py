import streamlit as st
import os
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime
from alpaca.trading.client import TradingClient
from evaluation.performance import (
    build_trade_segments, reconcile_open_segments, ticker_summary, win_loss_stats,
    drawdown_tracker, signal_quality_score, detect_problems, build_event_feed
)

st.set_page_config(
    page_title="Quantara",
    layout="wide",
    page_icon="⚡",
    initial_sidebar_state="collapsed"
)

from streamlit_autorefresh import st_autorefresh
st_autorefresh(interval=60000, key="live_refresh")

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

# ── Alpaca Loader ───────────────────────────────────────────────────────────────────
@st.cache_data(ttl=60)
def load_alpaca_account():
    try:
        client = TradingClient(
            os.environ.get("ALPACA_KEY"),
            os.environ.get("ALPACA_SECRET"),
            paper=True
        )
        account = client.get_account()
        positions = client.get_all_positions()
        return account, positions
    except Exception as e:
        return None, []

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

    # ── Live Alpaca Portfolio Summary ─────────────────────────────────────
    st.markdown("<div class='q-label'>Live Portfolio</div>", unsafe_allow_html=True)

    account, positions = load_alpaca_account()

    if account:
        port_value = float(account.portfolio_value)
        cash = float(account.cash)
        equity = float(account.equity)
        last_equity = float(account.last_equity)
        today_pnl = equity - last_equity
        total_pnl = equity - 10000
        total_return = (total_pnl / 10000) * 100

        pnl_color = "#69f0ae" if total_pnl >= 0 else "#e05252"
        today_color = "#69f0ae" if today_pnl >= 0 else "#e05252"
        pnl_prefix = "+" if total_pnl >= 0 else ""
        today_prefix = "+" if today_pnl >= 0 else ""

        c1, c2, c3, c4, c5 = st.columns(5)
        c1.markdown(f"""
        <div style='background:#0f1629;border:1px solid #1e2d4a;border-radius:10px;padding:16px 20px'>
            <div class='q-label'>Portfolio Value</div>
            <div style='font-family:JetBrains Mono,monospace;font-size:1.4rem;color:#e2e8f0;font-weight:500'>${port_value:,.2f}</div>
            <div style='font-size:11px;color:#475569;margin-top:4px'>Live · Alpaca</div>
        </div>""", unsafe_allow_html=True)

        c2.markdown(f"""
        <div style='background:#0f1629;border:1px solid #1e2d4a;border-radius:10px;padding:16px 20px'>
            <div class='q-label'>Total P&L</div>
            <div style='font-family:JetBrains Mono,monospace;font-size:1.4rem;color:{pnl_color};font-weight:500'>{pnl_prefix}${total_pnl:,.2f}</div>
            <div style='font-size:11px;color:#475569;margin-top:4px'>vs $10,000 start</div>
        </div>""", unsafe_allow_html=True)

        c3.markdown(f"""
        <div style='background:#0f1629;border:1px solid #1e2d4a;border-radius:10px;padding:16px 20px'>
            <div class='q-label'>Total Return</div>
            <div style='font-family:JetBrains Mono,monospace;font-size:1.4rem;color:{pnl_color};font-weight:500'>{pnl_prefix}{total_return:.2f}%</div>
            <div style='font-size:11px;color:#475569;margin-top:4px'>Since Apr 29</div>
        </div>""", unsafe_allow_html=True)

        c4.markdown(f"""
        <div style='background:#0f1629;border:1px solid #1e2d4a;border-radius:10px;padding:16px 20px'>
            <div class='q-label'>Today's P&L</div>
            <div style='font-family:JetBrains Mono,monospace;font-size:1.4rem;color:{today_color};font-weight:500'>{today_prefix}${today_pnl:,.2f}</div>
            <div style='font-size:11px;color:#475569;margin-top:4px'>vs yesterday close</div>
        </div>""", unsafe_allow_html=True)

        buying_power = float(account.buying_power)
        c5.markdown(f"""
        <div style='background:#0f1629;border:1px solid #1e2d4a;border-radius:10px;padding:16px 20px'>
            <div class='q-label'>Buying Power</div>
            <div style='font-family:JetBrains Mono,monospace;font-size:1.4rem;color:#e2e8f0;font-weight:500'>${buying_power:,.2f}</div>
            <div style='font-size:11px;color:#475569;margin-top:4px'>Available to trade</div>
        </div>""", unsafe_allow_html=True)

        st.markdown("<div style='height:16px'></div>", unsafe_allow_html=True)

        # Open positions row
        if positions:
            st.markdown("<div class='q-label'>Open Positions</div>", unsafe_allow_html=True)
            pos_cols = st.columns(len(positions))
            for col, p in zip(pos_cols, positions):
                upl = float(p.unrealized_pl)
                uplpct = float(p.unrealized_plpc) * 100
                pc = "#69f0ae" if upl >= 0 else "#e05252"
                prefix = "+" if upl >= 0 else ""
                tc = TICKER_COLORS.get(p.symbol, "#94a3b8")
                col.markdown(f"""
                <div style='background:#0f1629;border:1px solid #1e2d4a;border-radius:10px;padding:14px 16px;text-align:center'>
                    <div style='font-family:JetBrains Mono,monospace;font-size:13px;color:{tc};font-weight:600;letter-spacing:1px'>{p.symbol}</div>
                    <div style='font-family:JetBrains Mono,monospace;font-size:13px;color:#e2e8f0;margin-top:4px'>${float(p.current_price):.2f}</div>
                    <div style='font-size:11px;color:{pc};margin-top:4px'>{prefix}${upl:.2f} ({prefix}{uplpct:.1f}%)</div>
                    <div style='font-size:10px;color:#475569;margin-top:4px'>entry ${float(p.avg_entry_price):.2f} · {float(p.qty):.4f} sh</div>
                </div>""", unsafe_allow_html=True)
    else:
        st.warning("Could not connect to Alpaca — showing cached data only.")

    st.markdown("<div style='height:20px'></div>", unsafe_allow_html=True)

# ── Tabs ───────────────────────────────────────────────────────────────────────
tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs([
    "📈  Paper Trader",
    "📊  Strategy Results", 
    "🏆  Auto Selection",
    "🤖  ML Analysis",
    "💰  Performance",
    "📋  Recent Trading Events"
])

# ══════════════════════════════════════════════════════════════════════════════
# TAB 1 — PAPER TRADER
# ══════════════════════════════════════════════════════════════════════════════
with tab1:
    if load_error or log.empty:
        st.info("No paper trading data available.")
    else:
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

# ══════════════════════════════════════════════════════════════════════════════
# TAB 5 — PERFORMANCE
# ══════════════════════════════════════════════════════════════════════════════
with tab5:
    if load_error or log.empty:
        st.info("No paper trading data available.")
    else:
        segments = build_trade_segments(log)
        account, positions = load_alpaca_account()
        segments = reconcile_open_segments(segments, positions)
        summary = ticker_summary(segments, log)
        stats = win_loss_stats(segments)
        drawdown = drawdown_tracker(log)
        quality = signal_quality_score(log)
        problems = detect_problems(summary, drawdown, quality)

        # ── Problem detection alerts (grouped by ticker) ─────────────────
        st.markdown("<div class='q-label'>System Alerts</div>", unsafe_allow_html=True)

        # Group flags by ticker
        from collections import defaultdict
        grouped = defaultdict(list)
        for p in problems:
            grouped[p["Ticker"]].append(p)

        sev_icon = {"CRITICAL": "🔴", "WARNING": "🟡", "OK": "🟢"}
        sev_color = {"CRITICAL": "#e05252", "WARNING": "#fbbf24", "OK": "#69f0ae"}

        for ticker, flags in grouped.items():
            if ticker == "—":
                st.markdown(f"<div style='background:rgba(105,240,174,0.06);border:1px solid #69f0ae33;border-radius:8px;padding:12px 16px;margin-bottom:8px;font-size:13px;color:#cbd5e1'>🟢 {flags[0]['Message']}</div>", unsafe_allow_html=True)
                continue

            # Header line — show all severity icons present for this ticker
            icons = " ".join(sev_icon[f["Severity"]] for f in flags)
            tc = TICKER_COLORS.get(ticker, "#94a3b8")
            worst_sev = "CRITICAL" if any(f["Severity"] == "CRITICAL" for f in flags) else "WARNING"
            border_color = sev_color[worst_sev]

            lines = "".join(
                f"<div style='padding:6px 0 6px 8px;border-left:2px solid {sev_color[f['Severity']]};margin-bottom:4px;font-size:12px;color:#cbd5e1'>{sev_icon[f['Severity']]} {f['Message']}</div>"
                for f in flags
            )

            card_html = f"<div style='background:#0f1629;border:1px solid {border_color}33;border-radius:10px;padding:14px 18px;margin-bottom:10px'><div style='display:flex;align-items:center;gap:8px;margin-bottom:8px'><span style='font-family:JetBrains Mono,monospace;font-size:14px;color:{tc};font-weight:600;letter-spacing:1px'>{ticker}</span><span>{icons}</span></div>{lines}</div>"
            st.markdown(card_html, unsafe_allow_html=True)

        st.markdown("<div style='height:24px'></div>", unsafe_allow_html=True)

        # ── Overall win/loss stats row ──────────────────────────────────────
        st.markdown("<div class='q-label'>Win / Loss Summary — All Closed Trades</div>",
                    unsafe_allow_html=True)

        c1, c2, c3, c4, c5 = st.columns(5)
        c1.markdown(f"""
        <div style='background:#0f1629;border:1px solid #1e2d4a;border-radius:10px;padding:16px 20px'>
            <div class='q-label'>Win Rate</div>
            <div style='font-family:JetBrains Mono,monospace;font-size:1.4rem;color:#e2e8f0;font-weight:500'>{stats['win_rate']:.1f}%</div>
        </div>""", unsafe_allow_html=True)

        c2.markdown(f"""
        <div style='background:#0f1629;border:1px solid #1e2d4a;border-radius:10px;padding:16px 20px'>
            <div class='q-label'>Total Trades</div>
            <div style='font-family:JetBrains Mono,monospace;font-size:1.4rem;color:#e2e8f0;font-weight:500'>{stats['total_trades']}</div>
        </div>""", unsafe_allow_html=True)

        c3.markdown(f"""
        <div style='background:#0f1629;border:1px solid #1e2d4a;border-radius:10px;padding:16px 20px'>
            <div class='q-label'>Avg Win</div>
            <div style='font-family:JetBrains Mono,monospace;font-size:1.4rem;color:#69f0ae;font-weight:500'>+${stats['avg_win']:.0f}</div>
        </div>""", unsafe_allow_html=True)

        c4.markdown(f"""
        <div style='background:#0f1629;border:1px solid #1e2d4a;border-radius:10px;padding:16px 20px'>
            <div class='q-label'>Avg Loss</div>
            <div style='font-family:JetBrains Mono,monospace;font-size:1.4rem;color:#e05252;font-weight:500'>${stats['avg_loss']:.0f}</div>
        </div>""", unsafe_allow_html=True)

        c5.markdown(f"""
        <div style='background:#0f1629;border:1px solid #1e2d4a;border-radius:10px;padding:16px 20px'>
            <div class='q-label'>Best / Worst Trade</div>
            <div style='font-family:JetBrains Mono,monospace;font-size:1rem;color:#69f0ae;font-weight:500'>+${stats['biggest_win']:.0f}</div>
            <div style='font-family:JetBrains Mono,monospace;font-size:1rem;color:#e05252;font-weight:500'>${stats['biggest_loss']:.0f}</div>
        </div>""", unsafe_allow_html=True)

        st.markdown("<div style='height:24px'></div>", unsafe_allow_html=True)

        # ── Per ticker cards with expandable history ────────────────────────
        st.markdown("<div class='q-label'>Per Ticker Breakdown</div>", unsafe_allow_html=True)

        for _, row in summary.sort_values("Total_PnL", ascending=False).iterrows():
            ticker = row["Ticker"]
            total_pnl = row["Total_PnL"]
            is_open = row["Is_Open"]
            trade_count = row["Trade_Count"]
            switch_flag = row["Switch_Flag"]
            switches = row["Strategy_Switches"]

            pnl_color = "#69f0ae" if total_pnl >= 0 else "#e05252"
            pnl_prefix = "+" if total_pnl >= 0 else ""
            asterisk = "*" if is_open else ""
            tc = TICKER_COLORS.get(ticker, "#94a3b8")

            switch_badge = ""
            if switch_flag:
                switch_badge = f"<span style='background:rgba(251,191,36,0.1);color:#fbbf24;border:1px solid rgba(251,191,36,0.3);border-radius:6px;padding:2px 8px;font-size:10px;margin-left:8px'>⚠ {switches} switch{'es' if switches > 1 else ''}</span>"

            header_html = f"<div style='background:#0f1629;border:1px solid #1e2d4a;border-radius:10px;padding:16px 20px;margin-bottom:4px;display:flex;justify-content:space-between;align-items:center'><div style='display:flex;align-items:center;gap:14px'><span style='font-family:JetBrains Mono,monospace;font-size:15px;color:{tc};font-weight:600;letter-spacing:1px'>{ticker}</span>{switch_badge}</div><div style='display:flex;align-items:center;gap:24px'><span style='font-size:12px;color:#94a3b8'>{trade_count} trades</span><span style='font-family:JetBrains Mono,monospace;font-size:16px;color:{pnl_color};font-weight:600'>{pnl_prefix}${total_pnl:.0f}{asterisk}</span></div></div>"
            st.markdown(header_html, unsafe_allow_html=True)

            with st.expander(f"View {ticker} trade history"):
                tseg = segments[segments["Ticker"] == ticker].sort_values("Entry_Date")
                display_seg = tseg[[
                    "Strategy", "Entry_Date", "Entry_Price",
                    "Exit_Date", "Exit_Price", "Duration_Days", "PnL", "PnL_Pct", "Status"
                ]].copy()

                display_seg["Entry_Date"] = display_seg["Entry_Date"].dt.strftime("%Y-%m-%d")
                display_seg["Exit_Date"] = display_seg.apply(
                    lambda r: "OPEN*" if r["Status"] == "OPEN" else r["Exit_Date"].strftime("%Y-%m-%d"),
                    axis=1
                )
                display_seg["Entry_Price"] = display_seg["Entry_Price"].map("${:.2f}".format)
                display_seg["Exit_Price"] = display_seg["Exit_Price"].map("${:.2f}".format)
                display_seg["PnL"] = display_seg.apply(
                    lambda r: f"{'+' if r['PnL'] >= 0 else ''}${r['PnL']:.0f}{'*' if r['Status']=='OPEN' else ''}",
                    axis=1
                )
                display_seg["PnL_Pct"] = display_seg["PnL_Pct"].map("{:+.2f}%".format)

                def color_pnl_pct(val):
                    pct = float(val.replace("%", "").replace("+", ""))
                    color = "#69f0ae" if pct >= 0 else "#e05252"
                    return f"color: {color}; font-weight: 600"

                st.dataframe(
                    display_seg.style.map(color_pnl_pct, subset=["PnL_Pct"]),
                    use_container_width=True,
                    hide_index=True,
                )

            st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)

        st.caption("Asterisk (*) indicates an open position — P&L unrealized and subject to change")
        
        st.markdown("<div style='height:24px'></div>", unsafe_allow_html=True)
        st.markdown("<div class='q-label'>Drawdown from Live Peak</div>", unsafe_allow_html=True)

        dd_display = drawdown.copy()
        dd_display["Peak_Date"] = dd_display["Peak_Date"].dt.strftime("%Y-%m-%d")
        dd_display = dd_display[[
            "Ticker", "Peak_Price", "Peak_Date", "Current_Price",
            "Current_Drawdown_Pct", "Max_Drawdown_Pct"
        ]]
        dd_display["Peak_Price"] = dd_display["Peak_Price"].map("${:.2f}".format)
        dd_display["Current_Price"] = dd_display["Current_Price"].map("${:.2f}".format)
        dd_display["Current_Drawdown_Pct"] = dd_display["Current_Drawdown_Pct"].map("{:.1f}%".format)
        dd_display["Max_Drawdown_Pct"] = dd_display["Max_Drawdown_Pct"].map("{:.1f}%".format)

        def color_dd(val):
            pct = float(val.replace("%", ""))
            if pct <= -15:
                return "color: #e05252; font-weight: 600"
            elif pct <= -5:
                return "color: #fbbf24"
            return "color: #69f0ae"

        st.dataframe(
            dd_display.style.map(color_dd, subset=["Current_Drawdown_Pct", "Max_Drawdown_Pct"]),
            use_container_width=True,
            hide_index=True,
        )

# ══════════════════════════════════════════════════════════════════════════════
# TAB 6 — RECENT TRADING EVENTS
# ══════════════════════════════════════════════════════════════════════════════
with tab6:
    if load_error or log.empty:
        st.info("No paper trading data available.")
    else:
        segments = build_trade_segments(log)
        account, positions = load_alpaca_account()
        segments = reconcile_open_segments(segments, positions)
        summary = ticker_summary(segments, log)
        events = build_event_feed(segments, summary, log)

        st.markdown("<div class='q-label'>What's Happened to Your Portfolio</div>", unsafe_allow_html=True)

        col_a, col_b, col_c = st.columns([2, 1, 1])
        with col_a:
            days_back = st.selectbox(
                "Show events from",
                options=[7, 14, 30, 90, 999],
                format_func=lambda x: "All time" if x == 999 else f"Last {x} days",
                index=1,
            )
        with col_b:
            ticker_options = ["All Tickers"] + sorted(log["Ticker"].unique().tolist())
            ticker_filter = st.selectbox("Filter by ticker", ticker_options)
        with col_c:
            sort_mode = st.selectbox("Sort by", ["Most Recent", "Severity"])

        cutoff = pd.Timestamp.now() - pd.Timedelta(days=days_back)
        filtered_events = [e for e in events if pd.Timestamp(e["Date"]) >= cutoff]
        if ticker_filter != "All Tickers":
            filtered_events = [e for e in filtered_events if e["Ticker"] == ticker_filter]
        
        if sort_mode == "Severity":
            SEVERITY_ORDER = {"CRITICAL": 0, "NEGATIVE": 1, "WARNING": 2, "POSITIVE": 3, "NEUTRAL": 4}
            filtered_events = sorted(
                filtered_events,
                key=lambda e: SEVERITY_ORDER.get(e["Severity"], 5)
            )

        st.markdown("<div style='height:12px'></div>", unsafe_allow_html=True)

        SEVERITY_COLORS = {
            "CRITICAL": "#e05252",
            "NEGATIVE": "#e05252",
            "POSITIVE": "#69f0ae",
            "WARNING": "#fbbf24",
            "NEUTRAL": "#475569",
        }
        SEVERITY_ICONS = {
            "CRITICAL": "🔴",
            "NEGATIVE": "🔸",
            "POSITIVE": "🟢",
            "WARNING": "🟡",
            "NEUTRAL": "⚪",
        }

        if not filtered_events:
            st.markdown(
                "<div style='text-align:center;padding:30px;color:#475569'>No events in this range.</div>",
                unsafe_allow_html=True
            )
        else:
            for e in filtered_events:
                sev = e["Severity"]
                color = SEVERITY_COLORS.get(sev, "#475569")
                icon = SEVERITY_ICONS.get(sev, "⚪")
                tc = TICKER_COLORS.get(e["Ticker"], "#94a3b8")
                date_str = pd.Timestamp(e["Date"]).strftime("%b %d, %Y · %I:%M %p")

                opacity = "1" if sev != "NEUTRAL" else "0.75"
                border_weight = "1px" if sev in ["NEGATIVE", "NEUTRAL"] else "1.5px"

                card_html = (
                    f"<div style='background:#0f1629;border-left:{border_weight} solid {color};"
                    f"border-top:1px solid #1e2d4a;border-right:1px solid #1e2d4a;"
                    f"border-bottom:1px solid #1e2d4a;border-radius:8px;padding:14px 18px;"
                    f"margin-bottom:8px;opacity:{opacity}'>"
                    f"<div style='display:flex;justify-content:space-between;align-items:center;margin-bottom:6px'>"
                    f"<span style='font-family:JetBrains Mono,monospace;font-size:13px;color:{tc};font-weight:600'>{icon} {e['Ticker']}</span>"
                    f"<span style='font-family:JetBrains Mono,monospace;font-size:11px;color:#475569'>{date_str}</span>"
                    f"</div>"
                    f"<div style='font-size:13px;color:#cbd5e1;line-height:1.5'>{e['Message']}</div>"
                    f"</div>"
                )
                st.markdown(card_html, unsafe_allow_html=True)