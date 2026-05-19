import pandas as pd
import streamlit as st
import streamlit.components.v1 as components


# ============================================================
# PAGE CONFIG
# ============================================================

st.set_page_config(
    page_title="Portfolio Dashboard",
    layout="wide"
)


# ============================================================
# CSV LADEN
# ============================================================

df = pd.read_csv(
    "portfolio_analysis.csv",
    sep=";"
)


# ============================================================
# TITEL
# ============================================================

st.title("📊 Advanced Portfolio Dashboard")

st.write(
    "Aktienanalyse mit Momentum, RSI, EMA, "
    "Turnaround-Erkennung, Risiko und Dividenden."
)
# ============================================================
# LEGENDE
# ============================================================

with st.expander("📖 Dashboard Legende"):

    st.markdown("""

    ## ⭐ Ratings

    - **STRONG BUY** → sehr starke technische Struktur
    - **BUY** → bullish
    - **HOLD** → neutral
    - **TURNAROUND** → mögliche Trendwende
    - **WATCH - OVERBOUGHT** → stark gelaufen, Rücksetzer möglich
    - **AVOID** → schwache technische Lage

    ---

    ## 📈 Score System

    Jede Aktie bekommt Punkte für:

    - Kurs über EMA20
    - Kurs über EMA50
    - Kurs über EMA100
    - EMA20 > EMA50
    - EMA50 > EMA100
    - positive Wochenperformance
    - positive Monatsperformance
    - gesunder RSI

    Maximaler Score: **8**

    ---

    ## 📉 RSI

    RSI = Relative Strength Index

    - unter 30 → überverkauft
    - 30–70 → gesund
    - über 70 → heiß gelaufen

    ---

    ## 🔄 Turnaround Kandidat

    Eine Aktie gilt als Turnaround-Kandidat wenn:

    - sie zuvor stark gefallen ist
    - aber Momentum zurückkommt
    - Kurs EMA20 zurückerobert
    - RSI sich stabilisiert

    ---

    ## ⚠ Risk Level

    Risiko basiert auf:

    - RSI
    - Volatilität
    - Abstand zum EMA20
    - Beta

    Kategorien:

    - LOW RISK
    - MEDIUM RISK
    - HIGH RISK

    ---

    ## 🛑 Stop-Loss-Idee

    Vorschlag basierend auf EMA50.

    Kein Finanzrat.
    Nur technische Orientierung.

    ---

    ## 📍 52W High Abstand

    Zeigt wie weit die Aktie vom
    52-Wochen-Hoch entfernt ist.

    Beispiel:

    - -5% → nahe am Hoch
    - -40% → stark gefallen

    """)


# ============================================================
# SIDEBAR
# ============================================================

st.sidebar.header("Filter")
search_text = st.sidebar.text_input(
    "🔎 Aktie suchen",
    ""
)

ratings = st.sidebar.multiselect(
    "Ratings",
    options=df["Rating"].unique(),
    default=df["Rating"].unique()
)


risk_levels = st.sidebar.multiselect(
    "Risk Level",
    options=df["Risk Level"].unique(),
    default=df["Risk Level"].unique()
)


turnaround_only = st.sidebar.checkbox(
    "Nur Turnaround Kandidaten"
)


# ============================================================
# FILTER
# ============================================================

df_filtered = df[
    (df["Rating"].isin(ratings))
    &
    (df["Risk Level"].isin(risk_levels))
]
if search_text != "":

    df_filtered = df_filtered[
        df_filtered["Company"]
        .str.contains(
            search_text,
            case=False,
            na=False
        )
        |
        df_filtered["Ticker"]
        .str.contains(
            search_text,
            case=False,
            na=False
        )
    ]

if turnaround_only:
    df_filtered = df_filtered[
        df_filtered["Turnaround Candidate"] == "YES"
    ]


# ============================================================
# METRICS
# ============================================================

st.divider()

col1, col2, col3, col4, col5 = st.columns(5)

col1.metric(
    "Aktien",
    len(df_filtered)
)

col2.metric(
    "Ø Score",
    round(df_filtered["Score"].mean(), 2)
)

col3.metric(
    "Beste 1M %",
    f"{round(df_filtered['1M %'].max(), 2)}%"
)

col4.metric(
    "Turnaround",
    (
        df_filtered["Turnaround Candidate"]
        == "YES"
    ).sum()
)

col5.metric(
    "Strong Buy",
    (
        df_filtered["Rating"]
        == "STRONG BUY"
    ).sum()
)


# ============================================================
# TOP AKTIEN
# ============================================================

st.divider()

st.subheader("🔥 Top Aktien")


for _, row in df_filtered.iterrows():

    # ========================================================
    # FARBE
    # ========================================================

    if row["Rating"] == "STRONG BUY":
        color = "#16a34a"

    elif row["Rating"] == "BUY":
        color = "#84cc16"

    elif row["Rating"] == "TURNAROUND":
        color = "#2563eb"

    elif row["Rating"] == "WATCH - OVERBOUGHT":
        color = "#f59e0b"

    elif row["Rating"] == "AVOID":
        color = "#dc2626"

    else:
        color = "#6b7280"

    # ========================================================
    # CARD
    # ========================================================

    with st.container():

        components.html(
    f"""
    <div style="
        background-color:#ffffff;
        padding:20px;
        border-radius:18px;
        margin-bottom:18px;
        border-left:10px solid {color};
        box-shadow:0 4px 12px rgba(0,0,0,0.08);
        font-family:Arial;
    ">

        <h2>{row['Ticker']} - {row['Company']}</h2>
        <hr>

        <p><b>💰 Preis:</b> {row['Price']}</p>

        <p>
            <b>⭐ Rating:</b> {row['Rating']} |
            <b>📈 Score:</b> {row['Score']} |
            <b>⚠ Risiko:</b> {row['Risk Level']}
        </p>

        <p>
            <b>📊 Performance:</b><br>
            1D: {row['1D %']}% |
            1W: {row['1W %']}% |
            1M: {row['1M %']}% |
            3M: {row['3M %']}% |
            6M: {row['6M %']}%
        </p>

        <p>
            <b>📉 EMA:</b><br>
            EMA20: {row['EMA20']} |
            EMA50: {row['EMA50']} |
            EMA100: {row['EMA100']}
        </p>

        <p>
            <b>💵 Dividende:</b> {row['Dividend Yield %']} |
            <b>📅 Ex-Dividende:</b> {row['Ex Dividend Date']} |
            <b>🪙 Dividendensatz:</b> {row['Dividend Rate']}
        </p>

        <p><b>🛑 Stop-Loss-Idee:</b> {row['Stop Loss Idea']}</p>
        <p><b>🏢 Market Cap:</b> {row['Market Cap Class']}</p>
        <p><b>🔄 Turnaround:</b> {row['Turnaround Candidate']}</p>
        <p><b>🧠 Analyse:</b> {row['Reason']}</p>

    </div>
    """,
    height=430
)


# ============================================================
# TABELLE
# ============================================================

st.divider()

st.subheader("📋 Gesamttabelle")

st.dataframe(
    df_filtered,
    width="stretch"
)