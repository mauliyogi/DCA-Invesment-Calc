import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go

LOT_SIZE = 100  # IDX: 1 lot = 100 shares

st.set_page_config(page_title="DCA Investment Simulator", page_icon="📈", layout="wide")

# ---------- Styling ----------
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Sora:wght@600;700;800&family=Inter:wght@400;500;600&display=swap');

html, body, [class*="css"]  { font-family: 'Inter', sans-serif; }

.block-container { padding-top: 2rem; padding-bottom: 3rem; }

h1, h2, h3 { font-family: 'Sora', sans-serif; }

.hero {
    background: linear-gradient(135deg, #0F3D3E 0%, #1B5E5A 60%, #2E8B7A 100%);
    padding: 2rem 2.2rem;
    border-radius: 16px;
    color: #F4F1EA;
    margin-bottom: 1.6rem;
}
.hero h1 {
    font-size: 2rem;
    margin: 0 0 .3rem 0;
    color: #F4F1EA;
    letter-spacing: -0.02em;
}
.hero p {
    margin: 0;
    color: #CFE8E2;
    font-size: 0.95rem;
}

.lot-note {
    background: #FFF7E8;
    border-left: 4px solid #D98E04;
    padding: .7rem 1rem;
    border-radius: 8px;
    font-size: 0.85rem;
    color: #6B4A05;
    margin: .8rem 0 1.2rem 0;
}

/* ---- Custom metric cards (replaces st.metric so text colors are controllable) ---- */
.metric-row { display: flex; gap: 1rem; margin-bottom: 1rem; }
.metric-card {
    flex: 1;
    background: #FFFFFF;
    border: 1px solid #E7E2D8;
    border-radius: 12px;
    padding: 1rem 1.2rem;
    box-shadow: 0 1px 3px rgba(15,61,62,0.06);
}
.metric-label {
    font-family: 'Inter', sans-serif;
    font-size: 0.82rem;
    color: #8A8273;
    margin-bottom: .35rem;
}
.metric-value {
    font-family: 'Sora', sans-serif;
    font-size: 1.5rem;
    font-weight: 700;
    color: #D98E04;
    line-height: 1.2;
}
.metric-sub {
    font-family: 'Inter', sans-serif;
    font-size: 0.85rem;
    font-weight: 600;
    margin-top: .3rem;
    display: flex;
    align-items: baseline;
    gap: .4rem;
}
.metric-sub.positive { color: #1E8A5F; }
.metric-sub.negative { color: #C0392B; }
.metric-sub .pct {
    font-variant-numeric: tabular-nums;
    min-width: 4.5ch;
    text-align: right;
}

.stButton button {
    background: #0F3D3E;
    color: #F4F1EA;
    border-radius: 10px;
    border: none;
    padding: 0.6rem 1.4rem;
    font-weight: 600;
    font-family: 'Sora', sans-serif;
    transition: background .15s ease;
}
.stButton button:hover { background: #2E8B7A; color: white; }

section[data-testid="stSidebar"] { background: #F4F1EA; }
</style>
""", unsafe_allow_html=True)

# ---------- Hero ----------
st.markdown("""
<div class="hero">
    <h1>📈 DCA Investment Simulator</h1>
    <p>Simulate dollar-cost averaging on any ticker — purchases are rounded down to whole lots, just like real IDX trading.</p>
</div>
""", unsafe_allow_html=True)

# ---------- Inputs ----------
with st.container():
    c0, c1, c2 = st.columns([1.2, 1, 1])
    ticker = c0.text_input("Ticker", "BBCA.JK")
    start = c1.date_input("Start", pd.Timestamp("2020-01-01"))
    end = c2.date_input("End", pd.Timestamp.today())

    c3, c4 = st.columns([1, 1])
    mode = c3.radio("Investment Method", ["By Amount (Rp)", "By Lots"], horizontal=True)
    freq = c4.selectbox("Frequency", ["Daily", "Weekly", "Monthly", "Quarterly", "Semiannual", "Yearly"])

    if mode == "By Amount (Rp)":
        amount = st.number_input("Investment per period (IDR)", 1000, 10_000_000_000, 1_000_000, 1000)
        lots_per_period = None
    else:
        lots_per_period = st.number_input("Lots to buy per period", 1, 1_000_000, 1, 1)
        amount = None

if mode == "By Amount (Rp)":
    st.markdown(
        f'<div class="lot-note">🧮 Purchases are rounded down to whole <b>lots</b> '
        f'(1 lot = {LOT_SIZE} shares). If the per-period investment isn\'t enough to buy '
        f'even 1 lot, that period is simply skipped (no purchase, no carryover).</div>',
        unsafe_allow_html=True
    )
else:
    st.markdown(
        f'<div class="lot-note">🧮 Each period, exactly <b>{{lots}} lot(s)</b> '
        f'({LOT_SIZE} shares × lots) are bought at the prevailing price, regardless of '
        f'how much cash that costs. This simulates a fixed-quantity buying plan instead '
        f'of a fixed-budget one.</div>'.replace("{lots}", str(lots_per_period)),
        unsafe_allow_html=True
    )

mapfreq = {"Daily": "B", "Weekly": "W-FRI", "Monthly": "MS", "Quarterly": "QS", "Semiannual": "2QS", "Yearly": "YS"}

run = st.button("🚀 Run Simulation", use_container_width=False)

if run:
    with st.spinner("Fetching price data and simulating purchases..."):
        df = yf.download(ticker, start=start, end=end, auto_adjust=False, progress=False)

        if df.empty:
            st.error("No data found for this ticker / date range. Double check the symbol (e.g. `BBCA.JK`).")
            st.stop()

        # yfinance sometimes returns MultiIndex columns even for a single ticker
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)

        close = df["Close"].dropna()
        sched = pd.date_range(pd.Timestamp(start), pd.Timestamp(end), freq=mapfreq[freq])

        rows = []
        total_lots = 0
        invested = 0  # cumulative cash actually deployed into shares

        for d in sched:
            idx = close.index.searchsorted(d)
            if idx >= len(close):
                break
            day = close.index[idx]
            price = float(close.iloc[idx])

            lot_cost = price * LOT_SIZE

            if mode == "By Amount (Rp)":
                lots = int(amount // lot_cost)   # 0 if not enough for even 1 lot
            else:
                lots = int(lots_per_period)      # fixed quantity every period

            total_beli = lots * lot_cost          # actual nominal spent this period

            total_lots += lots
            invested += total_beli
            shares = total_lots * LOT_SIZE
            portfolio = shares * price

            rows.append({
                "Date": day,
                "Price": price,
                "Lots Bought": lots,
                "Total Lot": total_lots,
                "Total Beli": total_beli,
                "Portfolio Value": portfolio,
            })

        res = pd.DataFrame(rows)

        if res.empty:
            st.warning("No purchases were made — the schedule didn't line up with any trading days in range.")
            st.stop()

        final_portfolio = res["Portfolio Value"].iloc[-1]
        final_invested = res["Total Beli"].sum()
        gain = final_portfolio - final_invested
        gain_pct = (gain / final_invested * 100) if final_invested else 0

    st.markdown("### Results")

    gain_class = "positive" if gain >= 0 else "negative"
    gain_sign = "+" if gain >= 0 else ""

    st.markdown(f"""
    <div class="metric-row">
        <div class="metric-card">
            <div class="metric-label">Total Beli (Cash Deployed)</div>
            <div class="metric-value">Rp {final_invested:,.0f}</div>
        </div>
        <div class="metric-card">
            <div class="metric-label">Portfolio Value</div>
            <div class="metric-value">Rp {final_portfolio:,.0f}</div>
        </div>
        <div class="metric-card">
            <div class="metric-label">Gain / Loss</div>
            <div class="metric-value">Rp {gain:,.0f}</div>
            <div class="metric-sub {gain_class}">
                <span class="pct">{gain_sign}{gain_pct:,.2f}%</span>
            </div>
        </div>
    </div>
    """, unsafe_allow_html=True)

    res["Cumulative Invested"] = res["Total Beli"].cumsum()

    # ---- Single combined tooltip per point (no more duplicate hover blocks) ----
    fig = go.Figure()
    fig.add_scatter(
        x=res["Date"], y=res["Cumulative Invested"], mode="lines", name="Money Invested",
        line=dict(color="#D98E04", width=2.5),
        customdata=res[["Price", "Portfolio Value"]],
        hovertemplate=(
            "<b>%{x|%d %b %Y}</b><br>"
            "Price: %{customdata[0]:,.2f}<br>"
            "Invested: Rp %{y:,.0f}<br>"
            "Portfolio: Rp %{customdata[1]:,.0f}"
            "<extra></extra>"
        ),
    )
    fig.add_scatter(
        x=res["Date"], y=res["Portfolio Value"], mode="lines", name="Portfolio Value",
        line=dict(color="#0F3D3E", width=2.5),
        fill="tonexty",
        fillcolor="rgba(46,139,122,0.12)",
        hoverinfo="skip",  # info already shown by the "Money Invested" trace above
    )
    fig.update_layout(
        template="plotly_white",
        font=dict(family="Inter, sans-serif", color="#3A352C"),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        margin=dict(t=40, l=10, r=10, b=10),
        hovermode="x unified",
        plot_bgcolor="rgba(0,0,0,0)",
        paper_bgcolor="rgba(0,0,0,0)",
    )
    st.plotly_chart(fig, use_container_width=True)

    st.markdown("### Purchase Log")
    st.dataframe(
        res.style.format({
            "Price": "{:,.2f}",
            "Total Beli": "{:,.0f}",
            "Portfolio Value": "{:,.0f}",
            "Cumulative Invested": "{:,.0f}",
        }),
        use_container_width=True
    )

    st.download_button("⬇ Download CSV", res.to_csv(index=False), "simulation.csv", "text/csv")
