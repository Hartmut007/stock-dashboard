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
# DATUM FÜR DIVIDENDENKALENDER VORBEREITEN
# ============================================================

df["Ex Dividend Parsed"] = pd.to_datetime(
    df["Ex Dividend Date"],
    format="%d.%m.%Y",
    errors="coerce"
)

df["Dividend Year"] = df["Ex Dividend Parsed"].dt.year
df["Dividend Month"] = df["Ex Dividend Parsed"].dt.month


# ============================================================
# FUNDAMENTAL-SPALTEN ABSICHERN
# ============================================================

fundamental_defaults = {
    "Forward PE": "-",
    "Trailing PE": "-",
    "PEG Ratio": "-",
    "Revenue Growth": "-",
    "Earnings Growth": "-",
    "Profit Margin": "-",
    "Debt To Equity": "-",
    "Free Cashflow": "-",
    "Operating Cashflow": "-",
    "Fundamental Score": 0,
    "Fundamental Rating": "WEAK / UNKNOWN",
    "Fundamental Pros": "-",
    "Fundamental Cons": "-"
}

for column, default_value in fundamental_defaults.items():

    if column not in df.columns:
        df[column] = default_value



# ============================================================
# ENTSCHEIDUNGSLOGIK: ACTION SIGNAL, CRV, PRO / CONTRA
# ============================================================

def safe_float(value):

    try:
        if pd.isna(value):
            return None

        value = str(value)
        value = value.replace("€", "")
        value = value.replace("$", "")
        value = value.replace("%", "")
        value = value.replace(",", ".")
        value = value.strip()

        if value in ["", "-", "nan", "None"]:
            return None

        return float(value)

    except Exception:
        return None


def format_number(value):

    if value is None:
        return "-"

    return f"{value:.2f}"


def build_decision_data(row):

    price = safe_float(row.get("Price"))
    ema20 = safe_float(row.get("EMA20"))
    ema50 = safe_float(row.get("EMA50"))
    ema100 = safe_float(row.get("EMA100"))
    rsi = safe_float(row.get("RSI"))
    score = safe_float(row.get("Score"))
    perf_1m = safe_float(row.get("1M %"))
    perf_3m = safe_float(row.get("3M %"))
    perf_6m = safe_float(row.get("6M %"))

    fundamental_score = safe_float(row.get("Fundamental Score"))
    forward_pe = safe_float(row.get("Forward PE"))
    trailing_pe = safe_float(row.get("Trailing PE"))
    peg_ratio = safe_float(row.get("PEG Ratio"))
    revenue_growth = safe_float(row.get("Revenue Growth"))
    earnings_growth = safe_float(row.get("Earnings Growth"))
    profit_margin = safe_float(row.get("Profit Margin"))
    debt_to_equity = safe_float(row.get("Debt To Equity"))
    free_cashflow = safe_float(row.get("Free Cashflow"))

    rating = str(row.get("Rating", ""))
    risk_level = str(row.get("Risk Level", ""))
    turnaround = str(row.get("Turnaround Candidate", ""))
    fundamental_rating = str(row.get("Fundamental Rating", "WEAK / UNKNOWN"))
    fundamental_pros = str(row.get("Fundamental Pros", "-"))
    fundamental_cons = str(row.get("Fundamental Cons", "-"))

    pros = []
    cons = []

    # ----------------------------
    # ENTRY / STOP / TARGET / CRV
    # ----------------------------

    if price is not None:

        entry_low = price * 0.98
        entry_high = price * 1.02

    else:

        entry_low = None
        entry_high = None

    if ema50 is not None:

        stop_loss = ema50 * 0.97

    elif price is not None:

        stop_loss = price * 0.92

    else:

        stop_loss = None

    if price is not None and stop_loss is not None and price > stop_loss:

        risk = price - stop_loss
        target_1 = price + risk * 2
        target_2 = price + risk * 3
        crv = (target_1 - price) / risk

    else:

        target_1 = None
        target_2 = None
        crv = None

    # ----------------------------
    # PRO ARGUMENTE
    # ----------------------------

    if score is not None and score >= 6:
        pros.append("starker technischer Score")

    if rating in ["BUY", "STRONG BUY"]:
        pros.append("positives Rating")

    if price is not None and ema20 is not None and price > ema20:
        pros.append("Kurs über EMA20")

    if price is not None and ema50 is not None and price > ema50:
        pros.append("Kurs über EMA50")

    if price is not None and ema100 is not None and price > ema100:
        pros.append("Kurs über EMA100")

    if ema20 is not None and ema50 is not None and ema20 > ema50:
        pros.append("EMA20 über EMA50")

    if ema50 is not None and ema100 is not None and ema50 > ema100:
        pros.append("EMA50 über EMA100")

    if rsi is not None and 40 <= rsi <= 70:
        pros.append("RSI im gesunden Bereich")

    if perf_1m is not None and perf_1m > 0:
        pros.append("positive 1M-Performance")

    if perf_3m is not None and perf_3m > 0:
        pros.append("positive 3M-Performance")

    if crv is not None and crv >= 1.8:
        pros.append("attraktives Chance-Risiko-Verhältnis")

    if turnaround == "YES":
        pros.append("Turnaround-Kandidat")

    if fundamental_score is not None and fundamental_score >= 5:
        pros.append("solider Fundamental-Score")

    if fundamental_rating in ["SOLID", "VERY SOLID"]:
        pros.append("fundamental solide bewertet")

    if revenue_growth is not None and revenue_growth > 0:
        pros.append("positives Umsatzwachstum")

    if earnings_growth is not None and earnings_growth > 0:
        pros.append("positives Gewinnwachstum")

    if profit_margin is not None and profit_margin > 0:
        pros.append("positive Gewinnmarge")

    if free_cashflow is not None and free_cashflow > 0:
        pros.append("positiver Free Cashflow")

    if peg_ratio is not None and peg_ratio > 0 and peg_ratio <= 2:
        pros.append("PEG Ratio attraktiv")

    if fundamental_pros not in ["", "-", "nan", "None"]:
        pros.append(fundamental_pros)

    # ----------------------------
    # CONTRA ARGUMENTE
    # ----------------------------

    if score is not None and score <= 3:
        cons.append("schwacher technischer Score")

    if rating == "AVOID":
        cons.append("negatives Rating")

    if risk_level == "HIGH RISK":
        cons.append("hohes Risiko")

    if rsi is not None and rsi > 70:
        cons.append("RSI überkauft")

    if rsi is not None and rsi < 30:
        cons.append("RSI sehr schwach")

    if price is not None and ema50 is not None and price < ema50:
        cons.append("Kurs unter EMA50")

    if price is not None and ema100 is not None and price < ema100:
        cons.append("Kurs unter EMA100")

    if perf_1m is not None and perf_1m < 0:
        cons.append("negative 1M-Performance")

    if perf_3m is not None and perf_3m < 0:
        cons.append("negative 3M-Performance")

    if crv is not None and crv < 1.5:
        cons.append("CRV zu schwach")

    if price is not None and ema20 is not None and price > ema20 * 1.12:
        cons.append("Kurs weit über EMA20")

    if fundamental_score is not None and fundamental_score <= 2:
        cons.append("schwacher oder unvollständiger Fundamental-Score")

    if fundamental_rating == "WEAK / UNKNOWN":
        cons.append("Fundamentaldaten schwach oder unvollständig")

    if forward_pe is not None and forward_pe > 35:
        cons.append("Forward KGV hoch")

    if trailing_pe is not None and trailing_pe > 40:
        cons.append("KGV hoch")

    if peg_ratio is not None and peg_ratio > 2.5:
        cons.append("PEG Ratio hoch")

    if revenue_growth is not None and revenue_growth < 0:
        cons.append("negatives Umsatzwachstum")

    if earnings_growth is not None and earnings_growth < 0:
        cons.append("negatives Gewinnwachstum")

    if profit_margin is not None and profit_margin < 0:
        cons.append("negative Gewinnmarge")

    if debt_to_equity is not None and debt_to_equity > 200:
        cons.append("hohe Verschuldung")

    if free_cashflow is not None and free_cashflow < 0:
        cons.append("negativer Free Cashflow")

    if fundamental_cons not in ["", "-", "nan", "None"]:
        cons.append(fundamental_cons)

    fundamental_ok = (
        fundamental_score is None
        or fundamental_score == 0
        or fundamental_score >= 5
    )

    fundamental_weak = (
        fundamental_score is not None
        and fundamental_score > 0
        and fundamental_score <= 2
    )

    # ----------------------------
    # ACTION SIGNAL
    # ----------------------------

    if (
        score is not None
        and score >= 6
        and rating in ["BUY", "STRONG BUY"]
        and risk_level != "HIGH RISK"
        and rsi is not None
        and 40 <= rsi <= 70
        and crv is not None
        and crv >= 1.8
        and fundamental_ok
    ):

        action_signal = "🟢 BUY ZONE"
        setup_quality = "Sehr gut"
        action_sort = 1
        decision_summary = (
            "Kaufzone möglich – starkes technisches Setup, "
            "Risiko vertretbar, CRV attraktiv und Fundamentaldaten ausreichend solide."
        )

    elif (
        rsi is not None
        and rsi > 72
        and perf_1m is not None
        and perf_1m > 8
    ):

        action_signal = "🟠 TAKE PROFIT"
        setup_quality = "Überhitzt"
        action_sort = 4
        decision_summary = (
            "Aktie ist stark gelaufen. Gewinnmitnahme oder "
            "Rücksetzer beobachten."
        )

    elif turnaround == "YES":

        action_signal = "🔵 TURNAROUND WATCH"
        setup_quality = "Spekulativ"
        action_sort = 3
        decision_summary = (
            "Mögliche Trendwende sichtbar, aber Bestätigung abwarten."
        )

    elif (
        rating == "AVOID"
        or (score is not None and score <= 3)
        or fundamental_weak
        or (
            risk_level == "HIGH RISK"
            and perf_1m is not None
            and perf_1m < 0
        )
    ):

        action_signal = "🔴 SELL / AVOID"
        setup_quality = "Schwach"
        action_sort = 5
        decision_summary = (
            "Schwaches Setup oder erhöhtes Risiko. Aktuell eher meiden."
        )

    else:

        action_signal = "🟡 WATCH"
        setup_quality = "Neutral"
        action_sort = 2
        decision_summary = (
            "Interessant, aber noch kein klares Kaufsetup."
        )

    # ----------------------------
    # FORMATIERUNG
    # ----------------------------

    if entry_low is not None and entry_high is not None:
        entry_zone = f"{entry_low:.2f} - {entry_high:.2f}"
    else:
        entry_zone = "-"

    return pd.Series({
        "Action Signal": action_signal,
        "Action Sort": action_sort,
        "Entry Zone": entry_zone,
        "Stop Loss New": format_number(stop_loss),
        "Target 1": format_number(target_1),
        "Target 2": format_number(target_2),
        "CRV": round(crv, 2) if crv is not None else "-",
        "Setup Quality": setup_quality,
        "Pros": " | ".join(pros) if pros else "-",
        "Cons": " | ".join(cons) if cons else "-",
        "Decision Summary": decision_summary
    })


decision_columns = df.apply(
    build_decision_data,
    axis=1
)

df = pd.concat(
    [df, decision_columns],
    axis=1
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

    ## 🎯 Action Signale

    Diese Signale verbinden Technik, Risiko, CRV und Fundamentaldaten zu einer konkreteren Einschätzung.

    - **🟢 BUY ZONE** → Kaufzone möglich. Technisches Setup stark, Risiko nicht hoch, RSI gesund, CRV attraktiv und Fundamentaldaten mindestens solide.
    - **🟡 WATCH** → Beobachten. Aktie ist interessant, aber Einstieg, Momentum, CRV oder Fundamentaldaten sind noch nicht überzeugend genug.
    - **🔵 TURNAROUND WATCH** → Spekulativer Trendwechsel. Erste Erholung sichtbar, aber noch Bestätigung abwarten.
    - **🟠 TAKE PROFIT** → Aktie ist stark gelaufen oder überhitzt. Gewinnmitnahme oder Rücksetzer beobachten.
    - **🔴 SELL / AVOID** → Schwaches Setup, hohes Risiko oder negative Struktur. Aktuell eher meiden.

    Wichtig: Das Signal ist keine automatische Kauf- oder Verkaufsempfehlung, sondern eine regelbasierte Entscheidungshilfe.

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

    ---

    ## 📅 Dividendenkalender

    Der Dividendenkalender filtert nach dem Ex-Dividenden-Datum.

    Das Ex-Dividenden-Datum ist der relevante Stichtag.
    Wer die Aktie vor diesem Tag hält, ist grundsätzlich dividendenberechtigt.

    """)


# ============================================================
# SIDEBAR FILTER
# ============================================================

st.sidebar.header("Filter")

search_text = st.sidebar.text_input(
    "🔎 Aktie suchen",
    ""
)

stock_options = (
    df["Ticker"].astype(str)
    + " - "
    + df["Company"].astype(str)
).sort_values().tolist()

selected_stocks = st.sidebar.multiselect(
    "Aktien auswählen",
    options=stock_options,
    default=[]
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

action_signals = st.sidebar.multiselect(
    "Action Signal",
    options=df["Action Signal"].unique(),
    default=df["Action Signal"].unique()
)

turnaround_only = st.sidebar.checkbox(
    "Nur Turnaround Kandidaten"
)

sort_option = st.sidebar.selectbox(
    "Sortieren nach",
    [
        "Action Signal",
        "Score",
        "Fundamental Score",
        "CRV",
        "1M %",
        "6M %",
        "RSI",
        "Dividend Yield %",
        "Risk Level"
    ]
)


# ============================================================
# DIVIDENDENKALENDER FILTER
# ============================================================

st.sidebar.subheader("📅 Dividendenkalender")

dividend_years = sorted(
    df.loc[df["Dividend Year"] >= 2026, "Dividend Year"]
    .dropna()
    .astype(int)
    .unique()
)

selected_year = st.sidebar.selectbox(
    "Jahr",
    options=["Alle"] + dividend_years
)

months = {
    "Alle": None,
    "Januar": 1,
    "Februar": 2,
    "März": 3,
    "April": 4,
    "Mai": 5,
    "Juni": 6,
    "Juli": 7,
    "August": 8,
    "September": 9,
    "Oktober": 10,
    "November": 11,
    "Dezember": 12,
}

selected_month_name = st.sidebar.selectbox(
    "Monat",
    options=list(months.keys())
)

selected_month = months[selected_month_name]


# ============================================================
# FILTER
# ============================================================

df_filtered = df[
    (df["Rating"].isin(ratings))
    &
    (df["Risk Level"].isin(risk_levels))
    &
    (df["Action Signal"].isin(action_signals))
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

if selected_stocks:

    selected_tickers = [
        item.split(" - ")[0]
        for item in selected_stocks
    ]

    df_filtered = df_filtered[
        df_filtered["Ticker"].isin(selected_tickers)
    ]

if turnaround_only:

    df_filtered = df_filtered[
        df_filtered["Turnaround Candidate"] == "YES"
    ]

# Hinweis:
# Jahr und Monat filtern bewusst NICHT df_filtered.
# Dadurch bleiben alle Aktien in Gesamttabelle und Aktienübersicht sichtbar.
# Die Kalenderfilter werden nur unten im Dividendenkalender angewendet.


# ============================================================
# SORTIERUNG
# ============================================================

if sort_option in df_filtered.columns:

    if sort_option == "Action Signal":

        df_filtered = df_filtered.sort_values(
            by="Action Sort",
            ascending=True
        )

    elif sort_option == "Risk Level":

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

    elif sort_option == "CRV":

        df_filtered["CRV Numeric"] = (
            df_filtered["CRV"]
            .astype(str)
            .replace("-", "0")
            .astype(float)
        )

        df_filtered = df_filtered.sort_values(
            by="CRV Numeric",
            ascending=False
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

col1, col2, col3, col4, col5, col6 = st.columns(6)

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

col6.metric(
    "Ø Fundamental",
    round(df_filtered["Fundamental Score"].mean(), 2)
    if len(df_filtered) > 0 else 0
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
# DIVIDENDENKALENDER
# ============================================================

st.divider()

st.subheader("📅 Dividendenkalender")

dividend_calendar = df_filtered[
    (df_filtered["Ex Dividend Parsed"].notna())
    &
    (df_filtered["Dividend Year"] >= 2026)
]

if selected_year != "Alle":

    dividend_calendar = dividend_calendar[
        dividend_calendar["Dividend Year"] == selected_year
    ]

if selected_month is not None:

    dividend_calendar = dividend_calendar[
        dividend_calendar["Dividend Month"] == selected_month
    ]

dividend_calendar = dividend_calendar.sort_values(
    by="Ex Dividend Parsed",
    ascending=True
)[
    [
        "Ticker",
        "Company",
        "Dividend Yield %",
        "Dividend Rate",
        "Ex Dividend Date",
        "Price",
        "Rating",
        "Score",
        "Fundamental Score",
        "Fundamental Rating",
        "Action Signal",
        "CRV"
    ]
]

st.dataframe(
    dividend_calendar,
    width="stretch"
)


# ============================================================
# TABELLE
# ============================================================

st.divider()

st.subheader("📋 Gesamttabelle")

# Action Signal bewusst direkt nach Ticker und Company anzeigen,
# damit die Entscheidungseinschätzung in der Gesamtliste sofort sichtbar ist.
priority_columns = [
    "Ticker",
    "Company",
    "Action Signal"
]

remaining_columns = [
    column for column in df_filtered.columns
    if column not in priority_columns
]

table_columns = [
    column for column in priority_columns
    if column in df_filtered.columns
] + remaining_columns

st.dataframe(
    df_filtered[table_columns],
    width="stretch"
)


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
                🎯 <b>Signal:</b> {row['Action Signal']}
                |
                🧭 <b>Setup:</b> {row['Setup Quality']}
            </p>

            <p style="font-size:18px; margin:0 0 18px 0;">
                📍 <b>Einstiegszone:</b> {row['Entry Zone']}
                |
                🛑 <b>Stop:</b> {row['Stop Loss New']}
                |
                🎯 <b>Ziel 1:</b> {row['Target 1']}
                |
                🚀 <b>Ziel 2:</b> {row['Target 2']}
                |
                ⚖️ <b>CRV:</b> {row['CRV']}
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
                🧾 <b>Fundamental:</b> {row['Fundamental Rating']}
                |
                📊 <b>Fundamental Score:</b> {row['Fundamental Score']}/8
            </p>

            <p style="font-size:18px; margin:0 0 18px 0;">
                🏦 <b>Bewertung:</b><br>
                Forward KGV: {row['Forward PE']} |
                KGV: {row['Trailing PE']} |
                PEG: {row['PEG Ratio']}
            </p>

            <p style="font-size:18px; margin:0 0 18px 0;">
                📈 <b>Fundamentales Wachstum:</b><br>
                Umsatzwachstum: {row['Revenue Growth']} |
                Gewinnwachstum: {row['Earnings Growth']} |
                Marge: {row['Profit Margin']}
            </p>

            <p style="font-size:18px; margin:0 0 18px 0;">
                💸 <b>Cashflow / Verschuldung:</b><br>
                Free Cashflow: {row['Free Cashflow']} |
                Operating Cashflow: {row['Operating Cashflow']} |
                Debt/Equity: {row['Debt To Equity']}
            </p>

            <p style="font-size:18px; margin:0 0 18px 0;">
                🔄 <b>Turnaround:</b> {row['Turnaround Candidate']}
            </p>

            <p style="
                font-size:17px;
                margin:8px 0 14px 0;
                background:#ecfdf5;
                padding:12px 14px;
                border-radius:12px;
            ">
                ✅ <b>Pro:</b> {row['Pros']}
            </p>

            <p style="
                font-size:17px;
                margin:8px 0 14px 0;
                background:#fff7ed;
                padding:12px 14px;
                border-radius:12px;
            ">
                ⚠️ <b>Contra:</b> {row['Cons']}
            </p>

            <p style="
                font-size:17px;
                margin:8px 0 14px 0;
                background:#eef2ff;
                padding:12px 14px;
                border-radius:12px;
            ">
                🧭 <b>Entscheidung:</b> {row['Decision Summary']}
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
        height=1550
    )