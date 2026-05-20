import pandas as pd
import streamlit as st
import streamlit.components.v1 as components
import os
import subprocess


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

if not os.path.exists("portfolio_analysis.csv"):

    st.warning(
        "Portfolio-Datei nicht gefunden. "
        "Analyse wird erstellt..."
    )

    subprocess.run(
        ["python", "advanced_portfolio.py"]
    )

df = pd.read_csv(
    "portfolio_analysis.csv",
    sep=";"
)


# ============================================================
# TITEL
# ============================================================

st.title("📊 Hartmuts Dashboard")

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

    ## 🚦 Ampel

    - 🟢 stark / positiv
    - 🟡 neutral / beobachten
    - 🔴 schwach / riskant
    - 🔵 Turnaround-Kandidat

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

    ---

    ## 🛑 Stop-Loss-Idee

    Vorschlag basierend auf EMA50.

    Kein Finanzrat.
    Nur technische Orientierung.

    """)


# ============================================================
# SIDEBAR FILTER
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

sort_option = st.sidebar.selectbox(
    "Sortieren nach",
    [
        "Score",
        "1M %",
        "6M %",
        "RSI",
        "Dividend Yield %",
        "Risk Level"
    ]
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
# SORTIERUNG
# ============================================================

if sort_option in df_filtered.columns:

    if sort_option == "Risk Level":

        risk_order = {
            "LOW RISK": 1,
            "MEDIUM RISK": 2,
            "HIGH RISK": 3
        }

        df_filtered["Risk Sort"] = (
            df_filtered["Risk Level"]
            .map(risk_order)
            .fillna(99)
        )

        df_filtered = df_filtered.sort_values(
            by="Risk Sort",
            ascending=True
        )

    elif sort_option == "Dividend Yield %":

        df_filtered["Dividend Yield Numeric"] = (
            df_filtered["Dividend Yield %"]
            .astype(str)
            .str.replace("%", "", regex=False)
            .replace("-", "0")
            .astype(float)
        )

        df_filtered = df_filtered.sort_values(
            by="Dividend Yield Numeric",
            ascending=False
        )

    else:

        df_filtered = df_filtered.sort_values(
            by=sort_option,
            ascending=False
        )


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
    if len(df_filtered) > 0 else 0
)

col3.metric(
    "Beste 1M %",
    f"{round(df_filtered['1M %'].max(), 2)}%"
    if len(df_filtered) > 0 else "0%"
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
# HILFSFUNKTIONEN
# ============================================================

def get_border_color(rating):

    if rating == "STRONG BUY":
        return "#16a34a"

    if rating == "BUY":
        return "#22c55e"

    if rating == "TURNAROUND":
        return "#2563eb"

    if rating == "WATCH - OVERBOUGHT":
        return "#f59e0b"

    if rating == "HOLD":
        return "#9ca3af"

    if rating == "AVOID":
        return "#dc2626"

    return "#6b7280"


def get_rating_light(rating):

    if rating == "STRONG BUY":
        return "🟢"

    if rating == "BUY":
        return "🟢"

    if rating == "TURNAROUND":
        return "🔵"

    if rating == "WATCH - OVERBOUGHT":
        return "🟡"

    if rating == "HOLD":
        return "🟡"

    return "🔴"


def get_risk_light(risk):

    if risk == "LOW RISK":
        return "🟢"

    if risk == "MEDIUM RISK":
        return "🟡"

    if risk == "HIGH RISK":
        return "🔴"

    return "⚪"


# ============================================================
# AKTIENKARTEN
# ============================================================

st.divider()

st.subheader("🔥 Aktienübersicht")

for _, row in df_filtered.iterrows():

    color = get_border_color(row["Rating"])
    rating_light = get_rating_light(row["Rating"])
    risk_light = get_risk_light(row["Risk Level"])

    components.html(
        f"""
        <div style="
            background-color:#ffffff;
            padding:24px 26px;
            border-radius:22px;
            margin-bottom:26px;
            border-left:13px solid {color};
            box-shadow:0 4px 14px rgba(0,0,0,0.10);
            font-family:Arial, sans-serif;
            color:#111827;
            line-height:1.55;
        ">

            <h2 style="
                margin:0 0 16px 0;
                font-size:27px;
                font-weight:800;
            ">
                {row['Ticker']} - {row['Company']}
            </h2>

            <hr style="
                border:none;
                border-top:2px solid #9ca3af;
                margin:0 0 20px 0;
            ">

            <p style="font-size:18px; margin:0 0 18px 0;">
                💰 <b>Preis:</b> {row['Price']}
            </p>

            <p style="font-size:18px; margin:0 0 18px 0;">
                ⭐ <b>Rating:</b> {rating_light} {row['Rating']}
                |
                📈 <b>Score:</b> {row['Score']}
                |
                ⚠️ <b>Risiko:</b> {risk_light} {row['Risk Level']}
            </p>

            <p style="font-size:18px; margin:0 0 18px 0;">
                📊 <b>Performance:</b><br>
                1D: {row['1D %']}% |
                1W: {row['1W %']}% |
                1M: {row['1M %']}% |
                3M: {row['3M %']}% |
                6M: {row['6M %']}%
            </p>

            <p style="font-size:18px; margin:0 0 18px 0;">
                📉 <b>EMA:</b><br>
                EMA20: {row['EMA20']} |
                EMA50: {row['EMA50']} |
                EMA100: {row['EMA100']}
            </p>

            <p style="font-size:18px; margin:0 0 18px 0;">
                💵 <b>Dividende:</b> {row['Dividend Yield %']}
                |
                📅 <b>Ex-Dividende:</b> {row['Ex Dividend Date']}
                |
                🪙 <b>Dividendensatz:</b> {row['Dividend Rate']}
            </p>

            <p style="font-size:18px; margin:0 0 18px 0;">
                🛑 <b>Stop-Loss-Idee:</b> {row['Stop Loss Idea']}
            </p>

            <p style="font-size:18px; margin:0 0 18px 0;">
                🏢 <b>Market Cap:</b> {row['Market Cap Class']}
            </p>

            <p style="font-size:18px; margin:0 0 18px 0;">
                🔄 <b>Turnaround:</b> {row['Turnaround Candidate']}
            </p>

            <p style="
                font-size:17px;
                margin:8px 0 0 0;
                background:#f3f4f6;
                padding:12px 14px;
                border-radius:12px;
            ">
                🧠 <b>Analyse:</b> {row['Reason']}
            </p>

        </div>
        """,
        height=720
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