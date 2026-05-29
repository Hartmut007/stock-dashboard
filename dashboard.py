import pandas as pd
import streamlit as st
import os
import subprocess
import hmac
from datetime import datetime, date, timedelta
from supabase import create_client, Client
import yfinance as yf
import streamlit.components.v1 as components

# Optional: PyVis bleibt kompatibel, das neue Netzwerk nutzt aber ein eigenes statisches HTML/SVG.
try:
    from pyvis.network import Network
    import tempfile
    PYVIS_AVAILABLE = True
except Exception:
    PYVIS_AVAILABLE = False

# ============================================================
# PAGE CONFIG
# ============================================================

st.set_page_config(
    page_title="Portfolio Dashboard",
    layout="wide"
)

# ============================================================
# 🎨 PROFI-DESIGN / TERMINAL LOOK
# ============================================================

st.markdown(
    """
    <style>
    .block-container {
        padding-top: 0.8rem;
        padding-bottom: 1.6rem;
    }
    div[data-testid="stMetric"] {
        background: linear-gradient(135deg, rgba(15,23,42,0.98), rgba(30,41,59,0.94));
        border: 1px solid rgba(148,163,184,0.28);
        border-radius: 14px;
        padding: 9px 11px;
        box-shadow: 0 12px 28px rgba(15,23,42,0.14);
    }
    div[data-testid="stMetric"] label {
        color: #cbd5e1 !important;
    }
    div[data-testid="stMetric"] [data-testid="stMetricValue"] {
        color: #f8fafc !important;
        font-weight: 800;
    }
    .terminal-panel {
        background: radial-gradient(circle at top left, rgba(59,130,246,0.28), transparent 28%),
                    linear-gradient(135deg, #020617 0%, #0f172a 52%, #111827 100%);
        border: 1px solid rgba(56,189,248,0.32);
        border-radius: 24px;
        padding: 22px 24px;
        margin: 12px 0 18px 0;
        box-shadow: 0 20px 50px rgba(2,6,23,0.36);
        color: #e5e7eb;
    }
    .terminal-panel h3 {
        margin: 0 0 8px 0;
        color: #f8fafc;
        font-size: 1.08rem;
    }
    .terminal-panel p {
        margin: 0;
        color: #cbd5e1;
    }
    .terminal-chip {
        display: inline-block;
        padding: 6px 10px;
        margin: 8px 6px 0 0;
        border-radius: 999px;
        background: rgba(15,23,42,0.72);
        border: 1px solid rgba(148,163,184,0.28);
        color: #e5e7eb;
        font-size: 0.72rem;
        font-weight: 700;
    }
    .legend-dot {
        display:inline-block;
        width:10px;
        height:10px;
        border-radius:50%;
        margin-right:6px;
    }


    /* Kompaktere Standardschrift im Dashboard */
    html, body, [class*="css"] {
        font-size: 14px;
    }

    .stMarkdown, .stText, p, li, span, div {
        font-size: 0.88rem;
    }

    h1 {
        font-size: 1.65rem !important;
        margin-bottom: 0.55rem !important;
    }

    h2 {
        font-size: 1.32rem !important;
        margin-top: 0.75rem !important;
        margin-bottom: 0.45rem !important;
    }

    h3 {
        font-size: 1.08rem !important;
        margin-top: 0.6rem !important;
        margin-bottom: 0.35rem !important;
    }

    div[data-testid="stMetric"] label {
        font-size: 0.70rem !important;
    }

    div[data-testid="stMetric"] [data-testid="stMetricValue"] {
        font-size: 1.05rem !important;
        line-height: 1.15 !important;
    }

    div[data-testid="stMetric"] [data-testid="stMetricDelta"] {
        font-size: 0.70rem !important;
    }

    /* Sidebar kompakter */
    section[data-testid="stSidebar"] {
        font-size: 0.80rem !important;
    }

    section[data-testid="stSidebar"] * {
        font-size: 0.80rem !important;
    }

    section[data-testid="stSidebar"] h1,
    section[data-testid="stSidebar"] h2,
    section[data-testid="stSidebar"] h3 {
        font-size: 0.95rem !important;
        margin-top: 0.5rem !important;
        margin-bottom: 0.35rem !important;
    }

    section[data-testid="stSidebar"] label,
    section[data-testid="stSidebar"] p,
    section[data-testid="stSidebar"] span {
        font-size: 0.76rem !important;
    }

    section[data-testid="stSidebar"] div[data-baseweb="select"] * {
        font-size: 0.76rem !important;
    }

    section[data-testid="stSidebar"] input {
        font-size: 0.76rem !important;
        min-height: 32px !important;
    }

    section[data-testid="stSidebar"] button {
        font-size: 0.76rem !important;
        padding: 0.25rem 0.45rem !important;
        min-height: 32px !important;
    }

    /* Tabellen und Tabs kompakter */
    div[data-testid="stDataFrame"] {
        font-size: 0.78rem !important;
    }

    button[data-baseweb="tab"] p {
        font-size: 0.82rem !important;
        font-weight: 700 !important;
    }

    .terminal-panel {
        padding: 14px 16px;
        border-radius: 18px;
        margin: 8px 0 12px 0;
    }

    .terminal-panel p {
        font-size: 0.82rem;
        line-height: 1.35;
    }

    .terminal-chip {
        padding: 4px 8px;
        margin: 5px 4px 0 0;
        font-size: 0.68rem;
    }

    </style>
    """,
    unsafe_allow_html=True
)


# ============================================================
# 🔐 LOGIN-BEREICH
# ============================================================

def check_password():
    """Einfacher Login mit Benutzern aus Streamlit Secrets."""

    def password_entered():
        username = st.session_state.get("username", "").strip()
        password = st.session_state.get("password", "")

        users = st.secrets.get("users", {})

        if username in users and hmac.compare_digest(password, users[username]):
            st.session_state["password_correct"] = True
            st.session_state["current_user"] = username
            del st.session_state["password"]
        else:
            st.session_state["password_correct"] = False

    if st.session_state.get("password_correct", False):
        return True

    st.title("🔐 Login")
    st.write("Bitte melde dich an, um das Hartmut-Portfolio zu sehen.")

    st.text_input("Benutzername", key="username")
    st.text_input("Passwort", type="password", key="password")

    st.button("Einloggen", on_click=password_entered)

    if "password_correct" in st.session_state and not st.session_state["password_correct"]:
        st.error("Benutzername oder Passwort falsch.")

    return False


if not check_password():
    st.stop()


# Optional: eingeloggten Nutzer anzeigen
st.sidebar.success(f"Angemeldet als: {st.session_state.get('current_user', '')}")

if st.sidebar.button("Ausloggen"):
    for key in ["password_correct", "current_user", "username"]:
        if key in st.session_state:
            del st.session_state[key]
    st.rerun()

# ============================================================
# 💾 PERSÖNLICHE WATCHLIST / KAUFLIST IN SUPABASE SPEICHERN
# ============================================================

USER_LIST_COLUMNS = [
    "username",
    "list_type",
    "ticker",
    "name",
    "created_at"
]

SUPABASE_TABLE = "user_stock_lists"


@st.cache_resource
def get_supabase_client() -> Client:
    """Erstellt eine Supabase-Verbindung aus Streamlit Secrets."""

    supabase_url = st.secrets["supabase"]["url"]
    supabase_key = st.secrets["supabase"]["key"]

    return create_client(
        supabase_url,
        supabase_key
    )


def load_user_lists():
    """Lädt gespeicherte Watchlist- und Kauflisten aus Supabase."""

    try:
        supabase = get_supabase_client()

        response = (
            supabase
            .table(SUPABASE_TABLE)
            .select("username,list_type,ticker,name,created_at")
            .execute()
        )

        data = pd.DataFrame(response.data)

        if data.empty:
            data = pd.DataFrame(columns=USER_LIST_COLUMNS)

    except Exception as error:
        st.error(f"Supabase-Daten konnten nicht geladen werden: {error}")
        data = pd.DataFrame(columns=USER_LIST_COLUMNS)

    for column in USER_LIST_COLUMNS:
        if column not in data.columns:
            data[column] = ""

    return data[USER_LIST_COLUMNS]


def get_saved_tickers(username, list_type):
    """Gibt gespeicherte Ticker eines Nutzers für eine Liste zurück."""

    data = load_user_lists()

    user_data = data[
        (data["username"].astype(str) == str(username))
        &
        (data["list_type"].astype(str) == str(list_type))
    ]

    return user_data["ticker"].dropna().astype(str).tolist()


def update_user_list(username, list_type, selected_tickers, stock_df):
    """Aktualisiert eine Liste für einen Nutzer in Supabase."""

    try:
        supabase = get_supabase_client()

        # Alte Einträge dieses Nutzers für diese Liste löschen.
        # Danach wird die aktuelle Auswahl neu eingefügt.
        (
            supabase
            .table(SUPABASE_TABLE)
            .delete()
            .eq("username", username)
            .eq("list_type", list_type)
            .execute()
        )

        new_rows = []

        for ticker in selected_tickers:
            ticker = str(ticker).strip()

            stock_row = stock_df[
                stock_df["Ticker"].astype(str).str.strip() == ticker
            ]

            if not stock_row.empty:
                name = stock_row.iloc[0].get("Company", ticker)
            else:
                name = ticker

            new_rows.append({
                "username": username,
                "list_type": list_type,
                "ticker": ticker,
                "name": str(name),
                "created_at": datetime.now().isoformat()
            })

        if new_rows:
            (
                supabase
                .table(SUPABASE_TABLE)
                .insert(new_rows)
                .execute()
            )

    except Exception as error:
        st.error(f"Supabase-Daten konnten nicht gespeichert werden: {error}")

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

# Numeric-Spalten absichern, damit Mittelwerte, Sortierung und Regeln stabil bleiben.
for numeric_column in [
    "Score",
    "1D %",
    "1W %",
    "1M %",
    "3M %",
    "6M %",
    "RSI",
    "Fundamental Score"
]:

    if numeric_column in df.columns:
        df[numeric_column] = pd.to_numeric(
            df[numeric_column],
            errors="coerce"
        ).fillna(0)


# ============================================================
# STRATEGIE-HORIZONT
# ============================================================

strategy_mode = st.sidebar.selectbox(
    "Strategie-Horizont",
    [
        "Kurzfristig",
        "Mittelfristig",
        "Langfristig"
    ],
    index=1
)




# ============================================================
# ENTSCHEIDUNGSLOGIK: ACTION SIGNAL, CRV, PRO / CONTRA
# ============================================================

def safe_float(value):

    try:
        if pd.isna(value):
            return None

        value = str(value)

        for currency_text in [
            "€", "$", "%", "EUR", "USD", "GBP", "CHF",
            "JPY", "CAD", "AUD", "HKD", "CNY"
        ]:
            value = value.replace(currency_text, "")

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


def clean_text_value(value):

    value = str(value).strip()

    if value in ["", "-", "nan", "None"]:
        return ""

    return value


def unique_items(items):

    result = []

    for item in items:
        item = clean_text_value(item)

        if item and item not in result:
            result.append(item)

    return result


def build_trade_levels(price, ema20, ema50, ema100, high_52w):

    if price is None:
        return None, None, None, None, None, None, "-"

    entry_low = price * 0.98
    entry_high = price * 1.02

    # Stop-Loss wird je nach Zeithorizont anders gewählt.
    # Kurzfristig: näher am EMA20; mittelfristig: EMA50; langfristig: EMA100.
    if strategy_mode == "Kurzfristig":

        if ema20 is not None:
            stop_loss = ema20 * 0.97
        elif ema50 is not None:
            stop_loss = ema50 * 0.98
        else:
            stop_loss = price * 0.94

        fallback_target_1 = price * 1.08
        fallback_target_2 = price * 1.14

    elif strategy_mode == "Langfristig":

        if ema100 is not None:
            stop_loss = ema100 * 0.95
        elif ema50 is not None:
            stop_loss = ema50 * 0.95
        else:
            stop_loss = price * 0.85

        fallback_target_1 = price * 1.20
        fallback_target_2 = price * 1.35

    else:

        if ema50 is not None:
            stop_loss = ema50 * 0.97
        elif ema100 is not None:
            stop_loss = ema100 * 0.98
        else:
            stop_loss = price * 0.92

        fallback_target_1 = price * 1.12
        fallback_target_2 = price * 1.22

    target_basis = "Fallback-Ziel"

    # Echtes Ziel bevorzugen: 52W-Hoch, sofern es noch oberhalb des aktuellen Preises liegt.
    if high_52w is not None and high_52w > price * 1.03:
        target_1 = high_52w
        target_2 = max(high_52w * 1.05, fallback_target_2)
        target_basis = "52W-Hoch"
    else:
        target_1 = fallback_target_1
        target_2 = fallback_target_2

    if stop_loss is not None and stop_loss < price and target_1 > price:
        risk = price - stop_loss
        reward = target_1 - price
        crv = reward / risk if risk > 0 else None
    else:
        crv = None

    return entry_low, entry_high, stop_loss, target_1, target_2, crv, target_basis


def build_decision_data(row):

    price = safe_float(row.get("Price"))
    ema20 = safe_float(row.get("EMA20"))
    ema50 = safe_float(row.get("EMA50"))
    ema100 = safe_float(row.get("EMA100"))
    high_52w = safe_float(row.get("52W High"))
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
    fundamental_pros = clean_text_value(row.get("Fundamental Pros", "-"))
    fundamental_cons = clean_text_value(row.get("Fundamental Cons", "-"))

    pros = []
    cons = []

    # ----------------------------
    # ENTRY / STOP / TARGET / CRV
    # ----------------------------

    (
        entry_low,
        entry_high,
        stop_loss,
        target_1,
        target_2,
        crv,
        target_basis
    ) = build_trade_levels(
        price,
        ema20,
        ema50,
        ema100,
        high_52w
    )

    # ----------------------------
    # FUNDAMENTAL-DATENQUALITÄT
    # ----------------------------

    # Score 0 + WEAK / UNKNOWN wird als "Daten fehlen" behandelt, nicht automatisch als schlecht.
    has_fundamental_data = not (
        fundamental_score is None
        or (
            fundamental_score == 0
            and fundamental_rating in ["WEAK / UNKNOWN", "UNKNOWN", "-"]
        )
    )

    fundamental_ok = (
        not has_fundamental_data
        or (
            fundamental_score is not None
            and fundamental_score >= 5
        )
        or fundamental_rating in ["SOLID", "VERY SOLID"]
    )

    fundamental_weak = (
        has_fundamental_data
        and (
            (
                fundamental_score is not None
                and fundamental_score <= 2
            )
            or fundamental_rating == "WEAK"
        )
    )

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

    if crv is not None and crv >= 1.6:
        pros.append("attraktives Chance-Risiko-Verhältnis")

    if target_basis == "52W-Hoch":
        pros.append("Ziel basiert auf 52W-Hoch")

    if turnaround == "YES":
        pros.append("Turnaround-Kandidat")

    if has_fundamental_data and fundamental_score is not None and fundamental_score >= 5:
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

    if fundamental_pros:
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

    if crv is not None and crv < 1.2:
        cons.append("CRV zu schwach")

    if price is not None and ema20 is not None and price > ema20 * 1.12:
        cons.append("Kurs weit über EMA20")

    if not has_fundamental_data:
        cons.append("Fundamentaldaten unvollständig")

    if fundamental_weak:
        cons.append("schwacher Fundamental-Score")

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

    if fundamental_cons:
        cons.append(fundamental_cons)

    # Duplikate entfernen, damit Pro/Contra nicht unnötig lang wird.
    pros = unique_items(pros)
    cons = unique_items(cons)

    # ----------------------------
    # ACTION SIGNAL
    # ----------------------------

    if strategy_mode == "Kurzfristig":

        if (
            score is not None
            and score >= 6
            and rating in ["BUY", "STRONG BUY"]
            and risk_level != "HIGH RISK"
            and rsi is not None
            and 42 <= rsi <= 68
            and perf_1m is not None
            and perf_1m > 0
            and price is not None
            and ema20 is not None
            and price > ema20
            and crv is not None
            and crv >= 1.4
        ):

            action_signal = "🟢 BUY ZONE"
            setup_quality = "Kurzfristig stark"
            action_sort = 1
            decision_summary = (
                "Kurzfristige Kaufzone möglich – Momentum, EMA20, RSI "
                "und ein realistisches CRV sprechen für ein aktives Setup."
            )

        elif (
            rsi is not None
            and rsi > 72
            and perf_1m is not None
            and perf_1m > 8
        ):

            action_signal = "🟠 TAKE PROFIT"
            setup_quality = "Kurzfristig überhitzt"
            action_sort = 4
            decision_summary = (
                "Kurzfristig heiß gelaufen. Gewinnmitnahme, engerer Stop "
                "oder Rücksetzer beobachten."
            )

        elif turnaround == "YES":

            action_signal = "🔵 TURNAROUND WATCH"
            setup_quality = "Kurzfristig spekulativ"
            action_sort = 3
            decision_summary = (
                "Kurzfristige Trendwende möglich, aber Bestätigung abwarten."
            )

        elif (
            rating == "AVOID"
            or (score is not None and score <= 3)
            or (
                risk_level == "HIGH RISK"
                and perf_1m is not None
                and perf_1m < 0
            )
            or (
                price is not None
                and ema50 is not None
                and price < ema50
                and perf_1m is not None
                and perf_1m < 0
            )
        ):

            action_signal = "🔴 SELL / AVOID"
            setup_quality = "Kurzfristig schwach"
            action_sort = 5
            decision_summary = (
                "Kurzfristig schwaches Setup oder erhöhtes Risiko. "
                "Aktuell eher meiden."
            )

        else:

            action_signal = "🟡 WATCH"
            setup_quality = "Kurzfristig neutral"
            action_sort = 2
            decision_summary = (
                "Kurzfristig interessant, aber noch kein sauberes Einstiegssignal."
            )

    elif strategy_mode == "Langfristig":

        long_fundamental_buy = (
            has_fundamental_data
            and fundamental_score is not None
            and fundamental_score >= 6
            and fundamental_rating in ["SOLID", "VERY SOLID"]
        )

        long_quality_ok = (
            (free_cashflow is None or free_cashflow > 0)
            and (profit_margin is None or profit_margin > 0)
            and (revenue_growth is None or revenue_growth >= 0)
            and (debt_to_equity is None or debt_to_equity <= 200)
        )

        long_trend_ok = (
            price is None
            or ema100 is None
            or price >= ema100
            or (score is not None and score >= 5)
        )

        if (
            long_fundamental_buy
            and long_quality_ok
            and long_trend_ok
            and risk_level != "HIGH RISK"
            and (rsi is None or rsi < 78)
        ):

            action_signal = "🟢 BUY ZONE"
            setup_quality = "Langfristig solide"
            action_sort = 1
            decision_summary = (
                "Langfristige Kaufzone möglich – Fundamentaldaten, Qualität "
                "und Langfristtrend wirken ausreichend solide."
            )

        elif (
            rsi is not None
            and rsi > 78
            and perf_1m is not None
            and perf_1m > 12
        ):

            action_signal = "🟠 OVERHEATED"
            setup_quality = "Langfristig heiß"
            action_sort = 4
            decision_summary = (
                "Langfristig nicht zwingend schlecht, aber kurzfristig stark "
                "überhitzt. Rücksetzer abwarten oder Position enger überwachen."
            )

        elif (
            turnaround == "YES"
            and (
                not has_fundamental_data
                or (
                    fundamental_score is not None
                    and fundamental_score >= 4
                )
            )
        ):

            action_signal = "🔵 TURNAROUND WATCH"
            setup_quality = "Langfristig spekulativ"
            action_sort = 3
            decision_summary = (
                "Trendwende möglich. Für langfristige Käufe erst weitere "
                "Bestätigung und stabile Fundamentaldaten abwarten."
            )

        elif (
            fundamental_weak
            or (
                rating == "AVOID"
                and score is not None
                and score <= 3
            )
            or (
                risk_level == "HIGH RISK"
                and perf_6m is not None
                and perf_6m < 0
            )
        ):

            action_signal = "🔴 SELL / AVOID"
            setup_quality = "Langfristig schwach"
            action_sort = 5
            decision_summary = (
                "Langfristig schwach oder zu unsicher – Fundamentaldaten, "
                "Trend oder Risiko sprechen aktuell dagegen."
            )

        else:

            action_signal = "🟡 WATCH"
            setup_quality = "Langfristig beobachten"
            action_sort = 2
            decision_summary = (
                "Langfristig interessant, aber Qualität, Bewertung oder "
                "Trend liefern noch kein klares Kaufsetup."
            )

    else:

        if (
            score is not None
            and score >= 6
            and rating in ["BUY", "STRONG BUY"]
            and risk_level != "HIGH RISK"
            and rsi is not None
            and 40 <= rsi <= 70
            and crv is not None
            and crv >= 1.5
            and fundamental_ok
        ):

            action_signal = "🟢 BUY ZONE"
            setup_quality = "Sehr gut"
            action_sort = 1
            decision_summary = (
                "Kaufzone möglich – starkes technisches Setup, "
                "Risiko vertretbar, CRV realistisch attraktiv und Fundamentaldaten ausreichend solide."
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
        "Strategy Mode": strategy_mode,
        "Action Sort": action_sort,
        "Entry Zone": entry_zone,
        "Stop Loss New": format_number(stop_loss),
        "Target 1": format_number(target_1),
        "Target 2": format_number(target_2),
        "Target Basis": target_basis,
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
# 💎 BEWERTUNGS-HINWEIS: UNTERBEWERTET / FAIR / ÜBERBEWERTET
# ============================================================

def build_valuation_status(row):
    """
    Einfache regelbasierte Bewertung.
    Kein echter Fair Value, sondern ein Hinweis aus Bewertung + Wachstum + Qualität.
    """

    forward_pe = safe_float(row.get("Forward PE"))
    trailing_pe = safe_float(row.get("Trailing PE"))
    peg_ratio = safe_float(row.get("PEG Ratio"))
    revenue_growth = safe_float(row.get("Revenue Growth"))
    earnings_growth = safe_float(row.get("Earnings Growth"))
    profit_margin = safe_float(row.get("Profit Margin"))
    free_cashflow = safe_float(row.get("Free Cashflow"))
    fundamental_score = safe_float(row.get("Fundamental Score"))

    valuation_points = 0
    reasons = []

    # ----------------------------
    # BEWERTUNG
    # ----------------------------

    if forward_pe is not None:
        if forward_pe <= 15:
            valuation_points += 2
            reasons.append("günstiges Forward KGV")
        elif forward_pe <= 25:
            valuation_points += 1
            reasons.append("moderates Forward KGV")
        elif forward_pe >= 40:
            valuation_points -= 2
            reasons.append("hohes Forward KGV")
        elif forward_pe >= 30:
            valuation_points -= 1
            reasons.append("erhöhtes Forward KGV")

    if trailing_pe is not None:
        if trailing_pe <= 18:
            valuation_points += 1
            reasons.append("moderates KGV")
        elif trailing_pe >= 45:
            valuation_points -= 1
            reasons.append("hohes KGV")

    if peg_ratio is not None and peg_ratio > 0:
        if peg_ratio <= 1:
            valuation_points += 2
            reasons.append("attraktives PEG Ratio")
        elif peg_ratio <= 2:
            valuation_points += 1
            reasons.append("PEG Ratio noch vertretbar")
        elif peg_ratio >= 3:
            valuation_points -= 2
            reasons.append("PEG Ratio hoch")
        elif peg_ratio > 2:
            valuation_points -= 1
            reasons.append("PEG Ratio erhöht")

    # ----------------------------
    # QUALITÄT / WACHSTUM
    # ----------------------------

    if revenue_growth is not None:
        if revenue_growth > 0:
            valuation_points += 1
            reasons.append("positives Umsatzwachstum")
        elif revenue_growth < 0:
            valuation_points -= 1
            reasons.append("negatives Umsatzwachstum")

    if earnings_growth is not None:
        if earnings_growth > 0:
            valuation_points += 1
            reasons.append("positives Gewinnwachstum")
        elif earnings_growth < 0:
            valuation_points -= 1
            reasons.append("negatives Gewinnwachstum")

    if profit_margin is not None:
        if profit_margin > 0:
            valuation_points += 1
            reasons.append("positive Gewinnmarge")
        elif profit_margin < 0:
            valuation_points -= 1
            reasons.append("negative Gewinnmarge")

    if free_cashflow is not None:
        if free_cashflow > 0:
            valuation_points += 1
            reasons.append("positiver Free Cashflow")
        elif free_cashflow < 0:
            valuation_points -= 1
            reasons.append("negativer Free Cashflow")

    if fundamental_score is not None:
        if fundamental_score >= 6:
            valuation_points += 1
            reasons.append("starker Fundamental Score")
        elif fundamental_score <= 2:
            valuation_points -= 1
            reasons.append("schwacher Fundamental Score")

    # ----------------------------
    # LABEL
    # ----------------------------

    if len(reasons) < 2:
        valuation_status = "❓ Unklar"
        valuation_summary = "Zu wenige Bewertungsdaten vorhanden."
    elif valuation_points >= 4:
        valuation_status = "💎 Eher unterbewertet"
        valuation_summary = "Bewertung wirkt im Verhältnis zu Qualität und Wachstum attraktiv."
    elif valuation_points >= 1:
        valuation_status = "⚖️ Fair bewertet"
        valuation_summary = "Bewertung wirkt grundsätzlich vertretbar."
    elif valuation_points <= -3:
        valuation_status = "🔥 Eher überbewertet"
        valuation_summary = "Bewertung wirkt im Verhältnis zu Qualität und Wachstum anspruchsvoll."
    else:
        valuation_status = "⚖️ Fair bis leicht teuer"
        valuation_summary = "Bewertung ist nicht extrem, aber nicht klar günstig."

    return pd.Series({
        "Valuation Status": valuation_status,
        "Valuation Score": valuation_points,
        "Valuation Reasons": " | ".join(unique_items(reasons)) if reasons else "-",
        "Valuation Summary": valuation_summary
    })


valuation_columns = df.apply(
    build_valuation_status,
    axis=1
)

df = pd.concat(
    [df, valuation_columns],
    axis=1
)

# ============================================================
# 🧭 TERMINAL SCORE / RESEARCH-GRADE
# ============================================================

def build_terminal_score(row):
    """Kompakter Research-Score aus Technik, Fundamental, Bewertung, CRV und Risiko.
    Hinweis: Regelbasiertes Ranking, kein Finanzrat und kein echtes Kurszielmodell.
    """

    tech_score = safe_float(row.get("Score"))
    fundamental_score = safe_float(row.get("Fundamental Score"))
    valuation_score = safe_float(row.get("Valuation Score"))
    crv = safe_float(row.get("CRV"))
    risk_level = str(row.get("Risk Level", ""))
    action_signal = str(row.get("Action Signal", ""))

    total = 0

    if tech_score is not None:
        total += max(0, min(tech_score, 8)) / 8 * 25

    if fundamental_score is not None:
        total += max(0, min(fundamental_score, 8)) / 8 * 20

    if valuation_score is not None:
        # Valuation Score grob von -5 bis +5 auf 0 bis 20 Punkte normalisieren.
        total += max(0, min((valuation_score + 5) / 10, 1)) * 20

    if crv is not None:
        total += max(0, min(crv / 3, 1)) * 15

    if risk_level == "LOW RISK":
        total += 10
    elif risk_level == "MEDIUM RISK":
        total += 5
    elif risk_level == "HIGH RISK":
        total -= 5

    if "BUY ZONE" in action_signal:
        total += 10
    elif "WATCH" in action_signal:
        total += 5
    elif "OVERHEATED" in action_signal or "TAKE PROFIT" in action_signal:
        total += 0
    elif "SELL" in action_signal or "AVOID" in action_signal:
        total -= 10

    total = int(round(max(0, min(total, 100))))

    if total >= 80:
        grade = "A · Stark"
        summary = "Sehr starkes Gesamtbild aus Signal, Qualität, Bewertung und Risiko."
    elif total >= 65:
        grade = "B · Interessant"
        summary = "Interessantes Setup, aber einzelne Punkte sollten geprüft werden."
    elif total >= 50:
        grade = "C · Beobachten"
        summary = "Gemischtes Bild. Eher Watchlist als klare Aktion."
    elif total >= 35:
        grade = "D · Schwach"
        summary = "Viele Signale sind noch nicht überzeugend. Vorsichtig bleiben."
    else:
        grade = "E · Meiden"
        summary = "Schwaches Gesamtbild oder zu viele Risikofaktoren."

    return pd.Series({
        "Terminal Score": total,
        "Terminal Grade": grade,
        "Terminal Summary": summary
    })


terminal_columns = df.apply(
    build_terminal_score,
    axis=1
)

df = pd.concat(
    [df, terminal_columns],
    axis=1
)

# ============================================================
# STREAMLIT-TABELLENKOMPATIBILITÄT
# ============================================================

# Streamlit/PyArrow kann bei st.dataframe Probleme bekommen,
# wenn eine Spalte gemischt aus Zahlen und Text wie "-" besteht.
# Deshalb werden reine Anzeige-Spalten hier bewusst als Text behandelt.
display_text_columns = [
    "CRV",
    "Entry Zone",
    "Stop Loss New",
    "Target 1",
    "Target 2",
    "Price",
    "Dividend Yield %",
    "Dividend Rate",
    "Forward PE",
    "Trailing PE",
    "PEG Ratio",
    "Revenue Growth",
    "Earnings Growth",
    "Profit Margin",
    "Debt To Equity",
    "Free Cashflow",
    "Operating Cashflow"
]

for column in display_text_columns:
    if column in df.columns:
        df[column] = df[column].astype(str)

# ============================================================
# 📆 EARNINGS-KALENDER HILFSFUNKTIONEN
# ============================================================

def _format_earnings_date(value):
    """Normalisiert Earnings-Daten aus unterschiedlichen Yahoo/yfinance-Formaten."""
    try:
        if value is None or value == "" or pd.isna(value):
            return None
    except Exception:
        pass

    try:
        if isinstance(value, (list, tuple)) and len(value) > 0:
            value = value[0]

        dt = pd.to_datetime(value, errors="coerce")

        if pd.isna(dt):
            return None

        if hasattr(dt, "tz_convert"):
            try:
                dt = dt.tz_convert(None)
            except Exception:
                try:
                    dt = dt.tz_localize(None)
                except Exception:
                    pass

        return dt

    except Exception:
        return None


def _format_estimate_value(value, suffix=""):
    """Formatiert Schätzwerte kompakt."""
    try:
        if value is None or pd.isna(value):
            return "-"

        numeric = float(value)

        if abs(numeric) >= 1_000_000_000:
            return f"{numeric / 1_000_000_000:.2f} Mrd.{suffix}"

        if abs(numeric) >= 1_000_000:
            return f"{numeric / 1_000_000:.2f} Mio.{suffix}"

        return f"{numeric:.2f}{suffix}"

    except Exception:
        if value in [None, "", "nan", "None"]:
            return "-"
        return str(value)


def _extract_estimate_from_frame(frame):
    """Versucht aus yfinance-Schätztabellen den aktuellen Durchschnittswert zu ziehen."""
    try:
        if frame is None or frame.empty:
            return None

        candidate_rows = [
            "current qtr", "current quarter", "0q",
            "next qtr", "next quarter", "+1q"
        ]
        candidate_cols = ["avg", "Avg", "Average", "average"]

        lower_index = {str(idx).strip().lower(): idx for idx in frame.index}

        for row_name in candidate_rows:
            if row_name in lower_index:
                row_idx = lower_index[row_name]
                for col in candidate_cols:
                    if col in frame.columns:
                        return frame.loc[row_idx, col]

        for col in candidate_cols:
            if col in frame.columns and len(frame[col].dropna()) > 0:
                return frame[col].dropna().iloc[0]

    except Exception:
        return None

    return None


@st.cache_data(ttl=6 * 60 * 60, show_spinner=False)
def fetch_earnings_snapshot(ticker):
    """
    Holt Earnings-Datum und Schätzwerte pro Ticker.
    Daten kommen über yfinance/Yahoo Finance und können je nach Börsenplatz fehlen.
    """

    result = {
        "ticker": ticker,
        "earnings_date": None,
        "earnings_time": "-",
        "eps_estimate": "-",
        "revenue_estimate": "-",
        "source_status": "keine Daten",
    }

    try:
        ticker_object = yf.Ticker(ticker)

        # 1) Hauptquelle: Earnings-Dates-Tabelle
        try:
            earnings_dates = ticker_object.get_earnings_dates(limit=12)

            if earnings_dates is not None and not earnings_dates.empty:
                dates_frame = earnings_dates.copy()
                dates_frame = dates_frame.reset_index()

                date_column = dates_frame.columns[0]
                dates_frame["_parsed_date"] = pd.to_datetime(
                    dates_frame[date_column],
                    errors="coerce"
                )

                today_ts = pd.Timestamp.today().normalize()
                future_dates = dates_frame[dates_frame["_parsed_date"] >= today_ts].copy()

                if not future_dates.empty:
                    selected_row = future_dates.sort_values("_parsed_date").iloc[0]
                else:
                    selected_row = dates_frame.sort_values("_parsed_date", ascending=False).iloc[0]

                result["earnings_date"] = _format_earnings_date(selected_row.get("_parsed_date"))

                for eps_col in ["EPS Estimate", "epsEstimate", "EPS Est."]:
                    if eps_col in selected_row.index and not pd.isna(selected_row.get(eps_col)):
                        result["eps_estimate"] = _format_estimate_value(selected_row.get(eps_col))
                        break

                for time_col in ["Time", "time"]:
                    if time_col in selected_row.index and not pd.isna(selected_row.get(time_col)):
                        result["earnings_time"] = str(selected_row.get(time_col))
                        break

                result["source_status"] = "Earnings-Dates"

        except Exception:
            pass

        # 2) Fallback: calendar dict
        if result["earnings_date"] is None:
            try:
                calendar_data = ticker_object.calendar

                if isinstance(calendar_data, dict):
                    earnings_date = (
                        calendar_data.get("Earnings Date")
                        or calendar_data.get("EarningsDate")
                        or calendar_data.get("earningsDate")
                    )
                    parsed_date = _format_earnings_date(earnings_date)

                    if parsed_date is not None:
                        result["earnings_date"] = parsed_date
                        result["source_status"] = "Calendar"

                    eps_average = (
                        calendar_data.get("Earnings Average")
                        or calendar_data.get("EarningsAverage")
                    )

                    if eps_average is not None and result["eps_estimate"] == "-":
                        result["eps_estimate"] = _format_estimate_value(eps_average)

                    revenue_average = (
                        calendar_data.get("Revenue Average")
                        or calendar_data.get("RevenueAverage")
                    )

                    if revenue_average is not None:
                        result["revenue_estimate"] = _format_estimate_value(revenue_average)

            except Exception:
                pass

        # 3) Zusatz: EPS-/Umsatz-Schätzungen, falls verfügbar
        try:
            earnings_estimate = ticker_object.get_earnings_estimate()
            eps_estimate = _extract_estimate_from_frame(earnings_estimate)

            if eps_estimate is not None and result["eps_estimate"] == "-":
                result["eps_estimate"] = _format_estimate_value(eps_estimate)
        except Exception:
            pass

        try:
            revenue_estimate = ticker_object.get_revenue_estimate()
            revenue_avg = _extract_estimate_from_frame(revenue_estimate)

            if revenue_avg is not None and result["revenue_estimate"] == "-":
                result["revenue_estimate"] = _format_estimate_value(revenue_avg)
        except Exception:
            pass

    except Exception as error:
        result["source_status"] = f"Fehler: {error}"

    return result


def build_earnings_calendar(universe_df, max_tickers):
    """Baut einen Earningskalender für die angezeigte/gewählte Aktienmenge."""

    if universe_df.empty or "Ticker" not in universe_df.columns:
        return pd.DataFrame()

    ticker_frame = universe_df.dropna(subset=["Ticker"]).copy()
    ticker_frame["Ticker"] = ticker_frame["Ticker"].astype(str).str.strip()
    ticker_frame = ticker_frame.drop_duplicates(subset=["Ticker"]).head(max_tickers)

    rows = []

    progress = st.progress(0, text="Earningskalender wird aktualisiert...")
    total = len(ticker_frame)

    for idx, (_, stock_row) in enumerate(ticker_frame.iterrows(), start=1):
        ticker = str(stock_row.get("Ticker", "")).strip()

        if ticker:
            snapshot = fetch_earnings_snapshot(ticker)
            earnings_date = snapshot.get("earnings_date")

            if earnings_date is not None:
                days_until = (pd.Timestamp(earnings_date).normalize() - pd.Timestamp.today().normalize()).days
                earnings_date_text = pd.Timestamp(earnings_date).strftime("%d.%m.%Y")
            else:
                days_until = None
                earnings_date_text = "-"

            rows.append({
                "Ticker": ticker,
                "Company": stock_row.get("Company", ticker),
                "Earnings Date": earnings_date_text,
                "Days Until": days_until if days_until is not None else "-",
                "Time": snapshot.get("earnings_time", "-"),
                "EPS Estimate": snapshot.get("eps_estimate", "-"),
                "Revenue Estimate": snapshot.get("revenue_estimate", "-"),
                "Action Signal": stock_row.get("Action Signal", "-"),
                "Terminal Grade": stock_row.get("Terminal Grade", "-"),
                "Terminal Score": stock_row.get("Terminal Score", "-"),
                "Valuation Status": stock_row.get("Valuation Status", "-"),
                "Setup Quality": stock_row.get("Setup Quality", "-"),
                "Risk Level": stock_row.get("Risk Level", "-"),
                "Short Info": (
                    f"{stock_row.get('Action Signal', '-')} | "
                    f"{stock_row.get('Valuation Status', '-')} | "
                    f"Setup: {stock_row.get('Setup Quality', '-')} | "
                    f"Risiko: {stock_row.get('Risk Level', '-')}"
                ),
                "Data Source": snapshot.get("source_status", "-"),
            })

        progress.progress(idx / total if total else 1, text=f"Earningskalender: {idx}/{total} Aktien geprüft")

    progress.empty()

    earnings_df = pd.DataFrame(rows)

    if earnings_df.empty:
        return earnings_df

    earnings_df["_sort_days"] = pd.to_numeric(earnings_df["Days Until"], errors="coerce")
    earnings_df = earnings_df.sort_values(
        by=["_sort_days", "Ticker"],
        ascending=[True, True],
        na_position="last"
    ).drop(columns=["_sort_days"])

    return earnings_df


# ============================================================
# TITEL
# ============================================================

st.title("📊 Hartmuts Dashboard")

st.write(
    "Persönliches Aktien-Research-Terminal mit Signalen, Bewertung, Dividenden, "
    "Earnings, Watchlists und Lieferketten-Netzwerk."
)

# ============================================================
# TERMINAL DESIGN / COCKPIT
# ============================================================

st.markdown(
    """
<style>
    .terminal-hero {
        background: linear-gradient(135deg, #0f172a 0%, #111827 50%, #020617 100%);
        border: 1px solid rgba(148, 163, 184, 0.30);
        border-radius: 22px;
        padding: 22px 24px;
        margin: 12px 0 18px 0;
        box-shadow: 0 12px 34px rgba(2, 6, 23, 0.22);
    }
    .terminal-title {
        color: #f8fafc;
        font-size: 26px;
        font-weight: 850;
        margin-bottom: 5px;
        letter-spacing: -0.02em;
    }
    .terminal-subtitle {
        color: #cbd5e1;
        font-size: 15px;
        margin-bottom: 0;
    }
    .terminal-chip {
        display: inline-block;
        background: rgba(15, 23, 42, 0.72);
        border: 1px solid rgba(148, 163, 184, 0.28);
        color: #e5e7eb;
        padding: 5px 10px;
        border-radius: 999px;
        font-size: 12px;
        margin-right: 6px;
        margin-top: 8px;
    }
    .terminal-card {
        background: #ffffff;
        border: 1px solid #e5e7eb;
        border-radius: 18px;
        padding: 16px 18px;
        box-shadow: 0 8px 22px rgba(15, 23, 42, 0.07);
        margin-bottom: 12px;
    }
    .terminal-card-title {
        font-size: 14px;
        color: #64748b;
        font-weight: 700;
        text-transform: uppercase;
        letter-spacing: 0.04em;
        margin-bottom: 4px;
    }
    .terminal-card-value {
        font-size: 22px;
        color: #0f172a;
        font-weight: 850;
        margin-bottom: 4px;
    }
    .terminal-small {
        font-size: 13px;
        color: #64748b;
        line-height: 1.45;
    }
</style>
""",
    unsafe_allow_html=True
)

st.markdown(
    """
<div class="terminal-hero">
    <div class="terminal-title">🧭 Hartmut Research Terminal</div>
    <p class="terminal-subtitle">
        Deine zentrale Marktübersicht: Chancen, Risiken, Dividenden, Earnings, Nutzerlisten und Lieferketten-Zusammenhänge in einem kompakten Cockpit.
    </p>
    <span class="terminal-chip">Terminal Radar</span>
    <span class="terminal-chip">Bewertung</span>
    <span class="terminal-chip">Earnings</span>
    <span class="terminal-chip">Dividenden</span>
    <span class="terminal-chip">Netzwerk</span>
</div>
""",
    unsafe_allow_html=True
)


# ============================================================
# TERMINAL NAVIGATION / TABS
# ============================================================

# ============================================================
# INITIALER FILTER-FALLBACK
# ============================================================

# Einige Übersichtsmodule werden vor dem Sidebar-Filterblock gerendert.
# Damit diese Module nicht abbrechen, startet df_filtered zunächst als Kopie
# der vollständigen Analyse-Daten. Weiter unten wird df_filtered dann durch
# die echten Sidebar-Filter sauber überschrieben.
df_filtered = df.copy()

tab_overview, tab_analysis, tab_network, tab_lists, tab_earnings, tab_dividends, tab_admin = st.tabs([
    "📊 Übersicht",
    "🧠 Analyse",
    "🕸️ Netzwerk",
    "⭐ Listen",
    "📆 Earnings",
    "📅 Dividenden",
    "👑 Admin"
])

with tab_overview:

    # ============================================================
    # 📡 TERMINAL-RADAR: CHANCEN / RISIKEN / DIVIDENDEN
    # ============================================================

    with st.expander("📡 Terminal-Radar: Chancen, Risiken & Dividenden", expanded=True):
        radar_df = df_filtered.copy()

        for radar_numeric_column in [
            "Score",
            "Fundamental Score",
            "Valuation Score",
            "1M %",
            "6M %",
            "RSI"
        ]:
            if radar_numeric_column in radar_df.columns:
                radar_df[radar_numeric_column] = pd.to_numeric(
                    radar_df[radar_numeric_column],
                    errors="coerce"
                ).fillna(0)

        if "CRV" in radar_df.columns:
            radar_df["CRV Radar"] = pd.to_numeric(
                radar_df["CRV"],
                errors="coerce"
            ).fillna(0)
        else:
            radar_df["CRV Radar"] = 0

        if "Dividend Yield %" in radar_df.columns:
            radar_df["Dividend Yield Radar"] = pd.to_numeric(
                radar_df["Dividend Yield %"]
                .astype(str)
                .str.replace("%", "", regex=False)
                .str.replace(",", ".", regex=False)
                .replace("-", "0"),
                errors="coerce"
            ).fillna(0)
        else:
            radar_df["Dividend Yield Radar"] = 0

        radar_display_columns = [
            "Ticker",
            "Company",
            "Action Signal",
            "Valuation Status",
            "Score",
            "Fundamental Score",
            "Risk Level",
            "Price",
            "CRV",
            "Dividend Yield %"
        ]

        radar_display_columns = [
            column for column in radar_display_columns
            if column in radar_df.columns
        ]

        radar_col1, radar_col2, radar_col3 = st.columns(3)

        with radar_col1:
            st.markdown("#### 🟢 Top-Chancen")
            top_opportunities = radar_df.copy()
            if "Action Signal" in top_opportunities.columns:
                top_opportunities = top_opportunities[
                    top_opportunities["Action Signal"].astype(str).str.contains(
                        "BUY|TURNAROUND",
                        case=False,
                        na=False
                    )
                ]
            top_opportunities = top_opportunities.sort_values(
                by=["Score", "Fundamental Score", "CRV Radar", "Valuation Score"],
                ascending=[False, False, False, False]
            ).head(20)

            if top_opportunities.empty:
                st.info("Keine klaren Top-Chancen im aktuellen Filter.")
            else:
                st.dataframe(
                    top_opportunities[radar_display_columns],
                    width="stretch",
                    hide_index=True
                )

        with radar_col2:
            st.markdown("#### 🔴 Risiko-/Überhitzungsradar")
            risk_radar = radar_df.copy()
            risk_mask = pd.Series(False, index=risk_radar.index)

            if "Risk Level" in risk_radar.columns:
                risk_mask = risk_mask | (risk_radar["Risk Level"].astype(str) == "HIGH RISK")
            if "Action Signal" in risk_radar.columns:
                risk_mask = risk_mask | risk_radar["Action Signal"].astype(str).str.contains(
                    "AVOID|OVERHEATED|TAKE PROFIT",
                    case=False,
                    na=False
                )
            if "Valuation Status" in risk_radar.columns:
                risk_mask = risk_mask | risk_radar["Valuation Status"].astype(str).str.contains(
                    "überbewertet|teuer",
                    case=False,
                    na=False
                )

            risk_radar = risk_radar[risk_mask].sort_values(
                by=["Risk Level", "RSI", "1M %"],
                ascending=[True, False, False]
            ).head(20)

            if risk_radar.empty:
                st.info("Keine auffälligen Risiken im aktuellen Filter.")
            else:
                st.dataframe(
                    risk_radar[radar_display_columns],
                    width="stretch",
                    hide_index=True
                )

        with radar_col3:
            st.markdown("#### 💸 Dividendenradar")
            dividend_radar = radar_df[radar_df["Dividend Yield Radar"] > 0].copy()
            dividend_radar = dividend_radar.sort_values(
                by=["Dividend Yield Radar", "Fundamental Score", "Score"],
                ascending=[False, False, False]
            ).head(20)

            if dividend_radar.empty:
                st.info("Keine Dividendenwerte im aktuellen Filter.")
            else:
                st.dataframe(
                    dividend_radar[radar_display_columns],
                    width="stretch",
                    hide_index=True
                )


    # ============================================================
    # LEGENDE
    # ============================================================

    with st.expander("📖 Dashboard Legende", expanded=False):

        st.markdown("""

        # 📖 Dashboard-Legende & Entscheidungslogik

        Dieses Dashboard ist als **Research-Terminal** gedacht. Es kombiniert technische Signale, Fundamentaldaten, Bewertungsindikatoren, Dividenden, Watchlists und Lieferketten-Mapping. Die Signale sind **keine Kaufempfehlung**, sondern eine strukturierte Vorauswahl, damit interessante Aktien schneller sichtbar werden.

        ---

        ## 🧭 Grundidee

        Eine Aktie wird nicht nur nach einem einzigen Wert beurteilt. Das Dashboard schaut gleichzeitig auf:

        - **Trend / Momentum**: Läuft die Aktie technisch stabil oder schwach?
        - **Risiko**: Ist sie überhitzt, volatil oder technisch angeschlagen?
        - **Fundamentaldaten**: Gibt es Wachstum, Marge, Cashflow und solide Bewertung?
        - **Bewertung**: Wirkt sie im Verhältnis zu Qualität und Wachstum eher günstig oder teuer?
        - **Chance-Risiko-Verhältnis**: Passt das mögliche Ziel zum angenommenen Risiko?
        - **Kontext**: Hängt die Aktie an starken Trends wie KI, Cloud, Energie, Defense oder Cybersecurity?

        ---

        ## 📈 Technischer Score / Score-System

        Der normale **Score** ist ein technischer Punktwert. Er misst, ob Trend und Momentum stimmen.

        Eine Aktie bekommt Punkte für:

        - Kurs über **EMA20**
        - Kurs über **EMA50**
        - Kurs über **EMA100**
        - **EMA20 > EMA50**
        - **EMA50 > EMA100**
        - positive Wochenperformance
        - positive Monatsperformance
        - RSI im gesunden Bereich

        **Maximaler Score: 8**

        Interpretation:

        - **0–2** → technisch schwach
        - **3–4** → gemischt / noch kein klares Setup
        - **5–6** → technisch interessant
        - **7–8** → technisch stark

        Wichtig: Ein hoher Score heißt nicht automatisch „kaufen“. Eine Aktie kann technisch stark sein, aber trotzdem teuer, überhitzt oder fundamental schwach.

        ---

        ## 🧬 Fundamental Score

        Der **Fundamental Score** bewertet grob die Qualität einer Aktie anhand vorhandener Daten wie:

        - Umsatzwachstum
        - Gewinnwachstum
        - Gewinnmarge
        - Free Cashflow
        - Operating Cashflow
        - Verschuldung
        - KGV / Forward KGV
        - PEG Ratio

        Interpretation:

        - **0–2** → schwach oder Daten fehlen
        - **3–4** → gemischt
        - **5–6** → solide
        - **7–8** → sehr solide

        Wenn Fundamentaldaten fehlen, wertet das Dashboard die Aktie nicht automatisch schlecht. Es zeigt dann eher „unvollständige Daten“ oder „Unklar“.

        ---

        ## 💎 Valuation Status / Bewertungshinweis

        Der **Valuation Status** ist eine regelbasierte Einordnung:

        - **💎 Eher unterbewertet** → Bewertung wirkt im Verhältnis zu Qualität, Wachstum und Cashflow attraktiv.
        - **⚖️ Fair bewertet** → Bewertung wirkt vertretbar, aber nicht extrem günstig.
        - **⚖️ Fair bis leicht teuer** → nicht dramatisch teuer, aber kein klarer Bewertungsabschlag.
        - **🔥 Eher überbewertet** → Bewertung wirkt anspruchsvoll, vor allem wenn KGV/PEG hoch sind.
        - **❓ Unklar** → zu wenige Daten vorhanden.

        Verwendete Faktoren:

        - Forward KGV
        - Trailing KGV
        - PEG Ratio
        - Umsatzwachstum
        - Gewinnwachstum
        - Gewinnmarge
        - Free Cashflow
        - Fundamental Score

        Wichtig: Das ist **kein echter Fair Value** und kein DCF-Modell. Es ist ein Bewertungsfilter, der dir hilft, teure Hype-Aktien und mögliche Preis-Leistungs-Chancen schneller zu erkennen.

        ---

        ## 🧮 Valuation Score

        Der **Valuation Score** ist der Zahlenwert hinter dem Bewertungshinweis.

        Grobe Interpretation:

        - **ab +4** → eher günstig im Verhältnis zur Qualität
        - **+1 bis +3** → fair / vertretbar
        - **0 bis -2** → fair bis teuer / gemischt
        - **ab -3** → eher teuer oder fundamental schwach

        Der Score wird besser, wenn z. B. KGV/PEG attraktiv sind, Wachstum positiv ist und Cashflow/Marge stimmen. Er wird schlechter, wenn Bewertung hoch ist, Wachstum negativ ist oder Cashflow/Marge schwach sind.

        ---

        ## 🧭 Setup Quality

        **Setup Quality** beschreibt die Qualität des aktuellen Setups abhängig vom gewählten Strategie-Horizont.

        Beispiele:

        - **Sehr gut** → Technik, Risiko, CRV und Fundamentaldaten passen gut zusammen.
        - **Kurzfristig stark** → gutes Momentum, gesunder RSI, Kurs über wichtigen EMAs.
        - **Langfristig solide** → Fundamentaldaten und Langfristtrend wirken stabil.
        - **Spekulativ** → Aktie könnte interessant sein, aber Risiko/Unsicherheit ist höher.
        - **Neutral / beobachten** → kein klares Kauf- oder Verkaufssignal.
        - **Überhitzt** → Aktie ist stark gelaufen, RSI und Momentum wirken heiß.
        - **Schwach** → technische oder fundamentale Warnsignale überwiegen.

        Setup Quality ist also die textliche Kurzbeschreibung des aktuellen Setups.

        ---

        ## 🎯 Action Signal

        Das **Action Signal** ist die wichtigste Ampel des Dashboards.

        ### 🟢 BUY ZONE

        Eine Aktie kommt in die BUY ZONE, wenn mehrere Bedingungen zusammenpassen:

        - technischer Score stark genug
        - Rating positiv
        - Risiko nicht zu hoch
        - RSI nicht überhitzt
        - Chance-Risiko-Verhältnis sinnvoll
        - je nach Strategie-Horizont auch Fundamentaldaten ausreichend solide

        Bedeutung: Die Aktie ist interessant genug, um genauer geprüft zu werden. Es ist keine automatische Kaufempfehlung.

        ### 🟡 WATCH

        WATCH bedeutet: Die Aktie ist interessant, aber ein wichtiger Baustein fehlt noch.

        Häufige Gründe:

        - CRV noch zu schwach
        - RSI zu hoch oder zu niedrig
        - Trend noch nicht bestätigt
        - Fundamentaldaten gemischt
        - Bewertung nicht klar attraktiv

        ### 🔵 TURNAROUND WATCH

        TURNAROUND WATCH ist für Aktien gedacht, die vorher deutlich gefallen sind, aber erste Stabilisierung zeigen.

        Typische Kriterien:

        - 6M Performance stark negativ
        - 1M Performance wieder positiv
        - Kurs zurück über EMA20
        - RSI erholt sich über 40

        Bedeutung: Erste Trendwende möglich, aber spekulativer als BUY ZONE. Hier ist Bestätigung besonders wichtig.

        ### 🟠 TAKE PROFIT / OVERHEATED

        Dieses Signal erscheint, wenn eine Aktie kurzfristig stark gelaufen ist.

        Typische Merkmale:

        - RSI über 72
        - starke 1M Performance
        - Kurs deutlich über kurzfristigen Durchschnitten

        Bedeutung: Nicht automatisch verkaufen, aber Risiko von Rücksetzern steigt.

        ### 🔴 SELL / AVOID

        SELL / AVOID erscheint bei klaren Warnsignalen:

        - technischer Score sehr schwach
        - Rating negativ
        - hohes Risiko plus schwache Performance
        - schwacher Fundamental Score
        - negativer Trend

        Bedeutung: Aktie aktuell eher meiden oder sehr kritisch prüfen.

        ---

        ## 🧭 Strategie-Horizont

        Der Sidebar-Schalter **Strategie-Horizont** verändert die Bewertung:

        - **Kurzfristig** → Fokus auf EMA20, RSI, 1M-Momentum, kurzfristigen Stop und CRV.
        - **Mittelfristig** → Mischung aus Technik, Risiko, CRV und Fundamentaldaten. Das ist der Standardmodus.
        - **Langfristig** → Fokus auf Fundamental Score, Cashflow, Marge, Wachstum, Verschuldung und EMA100.

        Dadurch kann dieselbe Aktie je nach Horizont unterschiedlich bewertet werden. Eine Aktie kann kurzfristig überhitzt sein, aber langfristig trotzdem solide.

        ---

        ## ⚖️ CRV / Chance-Risiko-Verhältnis

        Das **CRV** vergleicht mögliches Ziel mit möglichem Risiko.

        Vereinfacht:

        - **CRV unter 1,2** → eher schwach
        - **CRV 1,2 bis 1,5** → okay, aber nicht stark
        - **CRV ab 1,5** → interessant
        - **CRV ab 2,0** → sehr attraktiv, wenn die Annahmen realistisch sind

        Ziel 1 basiert bevorzugt auf dem **52-Wochen-Hoch**, sofern dieses sinnvoll über dem aktuellen Kurs liegt. Falls nicht, nutzt das Dashboard ein vorsichtiges Fallback-Ziel je nach Strategie-Horizont.

        ---

        ## 📉 RSI

        RSI = Relative Strength Index.

        - **unter 30** → überverkauft / sehr schwach
        - **30–40** → angeschlagen, aber mögliche Stabilisierung
        - **40–70** → gesunder Bereich
        - **über 70** → überkauft / heiß gelaufen
        - **über 72/78** → Risiko für Rücksetzer steigt je nach Strategie-Modus

        ---

        ## ⚠ Risk Level

        Das Risk Level betrachtet technische Risikofaktoren wie:

        - Abstand zum EMA20
        - RSI-Überhitzung
        - Volatilität
        - Beta
        - schwache Trendstruktur

        Interpretation:

        - **LOW RISK** → ruhigeres Setup
        - **MEDIUM RISK** → normales Risiko
        - **HIGH RISK** → größere Schwankungen oder technische Warnsignale

        ---

        ## 🧪 Terminal Score / Terminal Grade

        Der **Terminal Score** fasst mehrere Module zusammen:

        - Action Signal
        - technischer Score
        - Fundamental Score
        - Bewertung
        - Risiko
        - CRV

        Daraus entsteht ein Terminal Grade, z. B.:

        - **A · Stark** → viele Faktoren passen zusammen
        - **B · Interessant** → gutes Setup, aber nicht perfekt
        - **C · Beobachten** → gemischt, noch kein klarer Vorteil
        - **D · Schwach** → mehrere Warnsignale

        Der Terminal Score soll dir helfen, viele Aktien schneller zu sortieren.

        ---


        ---

        ## 📆 Earnings / Earningskalender

        Der **Earningskalender** zeigt kommende Quartalszahlen-Termine, soweit sie über die Datenquelle verfügbar sind. Er hilft dir, vor wichtigen Unternehmensereignissen nicht überrascht zu werden.

        Angezeigt werden unter anderem:

        - erwartetes Earnings-Datum
        - Tage bis zum Termin
        - verfügbare EPS-Schätzungen
        - verfügbare Umsatz-Schätzungen
        - aktuelles Terminal Grade / Terminal Score
        - Action Signal, Bewertung und Risiko der Aktie

        Interpretation:

        - **Kurz vor Earnings** können Kurse stärker schwanken.
        - Eine Aktie mit gutem Setup kann nach starken Zahlen weiterlaufen, aber bei Enttäuschung auch stark fallen.
        - Bei High-Risk- oder Turnaround-Aktien sind Earnings besonders wichtig, weil sie die These bestätigen oder zerstören können.
        - Fehlende Schätzwerte bedeuten nicht automatisch, dass keine Earnings existieren — manchmal liefert Yahoo/yfinance nur keine verwertbaren Daten.

        Der Earningskalender ist deshalb ein **Risikokalender** und kein Kaufsignal. Vor Earnings sollte man Positionsgröße, Stop-Loss und Erwartungshaltung prüfen.

        ## 📡 Terminal-Radar

        Der Terminal-Radar zeigt schnelle Vorauswahlen:

        - **Top-Chancen** → Aktien mit BUY/TURNAROUND-Signal, hohem Score, guter Bewertung oder gutem CRV.
        - **Risiko-/Überhitzungsradar** → Aktien mit HIGH RISK, AVOID, TAKE PROFIT, OVERHEATED oder teurer Bewertung.
        - **Dividendenradar** → Aktien mit Dividendenrendite, sortiert nach Rendite und Qualität.

        Der Radar ersetzt keine Einzelprüfung, ist aber gut, um Kandidaten schneller zu finden.

        ---

        ## 🕸️ Netzwerk / Lieferketten-Mapping

        Das Mapping zeigt, welche Aktien miteinander verbunden sind.

        Beispiele:

        - **NVIDIA → TSMC / ASML / Micron / Vertiv / Microsoft**
        - **Apple → TSMC / Foxconn / Qualcomm / Broadcom**
        - **Defense → Rheinmetall / Hensoldt / Lockheed / RTX**

        Die Verbindung kann sein:

        - Lieferant / Zulieferer
        - Kunde / Nachfrage
        - Konkurrenz
        - Infrastruktur / Ermöglicher
        - Energie / Strombedarf
        - Speicher / HBM
        - Cloud / Plattform

        Ziel: Du sollst erkennen, **welche Aktien indirekt mit einem Trend oder einer Hauptaktie zusammenhängen**.

        ---

        ## 🍕 PizzINT / Geopolitischer Stress

        Der PizzINT-Bereich ist ein experimenteller OSINT-/Stressindikator. Das DOUGHCON-Level wird aktuell manuell gesetzt, weil wir keine offizielle stabile API von PizzINT verwenden.

        Die Idee dahinter:

        - bei höherem geopolitischem Stress defensive Sektoren stärker beobachten
        - Energie, Gold, Cybersecurity, Defense und Cash-Risiko stärker einordnen
        - spekulative High-Risk-/Turnaround-Aktien vorsichtiger bewerten

        ---

        ## 📅 Dividendenkalender

        Der Dividendenkalender filtert nach Ex-Dividenden-Datum. Wichtig: Der Kalender zeigt nur passende Dividendenereignisse, aber die Aktien bleiben in Übersicht und Gesamttabelle weiterhin sichtbar.

        ---

        ## Wichtig

        Alle Signale sind regelbasierte Orientierungshilfen. Sie ersetzen keine eigene Recherche, keine Fundamentalanalyse und keine Risikoprüfung. Das Dashboard soll helfen, schneller zu sortieren und Zusammenhänge zu erkennen.

        """)


    # ============================================================
    # 🍕 PIZZINT / GEOPOLITISCHER STRESS-INDIKATOR
    # ============================================================

    with st.expander("🍕 PizzINT / Geopolitischer Stress-Indikator", expanded=False):
        st.divider()

        st.subheader("🍕 PizzINT / Geopolitischer Stress-Indikator")

        st.caption(
            "Experimenteller OSINT-Indikator. Die Daten dienen nur als zusätzlicher "
            "Stimmungs- und Risiko-Hinweis und ersetzen keine Marktanalyse."
        )

        # Manuelle Einschätzung, kann später automatisiert werden.
        doughcon_level = st.selectbox(
            "DOUGHCON-Level einschätzen",
            options=[
                "1 - Ruhig",
                "2 - Beobachten",
                "3 - Erhöhte Aufmerksamkeit",
                "4 - Hoher Stress",
                "5 - Krisenmodus"
            ],
            index=2
        )

        if doughcon_level.startswith("1"):
            stress_label = "🟢 Niedrig"
            market_view = (
                "Normales Marktumfeld. Fokus bleibt auf technischen Signalen, "
                "Bewertungen und Trendstruktur."
            )
            focus_assets = "Qualitätsaktien, Tech, Dividendenwerte, breite Indizes"
        elif doughcon_level.startswith("2"):
            stress_label = "🟡 Leicht erhöht"
            market_view = (
                "Etwas mehr Vorsicht. Watchlist enger beobachten, "
                "aber keine Paniksignale."
            )
            focus_assets = "Qualitätsaktien, Cash-Reserve, defensive Werte"
        elif doughcon_level.startswith("3"):
            stress_label = "🟠 Erhöht"
            market_view = (
                "Geopolitische Risiken könnten stärker eingepreist werden. "
                "Turnaround- und High-Risk-Aktien vorsichtiger behandeln."
            )
            focus_assets = "Energie, Gold, Rüstung, Cybersecurity, defensive Aktien"
        elif doughcon_level.startswith("4"):
            stress_label = "🔴 Hoch"
            market_view = (
                "Risiko-Modus. Neue Käufe strenger prüfen, Stops enger beobachten, "
                "volatile Titel reduzieren."
            )
            focus_assets = "Gold, Energie, Rüstung, Cash, defensive Dividendenwerte"
        else:
            stress_label = "🚨 Extrem"
            market_view = (
                "Krisenmodus. Kapitalerhalt priorisieren, keine impulsiven Käufe, "
                "Marktreaktionen abwarten."
            )
            focus_assets = "Cash, Gold, kurzfristige Absicherung, defensive Sektoren"

        col_geo1, col_geo2, col_geo3 = st.columns(3)

        with col_geo1:
            st.metric("Geopolitischer Stress", stress_label)

        with col_geo2:
            st.metric("DOUGHCON", doughcon_level.split(" - ")[0])

        with col_geo3:
            st.metric("Marktmodus", "Risk Check")

        st.info(market_view)
        st.caption(f"Aktuell besonders beobachten: {focus_assets}")

        geo_focus_df = pd.DataFrame([
            {
                "Bereich": "Energie",
                "Warum relevant?": "Öl, Gas und Energiepreise reagieren oft sensibel auf geopolitische Spannungen.",
                "Beispiele": "XOM, CVX, SHEL, BP, ENPH"
            },
            {
                "Bereich": "Rüstung / Verteidigung",
                "Warum relevant?": "Verteidigungswerte können bei erhöhter Sicherheitslage stärker beobachtet werden.",
                "Beispiele": "LMT, RTX, NOC, HAG.DE, RHM.DE"
            },
            {
                "Bereich": "Cybersecurity",
                "Warum relevant?": "Cyberrisiken steigen häufig bei geopolitischen Konflikten.",
                "Beispiele": "CRWD, PANW, FTNT, ZS"
            },
            {
                "Bereich": "Gold / Sicherheit",
                "Warum relevant?": "Gold wird oft als sicherer Hafen betrachtet.",
                "Beispiele": "GOLD, NEM, AEM, GLD"
            },
            {
                "Bereich": "High-Risk / Turnaround",
                "Warum relevant?": "Spekulative Aktien können in Stressphasen stärker fallen.",
                "Beispiele": "enger prüfen, Positionsgröße reduzieren"
            }
        ])

        st.markdown("### 🧭 Mögliche Markt-Fokusbereiche")

        st.dataframe(
            geo_focus_df,
            width="stretch",
            hide_index=True
        )

        st.markdown("### 🍕 PizzINT Watch")

        pizza_watch_df = pd.DataFrame([
            {
                "Signal": "Pizza-Aktivität",
                "Interpretation": "Kann als humorvoller OSINT-Stimmungsindikator beobachtet werden.",
                "Relevanz fürs Portfolio": "Nur Zusatzsignal, niemals alleinige Entscheidungsbasis."
            },
            {
                "Signal": "DOUGHCON steigt",
                "Interpretation": "Mehr geopolitische Aufmerksamkeit.",
                "Relevanz fürs Portfolio": "Risk-Management prüfen, defensive Sektoren beobachten."
            },
            {
                "Signal": "DOUGHCON fällt",
                "Interpretation": "Lage wirkt entspannter.",
                "Relevanz fürs Portfolio": "Normale technische und fundamentale Signale stärker gewichten."
            }
        ])

        st.dataframe(
            pizza_watch_df,
            width="stretch",
            hide_index=True
        )

        st.link_button(
            "🍕 PizzINT extern öffnen",
            "https://www.pizzint.watch/"
        )



with tab_network:
    # ============================================================
    # 🕸️ AKTIEN-NETZWERK / THEMEN-MAPPING
    # ============================================================

    with st.expander("🕸️ Aktien-Netzwerk / Themen-Mapping", expanded=True):
        st.divider()

        st.subheader("🕸️ Aktien-Netzwerk / Themen-Mapping")

        st.markdown(
            """
            <div class="terminal-panel">
                <h3>Market Relationship Terminal</h3>
                <p>Wähle eine Hauptaktie und erkenne, welche Unternehmen in der Wertschöpfungskette, als Zulieferer, Kunden, Konkurrenz oder Infrastrukturpartner daran hängen.</p>
            </div>
            """,
            unsafe_allow_html=True
        )

        RELATIONSHIPS_FILE = "stock_relationships.csv"

        def infer_supply_chain_stage(category, relationship):
            """Leitet eine Lieferketten-/Wertschöpfungsstufe aus Kategorie und Beschreibung ab."""

            text_value = f"{category} {relationship}".lower()

            stage_rules = [
                ("1 - Rohstoffe / Energie", ["uran", "öl", "gas", "gold", "lithium", "kupfer", "rohstoff", "energie /", "stromerzeugung", "atomstrom"]),
                ("2 - Energie- & Strominfrastruktur", ["strom", "netz", "elektrifizierung", "energieausrüstung", "strominfrastruktur", "rechenzentrum", "kühlung", "vertiv", "eaton"]),
                ("3 - Produktionsausrüstung", ["lithografie", "chipausrüstung", "equipment", "prozesskontrolle", "maschinen", "fertigungsanlagen"]),
                ("4 - Fertigung / Foundry", ["foundry", "fertigung", "chipfertigung", "tsmc", "samsung foundry"]),
                ("5 - Komponenten / Speicher / Chips", ["speicher", "hbm", "dram", "nand", "gpu", "cpu", "custom chips", "chips", "beschleuniger", "netzwerk / custom"]),
                ("6 - Server / Netzwerk / Infrastruktur", ["server", "netzwerk", "interconnect", "datacenter", "dateninfrastruktur", "ki-infrastruktur"]),
                ("7 - Plattform / Cloud / Software", ["cloud", "hyperscaler", "azure", "aws", "google cloud", "oracle", "software", "cybersecurity", "identity"]),
                ("8 - Endmarkt / Nachfrage", ["modelle", "nachfrage", "enterprise", "werbung", "automotive", "ev", "pharma", "kunden"]),
                ("9 - Konkurrenz / Substitution", ["konkurrenz", "competition", "substitution", "eigene chips", "tpu", "trainium"]),
                ("10 - Risiko / Geopolitik / Defense", ["verteidigung", "defense", "geopolitik", "drohnen", "sensorik", "sicherheit"]),
            ]

            for stage, keywords in stage_rules:
                if any(keyword in text_value for keyword in keywords):
                    return stage

            return "99 - Sonstige Verbindung"

        def infer_connection_type(category, relationship, risk_note):
            """Leitet die Art der Verbindung ab: Lieferant, Kunde, Konkurrenz, Infrastruktur usw."""

            text_value = f"{category} {relationship} {risk_note}".lower()

            if any(word in text_value for word in ["konkurrenz", "konkurriert", "competition", "substitution", "eigene chips", "tpu", "trainium"]):
                return "Konkurrenz / Substitution"
            if any(word in text_value for word in ["liefert", "anbieter", "zuliefer", "fertigt", "maschinen", "anlagen", "speicher", "hbm"]):
                return "Lieferant / Zulieferer"
            if any(word in text_value for word in ["nutzt", "kauft", "nachfrage", "kunde", "cloud", "hyperscaler", "enterprise"]):
                return "Kunde / Nachfrage"
            if any(word in text_value for word in ["strom", "energie", "kühlung", "netz", "rechenzentrum", "infrastruktur"]):
                return "Infrastruktur / Ermöglicher"
            if any(word in text_value for word in ["risiko", "taiwan", "regulierung", "export", "geopolitik", "defense", "verteidigung"]):
                return "Risiko / Makro"

            return "Strategische Verbindung"

        if not os.path.exists(RELATIONSHIPS_FILE):

            st.warning(
                "Die Datei stock_relationships.csv wurde nicht gefunden. "
                "Bitte lege sie in den gleichen Ordner wie dashboard.py."
            )

        else:

            try:
                relationships_df = pd.read_csv(
                    RELATIONSHIPS_FILE,
                    encoding="utf-8",
                    sep=None,
                    engine="python"
                )
            except UnicodeDecodeError:
                try:
                    relationships_df = pd.read_csv(
                        RELATIONSHIPS_FILE,
                        encoding="latin1",
                        sep=None,
                        engine="python"
                    )
                except Exception as error:
                    st.error(f"stock_relationships.csv konnte nicht geladen werden: {error}")
                    relationships_df = pd.DataFrame()
            except Exception as error:
                st.error(f"stock_relationships.csv konnte nicht geladen werden: {error}")
                relationships_df = pd.DataFrame()

            needed_relationship_columns = [
                "source_ticker",
                "target_ticker",
                "target_name",
                "category",
                "relationship",
                "importance",
                "risk_note"
            ]

            missing_relationship_columns = [
                column for column in needed_relationship_columns
                if column not in relationships_df.columns
            ]

            if relationships_df.empty:

                st.info("Die Datei stock_relationships.csv ist noch leer.")

            elif missing_relationship_columns:

                st.error(
                    "In stock_relationships.csv fehlen diese Spalten: "
                    + ", ".join(missing_relationship_columns)
                )

            else:

                relationships_df = relationships_df.copy()

                for text_column in [
                    "source_ticker",
                    "target_ticker",
                    "target_name",
                    "category",
                    "relationship",
                    "importance",
                    "risk_note"
                ]:
                    relationships_df[text_column] = (
                        relationships_df[text_column]
                        .astype(str)
                        .str.strip()
                    )

                # Neue Mapping-Logik: Auch wenn die CSV diese Spalten noch nicht hat,
                # werden Lieferkettenstufe und Verbindungsart automatisch abgeleitet.
                if "supply_chain_stage" not in relationships_df.columns:
                    relationships_df["supply_chain_stage"] = relationships_df.apply(
                        lambda row: infer_supply_chain_stage(
                            row.get("category", ""),
                            row.get("relationship", "")
                        ),
                        axis=1
                    )
                else:
                    relationships_df["supply_chain_stage"] = (
                        relationships_df["supply_chain_stage"]
                        .astype(str)
                        .str.strip()
                    )

                if "connection_type" not in relationships_df.columns:
                    relationships_df["connection_type"] = relationships_df.apply(
                        lambda row: infer_connection_type(
                            row.get("category", ""),
                            row.get("relationship", ""),
                            row.get("risk_note", "")
                        ),
                        axis=1
                    )
                else:
                    relationships_df["connection_type"] = (
                        relationships_df["connection_type"]
                        .astype(str)
                        .str.strip()
                    )

                available_network_tickers = sorted(
                    relationships_df["source_ticker"]
                    .dropna()
                    .unique()
                    .tolist()
                )

                def reset_network_filters():
                    """Setzt die Netzwerkfilter zurück, bevor die Filter-Widgets neu aufgebaut werden."""
                    st.session_state["network_selected_category"] = "Alle"
                    st.session_state["network_selected_supply_chain_stage"] = "Alle"
                    st.session_state["network_selected_connection_type"] = "Alle"

                def switch_network_center(ticker):
                    """Wechselt das Netzwerk-Zentrum ohne URL-Wechsel, damit der Login erhalten bleibt."""
                    ticker = str(ticker).strip().upper()

                    if ticker in available_network_tickers:
                        st.session_state["_network_center_ticker"] = ticker
                        st.session_state["_network_picker"] = ticker
                        reset_network_filters()

                def on_network_picker_change():
                    """Reagiert auf manuelle Auswahl im Dropdown."""
                    ticker = str(st.session_state.get("_network_picker", "")).strip().upper()

                    if ticker in available_network_tickers:
                        st.session_state["_network_center_ticker"] = ticker
                        reset_network_filters()

                if "_network_center_ticker" not in st.session_state:
                    st.session_state["_network_center_ticker"] = available_network_tickers[0]

                if st.session_state["_network_center_ticker"] not in available_network_tickers:
                    st.session_state["_network_center_ticker"] = available_network_tickers[0]

                if "_network_picker" not in st.session_state:
                    st.session_state["_network_picker"] = st.session_state["_network_center_ticker"]

                if st.session_state["_network_picker"] not in available_network_tickers:
                    st.session_state["_network_picker"] = st.session_state["_network_center_ticker"]

                selected_index = available_network_tickers.index(
                    st.session_state["_network_center_ticker"]
                )

                selected_network_ticker = st.selectbox(
                    "Aktie für Netzwerk auswählen",
                    options=available_network_tickers,
                    index=selected_index,
                    key="_network_picker",
                    on_change=on_network_picker_change
                )

                selected_network_ticker = st.session_state.get(
                    "_network_center_ticker",
                    selected_network_ticker
                )

                selected_relationships_base = relationships_df[
                    relationships_df["source_ticker"] == selected_network_ticker
                ].copy()

                col_net_1, col_net_2, col_net_3, col_net_4 = st.columns(4)

                with col_net_1:
                    st.metric(
                        "Verbindungen",
                        len(selected_relationships_base)
                    )

                with col_net_2:
                    st.metric(
                        "Kategorien",
                        selected_relationships_base["category"].nunique()
                        if not selected_relationships_base.empty else 0
                    )

                with col_net_3:
                    st.metric(
                        "Lieferkettenstufen",
                        selected_relationships_base["supply_chain_stage"].nunique()
                        if not selected_relationships_base.empty else 0
                    )

                with col_net_4:
                    high_count = (
                        selected_relationships_base["importance"]
                        .astype(str)
                        .str.lower()
                        .isin(["hoch", "high"])
                        .sum()
                        if not selected_relationships_base.empty else 0
                    )
                    st.metric(
                        "Hohe Relevanz",
                        int(high_count)
                    )

                if selected_relationships_base.empty:

                    st.info("Für diese Aktie sind noch keine Beziehungen hinterlegt.")

                else:

                    filter_col_1, filter_col_2, filter_col_3 = st.columns(3)

                    with filter_col_1:
                        category_options = ["Alle"] + sorted(
                            selected_relationships_base["category"]
                            .dropna()
                            .astype(str)
                            .unique()
                            .tolist()
                        )

                        selected_network_category = st.selectbox(
                            "Kategorie filtern",
                            options=category_options,
                            index=0,
                            key="network_selected_category"
                        )

                    with filter_col_2:
                        stage_options = ["Alle"] + sorted(
                            selected_relationships_base["supply_chain_stage"]
                            .dropna()
                            .astype(str)
                            .unique()
                            .tolist()
                        )

                        selected_supply_chain_stage = st.selectbox(
                            "Lieferkettenstufe filtern",
                            options=stage_options,
                            index=0,
                            key="network_selected_supply_chain_stage"
                        )

                    with filter_col_3:
                        connection_type_options = ["Alle"] + sorted(
                            selected_relationships_base["connection_type"]
                            .dropna()
                            .astype(str)
                            .unique()
                            .tolist()
                        )

                        selected_connection_type = st.selectbox(
                            "Verbindungsart filtern",
                            options=connection_type_options,
                            index=0,
                            key="network_selected_connection_type"
                        )

                    selected_relationships = selected_relationships_base.copy()

                    if selected_network_category != "Alle":
                        selected_relationships = selected_relationships[
                            selected_relationships["category"] == selected_network_category
                        ]

                    if selected_supply_chain_stage != "Alle":
                        selected_relationships = selected_relationships[
                            selected_relationships["supply_chain_stage"] == selected_supply_chain_stage
                        ]

                    if selected_connection_type != "Alle":
                        selected_relationships = selected_relationships[
                            selected_relationships["connection_type"] == selected_connection_type
                        ]

                    dashboard_signal_columns = [
                        "Ticker",
                        "Company",
                        "Action Signal",
                        "Rating",
                        "Score",
                        "Risk Level",
                        "Price",
                        "CRV"
                    ]

                    available_signal_columns = [
                        column for column in dashboard_signal_columns
                        if column in df.columns
                    ]

                    signal_df = df[available_signal_columns].copy()
                    signal_df["Ticker"] = signal_df["Ticker"].astype(str).str.strip()

                    network_view = selected_relationships.merge(
                        signal_df,
                        left_on="target_ticker",
                        right_on="Ticker",
                        how="left"
                    )

                    network_view["Ticker"] = network_view["target_ticker"]

                    if "Company" in network_view.columns:
                        network_view["Company"] = network_view["Company"].fillna(
                            network_view["target_name"]
                        )
                    else:
                        network_view["Company"] = network_view["target_name"]

                    importance_order = {
                        "hoch": 1,
                        "high": 1,
                        "mittel": 2,
                        "medium": 2,
                        "niedrig": 3,
                        "low": 3
                    }

                    network_view["Importance Sort"] = (
                        network_view["importance"]
                        .astype(str)
                        .str.lower()
                        .map(importance_order)
                        .fillna(9)
                    )

                    network_view = network_view.sort_values(
                        by=["supply_chain_stage", "category", "Importance Sort", "Ticker"],
                        ascending=True
                    )

                    display_columns = [
                        "supply_chain_stage",
                        "connection_type",
                        "category",
                        "Ticker",
                        "Company",
                        "importance",
                        "relationship",
                        "risk_note",
                        "Action Signal",
                        "Rating",
                        "Score",
                        "Risk Level",
                        "Price",
                        "CRV"
                    ]

                    display_columns = [
                        column for column in display_columns
                        if column in network_view.columns
                    ]

                    network_display = network_view[display_columns].rename(columns={
                        "supply_chain_stage": "Lieferkettenstufe",
                        "connection_type": "Verbindungsart",
                        "category": "Kategorie",
                        "importance": "Wichtigkeit",
                        "relationship": "Warum verbunden?",
                        "risk_note": "Risiko-Hinweis"
                    })

                    # ============================================================
                    # ============================================================
                    # 🕸️ PROFI-SPINNENNETZ / WERTSCHÖPFUNGSKETTE
                    # ============================================================

                    # ============================================================
                    # 🕸️ PROFI-NETZWERK / FOKUS-WERTSCHÖPFUNGSKETTE
                    # ============================================================

                    with st.expander("🕸️ Netzwerk / Wertschöpfungskette anzeigen", expanded=False):
                        st.caption(
                            "Ruhige Profi-Ansicht: keine Physik, kein Wackeln. "
                            "Ein Klick zeigt Details rechts. Den Mittelpunkt wechselst du zuverlässig über die Buttons unter dem Netzwerk."
                        )

                        import json
                        import math
                        import html

                        def get_connection_color(connection_type, action_signal=""):
                            text_value = f"{connection_type} {action_signal}".lower()
                            if "avoid" in text_value or "sell" in text_value or "schwach" in text_value:
                                return "#ef4444"
                            if "konkurrenz" in text_value or "substitution" in text_value:
                                return "#f97316"
                            if "lieferant" in text_value or "zulieferer" in text_value:
                                return "#22c55e"
                            if "kunde" in text_value or "nachfrage" in text_value:
                                return "#8b5cf6"
                            if "infrastruktur" in text_value or "energie" in text_value or "strom" in text_value:
                                return "#f59e0b"
                            if "risk" in text_value or "risiko" in text_value:
                                return "#f43f5e"
                            return "#38bdf8"

                        def get_signal_badge(action_signal):
                            text_value = str(action_signal)
                            low_value = text_value.lower()
                            if "buy" in low_value:
                                return "BUY", "#22c55e"
                            if "watch" in low_value:
                                return "WATCH", "#eab308"
                            if "avoid" in low_value or "sell" in low_value:
                                return "RISK", "#ef4444"
                            if text_value.strip() in ["", "nan", "None"]:
                                return "N/A", "#64748b"
                            return text_value[:10], "#38bdf8"

                        spider_records = network_view.fillna("").to_dict(orient="records")

                        if not spider_records:
                            st.info("Für die aktuelle Auswahl gibt es keine Netzwerkdaten.")
                        else:
                            total_network_records = len(spider_records)

                            st.caption(
                                f"Für {selected_network_ticker} sind {total_network_records} Beziehungen vorhanden. "
                                "Für das Spinnennetz werden nur die wichtigsten angezeigt; die vollständige Liste bleibt unten als Tabelle sichtbar."
                            )

                            network_display_mode = st.radio(
                                "Darstellung im Spinnennetz",
                                options=[
                                    "Top-Beziehungen",
                                    "Ausbalanciert nach Lieferkettenstufen",
                                    "Alle gefilterten Beziehungen"
                                ],
                                index=0,
                                horizontal=True,
                                key=f"spider_display_mode_{selected_network_ticker}"
                            )

                            max_slider_upper = min(80, max(10, total_network_records))
                            default_nodes = min(28, max_slider_upper)

                            max_visible_nodes = st.slider(
                                "Maximale Aktien im Spinnennetz",
                                min_value=10,
                                max_value=max_slider_upper,
                                value=default_nodes,
                                step=5,
                                key=f"spider_max_nodes_static_{selected_network_ticker}"
                            )

                            def relationship_priority(row):
                                importance_sort = row.get("Importance Sort", 9)
                                try:
                                    importance_sort = int(float(importance_sort))
                                except Exception:
                                    importance_sort = 9

                                action_signal = str(row.get("Action Signal", "")).lower()
                                has_dashboard_signal = 0 if action_signal and action_signal not in ["nan", "none"] else 1

                                if "strong buy" in action_signal:
                                    signal_sort = 0
                                elif "buy" in action_signal:
                                    signal_sort = 1
                                elif "turnaround" in action_signal:
                                    signal_sort = 2
                                elif "watch" in action_signal:
                                    signal_sort = 3
                                elif "avoid" in action_signal or "sell" in action_signal:
                                    signal_sort = 5
                                else:
                                    signal_sort = 4

                                stage = str(row.get("supply_chain_stage", "99"))
                                category = str(row.get("category", ""))
                                ticker = str(row.get("Ticker", row.get("target_ticker", "")))

                                return (
                                    importance_sort,
                                    has_dashboard_signal,
                                    signal_sort,
                                    stage,
                                    category,
                                    ticker
                                )

                            prioritized_records = sorted(
                                spider_records,
                                key=relationship_priority
                            )

                            if network_display_mode == "Alle gefilterten Beziehungen":
                                spider_records_sorted = prioritized_records[:max_visible_nodes]

                            elif network_display_mode == "Ausbalanciert nach Lieferkettenstufen":
                                grouped_records = {}
                                for row in prioritized_records:
                                    stage_name = str(row.get("supply_chain_stage", "99 - Sonstige Verbindung"))
                                    grouped_records.setdefault(stage_name, []).append(row)

                                stage_count = max(1, len(grouped_records))
                                per_stage_limit = max(1, max_visible_nodes // stage_count)

                                balanced_records = []
                                used_tickers = set()

                                for stage_name in sorted(grouped_records.keys()):
                                    for row in grouped_records[stage_name][:per_stage_limit]:
                                        ticker = str(row.get("Ticker", row.get("target_ticker", "")))
                                        if ticker not in used_tickers:
                                            balanced_records.append(row)
                                            used_tickers.add(ticker)

                                if len(balanced_records) < max_visible_nodes:
                                    for row in prioritized_records:
                                        ticker = str(row.get("Ticker", row.get("target_ticker", "")))
                                        if ticker not in used_tickers:
                                            balanced_records.append(row)
                                            used_tickers.add(ticker)
                                        if len(balanced_records) >= max_visible_nodes:
                                            break

                                spider_records_sorted = balanced_records[:max_visible_nodes]

                            else:
                                # Empfohlener Modus: Wichtigkeit + vorhandenes Dashboard-Signal + saubere Sortierung.
                                spider_records_sorted = prioritized_records[:max_visible_nodes]

                            st.caption(
                                f"Im Spinnennetz sichtbar: {len(spider_records_sorted)} von {total_network_records} Beziehungen."
                            )

                            stage_names = []
                            for row in spider_records_sorted:
                                stage_name = str(row.get("supply_chain_stage", "99 - Sonstige Verbindung"))
                                if stage_name not in stage_names:
                                    stage_names.append(stage_name)

                            width = 1320
                            height = 760
                            center_x = 470
                            center_y = 380
                            stage_radius = 190
                            stock_radius_inner = 335
                            stock_radius_outer = 435

                            available_source_tickers = set(available_network_tickers)
                            nodes = []
                            edges = []

                            center_company = selected_network_ticker
                            if "Ticker" in df.columns and "Company" in df.columns:
                                center_match = df[df["Ticker"].astype(str).str.strip() == selected_network_ticker]
                                if not center_match.empty:
                                    center_company = str(center_match.iloc[0].get("Company", selected_network_ticker))

                            nodes.append({
                                "id": selected_network_ticker,
                                "label": selected_network_ticker,
                                "name": center_company,
                                "type": "center",
                                "x": center_x,
                                "y": center_y,
                                "w": 150,
                                "h": 64,
                                "color": "#38bdf8",
                                "stage": "Hauptaktie",
                                "category": "Fokuswert",
                                "connection": "Zentrum",
                                "relationship": "Ausgangspunkt der Wertschöpfungskette und aller angezeigten Beziehungen.",
                                "risk": "-",
                                "importance": "Fokus",
                                "signal": "Fokus",
                                "rating": "-",
                                "score": "-",
                                "risk_level": "-",
                                "price": "-",
                                "crv": "-",
                                "can_drill": False
                            })

                            stage_positions = {}
                            total_stages = max(len(stage_names), 1)

                            for stage_index, stage_name in enumerate(stage_names):
                                angle = -math.pi / 2 + (2 * math.pi * stage_index / total_stages)
                                stage_x = center_x + stage_radius * math.cos(angle)
                                stage_y = center_y + stage_radius * math.sin(angle)
                                stage_id = f"stage::{stage_name}"
                                stage_label = stage_name.split(" - ", 1)[-1]
                                if len(stage_label) > 23:
                                    stage_label = stage_label[:21] + "…"
                                stage_positions[stage_name] = (stage_x, stage_y, angle, stage_id)

                                nodes.append({
                                    "id": stage_id,
                                    "label": stage_label,
                                    "name": stage_name,
                                    "type": "stage",
                                    "x": stage_x,
                                    "y": stage_y,
                                    "w": 158,
                                    "h": 42,
                                    "color": "#0f172a",
                                    "stage": stage_name,
                                    "category": "Lieferkettenstufe",
                                    "connection": "Zwischenstufe",
                                    "relationship": f"Diese Stufe bündelt Beziehungen im Netzwerk von {selected_network_ticker}.",
                                    "risk": "-",
                                    "importance": "Stage",
                                    "signal": "Stage",
                                    "rating": "-",
                                    "score": "-",
                                    "risk_level": "-",
                                    "price": "-",
                                    "crv": "-",
                                    "can_drill": False
                                })
                                edges.append({"from": selected_network_ticker, "to": stage_id, "kind": "stage"})

                            for stage_name in stage_names:
                                group = [
                                    row for row in spider_records_sorted
                                    if str(row.get("supply_chain_stage", "99 - Sonstige Verbindung")) == stage_name
                                ]

                                stage_x, stage_y, base_angle, stage_id = stage_positions[stage_name]
                                count = max(len(group), 1)
                                spread = min(1.10, 0.20 * count)

                                for item_index, row in enumerate(group):
                                    ticker = str(row.get("Ticker", row.get("target_ticker", ""))).strip()
                                    if not ticker:
                                        continue

                                    local_angle = base_angle if count == 1 else base_angle - spread / 2 + spread * item_index / max(count - 1, 1)
                                    radius = stock_radius_inner if item_index % 2 == 0 else stock_radius_outer
                                    node_x = center_x + radius * math.cos(local_angle)
                                    node_y = center_y + radius * math.sin(local_angle)

                                    connection_type = str(row.get("connection_type", "Strategische Verbindung"))
                                    action_signal = str(row.get("Action Signal", ""))
                                    badge, badge_color = get_signal_badge(action_signal)
                                    color = get_connection_color(connection_type, action_signal)
                                    importance = str(row.get("importance", ""))
                                    node_w = 124
                                    if importance.lower() in ["hoch", "high"]:
                                        node_w = 140
                                    elif importance.lower() in ["mittel", "medium"]:
                                        node_w = 130

                                    nodes.append({
                                        "id": ticker,
                                        "label": ticker,
                                        "name": str(row.get("Company", row.get("target_name", ticker))),
                                        "type": "stock",
                                        "x": node_x,
                                        "y": node_y,
                                        "w": node_w,
                                        "h": 50,
                                        "color": color,
                                        "badge": badge,
                                        "badge_color": badge_color,
                                        "stage": stage_name,
                                        "category": str(row.get("category", "")),
                                        "connection": connection_type,
                                        "relationship": str(row.get("relationship", "")),
                                        "risk": str(row.get("risk_note", "")),
                                        "importance": importance,
                                        "signal": action_signal if action_signal else "Nicht in Hauptliste",
                                        "rating": str(row.get("Rating", "")),
                                        "score": str(row.get("Score", "")),
                                        "risk_level": str(row.get("Risk Level", "")),
                                        "price": str(row.get("Price", "")),
                                        "crv": str(row.get("CRV", "")),
                                        "can_drill": ticker in available_source_tickers
                                    })
                                    edges.append({"from": stage_id, "to": ticker, "kind": "stock"})

                            nodes_json = json.dumps(nodes, ensure_ascii=False)
                            edges_json = json.dumps(edges, ensure_ascii=False)
                            center_id_json = json.dumps(selected_network_ticker, ensure_ascii=False)

                            network_html = f'''
                            <!DOCTYPE html>
                            <html>
                            <head>
                            <meta charset="utf-8" />
                            <style>
                                * {{ box-sizing: border-box; }}
                                body {{ margin: 0; background: #020617; color: #e5e7eb; font-family: Inter, Arial, sans-serif; }}
                                .terminal-wrap {{ width: 100%; height: 820px; display: grid; grid-template-columns: minmax(780px, 1fr) 390px; gap: 16px; background: radial-gradient(circle at 16% 16%, rgba(56,189,248,0.18), transparent 30%), radial-gradient(circle at 82% 10%, rgba(168,85,247,0.14), transparent 30%), linear-gradient(135deg, #020617, #0f172a 58%, #111827); border: 1px solid rgba(56,189,248,0.28); border-radius: 24px; padding: 16px; overflow: hidden; }}
                                .network-card {{ position: relative; min-width: 0; border: 1px solid rgba(148,163,184,0.20); border-radius: 20px; background: rgba(2,6,23,0.48); overflow: hidden; box-shadow: inset 0 0 80px rgba(14,165,233,0.06); }}
                                .detail-card {{ border: 1px solid rgba(148,163,184,0.22); border-radius: 20px; padding: 18px; background: rgba(15,23,42,0.90); box-shadow: 0 18px 42px rgba(0,0,0,0.30); overflow: auto; }}
                                .detail-kicker {{ color: #38bdf8; font-size: 12px; letter-spacing: 0.12em; text-transform: uppercase; font-weight: 900; }}
                                .detail-title {{ margin: 8px 0 4px; font-size: 27px; line-height: 1.05; font-weight: 950; color: #f8fafc; }}
                                .detail-subtitle {{ color: #cbd5e1; font-size: 14px; margin-bottom: 14px; }}
                                .pill-row {{ display: flex; flex-wrap: wrap; gap: 8px; margin: 12px 0 16px; }}
                                .pill {{ border-radius: 999px; border: 1px solid rgba(148,163,184,0.25); background: rgba(30,41,59,0.72); padding: 6px 9px; color: #e5e7eb; font-size: 12px; font-weight: 750; }}
                                .section {{ margin-top: 14px; padding-top: 10px; border-top: 1px solid rgba(148,163,184,0.14); }}
                                .section h4 {{ margin: 0 0 6px; color: #93c5fd; font-size: 12px; letter-spacing: 0.08em; text-transform: uppercase; }}
                                .section p {{ margin: 0; color: #e5e7eb; font-size: 14px; line-height: 1.45; }}
                                .hint {{ position: absolute; top: 14px; left: 16px; color: #cbd5e1; background: rgba(2,6,23,0.74); border: 1px solid rgba(148,163,184,0.18); border-radius: 999px; padding: 8px 11px; font-size: 12px; z-index: 3; }}
                                .legend {{ position: absolute; left: 16px; bottom: 14px; display: flex; flex-wrap: wrap; gap: 8px; max-width: 720px; padding: 8px 10px; border-radius: 999px; background: rgba(2,6,23,0.74); border: 1px solid rgba(148,163,184,0.18); backdrop-filter: blur(10px); }}
                                .legend span {{ font-size: 11px; color: #cbd5e1; }}
                                .dot {{ display:inline-block; width:9px; height:9px; border-radius:999px; margin-right:5px; vertical-align:middle; }}
                                .tooltip {{ position: fixed; max-width: 360px; pointer-events: none; background: rgba(15,23,42,0.96); border: 1px solid rgba(56,189,248,0.30); color: #e5e7eb; border-radius: 14px; padding: 11px 12px; font-size: 12px; line-height: 1.35; box-shadow: 0 18px 42px rgba(0,0,0,0.38); opacity: 0; transform: translate(12px, 12px); transition: opacity .08s ease; z-index: 99; }}
                                .tooltip b {{ color: #f8fafc; font-size: 13px; }}
                                svg {{ width: 100%; height: 100%; display: block; }}
                                .edge {{ stroke: rgba(148,163,184,0.28); stroke-width: 1.5; fill: none; }}
                                .edge-stage {{ stroke: rgba(56,189,248,0.30); stroke-width: 1.9; stroke-dasharray: 7 8; }}
                                .node {{ cursor: pointer; transition: opacity .12s ease; }}
                                .node rect {{ stroke: rgba(248,250,252,0.60); stroke-width: 1.25; filter: drop-shadow(0 10px 14px rgba(0,0,0,0.35)); }}
                                .node text {{ pointer-events: none; font-weight: 900; fill: #f8fafc; paint-order: stroke; stroke: #020617; stroke-width: 3px; stroke-linejoin: round; }}
                                .node:hover rect {{ stroke: #f8fafc; stroke-width: 2.2; }}
                                .node.active rect {{ stroke: #f8fafc; stroke-width: 2.8; }}
                                .center-node rect {{ fill: #0ea5e9; stroke: #e0f2fe; stroke-width: 2.8; }}
                                .center-node text {{ font-size: 21px; }}
                                .stage-node rect {{ fill: rgba(15,23,42,0.94); stroke: rgba(56,189,248,0.58); stroke-width: 1.8; }}
                                .stage-node text {{ font-size: 11px; fill: #bfdbfe; }}
                                .stock-node text {{ font-size: 14px; }}
                                .badge-text {{ font-size: 9px; font-weight: 950; fill: #020617; stroke: none; paint-order: normal; }}
                                .drill {{ font-size: 10px; fill: #93c5fd; stroke: none; paint-order: normal; }}
                            </style>
                            </head>
                            <body>
                                <div class="terminal-wrap"><div class="network-card"><div class="hint">Klick = Detail · Zentrum wechseln über Buttons unter dem Netzwerk</div><svg viewBox="0 0 {width} {height}" id="networkSvg" preserveAspectRatio="xMidYMid meet"><g id="edges"></g><g id="nodes"></g></svg><div class="legend"><span><i class="dot" style="background:#22c55e"></i>Lieferant</span><span><i class="dot" style="background:#8b5cf6"></i>Kunde/Nachfrage</span><span><i class="dot" style="background:#f59e0b"></i>Infrastruktur/Energie</span><span><i class="dot" style="background:#f97316"></i>Konkurrenz</span><span><i class="dot" style="background:#ef4444"></i>Risk/Avoid</span><span><i class="dot" style="background:#38bdf8"></i>Strategisch</span></div><div class="tooltip" id="tooltip"></div></div>
                                    <aside class="detail-card" id="detailCard"><div class="detail-kicker">Market Relationship Focus</div><div class="detail-title">{html.escape(selected_network_ticker)}</div><div class="detail-subtitle">Klicke auf eine Karte im Netzwerk, um die Verbindung im Detail zu sehen.</div><div class="pill-row"><span class="pill">Zentrum</span><span class="pill">Wertschöpfungskette</span></div><div class="section"><h4>Bedienung</h4><p>Mouseover zeigt Schnellinfos. Das Zentrum wechselst du über die Streamlit-Buttons unter dem Netzwerk.</p></div></aside></div>
                                <script>
                                    const nodes = {nodes_json}; const edges = {edges_json}; const centerId = {center_id_json};
                                    const nodesById = Object.fromEntries(nodes.map(n => [n.id, n]));
                                    const edgeLayer = document.getElementById('edges'); const nodeLayer = document.getElementById('nodes'); const detailCard = document.getElementById('detailCard'); const tooltip = document.getElementById('tooltip');
                                    function esc(value) {{ return String(value ?? '').replace(/[&<>'"]/g, ch => ({{'&':'&amp;','<':'&lt;','>':'&gt;',"'":'&#39;','"':'&quot;'}}[ch])); }}
                                    function detailHtml(n) {{ const typeLabel = n.type === 'center' ? 'Hauptaktie' : n.type === 'stage' ? 'Lieferkettenstufe' : 'Verbundene Aktie'; const drillInfo = n.can_drill ? '<span class="pill">Als Zentrum verfügbar</span>' : ''; return `<div class="detail-kicker">${{esc(typeLabel)}}</div><div class="detail-title">${{esc(n.label)}} <span style="font-size:16px;color:#94a3b8;">${{n.name && n.name !== n.label ? '— ' + esc(n.name) : ''}}</span></div><div class="detail-subtitle">${{esc(n.stage || '-')}}</div><div class="pill-row"><span class="pill" style="border-color:${{esc(n.color)}};">${{esc(n.connection || '-')}}</span><span class="pill">${{esc(n.category || '-')}}</span><span class="pill">Wichtigkeit: ${{esc(n.importance || '-')}}</span>${{drillInfo}}</div><div class="section"><h4>Warum verbunden?</h4><p>${{esc(n.relationship || '-')}}</p></div><div class="section"><h4>Risiko / Hinweis</h4><p>${{esc(n.risk || '-')}}</p></div><div class="section"><h4>Dashboard-Signal</h4><p>${{esc(n.signal || '-')}} · Rating: ${{esc(n.rating || '-')}} · Score: ${{esc(n.score || '-')}} · Risk: ${{esc(n.risk_level || '-')}}</p></div><div class="section"><h4>Kurs / CRV</h4><p>Preis: ${{esc(n.price || '-')}} · CRV: ${{esc(n.crv || '-')}}</p></div>`; }}
                                    function tooltipHtml(n) {{ return `<b>${{esc(n.label)}}${{n.name && n.name !== n.label ? ' — ' + esc(n.name) : ''}}</b><br><span>Stufe: ${{esc(n.stage || '-')}}</span><br><span>Verbindung: ${{esc(n.connection || '-')}}</span><br><span>Signal: ${{esc(n.signal || '-')}} · Score: ${{esc(n.score || '-')}}</span><br><span>Warum: ${{esc(n.relationship || '-')}}</span>`; }}
                                    function showDetails(nodeId) {{ const n = nodesById[nodeId]; if (!n) return; document.querySelectorAll('.node').forEach(el => el.classList.remove('active')); const active = document.querySelector(`[data-node-id="${{CSS.escape(nodeId)}}"]`); if (active) active.classList.add('active'); detailCard.innerHTML = detailHtml(n); }}
                                    function navigateToTicker(ticker) {{
                                        const n = nodesById[ticker];
                                        if (!n || !n.can_drill) return;
                                        const targetUrl = `?network_ticker=${{encodeURIComponent(String(ticker).toUpperCase())}}&network_reset=1`;
                                        try {{
                                            window.top.location.assign(targetUrl);
                                        }} catch (e) {{
                                            try {{ window.open(targetUrl, '_top'); }} catch (e2) {{ window.location.href = targetUrl; }}
                                        }}
                                    }}
                                    function drawEdges() {{ edges.forEach(e => {{ const a = nodesById[e.from]; const b = nodesById[e.to]; if (!a || !b) return; const line = document.createElementNS('http://www.w3.org/2000/svg', 'line'); line.setAttribute('x1', a.x); line.setAttribute('y1', a.y); line.setAttribute('x2', b.x); line.setAttribute('y2', b.y); line.setAttribute('class', e.kind === 'stage' ? 'edge edge-stage' : 'edge'); edgeLayer.appendChild(line); }}); }}
                                    function drawNodes() {{ nodes.forEach(n => {{ const g = document.createElementNS('http://www.w3.org/2000/svg', 'g'); g.setAttribute('class', `node ${{n.type}}-node`); g.setAttribute('data-node-id', n.id); g.setAttribute('transform', `translate(${{n.x}}, ${{n.y}})`); const rect = document.createElementNS('http://www.w3.org/2000/svg', 'rect'); rect.setAttribute('x', -n.w / 2); rect.setAttribute('y', -n.h / 2); rect.setAttribute('width', n.w); rect.setAttribute('height', n.h); rect.setAttribute('rx', n.type === 'center' ? 18 : 14); rect.setAttribute('fill', n.type === 'stage' ? 'rgba(15,23,42,0.94)' : n.color); g.appendChild(rect); const title = document.createElementNS('http://www.w3.org/2000/svg', 'text'); title.setAttribute('text-anchor', 'middle'); title.setAttribute('dominant-baseline', 'central'); title.setAttribute('y', n.type === 'stock' ? -5 : 0); title.textContent = n.label; g.appendChild(title); if (n.type === 'stock') {{ const badgeBg = document.createElementNS('http://www.w3.org/2000/svg', 'rect'); badgeBg.setAttribute('x', -30); badgeBg.setAttribute('y', 11); badgeBg.setAttribute('width', 60); badgeBg.setAttribute('height', 16); badgeBg.setAttribute('rx', 8); badgeBg.setAttribute('fill', n.badge_color || '#64748b'); g.appendChild(badgeBg); const badgeText = document.createElementNS('http://www.w3.org/2000/svg', 'text'); badgeText.setAttribute('class', 'badge-text'); badgeText.setAttribute('text-anchor', 'middle'); badgeText.setAttribute('x', 0); badgeText.setAttribute('y', 22.5); badgeText.textContent = n.badge || 'N/A'; g.appendChild(badgeText); if (n.can_drill) {{ const drillText = document.createElementNS('http://www.w3.org/2000/svg', 'text'); drillText.setAttribute('class', 'drill'); drillText.setAttribute('text-anchor', 'middle'); drillText.setAttribute('x', 0); drillText.setAttribute('y', -19); drillText.textContent = '↻'; g.appendChild(drillText); }} }} g.addEventListener('click', () => showDetails(n.id)); g.addEventListener('dblclick', (ev) => {{ ev.preventDefault(); showDetails(n.id); }}); g.addEventListener('mouseenter', () => {{ tooltip.innerHTML = tooltipHtml(n); tooltip.style.opacity = '1'; }}); g.addEventListener('mousemove', (ev) => {{ tooltip.style.left = ev.clientX + 'px'; tooltip.style.top = ev.clientY + 'px'; }}); g.addEventListener('mouseleave', () => {{ tooltip.style.opacity = '0'; }}); nodeLayer.appendChild(g); }}); }}
                                    drawEdges(); drawNodes(); showDetails(centerId);
                                </script>
                            </body>
                            </html>
                            '''

                            components.html(network_html, height=850, scrolling=False)

                            st.markdown(
                                """
                                <div class="terminal-panel" style="padding:14px 16px; margin-top:8px;">
                                    <b>Bedienung:</b> Mouseover zeigt Schnellinfos. Klick zeigt Details rechts. Das Zentrum wechselst du über die Buttons unten — ohne URL-Wechsel, der Login bleibt erhalten.
                                </div>
                                """,
                                unsafe_allow_html=True
                            )

                            # Streamlit-native Navigation: zuverlässig und ohne URL-Wechsel, damit der Login erhalten bleibt.
                            drill_candidates = (
                                network_view["target_ticker"]
                                .dropna()
                                .astype(str)
                                .str.strip()
                                .str.upper()
                                .unique()
                                .tolist()
                            )

                            drill_candidates = [
                                ticker for ticker in drill_candidates
                                if ticker in available_network_tickers and ticker != selected_network_ticker
                            ]

                            if drill_candidates:
                                st.markdown("#### 🔁 Verbundene Aktie als neues Zentrum öffnen")
                                st.caption("Diese Auswahl setzt Kategorie-, Lieferketten- und Verbindungsfilter automatisch zurück, ohne den Login zu verlassen.")

                                # Kompakte Button-Matrix
                                button_columns = st.columns(6)
                                for idx, ticker in enumerate(drill_candidates[:30]):
                                    with button_columns[idx % 6]:
                                        st.button(
                                            f"↻ {ticker}",
                                            key=f"switch_network_center_{selected_network_ticker}_{ticker}",
                                            use_container_width=True,
                                            on_click=switch_network_center,
                                            args=(ticker,)
                                        )
                            else:
                                st.caption("Keine verbundenen Aktien aus dieser Ansicht sind aktuell selbst als Hauptaktie im Mapping hinterlegt.")

                    with st.expander("🧾 Detailtabelle anzeigen", expanded=False):

                        st.dataframe(
                            network_display,
                            width="stretch",
                            hide_index=True
                        )

                    with st.expander("🏭 Lieferkette als Stufenansicht anzeigen", expanded=False):

                        stage_groups = network_view.groupby("supply_chain_stage", sort=True)

                        for stage, stage_group in stage_groups:
                            st.markdown(f"### {stage}")

                            for _, rel_row in stage_group.iterrows():
                                ticker = rel_row.get("Ticker", "")
                                name = rel_row.get("Company", "")
                                category = rel_row.get("category", "")
                                connection_type = rel_row.get("connection_type", "")
                                importance = rel_row.get("importance", "")
                                relationship = rel_row.get("relationship", "")
                                risk_note = rel_row.get("risk_note", "")
                                action_signal = rel_row.get("Action Signal", "-")
                                rating = rel_row.get("Rating", "-")
                                score = rel_row.get("Score", "-")

                                st.markdown(
                                    f"**{ticker} - {name}**  \n"
                                    f"Kategorie: **{category}** | Verbindungsart: **{connection_type}** | Wichtigkeit: **{importance}**  \n"
                                    f"Warum verbunden: {relationship}  \n"
                                    f"Risiko: {risk_note}  \n"
                                    f"Dashboard-Signal: **{action_signal}** | Rating: **{rating}** | Score: **{score}**"
                                )
                                st.divider()

                    with st.expander("🧩 Netzwerk als Kategorienansicht anzeigen", expanded=False):

                        grouped_categories = network_view.groupby("category")

                        for category, group in grouped_categories:
                            st.markdown(f"### {category}")

                            for _, rel_row in group.iterrows():
                                ticker = rel_row.get("Ticker", "")
                                name = rel_row.get("Company", "")
                                stage = rel_row.get("supply_chain_stage", "")
                                connection_type = rel_row.get("connection_type", "")
                                importance = rel_row.get("importance", "")
                                relationship = rel_row.get("relationship", "")
                                risk_note = rel_row.get("risk_note", "")

                                st.markdown(
                                    f"**{ticker} - {name}**  \n"
                                    f"Stufe: **{stage}** | Verbindungsart: **{connection_type}** | Wichtigkeit: **{importance}**  \n"
                                    f"Verbindung: {relationship}  \n"
                                    f"Risiko: {risk_note}"
                                )

                                st.divider()

                    signal_summary = network_view["Action Signal"].fillna("Nicht in Hauptliste").value_counts()

                    with st.expander("📊 Netzwerk-Signal anzeigen", expanded=False):
                        st.caption(
                            "Zählt die aktuellen Dashboard-Signale der verbundenen Aktien, "
                            "sofern sie in deiner Hauptliste vorhanden sind. Diese Auswertung steht bewusst unter der Detail- und Kategorienansicht, damit erst die Beziehungen sichtbar sind und danach die Zusammenfassung folgt."
                        )

                        signal_summary_df = signal_summary.reset_index()
                        signal_summary_df.columns = ["Action Signal", "Anzahl"]

                        st.dataframe(
                            signal_summary_df,
                            width="stretch",
                            hide_index=True
                        )

                        bullish_count = network_view["Action Signal"].astype(str).str.contains(
                            "BUY", case=False, na=False
                        ).sum()
                        avoid_count = network_view["Action Signal"].astype(str).str.contains(
                            "AVOID|SELL", case=False, na=False
                        ).sum()
                        watch_count = network_view["Action Signal"].astype(str).str.contains(
                            "WATCH", case=False, na=False
                        ).sum()

                        col_signal_1, col_signal_2, col_signal_3 = st.columns(3)
                        col_signal_1.metric("Bullish im Netzwerk", int(bullish_count))
                        col_signal_2.metric("Watch / Beobachten", int(watch_count))
                        col_signal_3.metric("Schwach / Avoid", int(avoid_count))

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

action_signal_options = (
    df[["Action Signal", "Action Sort"]]
    .drop_duplicates()
    .sort_values("Action Sort")["Action Signal"]
    .tolist()
)

action_signals = st.sidebar.multiselect(
    "Action Signal",
    options=action_signal_options,
    default=action_signal_options
)

# ----------------------------
# Zusätzliche Bewertungs-/Preisfilter
# ----------------------------

if "Valuation Status" in df.columns:
    valuation_status_options = sorted(
        df["Valuation Status"].dropna().astype(str).unique().tolist()
    )
else:
    valuation_status_options = []

selected_valuation_status = st.sidebar.multiselect(
    "Valuation Status",
    options=valuation_status_options,
    default=valuation_status_options
)

if "Setup Quality" in df.columns:
    setup_quality_options = sorted(
        df["Setup Quality"].dropna().astype(str).unique().tolist()
    )
else:
    setup_quality_options = []

selected_setup_quality = st.sidebar.multiselect(
    "Setup Quality",
    options=setup_quality_options,
    default=setup_quality_options
)

# Preisbereich: Price ist im Dashboard eine Anzeige-Spalte und kann Text enthalten.
# Deshalb wird für den Filter eine separate numerische Serie verwendet.
price_filter_values = df["Price"].apply(safe_float) if "Price" in df.columns else pd.Series(dtype=float)
valid_price_values = price_filter_values.dropna()

if not valid_price_values.empty:
    price_min = float(valid_price_values.min())
    price_max = float(valid_price_values.max())

    selected_price_range = st.sidebar.slider(
        "Price Range",
        min_value=price_min,
        max_value=price_max,
        value=(price_min, price_max),
        step=max(round((price_max - price_min) / 200, 2), 0.01)
    )
else:
    selected_price_range = None
    st.sidebar.caption("Price Range: keine verwertbaren Preisdaten")

valuation_score_values = (
    pd.to_numeric(df["Valuation Score"], errors="coerce")
    if "Valuation Score" in df.columns
    else pd.Series(dtype=float)
)
valid_valuation_scores = valuation_score_values.dropna()

if not valid_valuation_scores.empty:
    valuation_score_min = int(valid_valuation_scores.min())
    valuation_score_max = int(valid_valuation_scores.max())

    selected_valuation_score_range = st.sidebar.slider(
        "Valuation Score",
        min_value=valuation_score_min,
        max_value=valuation_score_max,
        value=(valuation_score_min, valuation_score_max),
        step=1
    )
else:
    selected_valuation_score_range = None
    st.sidebar.caption("Valuation Score: keine Daten")

turnaround_only = st.sidebar.checkbox(
    "Nur Turnaround Kandidaten"
)

sort_option = st.sidebar.selectbox(
    "Sortieren nach",
    [
        "Action Signal",
        "Terminal Score",
        "Valuation Score",
        "Valuation Status",
        "Setup Quality",
        "Price",
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
].copy()

if selected_valuation_status and "Valuation Status" in df_filtered.columns:
    df_filtered = df_filtered[
        df_filtered["Valuation Status"].astype(str).isin(selected_valuation_status)
    ]

if selected_setup_quality and "Setup Quality" in df_filtered.columns:
    df_filtered = df_filtered[
        df_filtered["Setup Quality"].astype(str).isin(selected_setup_quality)
    ]

if selected_price_range is not None and "Price" in df.columns:
    price_mask = price_filter_values.loc[df_filtered.index].between(
        selected_price_range[0],
        selected_price_range[1],
        inclusive="both"
    )
    df_filtered = df_filtered[price_mask.fillna(False)]

if selected_valuation_score_range is not None and "Valuation Score" in df.columns:
    valuation_score_mask = valuation_score_values.loc[df_filtered.index].between(
        selected_valuation_score_range[0],
        selected_valuation_score_range[1],
        inclusive="both"
    )
    df_filtered = df_filtered[valuation_score_mask.fillna(False)]

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

    elif sort_option == "Price":

        df_filtered["Price Numeric"] = df_filtered["Price"].apply(safe_float).fillna(0)

        df_filtered = df_filtered.sort_values(
            by="Price Numeric",
            ascending=False
        )

    elif sort_option == "Valuation Score":

        df_filtered["Valuation Score Numeric"] = pd.to_numeric(
            df_filtered["Valuation Score"],
            errors="coerce"
        ).fillna(0)

        df_filtered = df_filtered.sort_values(
            by="Valuation Score Numeric",
            ascending=False
        )

    elif sort_option == "Terminal Score":

        df_filtered["Terminal Score Numeric"] = pd.to_numeric(
            df_filtered["Terminal Score"],
            errors="coerce"
        ).fillna(0)

        df_filtered = df_filtered.sort_values(
            by="Terminal Score Numeric",
            ascending=False
        )

    elif sort_option in ["Setup Quality", "Valuation Status"]:

        df_filtered = df_filtered.sort_values(
            by=sort_option,
            ascending=True
        )

    elif sort_option == "CRV":

        df_filtered["CRV Numeric"] = pd.to_numeric(
            df_filtered["CRV"],
            errors="coerce"
        ).fillna(0)

        df_filtered = df_filtered.sort_values(
            by="CRV Numeric",
            ascending=False
        )

    elif sort_option == "Dividend Yield %":

        df_filtered["Dividend Yield Numeric"] = pd.to_numeric(
            df_filtered["Dividend Yield %"]
            .astype(str)
            .str.replace("%", "", regex=False)
            .replace("-", "0"),
            errors="coerce"
        ).fillna(0)

        df_filtered = df_filtered.sort_values(
            by="Dividend Yield Numeric",
            ascending=False
        )

    else:

        df_filtered = df_filtered.sort_values(
            by=sort_option,
            ascending=False
        )


with tab_overview:
    # ============================================================
    # METRICS
    # ============================================================

    with st.expander("📊 Markt-Metriken / Filter-Zusammenfassung", expanded=False):
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


with tab_earnings:
    # ============================================================
    # 📆 EARNINGSKALENDER
    # ============================================================

    with st.expander("📆 Earningskalender: Termine, Erwartungen & Kontext", expanded=True):
        st.caption(
            "Zeigt kommende Earnings-Termine und verfügbare EPS-/Umsatzschätzungen. "
            "Nicht jede Aktie liefert über Yahoo/yfinance saubere Zukunftsdaten; fehlende Werte werden bewusst als '-' angezeigt."
        )

        earnings_universe_mode = st.radio(
            "Earnings-Universum",
            options=[
                "Aktuell gefilterte Aktien",
                "Alle Aktien aus der Analyse"
            ],
            horizontal=True,
            key="earnings_universe_mode"
        )

        earnings_universe_df = df_filtered.copy() if earnings_universe_mode == "Aktuell gefilterte Aktien" else df.copy()

        earnings_universe_df = earnings_universe_df.dropna(subset=["Ticker"]).copy()
        earnings_universe_df["Ticker"] = earnings_universe_df["Ticker"].astype(str).str.strip()
        earnings_universe_df = earnings_universe_df.drop_duplicates(subset=["Ticker"])

        col_earn_1, col_earn_2, col_earn_3 = st.columns([1, 1, 2])

        with col_earn_1:
            earnings_days_forward = st.selectbox(
                "Zeitraum",
                options=[7, 14, 30, 60, 90, 180, 365],
                index=4,
                format_func=lambda value: f"nächste {value} Tage",
                key="earnings_days_forward"
            )

        with col_earn_2:
            earnings_count = len(earnings_universe_df)

            if earnings_count == 0:
                max_earnings_scan = 0
                st.warning("Keine Aktien für den Earnings-Scan verfügbar.")

            elif earnings_count == 1:
                max_earnings_scan = 1
                st.caption("1 Aktie für den Earnings-Scan verfügbar.")

            else:
                slider_max = earnings_count
                slider_default = min(200, slider_max)

                # Eigener Key je Universum/Anzahl, damit Streamlit keinen alten
                # Slider-Wert verwendet, der außerhalb der neuen Range liegt.
                earnings_slider_key = (
                    f"max_earnings_scan_{earnings_universe_mode}_{earnings_count}"
                    .replace(" ", "_")
                    .replace("ä", "ae")
                )

                max_earnings_scan = st.slider(
                    "Max. Aktien scannen",
                    min_value=1,
                    max_value=slider_max,
                    value=slider_default,
                    step=1 if slider_max < 50 else 10,
                    key=earnings_slider_key
                )

        with col_earn_3:
            st.info(
                "Für große Watchlists kann der Scan etwas dauern. "
                "Die Ergebnisse werden 6 Stunden gecacht."
            )

        run_earnings_scan = st.button(
            "📆 Earningskalender aktualisieren",
            key="run_earnings_scan"
        )

        if run_earnings_scan:
            earnings_calendar_df = build_earnings_calendar(
                earnings_universe_df,
                max_tickers=max_earnings_scan
            )

            st.session_state["earnings_calendar_df"] = earnings_calendar_df
        else:
            earnings_calendar_df = st.session_state.get(
                "earnings_calendar_df",
                pd.DataFrame()
            )

        if earnings_calendar_df.empty:
            st.info(
                "Noch keine Earnings-Daten geladen. Klicke auf 'Earningskalender aktualisieren'."
            )
        else:
            earnings_calendar_view = earnings_calendar_df.copy()

            earnings_calendar_view["Days Until Numeric"] = pd.to_numeric(
                earnings_calendar_view["Days Until"],
                errors="coerce"
            )

            earnings_calendar_view = earnings_calendar_view[
                (earnings_calendar_view["Days Until Numeric"].notna())
                &
                (earnings_calendar_view["Days Until Numeric"] >= 0)
                &
                (earnings_calendar_view["Days Until Numeric"] <= earnings_days_forward)
            ].copy()

            upcoming_count = len(earnings_calendar_view)
            next_7_count = int((earnings_calendar_view["Days Until Numeric"] <= 7).sum()) if upcoming_count else 0
            next_30_count = int((earnings_calendar_view["Days Until Numeric"] <= 30).sum()) if upcoming_count else 0

            e1, e2, e3, e4 = st.columns(4)
            e1.metric("Treffer im Zeitraum", upcoming_count)
            e2.metric("nächste 7 Tage", next_7_count)
            e3.metric("nächste 30 Tage", next_30_count)
            e4.metric("gescannte Aktien", len(earnings_calendar_df))

            display_earnings_columns = [
                "Ticker",
                "Company",
                "Earnings Date",
                "Days Until",
                "Time",
                "EPS Estimate",
                "Revenue Estimate",
                "Terminal Grade",
                "Terminal Score",
                "Action Signal",
                "Valuation Status",
                "Setup Quality",
                "Risk Level",
                "Short Info",
                "Data Source"
            ]

            display_earnings_columns = [
                column for column in display_earnings_columns
                if column in earnings_calendar_view.columns
            ]

            st.dataframe(
                earnings_calendar_view[display_earnings_columns],
                width="stretch",
                hide_index=True
            )

            st.download_button(
                "⬇️ Earningskalender als CSV exportieren",
                data=earnings_calendar_view[display_earnings_columns].to_csv(index=False, sep=";").encode("utf-8-sig"),
                file_name="hartmut_terminal_earningskalender.csv",
                mime="text/csv"
            )

            with st.expander("ℹ️ Hinweis zur Datenqualität", expanded=False):
                st.write(
                    "Earnings-Daten und Analystenerwartungen kommen über Yahoo/yfinance. "
                    "Bei deutschen Nebenwerten, exotischen Börsenplätzen oder sehr kleinen Titeln fehlen diese Daten häufig. "
                    "Ein '-' bedeutet daher nicht automatisch, dass keine Earnings existieren, sondern dass keine verwertbare Schätzung gefunden wurde."
                )


with tab_dividends:
    # ============================================================
    # DIVIDENDENKALENDER
    # ============================================================

    with st.expander("📅 Dividendenkalender", expanded=True):
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
                "Strategy Mode",
                "CRV",
                "Target Basis"
            ]
        ]

        st.dataframe(
            dividend_calendar,
            width="stretch"
        )

        st.download_button(
            "⬇️ Dividendenkalender als CSV exportieren",
            data=dividend_calendar.to_csv(index=False, sep=";").encode("utf-8-sig"),
            file_name="hartmut_terminal_dividendenkalender.csv",
            mime="text/csv"
        )


with tab_analysis:
    # ============================================================
    # TABELLE
    # ============================================================

    with st.expander("📋 Gesamttabelle", expanded=False):
        st.divider()

        st.subheader("📋 Gesamttabelle")

        # Action Signal bewusst direkt nach Ticker und Company anzeigen,
        # damit die Entscheidungseinschätzung in der Gesamtliste sofort sichtbar ist.
        priority_columns = [
            "Ticker",
            "Company",
            "Terminal Grade",
            "Terminal Score",
            "Action Signal",
            "Valuation Status",
            "Valuation Score",
            "Strategy Mode"
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

        st.download_button(
            "⬇️ Gefilterte Gesamttabelle als CSV exportieren",
            data=df_filtered[table_columns].to_csv(index=False, sep=";").encode("utf-8-sig"),
            file_name="hartmut_terminal_gefilterte_gesamttabelle.csv",
            mime="text/csv"
        )


with tab_lists:
    # ============================================================
    # ⭐ PERSÖNLICHE WATCHLIST & KAUFLIST
    # ============================================================

    with st.expander("⭐ Persönliche Watchlist & Kaufliste", expanded=True):
        st.divider()

        st.subheader("⭐ Persönliche Aktienlisten")

        current_user = st.session_state.get("current_user", "").strip()

        stock_options_df = df.dropna(subset=["Ticker"]).copy()
        stock_options_df["Ticker"] = stock_options_df["Ticker"].astype(str).str.strip()
        stock_options_df["Company"] = stock_options_df["Company"].astype(str).str.strip()

        # Doppelte Ticker vermeiden, damit die Auswahl stabil bleibt
        stock_options_df = stock_options_df.drop_duplicates(subset=["Ticker"])

        stock_options_df["display"] = (
            stock_options_df["Ticker"] + " - " + stock_options_df["Company"]
        )

        stock_options_df = stock_options_df.sort_values(by="display")

        ticker_to_display = dict(
            zip(stock_options_df["Ticker"], stock_options_df["display"])
        )

        display_to_ticker = dict(
            zip(stock_options_df["display"], stock_options_df["Ticker"])
        )

        all_displays = stock_options_df["display"].tolist()

        saved_watchlist_tickers = get_saved_tickers(
            current_user,
            "watchlist"
        )

        saved_buy_tickers = get_saved_tickers(
            current_user,
            "buy"
        )

        saved_watchlist_displays = [
            ticker_to_display[ticker]
            for ticker in saved_watchlist_tickers
            if ticker in ticker_to_display
        ]

        saved_buy_displays = [
            ticker_to_display[ticker]
            for ticker in saved_buy_tickers
            if ticker in ticker_to_display
        ]

        col_watchlist, col_buylist = st.columns(2)

        with col_watchlist:

            st.markdown("### ⭐ Watchlist-Aktien")

            selected_watchlist_displays = st.multiselect(
                "Aktien auswählen, die auf deiner Watchlist bleiben sollen",
                options=all_displays,
                default=saved_watchlist_displays,
                key=f"watchlist_select_{current_user}"
            )

            selected_watchlist_tickers = [
                display_to_ticker[item]
                for item in selected_watchlist_displays
            ]

            if st.button(
                "Watchlist speichern",
                key=f"save_watchlist_{current_user}"
            ):
                update_user_list(
                    username=current_user,
                    list_type="watchlist",
                    selected_tickers=selected_watchlist_tickers,
                    stock_df=df
                )

                st.success("Watchlist gespeichert.")
                st.rerun()

            if selected_watchlist_tickers:

                user_watchlist_df = df[
                    df["Ticker"].astype(str).isin(selected_watchlist_tickers)
                ].copy()

                watchlist_columns = [
                    "Ticker",
                    "Company",
                    "Action Signal",
                    "Rating",
                    "Score",
                    "Risk Level",
                    "Price",
                    "CRV"
                ]

                watchlist_columns = [
                    column for column in watchlist_columns
                    if column in user_watchlist_df.columns
                ]

                st.dataframe(
                    user_watchlist_df[watchlist_columns],
                    width="stretch",
                    hide_index=True
                )

            else:

                st.info("Noch keine Watchlist-Aktien ausgewählt.")


        with col_buylist:

            st.markdown("### 🛒 Kauf-Aktien")

            selected_buy_displays = st.multiselect(
                "Aktien auswählen, die auf deiner Kaufliste bleiben sollen",
                options=all_displays,
                default=saved_buy_displays,
                key=f"buy_select_{current_user}"
            )

            selected_buy_tickers = [
                display_to_ticker[item]
                for item in selected_buy_displays
            ]

            if st.button(
                "Kaufliste speichern",
                key=f"save_buy_{current_user}"
            ):
                update_user_list(
                    username=current_user,
                    list_type="buy",
                    selected_tickers=selected_buy_tickers,
                    stock_df=df
                )

                st.success("Kaufliste gespeichert.")
                st.rerun()

            if selected_buy_tickers:

                user_buy_df = df[
                    df["Ticker"].astype(str).isin(selected_buy_tickers)
                ].copy()

                buy_columns = [
                    "Ticker",
                    "Company",
                    "Action Signal",
                    "Rating",
                    "Score",
                    "Risk Level",
                    "Price",
                    "CRV"
                ]

                buy_columns = [
                    column for column in buy_columns
                    if column in user_buy_df.columns
                ]

                st.dataframe(
                    user_buy_df[buy_columns],
                    width="stretch",
                    hide_index=True
                )

            else:

                st.info("Noch keine Kauf-Aktien ausgewählt.")


        # ============================================================
        # 📡 LISTEN-RADAR: EIGENE LISTEN MIT SIGNALEN
        # ============================================================

        st.markdown("### 📡 Listen-Radar")

        combined_user_tickers = sorted(
            set(selected_watchlist_tickers + selected_buy_tickers)
        )

        if not combined_user_tickers:
            st.caption("Noch keine Aktien in Watchlist oder Kaufliste gespeichert.")
        else:
            list_radar_df = df[
                df["Ticker"].astype(str).str.strip().isin(combined_user_tickers)
            ].copy()

            list_radar_df["Liste"] = list_radar_df["Ticker"].astype(str).apply(
                lambda ticker: "Watchlist & Kauf"
                if ticker in selected_watchlist_tickers and ticker in selected_buy_tickers
                else "Watchlist"
                if ticker in selected_watchlist_tickers
                else "Kauf"
            )

            list_radar_columns = [
                "Liste",
                "Ticker",
                "Company",
                "Terminal Grade",
                "Terminal Score",
                "Action Signal",
                "Valuation Status",
                "Score",
                "Fundamental Score",
                "Risk Level",
                "Price",
                "CRV",
                "Dividend Yield %"
            ]

            list_radar_columns = [
                column for column in list_radar_columns
                if column in list_radar_df.columns
            ]

            signal_counts = (
                list_radar_df["Action Signal"].astype(str).value_counts()
                if "Action Signal" in list_radar_df.columns
                else pd.Series(dtype=int)
            )

            lr1, lr2, lr3, lr4 = st.columns(4)
            lr1.metric("Listen-Aktien", len(list_radar_df))
            lr2.metric("BUY/STRONG", int(signal_counts[signal_counts.index.str.contains("BUY", case=False, na=False)].sum()) if not signal_counts.empty else 0)
            lr3.metric("WATCH", int(signal_counts[signal_counts.index.str.contains("WATCH", case=False, na=False)].sum()) if not signal_counts.empty else 0)
            lr4.metric("AVOID/RISK", int(signal_counts[signal_counts.index.str.contains("AVOID|SELL|OVERHEATED|TAKE", case=False, na=False)].sum()) if not signal_counts.empty else 0)

            st.dataframe(
                list_radar_df[list_radar_columns],
                width="stretch",
                hide_index=True
            )


with tab_admin:
    # ============================================================
    # 👑 SUPERUSER-ANSICHT / SYSTEMSTATUS
    # ============================================================

    superusers = st.secrets.get("app", {}).get("superusers", [])

    if current_user in superusers:

        with st.expander("🩺 Systemstatus & Datenqualität", expanded=True):
            rel_file_exists = os.path.exists("stock_relationships.csv")
            portfolio_file_exists = os.path.exists("portfolio_analysis.csv")
            missing_fundamental = 0
            if "Fundamental Rating" in df.columns:
                missing_fundamental = (df["Fundamental Rating"].astype(str).isin(["WEAK / UNKNOWN", "UNKNOWN", "-"])).sum()

            s1, s2, s3, s4 = st.columns(4)
            s1.metric("Aktien geladen", len(df))
            s2.metric("Beziehungen", len(relationships_df) if 'relationships_df' in globals() else 0)
            s3.metric("Unklare Fundamentals", int(missing_fundamental))
            s4.metric("Supabase", "aktiv" if "supabase" in st.secrets else "fehlt")

            status_df = pd.DataFrame([
                {"Prüfung": "portfolio_analysis.csv", "Status": "OK" if portfolio_file_exists else "Fehlt"},
                {"Prüfung": "stock_relationships.csv", "Status": "OK" if rel_file_exists else "Fehlt"},
                {"Prüfung": "Supabase Secrets", "Status": "OK" if "supabase" in st.secrets else "Fehlt"},
                {"Prüfung": "Nutzerlisten-Tabelle", "Status": "wird beim Laden geprüft"},
            ])
            st.dataframe(status_df, width="stretch", hide_index=True)

        with st.expander("👑 Superuser-Übersicht", expanded=True):


            all_user_lists = load_user_lists()

            if all_user_lists.empty:

                st.info("Noch keine gespeicherten Nutzerlisten vorhanden.")

            else:

                all_user_lists = all_user_lists.copy()

                # ============================================================
                # 📡 SUPERUSER-LISTEN-RADAR
                # ============================================================
                # Gleiche Idee wie im Tab "Listen", aber für alle Nutzer.
                # Die Original-Superuser-Übersicht bleibt darunter erhalten.
                admin_lists_raw = all_user_lists.copy()
                admin_lists_raw["Ticker"] = admin_lists_raw["ticker"].astype(str).str.strip()
                admin_lists_raw["User"] = admin_lists_raw["username"].astype(str).str.strip()
                admin_lists_raw["Liste"] = admin_lists_raw["list_type"].replace({
                    "watchlist": "Watchlist",
                    "buy": "Kauf"
                })

                admin_signal_columns = [
                    "Ticker",
                    "Company",
                    "Terminal Grade",
                    "Terminal Score",
                    "Action Signal",
                    "Valuation Status",
                    "Valuation Score",
                    "Score",
                    "Fundamental Score",
                    "Risk Level",
                    "Price",
                    "CRV",
                    "Dividend Yield %"
                ]

                admin_signal_columns = [
                    column for column in admin_signal_columns
                    if column in df.columns
                ]

                admin_signal_df = df[admin_signal_columns].copy()
                admin_signal_df["Ticker"] = admin_signal_df["Ticker"].astype(str).str.strip()

                admin_radar_df = admin_lists_raw.merge(
                    admin_signal_df,
                    on="Ticker",
                    how="left"
                )

                if "Company" not in admin_radar_df.columns:
                    admin_radar_df["Company"] = admin_radar_df.get("name", "")
                else:
                    admin_radar_df["Company"] = admin_radar_df["Company"].fillna(
                        admin_radar_df.get("name", "")
                    )

                admin_radar_columns = [
                    "Liste",
                    "User",
                    "Ticker",
                    "Company",
                    "Terminal Grade",
                    "Terminal Score",
                    "Action Signal",
                    "Valuation Status",
                    "Valuation Score",
                    "Score",
                    "Fundamental Score",
                    "Risk Level",
                    "Price",
                    "CRV",
                    "Dividend Yield %"
                ]

                admin_radar_columns = [
                    column for column in admin_radar_columns
                    if column in admin_radar_df.columns
                ]

                st.markdown("### 📡 Superuser-Listen-Radar")

                admin_signal_counts = (
                    admin_radar_df["Action Signal"].astype(str).value_counts()
                    if "Action Signal" in admin_radar_df.columns
                    else pd.Series(dtype=int)
                )

                ar1, ar2, ar3, ar4, ar5 = st.columns(5)
                ar1.metric("Einträge", len(admin_radar_df))
                ar2.metric("Nutzer", admin_radar_df["User"].nunique() if "User" in admin_radar_df.columns else 0)
                ar3.metric("Ticker", admin_radar_df["Ticker"].nunique() if "Ticker" in admin_radar_df.columns else 0)
                ar4.metric(
                    "BUY/STRONG",
                    int(admin_signal_counts[admin_signal_counts.index.str.contains("BUY", case=False, na=False)].sum())
                    if not admin_signal_counts.empty else 0
                )
                ar5.metric(
                    "Risiko/Exit",
                    int(admin_signal_counts[admin_signal_counts.index.str.contains("AVOID|SELL|OVERHEATED|TAKE", case=False, na=False)].sum())
                    if not admin_signal_counts.empty else 0
                )

                st.dataframe(
                    admin_radar_df[admin_radar_columns].sort_values(
                        by=[column for column in ["Liste", "User", "Terminal Score", "Ticker"] if column in admin_radar_columns],
                        ascending=[True, True, False, True][:len([column for column in ["Liste", "User", "Terminal Score", "Ticker"] if column in admin_radar_columns])]
                    ),
                    width="stretch",
                    hide_index=True
                )

                st.markdown("### 👑 Rohübersicht aller Nutzerlisten")

                all_user_lists["Liste"] = all_user_lists["list_type"].replace({
                    "watchlist": "Watchlist",
                    "buy": "Kauf"
                })

                all_user_lists = all_user_lists.rename(columns={
                    "username": "User",
                    "ticker": "Ticker",
                    "name": "Company",
                    "created_at": "Gespeichert am"
                })

                all_user_lists = all_user_lists[
                    [
                        "Liste",
                        "Ticker",
                        "Company",
                        "User",
                        "Gespeichert am"
                    ]
                ].sort_values(
                    by=[
                        "Liste",
                        "User",
                        "Ticker"
                    ]
                )

                st.dataframe(
                    all_user_lists,
                    width="stretch",
                    hide_index=True
                )


with tab_analysis:
    # ============================================================
    # AKTIENKARTEN
    # ============================================================

    with st.expander("🔥 Aktienübersicht / Karten", expanded=False):
        st.divider()

        st.subheader("🔥 Aktienübersicht")

        for _, row in df_filtered.iterrows():

            color = get_border_color(row["Rating"])
            rating_light = get_rating_light(row["Rating"])
            risk_light = get_risk_light(row["Risk Level"])

            card_html = f"""
        <div style="background-color:#ffffff; padding:16px 18px; border-radius:16px; margin-bottom:16px; border-left:8px solid {color}; box-shadow:0 4px 14px rgba(0,0,0,0.10); font-family:Arial, sans-serif; color:#111827; line-height:1.55; overflow-wrap:break-word; word-break:break-word;">
        <h2 style="margin:0 0 16px 0; font-size:21px; font-weight:800;">{row['Ticker']} - {row['Company']}</h2>
        <hr style="border:none; border-top:2px solid #9ca3af; margin:0 0 20px 0;">

        <p style="font-size:14px; margin:0 0 10px 0;">💰 <b>Preis:</b> {row['Price']}</p>

        <p style="font-size:14px; margin:0 0 10px 0;">⭐ <b>Rating:</b> {rating_light} {row['Rating']} | 📈 <b>Score:</b> {row['Score']} | ⚠️ <b>Risiko:</b> {risk_light} {row['Risk Level']}</p>

        <p style="font-size:14px; margin:0 0 10px 0;">🎯 <b>Signal:</b> {row['Action Signal']} | 🧭 <b>Setup:</b> {row['Setup Quality']} | 🕒 <b>Horizont:</b> {row['Strategy Mode']}</p>

        <p style="font-size:14px; margin:0 0 10px 0;">📍 <b>Einstiegszone:</b> {row['Entry Zone']} | 🛑 <b>Stop:</b> {row['Stop Loss New']} | 🎯 <b>Ziel 1:</b> {row['Target 1']} | 🚀 <b>Ziel 2:</b> {row['Target 2']} | ⚖️ <b>CRV:</b> {row['CRV']} | 🧱 <b>Zielbasis:</b> {row['Target Basis']}</p>

        <p style="font-size:14px; margin:0 0 10px 0;">📊 <b>Performance:</b><br>1D: {row['1D %']}% | 1W: {row['1W %']}% | 1M: {row['1M %']}% | 3M: {row['3M %']}% | 6M: {row['6M %']}%</p>

        <p style="font-size:14px; margin:0 0 10px 0;">📉 <b>EMA:</b><br>EMA20: {row['EMA20']} | EMA50: {row['EMA50']} | EMA100: {row['EMA100']}</p>

        <p style="font-size:14px; margin:0 0 10px 0;">💵 <b>Dividende:</b> {row['Dividend Yield %']} | 📅 <b>Ex-Dividende:</b> {row['Ex Dividend Date']} | 🪙 <b>Dividendensatz:</b> {row['Dividend Rate']}</p>

        <p style="font-size:14px; margin:0 0 10px 0;">🛑 <b>Stop-Loss-Idee:</b> {row['Stop Loss Idea']}</p>

        <p style="font-size:14px; margin:0 0 10px 0;">🏢 <b>Market Cap:</b> {row['Market Cap Class']}</p>

        <p style="font-size:14px; margin:0 0 10px 0;">🧾 <b>Fundamental:</b> {row['Fundamental Rating']} | 📊 <b>Fundamental Score:</b> {row['Fundamental Score']}/8</p>

        <p style="font-size:14px; margin:0 0 10px 0;">🧭 <b>Terminal-Grade:</b> {row['Terminal Grade']} | Terminal Score: {row['Terminal Score']}/100</p>

        <div style="font-size:13px; margin:6px 0 10px 0; background:#eef2ff; padding:9px 11px; border-radius:10px;">🧭 <b>Terminal-Fazit:</b> {row['Terminal Summary']}</div>

        <p style="font-size:14px; margin:0 0 10px 0;">💎 <b>Bewertungshinweis:</b> {row['Valuation Status']} | Punkte: {row['Valuation Score']}</p>

        <div style="font-size:13px; margin:6px 0 10px 0; background:#f8fafc; padding:9px 11px; border-radius:10px;">💬 <b>Bewertungsgrund:</b> {row['Valuation Summary']}<br><b>Details:</b> {row['Valuation Reasons']}</div>

        <p style="font-size:14px; margin:0 0 10px 0;">🏦 <b>Bewertung:</b><br>Forward KGV: {row['Forward PE']} | KGV: {row['Trailing PE']} | PEG: {row['PEG Ratio']}</p>

        <p style="font-size:14px; margin:0 0 10px 0;">📈 <b>Fundamentales Wachstum:</b><br>Umsatzwachstum: {row['Revenue Growth']} | Gewinnwachstum: {row['Earnings Growth']} | Marge: {row['Profit Margin']}</p>

        <p style="font-size:14px; margin:0 0 10px 0;">💸 <b>Cashflow / Verschuldung:</b><br>Free Cashflow: {row['Free Cashflow']} | Operating Cashflow: {row['Operating Cashflow']} | Debt/Equity: {row['Debt To Equity']}</p>

        <p style="font-size:14px; margin:0 0 10px 0;">🔄 <b>Turnaround:</b> {row['Turnaround Candidate']}</p>

        <div style="font-size:13px; margin:6px 0 10px 0; background:#ecfdf5; padding:9px 11px; border-radius:10px;">✅ <b>Pro:</b> {row['Pros']}</div>

        <div style="font-size:13px; margin:6px 0 10px 0; background:#fff7ed; padding:9px 11px; border-radius:10px;">⚠️ <b>Contra:</b> {row['Cons']}</div>

        <div style="font-size:13px; margin:6px 0 10px 0; background:#eef2ff; padding:9px 11px; border-radius:10px;">🧭 <b>Entscheidung:</b> {row['Decision Summary']}</div>

        <div style="font-size:13px; margin:8px 0 0 0; background:#f3f4f6; padding:9px 11px; border-radius:10px;">🧠 <b>Analyse:</b> {row['Reason']}</div>
        </div>
        """

            st.markdown(card_html, unsafe_allow_html=True)
